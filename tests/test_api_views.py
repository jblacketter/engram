import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rest_framework.test import APIClient

from core.models import Memory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_memory(**overrides):
    """Create a mock Memory instance with all serializer-required fields."""
    defaults = {
        "id": uuid.uuid4(),
        "content": "Test content",
        "source": "api",
        "tags": ["test"],
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


@pytest.fixture
def client():
    return APIClient()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealthView:
    def test_health_returns_ok(self, client):
        with patch("api.views.connection") as mock_conn:
            mock_conn.ensure_connection = MagicMock()
            response = client.get("/api/health/")
        assert response.status_code == 200
        assert response.data["status"] == "ok"
        assert response.data["database"] is True


# ---------------------------------------------------------------------------
# Memory List + Create
# ---------------------------------------------------------------------------

class TestMemoryListCreateView:
    def test_list_memories_returns_200(self, client):
        mems = [_make_memory(), _make_memory()]
        with patch("api.views.memory_service") as svc:
            svc.list_recent = AsyncMock(return_value=mems)
            response = client.get("/api/memories/")

        assert response.status_code == 200
        assert len(response.data) == 2

    def test_create_memory_returns_201(self, client):
        mem = _make_memory()
        with patch("api.views.memory_service") as svc:
            svc.create_memory = AsyncMock(return_value=mem)
            response = client.post(
                "/api/memories/",
                {"content": "Hello world"},
                format="json",
            )

        assert response.status_code == 201
        assert response.data["content"] == "Test content"
        svc.create_memory.assert_called_once()

    def test_create_memory_content_too_long(self, client):
        response = client.post(
            "/api/memories/",
            {"content": "x" * 50001},
            format="json",
        )
        assert response.status_code == 400

    def test_create_memory_importance_out_of_range(self, client):
        response = client.post(
            "/api/memories/",
            {"content": "test", "importance": 1.5},
            format="json",
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Memory Detail
# ---------------------------------------------------------------------------

class TestMemoryDetailView:
    def test_get_memory_returns_200(self, client):
        mem = _make_memory()
        with patch("api.views.memory_service") as svc:
            svc.get_memory = AsyncMock(return_value=mem)
            response = client.get(f"/api/memories/{mem.id}/")

        assert response.status_code == 200
        assert response.data["id"] == str(mem.id)

    def test_get_memory_calls_service_with_uuid(self, client):
        mem = _make_memory()
        with patch("api.views.memory_service") as svc:
            svc.get_memory = AsyncMock(return_value=mem)
            client.get(f"/api/memories/{mem.id}/")
            svc.get_memory.assert_called_once_with(mem.id)

    def test_get_nonexistent_memory_returns_404(self, client):
        with patch("api.views.memory_service") as svc:
            svc.get_memory = AsyncMock(side_effect=Memory.DoesNotExist)
            response = client.get(f"/api/memories/{uuid.uuid4()}/")

        assert response.status_code == 404

    def test_update_memory_returns_200(self, client):
        mem = _make_memory(content="Updated content")
        with patch("api.views.memory_service") as svc:
            svc.update_memory = AsyncMock(return_value=mem)
            response = client.patch(
                f"/api/memories/{mem.id}/",
                {"content": "Updated content"},
                format="json",
            )

        assert response.status_code == 200
        svc.update_memory.assert_called_once()

    def test_update_nonexistent_memory_returns_404(self, client):
        with patch("api.views.memory_service") as svc:
            svc.update_memory = AsyncMock(side_effect=Memory.DoesNotExist)
            response = client.patch(
                f"/api/memories/{uuid.uuid4()}/",
                {"content": "x"},
                format="json",
            )

        assert response.status_code == 404

    def test_delete_memory_returns_204(self, client):
        mid = uuid.uuid4()
        with patch("api.views.memory_service") as svc:
            svc.delete_memory = AsyncMock()
            response = client.delete(f"/api/memories/{mid}/")

        assert response.status_code == 204

    def test_delete_nonexistent_memory_returns_404(self, client):
        with patch("api.views.memory_service") as svc:
            svc.delete_memory = AsyncMock(side_effect=Memory.DoesNotExist)
            response = client.delete(f"/api/memories/{uuid.uuid4()}/")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class TestSearchView:
    def test_search_returns_results(self, client):
        results = [
            {
                "id": uuid.uuid4(),
                "content": "Match",
                "source": "api",
                "tags": [],
                "metadata": {},
                "importance": 0.5,
                "rrf_score": 0.016,
                "created_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
            }
        ]
        with patch("api.views.search_service") as svc:
            svc.search = AsyncMock(return_value=results)
            response = client.post(
                "/api/search/",
                {"query": "test"},
                format="json",
            )

        assert response.status_code == 200
        assert len(response.data) == 1
        assert "rrf_score" in response.data[0]

    def test_search_validation_requires_query(self, client):
        response = client.post("/api/search/", {}, format="json")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStatsView:
    def test_stats_returns_counts(self, client):
        now = datetime(2026, 3, 3, tzinfo=timezone.utc)
        with patch("api.views.Memory") as MockMemory:
            MockMemory.objects.count.return_value = 42
            MockMemory.objects.values.return_value.annotate.return_value = [
                {"source": "api", "count": 30},
                {"source": "mcp", "count": 12},
            ]
            MockMemory.objects.aggregate.return_value = {
                "earliest": now,
                "latest": now,
            }
            MockMemory.objects.values_list.return_value = [
                ["python", "django"],
                ["python"],
            ]
            response = client.get("/api/stats/")

        assert response.status_code == 200
        assert response.data["total"] == 42
        assert "api" in response.data["by_source"]

    def test_stats_empty_db(self, client):
        with patch("api.views.Memory") as MockMemory:
            MockMemory.objects.count.return_value = 0
            response = client.get("/api/stats/")

        assert response.status_code == 200
        assert response.data["total"] == 0


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

class TestTagsView:
    def test_tags_returns_tag_counts(self, client):
        with patch("api.views.Memory") as MockMemory:
            MockMemory.objects.values_list.return_value = [
                ["python", "django"],
                ["python", "api"],
            ]
            response = client.get("/api/tags/")

        assert response.status_code == 200
        tags = {item["tag"]: item["count"] for item in response.data}
        assert tags["python"] == 2
        assert tags["django"] == 1
        assert tags["api"] == 1
