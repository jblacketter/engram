import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APIClient

from core.models import Memory

# DRF settings for secured mode (REST_API_KEY is set)
SECURED_DRF_SETTINGS = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.authentication.APIKeyAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {"read": "100/min", "write": "30/min"},
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# DRF settings for dev mode (REST_API_KEY is empty)
DEV_DRF_SETTINGS = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.authentication.APIKeyAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {"read": "100/min", "write": "30/min"},
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}


def _make_memory(**overrides):
    defaults = {
        "id": uuid.uuid4(),
        "content": "Test content",
        "source": "api",
        "tags": [],
        "metadata": {},
        "importance": 0.5,
        "decay_factor": 1.0,
        "access_count": 0,
        "last_accessed": None,
        "created_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    mem = MagicMock(spec=Memory)
    for k, v in defaults.items():
        setattr(mem, k, v)
    return mem


TEST_API_KEY = "test-secret-key-123"


# ---------------------------------------------------------------------------
# Secured mode
# ---------------------------------------------------------------------------

@override_settings(REST_FRAMEWORK=SECURED_DRF_SETTINGS, REST_API_KEY=TEST_API_KEY)
class TestSecuredMode:
    def test_valid_api_key_returns_200(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {TEST_API_KEY}")
        mem = _make_memory()
        with patch("api.views.memory_service") as svc:
            svc.list_recent = AsyncMock(return_value=[mem])
            response = client.get("/api/memories/")

        assert response.status_code == 200

    def test_missing_bearer_returns_403(self):
        client = APIClient()
        with patch("api.views.memory_service") as svc:
            svc.list_recent = AsyncMock(return_value=[])
            response = client.get("/api/memories/")

        assert response.status_code == 403

    def test_invalid_token_returns_403(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer wrong-key")
        with patch("api.views.memory_service") as svc:
            svc.list_recent = AsyncMock(return_value=[])
            response = client.get("/api/memories/")

        assert response.status_code == 403

    def test_health_allows_unauthenticated(self):
        """Health endpoint overrides to AllowAny — no auth required."""
        client = APIClient()
        with patch("api.views.connection") as mock_conn:
            mock_conn.ensure_connection = MagicMock()
            response = client.get("/api/health/")

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Dev mode
# ---------------------------------------------------------------------------

@override_settings(REST_FRAMEWORK=DEV_DRF_SETTINGS, REST_API_KEY="")
class TestDevMode:
    def test_no_header_returns_200(self):
        client = APIClient()
        mem = _make_memory()
        with patch("api.views.memory_service") as svc:
            svc.list_recent = AsyncMock(return_value=[mem])
            response = client.get("/api/memories/")

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Session auth (secured mode)
# ---------------------------------------------------------------------------

@override_settings(REST_FRAMEWORK=SECURED_DRF_SETTINGS, REST_API_KEY=TEST_API_KEY)
class TestSessionAuth:
    @pytest.mark.django_db
    def test_session_auth_works_in_secured_mode(self):
        User.objects.create_user(username="testuser", password="testpass")
        client = APIClient()
        client.login(username="testuser", password="testpass")
        mem = _make_memory()
        with patch("api.views.memory_service") as svc:
            svc.list_recent = AsyncMock(return_value=[mem])
            response = client.get("/api/memories/")

        assert response.status_code == 200
