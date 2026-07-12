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
