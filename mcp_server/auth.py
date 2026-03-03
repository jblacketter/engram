from django.conf import settings
from fastmcp.server.auth.providers.debug import DebugTokenVerifier


def build_auth() -> DebugTokenVerifier | None:
    """Build auth provider. Returns None (no auth) when MCP_API_KEY is empty."""
    api_key = settings.MCP_API_KEY
    if not api_key:
        return None  # Dev mode: no auth, no header required

    async def verify_api_key(token: str) -> bool:
        return token == api_key

    return DebugTokenVerifier(validate=verify_api_key)
