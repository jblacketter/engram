from unittest.mock import AsyncMock, patch

import pytest
from django.core.cache import cache
from rest_framework.permissions import AllowAny
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from rest_framework.test import APIClient

# NOTE: SimpleRateThrottle captures DEFAULT_THROTTLE_RATES at import time, so
# override_settings(REST_FRAMEWORK=...) cannot change rates afterwards. Patch
# the class attribute directly instead. Low rates trigger throttling quickly;
# cache.clear() keeps throttle history from leaking between tests.
LOW_RATES = {"read": "2/min", "write": "2/min"}


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture(autouse=True)
def _throttle_env():
    cache.clear()
    with (
        patch.object(SimpleRateThrottle, "THROTTLE_RATES", LOW_RATES),
        patch.object(APIView, "permission_classes", [AllowAny]),
    ):
        yield
    cache.clear()


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
