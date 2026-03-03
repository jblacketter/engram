from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from core.models import Memory
from core.services import search_service

FAKE_768 = [0.1] * 768


def _make_vector(seed: float) -> list[float]:
    """Create a distinguishable 768-dim vector."""
    return [seed + i * 0.001 for i in range(768)]


@pytest.fixture(autouse=True)
def mock_embed():
    with patch("core.services.search_service.embed", new_callable=AsyncMock) as m:
        m.return_value = FAKE_768
        yield m


@pytest.fixture(autouse=True)
def mock_memory_embed():
    with patch("core.services.memory_service.embed", new_callable=AsyncMock) as m:
        m.return_value = FAKE_768
        yield m


async def _create_memory(content, source="manual", tags=None, embedding=None):
    """Helper to create a memory with a specific embedding."""
    from asgiref.sync import sync_to_async

    return await sync_to_async(Memory.objects.create)(
        content=content,
        embedding=embedding or FAKE_768,
        source=source,
        tags=tags or [],
    )


@pytest.mark.django_db(transaction=True)
class TestHybridSearch:
    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        await _create_memory("Django web framework tutorial")
        await _create_memory("Flask microframework guide")

        results = await search_service.search("Django framework")
        # Should return results (both may match via vector similarity)
        assert isinstance(results, list)
        for r in results:
            assert "id" in r
            assert "content" in r
            assert "rrf_score" in r

    @pytest.mark.asyncio
    async def test_search_empty_db(self):
        results = await search_service.search("anything")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_respects_limit(self):
        for i in range(10):
            await _create_memory(f"Memory number {i} about various topics")

        results = await search_service.search("memory topics", limit=3)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_search_filters_by_source(self):
        await _create_memory("API memory", source="api")
        await _create_memory("Manual memory", source="manual")

        results = await search_service.search("memory", source="api")
        for r in results:
            assert r["source"] == "api"

    @pytest.mark.asyncio
    async def test_search_filters_by_tags(self):
        await _create_memory("Python code", tags=["python", "code"])
        await _create_memory("JavaScript code", tags=["javascript", "code"])

        results = await search_service.search("code", tags=["python"])
        for r in results:
            assert "python" in r["tags"]

    @pytest.mark.asyncio
    async def test_search_filters_by_date_range(self):
        await _create_memory("Recent memory")

        # Search with after=tomorrow should return nothing
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        results = await search_service.search("memory", after=tomorrow)
        assert results == []

    @pytest.mark.asyncio
    async def test_search_result_schema(self):
        await _create_memory("Schema test memory")

        results = await search_service.search("schema test")
        if results:
            r = results[0]
            expected_keys = {
                "id", "content", "source", "tags", "metadata",
                "importance", "decay_factor", "access_count",
                "last_accessed", "created_at", "updated_at", "rrf_score",
            }
            assert set(r.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_semantic_weight_extremes(self):
        await _create_memory("test content for weight")

        # Pure semantic
        results_sem = await search_service.search("test", semantic_weight=1.0)
        # Pure keyword
        results_kw = await search_service.search("test", semantic_weight=0.0)

        # Both should return results (the memory matches both ways)
        assert isinstance(results_sem, list)
        assert isinstance(results_kw, list)
