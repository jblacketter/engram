"""Tests for the identity MCP resources (Phase 11)."""

import os

import pytest
from django.test import override_settings

from core.services.identity_service import MAX_FILE_BYTES
from mcp_server import resources
from mcp_server.server import mcp


def _fn(resource):
    return getattr(resource, "fn", resource)


@pytest.fixture
def identity_dir(tmp_path):
    (tmp_path / "context").mkdir()
    (tmp_path / "projects").mkdir()
    (tmp_path / "identity.md").write_text("# Identity\nI am the user.")
    (tmp_path / "context" / "infra.md").write_text("# Infra\nservers etc.")
    (tmp_path / "projects" / "engram.md").write_text("# Project: engram")
    with override_settings(ENGRAM_IDENTITY_DIR=str(tmp_path)):
        yield tmp_path


@pytest.mark.asyncio
async def test_all_resources_registered():
    registered = set((await mcp.get_resources()).keys())
    templates = set((await mcp.get_resource_templates()).keys())
    assert {"engram://identity", "engram://context", "engram://projects"} <= registered
    assert {"engram://context/{topic}", "engram://projects/{domain}"} <= templates


class TestReads:
    def test_identity_present(self, identity_dir):
        assert "I am the user." in _fn(resources.identity)()

    def test_identity_missing(self, tmp_path):
        with override_settings(ENGRAM_IDENTITY_DIR=str(tmp_path / "nowhere")):
            out = _fn(resources.identity)()
        assert "Not found" in out and "init_identity" in out

    def test_context_index_and_topic(self, identity_dir):
        assert "engram://context/infra" in _fn(resources.context_index)()
        assert "servers etc." in _fn(resources.context_topic)("infra")

    def test_projects_index_and_domain(self, identity_dir):
        assert "engram://projects/engram" in _fn(resources.projects_index)()
        assert "# Project: engram" in _fn(resources.project_context)("engram")

    def test_missing_topic_not_found(self, identity_dir):
        assert "Not found" in _fn(resources.context_topic)("nonexistent")

    def test_oversized_file_bounded_error(self, identity_dir):
        (identity_dir / "context" / "huge.md").write_bytes(b"a" * (MAX_FILE_BYTES + 1))
        out = _fn(resources.context_topic)("huge")
        assert "Unreadable" in out and "exceeds" in out
        assert len(out) < 500  # error message, never partial content

    def test_invalid_utf8_bounded_error(self, identity_dir):
        (identity_dir / "context" / "binary.md").write_bytes(b"\xff\xfe\x00")
        out = _fn(resources.context_topic)("binary")
        assert "Unreadable" in out and "UTF-8" in out


class TestValidation:
    @pytest.mark.parametrize("bad", [
        "..", "../secret", "a/b", "/etc/passwd", "%2e%2e", "café",
        "a\\b", "UPPER", "dot.dot", "", "a b",
    ])
    def test_domain_slugs_rejected(self, identity_dir, bad):
        out = _fn(resources.project_context)(bad)
        assert "Invalid domain slug" in out

    def test_topic_allows_underscore_domain_does_not(self, identity_dir):
        (identity_dir / "context" / "my_topic.md").write_text("ok")
        assert "ok" in _fn(resources.context_topic)("my_topic")
        assert "Invalid domain slug" in _fn(resources.project_context)("my_domain")

    def test_symlink_escape_reported_not_served(self, identity_dir, tmp_path):
        secret = tmp_path.parent / f"{tmp_path.name}-outside-secret.md"
        secret.write_text("TOP SECRET")
        try:
            os.symlink(secret, identity_dir / "projects" / "sneaky.md")
            out = _fn(resources.project_context)("sneaky")
            assert "TOP SECRET" not in out
            assert "Not found" in out
        finally:
            secret.unlink()

    def test_sibling_prefix_directory_not_confused(self, tmp_path):
        real = tmp_path / "identity"
        evil = tmp_path / "identity-evil"
        (real / "projects").mkdir(parents=True)
        (evil / "projects").mkdir(parents=True)
        (evil / "projects" / "trap.md").write_text("EVIL")
        with override_settings(ENGRAM_IDENTITY_DIR=str(real)):
            out = _fn(resources.project_context)("trap")
        assert "EVIL" not in out and "Not found" in out
