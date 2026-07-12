import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.test import APIClient
from rest_framework.views import APIView

from core.models import Memory

# NOTE: DRF resolves DEFAULT_PERMISSION_CLASSES once at import time (base.py
# picks IsAuthenticated vs AllowAny from REST_API_KEY), so override_settings
# on REST_FRAMEWORK cannot change view permissions afterwards. These tests
# patch APIView.permission_classes directly instead, and use override_settings
# only for REST_API_KEY, which APIKeyAuthentication reads at request time.

TEST_API_KEY = "test-secret-key-123"


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


# ---------------------------------------------------------------------------
# Secured mode
# ---------------------------------------------------------------------------

class TestSecuredMode:
    @pytest.fixture(autouse=True)
    def _secured_mode(self):
        with (
            patch.object(APIView, "permission_classes", [IsAuthenticated]),
            override_settings(REST_API_KEY=TEST_API_KEY),
        ):
            yield

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

class TestDevMode:
    @pytest.fixture(autouse=True)
    def _dev_mode(self):
        with (
            patch.object(APIView, "permission_classes", [AllowAny]),
            override_settings(REST_API_KEY=""),
        ):
            yield

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

class TestSessionAuth:
    @pytest.fixture(autouse=True)
    def _secured_mode(self):
        with (
            patch.object(APIView, "permission_classes", [IsAuthenticated]),
            override_settings(REST_API_KEY=TEST_API_KEY),
        ):
            yield

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
