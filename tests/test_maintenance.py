"""Tests for the maintenance command and provider selection (Phase 13)."""

from io import StringIO
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from django.core.management import call_command
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from core.services import memory_service

FAKE_768 = [0.1] * 768


@pytest.fixture(autouse=True)
def mock_embed():
    with patch("core.services.memory_service.embed", new_callable=AsyncMock) as m:
        m.return_value = FAKE_768
        yield m


@pytest.mark.django_db(transaction=True)
class TestMaintenanceCommand:
    def test_decay_only(self):
        out = StringIO()
        with patch(
            "intelligence.management.commands.maintenance.run_decay",
            new_callable=AsyncMock,
        ) as decay:
            decay.return_value = [{"id": "x", "old": 1.0, "new": 0.9}]
            call_command("maintenance", stdout=out)
        assert "decay: 1 memories updated" in out.getvalue()

    def test_digest_stored_as_memory_local_only(self, mock_embed):
        out = StringIO()
        with patch(
            "intelligence.management.commands.maintenance.run_decay",
            new_callable=AsyncMock, return_value=[],
        ), patch(
            "intelligence.management.commands.maintenance.generate_report",
            new_callable=AsyncMock, return_value="# Weekly digest\ncontent",
        ) as report:
            call_command("maintenance", "--digest", "--days", "14", stdout=out)

        report.assert_called_once_with(days=14)
        # embedded locally only
        assert mock_embed.call_args.kwargs["allow_cloud_fallback"] is False

        from asgiref.sync import async_to_sync
        rows = async_to_sync(memory_service.list_recent)(tags=["type:digest"])
        assert len(rows) == 1
        assert rows[0].source == "maintenance"
        assert "Weekly digest" in rows[0].content
        assert not any(t.startswith("domain:") for t in rows[0].tags)

    def test_decay_failure_exits_nonzero(self):
        with patch(
            "intelligence.management.commands.maintenance.run_decay",
            new_callable=AsyncMock, side_effect=RuntimeError("db down"),
        ):
            with pytest.raises(SystemExit):
                call_command("maintenance")

    def test_digest_failure_exits_nonzero(self):
        with patch(
            "intelligence.management.commands.maintenance.run_decay",
            new_callable=AsyncMock, return_value=[],
        ), patch(
            "intelligence.management.commands.maintenance.generate_report",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("ollama down"),
        ):
            with pytest.raises(SystemExit):
                call_command("maintenance", "--digest")


class TestProviderSelection:
    def test_default_is_ollama(self):
        from embeddings import registry
        from embeddings.ollama_provider import OllamaProvider
        with override_settings(EMBEDDING_PROVIDER="ollama"):
            assert isinstance(registry.get_provider(), OllamaProvider)

    def test_openrouter_selectable(self):
        from embeddings import registry
        from embeddings.openrouter_provider import OpenRouterProvider
        with override_settings(EMBEDDING_PROVIDER="openrouter"):
            assert isinstance(registry.get_provider(), OpenRouterProvider)

    def test_unknown_provider_raises(self):
        from embeddings import registry
        with override_settings(EMBEDDING_PROVIDER="magic"):
            with pytest.raises(ImproperlyConfigured, match="magic"):
                registry.get_provider()


@pytest.mark.django_db(transaction=True)
class TestIdentitySyncCloudPrimaryRefusal:
    @pytest.mark.asyncio
    async def test_cloud_primary_refused_without_opt_in(self, tmp_path):
        from core.services import identity_service
        (tmp_path / "identity.md").write_text("private")
        with override_settings(
            EMBEDDING_PROVIDER="openrouter", ENGRAM_IDENTITY_CLOUD_EMBED=False
        ):
            report = await identity_service.sync(tmp_path)
        assert any("refused" in e for e in report["errors"])
        assert not report["created"]

    @pytest.mark.asyncio
    async def test_cloud_primary_allowed_with_opt_in(self, tmp_path):
        from core.services import identity_service
        (tmp_path / "identity.md").write_text("private")
        with override_settings(
            EMBEDDING_PROVIDER="openrouter", ENGRAM_IDENTITY_CLOUD_EMBED=True
        ):
            report = await identity_service.sync(tmp_path)
        assert len(report["created"]) == 1


class TestSchedulerCommandPropagatesFailure:
    """Regression: the compose scheduler loop must NOT suppress a failing
    `maintenance` invocation — the container has to exit non-zero so
    compose observes the failure instead of a log line."""

    def _scheduler_command(self):
        import yaml
        from pathlib import Path
        compose = yaml.safe_load(
            (Path(__file__).parent.parent / "docker-compose.prod.yml").read_text()
        )
        service = compose["services"]["scheduler"]
        assert service["entrypoint"] == ["sh", "-c"]
        # compose $$ escaping -> literal $ for the container shell
        return service["command"][0].replace("$$", "$")

    def test_failing_maintenance_exits_loop_nonzero(self, tmp_path):
        import stat
        import subprocess
        script = self._scheduler_command()
        assert "|| echo" not in script  # the old masking pattern is gone

        # Stub `python` that fails with a distinctive code
        stub = tmp_path / "python"
        stub.write_text("#!/bin/sh\nexit 7\n")
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        env = {"PATH": f"{tmp_path}:/usr/bin:/bin"}

        proc = subprocess.run(
            ["sh", "-c", script], env=env,
            capture_output=True, text=True, timeout=10,
        )
        assert proc.returncode == 7  # failure propagated, loop did not continue
        assert "maintenance failed with exit 7" in proc.stderr

    def test_success_reaches_sleep_then_later_failure_still_propagates(self, tmp_path):
        """A succeeding run continues to the daily sleep (no spurious exit),
        and a failure on a LATER iteration still exits the loop non-zero."""
        import stat
        import subprocess
        script = self._scheduler_command()

        state = tmp_path / "ran-once"
        stub = tmp_path / "python"
        stub.write_text(
            "#!/bin/sh\n"
            f"if [ -f '{state}' ]; then exit 7; fi\n"
            f"touch '{state}'\n"
            "exit 0\n"
        )
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
        sleep_stub = tmp_path / "sleep"
        sleep_stub.write_text("#!/bin/sh\necho SLEPT-$1\nexit 0\n")
        sleep_stub.chmod(sleep_stub.stat().st_mode | stat.S_IEXEC)
        env = {"PATH": f"{tmp_path}:/usr/bin:/bin"}

        proc = subprocess.run(
            ["sh", "-c", script], env=env,
            capture_output=True, text=True, timeout=10,
        )
        assert "SLEPT-86400" in proc.stdout   # success path reached the sleep
        assert proc.returncode == 7           # later failure still propagated
