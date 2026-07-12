from asgiref.sync import sync_to_async
from django.conf import settings
from fastmcp.server.auth.auth import TokenVerifier
from mcp.server.auth.provider import AccessToken

from core.models import AgentKey
from core.services import scoping


class EngramTokenVerifier(TokenVerifier):
    """Accepts the global MCP_API_KEY (owner principal) or an active
    per-agent key (agent principal, claims carry the agent id).

    Enabled when a global key is configured OR any agent key exists at
    server start (keys created later need a server restart to take effect
    — documented in the README).
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or not token.strip():
            return None
        global_key = settings.MCP_API_KEY
        if global_key and token == global_key:
            return AccessToken(
                token=token, client_id="owner", scopes=[],
                claims={"principal": "owner"},
            )
        agent = await sync_to_async(scoping.resolve_agent_key)(token)
        if agent is not None:
            from django.utils import timezone
            await sync_to_async(
                AgentKey.objects.filter(pk=agent.pk).update
            )(last_used_at=timezone.now())
            return AccessToken(
                token=token, client_id=f"agent:{agent.name}", scopes=[],
                claims={"principal": "agent", "agent_id": str(agent.pk)},
            )
        return None


def build_auth() -> EngramTokenVerifier | None:
    """Build the auth provider.

    None (no auth, open server — unchanged dev behavior) only when there is
    no global MCP_API_KEY AND no agent keys exist.
    """
    if settings.MCP_API_KEY:
        return EngramTokenVerifier()
    try:
        if AgentKey.objects.filter(is_active=True).exists():
            return EngramTokenVerifier()
    except Exception:
        # Database unavailable at import (e.g. collectstatic) — fall back
        # to the global-key rule only.
        pass
    return None


async def current_agent() -> AgentKey | None:
    """The AgentKey for the current MCP request, or None for owner /
    anonymous (auth disabled). Raises scoping.ScopeError if the token's
    key has been revoked since issuance."""
    from fastmcp.server.dependencies import get_access_token

    try:
        access = get_access_token()
    except Exception:
        return None
    if access is None:
        return None
    claims = access.claims or {}
    if claims.get("principal") != "agent":
        return None
    try:
        return await sync_to_async(AgentKey.objects.get)(
            pk=claims["agent_id"], is_active=True
        )
    except AgentKey.DoesNotExist:
        raise scoping.ScopeError("this agent key has been revoked")
