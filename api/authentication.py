from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from core.models import AgentKey
from core.services import scoping


class APIKeyUser:
    """Represents a successfully authenticated API key holder."""

    is_authenticated = True
    is_active = True
    is_anonymous = False
    username = "api-key-user"


class AgentUser(APIKeyUser):
    """An authenticated per-agent key holder."""

    def __init__(self, agent: AgentKey):
        self.agent = agent
        self.username = f"agent:{agent.name}"


class APIKeyAuthentication(BaseAuthentication):
    """Bearer auth for the owner key and per-agent keys.

    - Global REST_API_KEY -> owner principal (request.auth is None).
    - egk_-prefixed agent key -> agent principal (request.auth is the
      AgentKey record; views enforce domain scoping from it). Agent keys
      authenticate even in dev mode (empty REST_API_KEY) — presenting a
      key opts into enforcement; callers sending no key see unchanged
      behavior.
    """

    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith(f"{self.keyword} "):
            return None  # Fall through to next auth class
        token = auth_header[len(self.keyword) + 1 :]

        expected = settings.REST_API_KEY
        if expected and token == expected:
            return (APIKeyUser(), None)  # Owner principal

        if token.startswith(scoping.KEY_PREFIX):
            agent = scoping.resolve_agent_key(token)
            if agent is None:
                raise AuthenticationFailed("Invalid or revoked agent key.")
            AgentKey.objects.filter(pk=agent.pk).update(last_used_at=timezone.now())
            return (AgentUser(agent), agent)

        if not expected:
            return None  # Dev mode: skip API key auth entirely
        raise AuthenticationFailed("Invalid API key.")


def request_agent(request) -> AgentKey | None:
    """The AgentKey principal for a DRF request, or None (owner/anonymous)."""
    auth = getattr(request, "auth", None)
    return auth if isinstance(auth, AgentKey) else None
