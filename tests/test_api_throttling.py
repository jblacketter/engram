from unittest.mock import AsyncMock, patch

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

# Low rates to trigger throttling quickly in tests
THROTTLE_DRF_SETTINGS = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {"read": "2/min", "write": "2/min"},
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}


@pytest.fixture
def client():
    return APIClient()


@override_settings(REST_FRAMEWORK=THROTTLE_DRF_SETTINGS)
class TestReadThrottle:
    def test_read_throttle_returns_429_when_exceeded(self, client):
        with patch("api.views.Memory") as MockMemory:
            MockMemory.objects.values_list.return_value = []
            # First 2 requests should succeed (rate is 2/min)
            for _ in range(2):
                response = client.get("/api/tags/")
                assert response.status_code == 200

            # 3rd request should be throttled
            response = client.get("/api/tags/")
            assert response.status_code == 429


@override_settings(REST_FRAMEWORK=THROTTLE_DRF_SETTINGS)
class TestWriteThrottle:
    def test_write_throttle_returns_429_when_exceeded(self, client):
        with patch("api.views.search_service") as svc:
            svc.search = AsyncMock(return_value=[])
            # First 2 requests should succeed
            for _ in range(2):
                response = client.post(
                    "/api/search/",
                    {"query": "test"},
                    format="json",
                )
                assert response.status_code == 200

            # 3rd request should be throttled
            response = client.post(
                "/api/search/",
                {"query": "test"},
                format="json",
            )
            assert response.status_code == 429
