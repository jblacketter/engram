import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.models import Memory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_memory(**overrides):
    """Create a mock Memory instance."""
    defaults = {
        "id": uuid.uuid4(),
        "content": "Test content",
        "source": "mcp",
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


# ---------------------------------------------------------------------------
# store_memory
# ---------------------------------------------------------------------------

class TestStoreMemory:
    @pytest.mark.asyncio
    async def test_store_calls_service_and_returns_id(self):
        mem = _make_memory()
        with patch("mcp_server.tools.memory.memory_service") as svc:
            svc.create_memory = AsyncMock(return_value=mem)
            from mcp_server.tools.memory import store_memory
            result = await store_memory.fn("Hello world")

            svc.create_memory.assert_called_once_with(
                content="Hello world",
                source="mcp",
                tags=None,
                importance=0.5,
            )
            data = json.loads(result)
            assert data["id"] == str(mem.id)
            assert data["status"] == "stored"

    @pytest.mark.asyncio
    async def test_store_default_source_is_mcp(self):
        mem = _make_memory()
        with patch("mcp_server.tools.memory.memory_service") as svc:
            svc.create_memory = AsyncMock(return_value=mem)
            from mcp_server.tools.memory import store_memory
            await store_memory.fn("Content")

            call_kwargs = svc.create_memory.call_args.kwargs
            assert call_kwargs["source"] == "mcp"

    @pytest.mark.asyncio
    async def test_store_handles_embedding_failure(self):
        with patch("mcp_server.tools.memory.memory_service") as svc:
            svc.create_memory = AsyncMock(side_effect=httpx.ConnectError("refused"))
            from mcp_server.tools.memory import store_memory
            result = await store_memory.fn("Content")

            assert "unavailable" in result.lower()


# ---------------------------------------------------------------------------
# get_memory
# ---------------------------------------------------------------------------

class TestGetMemory:
    @pytest.mark.asyncio
    async def test_get_returns_memory_json(self):
        mem = _make_memory()
        with patch("mcp_server.tools.memory.memory_service") as svc:
            svc.get_memory = AsyncMock(return_value=mem)
            from mcp_server.tools.memory import get_memory
            result = await get_memory.fn(str(mem.id))

            data = json.loads(result)
            assert data["id"] == str(mem.id)
            assert data["content"] == "Test content"

    @pytest.mark.asyncio
    async def test_get_not_found(self):
        with patch("mcp_server.tools.memory.memory_service") as svc:
            svc.get_memory = AsyncMock(side_effect=Memory.DoesNotExist)
            from mcp_server.tools.memory import get_memory
            result = await get_memory.fn(str(uuid.uuid4()))

            assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_get_invalid_uuid(self):
        from mcp_server.tools.memory import get_memory
        result = await get_memory.fn("not-a-uuid")
        assert "invalid" in result.lower()


# ---------------------------------------------------------------------------
# update_memory
# ---------------------------------------------------------------------------

class TestUpdateMemory:
    @pytest.mark.asyncio
    async def test_update_forwards_fields(self):
        mem = _make_memory()
        with patch("mcp_server.tools.memory.memory_service") as svc:
            svc.update_memory = AsyncMock(return_value=mem)
            from mcp_server.tools.memory import update_memory
            result = await update_memory.fn(str(mem.id), content="New content")

            svc.update_memory.assert_called_once_with(mem.id, content="New content")
            data = json.loads(result)
            assert data["status"] == "updated"

    @pytest.mark.asyncio
    async def test_update_no_fields_returns_message(self):
        from mcp_server.tools.memory import update_memory
        result = await update_memory.fn(str(uuid.uuid4()))
        assert "no fields" in result.lower()

    @pytest.mark.asyncio
    async def test_update_not_found(self):
        with patch("mcp_server.tools.memory.memory_service") as svc:
            svc.update_memory = AsyncMock(side_effect=Memory.DoesNotExist)
            from mcp_server.tools.memory import update_memory
            result = await update_memory.fn(str(uuid.uuid4()), content="X")

            assert "not found" in result.lower()


# ---------------------------------------------------------------------------
# delete_memory
# ---------------------------------------------------------------------------

class TestDeleteMemory:
    @pytest.mark.asyncio
    async def test_delete_success(self):
        mid = uuid.uuid4()
        with patch("mcp_server.tools.memory.memory_service") as svc:
            svc.delete_memory = AsyncMock()
            from mcp_server.tools.memory import delete_memory
            result = await delete_memory.fn(str(mid))

            assert "deleted" in result.lower()

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        with patch("mcp_server.tools.memory.memory_service") as svc:
            svc.delete_memory = AsyncMock(side_effect=Memory.DoesNotExist)
            from mcp_server.tools.memory import delete_memory
            result = await delete_memory.fn(str(uuid.uuid4()))

            assert "not found" in result.lower()


# ---------------------------------------------------------------------------
# search_brain
# ---------------------------------------------------------------------------

class TestSearchBrain:
    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        results = [
            {
                "id": uuid.uuid4(),
                "content": "Match",
                "source": "mcp",
                "tags": [],
                "metadata": {},
                "importance": 0.5,
                "decay_factor": 1.0,
                "access_count": 0,
                "last_accessed": None,
                "created_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
                "rrf_score": 0.016,
            }
        ]
        with patch("mcp_server.tools.search.search_service") as svc:
            svc.search = AsyncMock(return_value=results)
            from mcp_server.tools.search import search_brain
            result = await search_brain.fn("test query")

            svc.search.assert_called_once()
            data = json.loads(result)
            assert len(data) == 1
            assert "rrf_score" in data[0]

    @pytest.mark.asyncio
    async def test_search_empty_results(self):
        with patch("mcp_server.tools.search.search_service") as svc:
            svc.search = AsyncMock(return_value=[])
            from mcp_server.tools.search import search_brain
            result = await search_brain.fn("nothing")

            assert "no matching" in result.lower()

    @pytest.mark.asyncio
    async def test_search_forwards_params(self):
        with patch("mcp_server.tools.search.search_service") as svc:
            svc.search = AsyncMock(return_value=[])
            from mcp_server.tools.search import search_brain
            await search_brain.fn("q", limit=5, tags=["a"], source="api", semantic_weight=0.8)

            call_kwargs = svc.search.call_args.kwargs
            assert call_kwargs["limit"] == 5
            assert call_kwargs["tags"] == ["a"]
            assert call_kwargs["source"] == "api"
            assert call_kwargs["semantic_weight"] == 0.8


# ---------------------------------------------------------------------------
# find_related
# ---------------------------------------------------------------------------

class TestFindRelated:
    @pytest.mark.asyncio
    async def test_find_related_uses_semantic_weight_1(self):
        mem = _make_memory()
        with (
            patch("mcp_server.tools.search.memory_service") as mem_svc,
            patch("mcp_server.tools.search.search_service") as search_svc,
        ):
            mem_svc.get_memory = AsyncMock(return_value=mem)
            search_svc.search = AsyncMock(return_value=[])
            from mcp_server.tools.search import find_related
            await find_related.fn(str(mem.id))

            call_kwargs = search_svc.search.call_args.kwargs
            assert call_kwargs["semantic_weight"] == 1.0
            assert call_kwargs["query"] == mem.content

    @pytest.mark.asyncio
    async def test_find_related_excludes_self(self):
        mem = _make_memory()
        other_id = uuid.uuid4()
        results = [
            {"id": mem.id, "content": "self", "rrf_score": 0.02,
             "source": "mcp", "tags": [], "metadata": {},
             "importance": 0.5, "decay_factor": 1.0, "access_count": 0,
             "last_accessed": None,
             "created_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
             "updated_at": datetime(2026, 3, 3, tzinfo=timezone.utc)},
            {"id": other_id, "content": "related", "rrf_score": 0.01,
             "source": "mcp", "tags": [], "metadata": {},
             "importance": 0.5, "decay_factor": 1.0, "access_count": 0,
             "last_accessed": None,
             "created_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
             "updated_at": datetime(2026, 3, 3, tzinfo=timezone.utc)},
        ]
        with (
            patch("mcp_server.tools.search.memory_service") as mem_svc,
            patch("mcp_server.tools.search.search_service") as search_svc,
        ):
            mem_svc.get_memory = AsyncMock(return_value=mem)
            search_svc.search = AsyncMock(return_value=results)
            from mcp_server.tools.search import find_related
            result = await find_related.fn(str(mem.id))

            data = json.loads(result)
            ids = [r["id"] for r in data]
            assert str(mem.id) not in ids
            assert str(other_id) in ids

    @pytest.mark.asyncio
    async def test_find_related_no_filter_args_unchanged_behavior(self):
        """Regression: calling find_related without tags/source must pass None
        for both filters (preserving the pre-scoping default behavior)."""
        mem = _make_memory()
        with (
            patch("mcp_server.tools.search.memory_service") as mem_svc,
            patch("mcp_server.tools.search.search_service") as search_svc,
        ):
            mem_svc.get_memory = AsyncMock(return_value=mem)
            search_svc.search = AsyncMock(return_value=[])
            from mcp_server.tools.search import find_related
            await find_related.fn(str(mem.id))

            call_kwargs = search_svc.search.call_args.kwargs
            assert call_kwargs["tags"] is None
            assert call_kwargs["source"] is None

    @pytest.mark.asyncio
    async def test_find_related_forwards_tags_filter(self):
        mem = _make_memory()
        with (
            patch("mcp_server.tools.search.memory_service") as mem_svc,
            patch("mcp_server.tools.search.search_service") as search_svc,
        ):
            mem_svc.get_memory = AsyncMock(return_value=mem)
            search_svc.search = AsyncMock(return_value=[])
            from mcp_server.tools.search import find_related
            await find_related.fn(str(mem.id), tags=["domain:qa"])

            call_kwargs = search_svc.search.call_args.kwargs
            assert call_kwargs["tags"] == ["domain:qa"]
            assert call_kwargs["source"] is None
            assert call_kwargs["semantic_weight"] == 1.0

    @pytest.mark.asyncio
    async def test_find_related_forwards_source_filter(self):
        mem = _make_memory()
        with (
            patch("mcp_server.tools.search.memory_service") as mem_svc,
            patch("mcp_server.tools.search.search_service") as search_svc,
        ):
            mem_svc.get_memory = AsyncMock(return_value=mem)
            search_svc.search = AsyncMock(return_value=[])
            from mcp_server.tools.search import find_related
            await find_related.fn(str(mem.id), source="aegis")

            call_kwargs = search_svc.search.call_args.kwargs
            assert call_kwargs["source"] == "aegis"
            assert call_kwargs["tags"] is None

    @pytest.mark.asyncio
    async def test_find_related_excludes_self_under_filters(self):
        """Self-exclusion must hold even when tag/source filters are applied
        (the search service may return the source memory if it matches the filter)."""
        mem = _make_memory(tags=["domain:qa"])
        other_id = uuid.uuid4()
        results = [
            {"id": mem.id, "content": "self", "rrf_score": 0.02,
             "source": "aegis", "tags": ["domain:qa"], "metadata": {},
             "importance": 0.5, "decay_factor": 1.0, "access_count": 0,
             "last_accessed": None,
             "created_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
             "updated_at": datetime(2026, 3, 3, tzinfo=timezone.utc)},
            {"id": other_id, "content": "related", "rrf_score": 0.01,
             "source": "aegis", "tags": ["domain:qa"], "metadata": {},
             "importance": 0.5, "decay_factor": 1.0, "access_count": 0,
             "last_accessed": None,
             "created_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
             "updated_at": datetime(2026, 3, 3, tzinfo=timezone.utc)},
        ]
        with (
            patch("mcp_server.tools.search.memory_service") as mem_svc,
            patch("mcp_server.tools.search.search_service") as search_svc,
        ):
            mem_svc.get_memory = AsyncMock(return_value=mem)
            search_svc.search = AsyncMock(return_value=results)
            from mcp_server.tools.search import find_related
            result = await find_related.fn(
                str(mem.id), tags=["domain:qa"], source="aegis"
            )

            data = json.loads(result)
            ids = [r["id"] for r in data]
            assert str(mem.id) not in ids
            assert str(other_id) in ids


# ---------------------------------------------------------------------------
# list_recent_memories
# ---------------------------------------------------------------------------

class TestListRecentMemories:
    @pytest.mark.asyncio
    async def test_list_recent_forwards_params(self):
        mems = [_make_memory(), _make_memory()]
        with patch("mcp_server.tools.search.memory_service") as svc:
            svc.list_recent = AsyncMock(return_value=mems)
            from mcp_server.tools.search import list_recent_memories
            result = await list_recent_memories.fn(limit=5, source="api")

            svc.list_recent.assert_called_once_with(limit=5, source="api", tags=None)
            data = json.loads(result)
            assert len(data) == 2

    @pytest.mark.asyncio
    async def test_list_recent_empty(self):
        with patch("mcp_server.tools.search.memory_service") as svc:
            svc.list_recent = AsyncMock(return_value=[])
            from mcp_server.tools.search import list_recent_memories
            result = await list_recent_memories.fn()

            assert "no memories" in result.lower()

    @pytest.mark.asyncio
    async def test_list_recent_no_filter_args_unchanged_behavior(self):
        """Regression: bare call must forward source=None and tags=None,
        preserving the pre-scoping default."""
        with patch("mcp_server.tools.search.memory_service") as svc:
            svc.list_recent = AsyncMock(return_value=[])
            from mcp_server.tools.search import list_recent_memories
            await list_recent_memories.fn()

            call_kwargs = svc.list_recent.call_args.kwargs
            assert call_kwargs["source"] is None
            assert call_kwargs["tags"] is None

    @pytest.mark.asyncio
    async def test_list_recent_forwards_tags_filter(self):
        mems = [_make_memory(tags=["domain:qa"])]
        with patch("mcp_server.tools.search.memory_service") as svc:
            svc.list_recent = AsyncMock(return_value=mems)
            from mcp_server.tools.search import list_recent_memories
            await list_recent_memories.fn(tags=["domain:qa"])

            call_kwargs = svc.list_recent.call_args.kwargs
            assert call_kwargs["tags"] == ["domain:qa"]
            assert call_kwargs["source"] is None


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    @pytest.mark.asyncio
    async def test_get_stats_empty_db(self):
        with patch("mcp_server.tools.stats.Memory") as MockMemory:
            MockMemory.objects.count = MagicMock(return_value=0)

            with patch("mcp_server.tools.stats.sync_to_async") as mock_s2a:
                mock_s2a.side_effect = lambda fn: AsyncMock(return_value=fn())

                from mcp_server.tools.stats import get_stats
                result = await get_stats.fn()

                data = json.loads(result)
                assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_data(self):
        now = datetime(2026, 3, 3, tzinfo=timezone.utc)
        with (
            patch("mcp_server.tools.stats.Memory") as MockMemory,
            patch("mcp_server.tools.stats.sync_to_async") as mock_s2a,
        ):
            MockMemory.objects.count = MagicMock(return_value=42)
            MockMemory.objects.values.return_value.annotate.return_value = [
                {"source": "mcp", "count": 30},
                {"source": "api", "count": 12},
            ]
            MockMemory.objects.aggregate = MagicMock(
                return_value={"earliest": now, "latest": now}
            )
            MockMemory.objects.values_list.return_value = [
                ["python", "django"],
                ["python"],
            ]

            mock_s2a.side_effect = lambda fn: AsyncMock(return_value=fn())

            from mcp_server.tools.stats import get_stats
            result = await get_stats.fn()

            data = json.loads(result)
            assert data["total"] == 42
            assert "mcp" in data["by_source"]


# ---------------------------------------------------------------------------
# Decimal serialization regression tests
# ---------------------------------------------------------------------------

class TestDecimalSerialization:
    def test_serialize_results_handles_decimal_rrf_score(self):
        """Regression: rrf_score from PostgreSQL may be Decimal, not float."""
        from mcp_server.tools.search import _serialize_results

        results = [
            {
                "id": uuid.uuid4(),
                "content": "Test",
                "source": "mcp",
                "tags": [],
                "metadata": {},
                "importance": 0.5,
                "decay_factor": 1.0,
                "access_count": 0,
                "last_accessed": None,
                "created_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
                "rrf_score": Decimal("0.016393442622950819"),
            }
        ]
        # Should not raise TypeError
        serialized = _serialize_results(results)
        data = json.loads(serialized)
        assert isinstance(data[0]["rrf_score"], float)
        assert data[0]["rrf_score"] == pytest.approx(0.0164, abs=1e-3)

    @pytest.mark.asyncio
    async def test_search_brain_with_decimal_scores(self):
        """Regression: search_brain should produce valid JSON even with Decimal scores."""
        results = [
            {
                "id": uuid.uuid4(),
                "content": "Match",
                "source": "mcp",
                "tags": [],
                "metadata": {},
                "importance": Decimal("0.5"),
                "decay_factor": Decimal("1.0"),
                "access_count": 0,
                "last_accessed": None,
                "created_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
                "rrf_score": Decimal("0.01"),
            }
        ]
        with patch("mcp_server.tools.search.search_service") as svc:
            svc.search = AsyncMock(return_value=results)
            from mcp_server.tools.search import search_brain
            result = await search_brain.fn("test")

            # Should produce valid JSON without TypeError
            data = json.loads(result)
            assert isinstance(data[0]["rrf_score"], float)

    @pytest.mark.asyncio
    async def test_find_related_with_decimal_scores(self):
        """Regression: find_related should produce valid JSON even with Decimal scores."""
        mem = _make_memory()
        other_id = uuid.uuid4()
        results = [
            {
                "id": other_id,
                "content": "related",
                "source": "mcp",
                "tags": [],
                "metadata": {},
                "importance": 0.5,
                "decay_factor": 1.0,
                "access_count": 0,
                "last_accessed": None,
                "created_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 3, 3, tzinfo=timezone.utc),
                "rrf_score": Decimal("0.008"),
            }
        ]
        with (
            patch("mcp_server.tools.search.memory_service") as mem_svc,
            patch("mcp_server.tools.search.search_service") as search_svc,
        ):
            mem_svc.get_memory = AsyncMock(return_value=mem)
            search_svc.search = AsyncMock(return_value=results)
            from mcp_server.tools.search import find_related
            result = await find_related.fn(str(mem.id))

            data = json.loads(result)
            assert isinstance(data[0]["rrf_score"], float)
