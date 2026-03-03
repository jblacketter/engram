from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class APIKeyUser:
    """Represents a successfully authenticated API key holder."""

    is_authenticated = True
    is_active = True
    is_anonymous = False
    username = "api-key-user"


class APIKeyAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith(f"{self.keyword} "):
            return None  # Fall through to next auth class
        token = auth_header[len(self.keyword) + 1 :]
        expected = settings.REST_API_KEY
        if not expected:
            return None  # Dev mode: skip API key auth entirely
        if token != expected:
            raise AuthenticationFailed("Invalid API key.")
        return (APIKeyUser(), None)  # Authenticated principal
