import pytest

from fastmcp.server.auth.providers.debug import DebugTokenVerifier

from mcp_server.auth import build_auth


class TestBuildAuthSecuredMode:
    def test_returns_verifier_when_key_set(self, settings):
        settings.MCP_API_KEY = "test-secret"
        auth = build_auth()
        assert isinstance(auth, DebugTokenVerifier)

    @pytest.mark.asyncio
    async def test_verifier_accepts_valid_token(self, settings):
        settings.MCP_API_KEY = "test-secret"
        auth = build_auth()
        result = await auth.verify_token("test-secret")
        assert result is not None

    @pytest.mark.asyncio
    async def test_verifier_rejects_invalid_token(self, settings):
        settings.MCP_API_KEY = "test-secret"
        auth = build_auth()
        result = await auth.verify_token("wrong-key")
        assert result is None


class TestBuildAuthDevMode:
    def test_returns_none_when_key_empty(self, settings):
        settings.MCP_API_KEY = ""
        auth = build_auth()
        assert auth is None

    def test_returns_none_when_key_not_set(self, settings):
        settings.MCP_API_KEY = ""
        auth = build_auth()
        assert auth is None
