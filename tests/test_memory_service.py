from unittest.mock import AsyncMock, patch

import pytest

from core.models import Memory
from core.services import memory_service

FAKE_768 = [0.1] * 768


@pytest.fixture(autouse=True)
def mock_embed():
    with patch("core.services.memory_service.embed", new_callable=AsyncMock) as m:
        m.return_value = FAKE_768
        yield m


@pytest.mark.django_db(transaction=True)
class TestCreateMemory:
    @pytest.mark.asyncio
    async def test_create_stores_content_and_embedding(self):
        mem = await memory_service.create_memory("Test content", source="api")
        assert mem.content == "Test content"
        assert mem.source == "api"
        assert list(mem.embedding) == FAKE_768
        assert mem.tags == []
        assert mem.metadata == {}
        assert mem.importance == 0.5

    @pytest.mark.asyncio
    async def test_create_with_tags_and_metadata(self):
        mem = await memory_service.create_memory(
            "Tagged content",
            tags=["python", "django"],
            metadata={"origin": "test"},
            importance=0.9,
        )
        assert mem.tags == ["python", "django"]
        assert mem.metadata == {"origin": "test"}
        assert mem.importance == 0.9


@pytest.mark.django_db(transaction=True)
class TestGetMemory:
    @pytest.mark.asyncio
    async def test_get_increments_access_count(self):
        mem = await memory_service.create_memory("Access test")
        assert mem.access_count == 0

        fetched = await memory_service.get_memory(mem.id)
        assert fetched.access_count == 1
        assert fetched.last_accessed is not None

        fetched2 = await memory_service.get_memory(mem.id)
        assert fetched2.access_count == 2

    @pytest.mark.asyncio
    async def test_get_nonexistent_raises(self):
        import uuid

        with pytest.raises(Memory.DoesNotExist):
            await memory_service.get_memory(uuid.uuid4())


@pytest.mark.django_db(transaction=True)
class TestUpdateMemory:
    @pytest.mark.asyncio
    async def test_update_content_re_embeds(self, mock_embed):
        mem = await memory_service.create_memory("Original")
        mock_embed.reset_mock()

        updated = await memory_service.update_memory(mem.id, content="Updated")
        assert updated.content == "Updated"
        mock_embed.assert_called_once_with("Updated")

    @pytest.mark.asyncio
    async def test_update_non_content_field_skips_embed(self, mock_embed):
        mem = await memory_service.create_memory("Content")
        mock_embed.reset_mock()

        updated = await memory_service.update_memory(mem.id, importance=0.8)
        assert updated.importance == 0.8
        mock_embed.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_tags(self):
        mem = await memory_service.create_memory("Taggable")
        updated = await memory_service.update_memory(mem.id, tags=["new-tag"])
        assert updated.tags == ["new-tag"]


@pytest.mark.django_db(transaction=True)
class TestDeleteMemory:
    @pytest.mark.asyncio
    async def test_delete_removes_row(self):
        mem = await memory_service.create_memory("To delete")
        await memory_service.delete_memory(mem.id)

        with pytest.raises(Memory.DoesNotExist):
            await memory_service.get_memory(mem.id)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raises(self):
        import uuid

        with pytest.raises(Memory.DoesNotExist):
            await memory_service.delete_memory(uuid.uuid4())


@pytest.mark.django_db(transaction=True)
class TestListRecent:
    @pytest.mark.asyncio
    async def test_list_recent_returns_ordered(self):
        await memory_service.create_memory("First", source="api")
        await memory_service.create_memory("Second", source="api")
        await memory_service.create_memory("Third", source="manual")

        results = await memory_service.list_recent(limit=10)
        assert len(results) == 3
        # Most recent first
        assert results[0].content == "Third"

    @pytest.mark.asyncio
    async def test_list_recent_filters_by_source(self):
        await memory_service.create_memory("API one", source="api")
        await memory_service.create_memory("Manual one", source="manual")

        results = await memory_service.list_recent(source="api")
        assert len(results) == 1
        assert results[0].source == "api"

    @pytest.mark.asyncio
    async def test_list_recent_respects_limit(self):
        for i in range(5):
            await memory_service.create_memory(f"Memory {i}")

        results = await memory_service.list_recent(limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_list_recent_filters_by_tags(self):
        await memory_service.create_memory("QA one", tags=["domain:qa"])
        await memory_service.create_memory("Personal one", tags=["domain:personal"])
        await memory_service.create_memory("Untagged")

        results = await memory_service.list_recent(tags=["domain:qa"])
        assert len(results) == 1
        assert results[0].content == "QA one"

    @pytest.mark.asyncio
    async def test_list_recent_no_tag_filter_returns_all(self):
        """Regression: list_recent() with no tags arg must return all memories,
        unchanged from pre-scoping behavior."""
        await memory_service.create_memory("QA one", tags=["domain:qa"])
        await memory_service.create_memory("Personal one", tags=["domain:personal"])

        results = await memory_service.list_recent()
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_list_recent_combines_source_and_tags(self):
        await memory_service.create_memory(
            "QA from aegis", source="aegis", tags=["domain:qa"]
        )
        await memory_service.create_memory(
            "QA from manual", source="manual", tags=["domain:qa"]
        )

        results = await memory_service.list_recent(
            source="aegis", tags=["domain:qa"]
        )
        assert len(results) == 1
        assert results[0].source == "aegis"


class TestListRecentFilterChain:
    """Non-DB unit tests proving the QuerySet filter chain orchestration.
    These complement the @pytest.mark.django_db tests in TestListRecent
    (which require a live Postgres connection) so the filter wiring is
    verifiable in any environment.
    """

    def _mock_qs(self):
        from unittest.mock import MagicMock
        qs = MagicMock(name="qs")
        qs.order_by.return_value = qs
        qs.filter.return_value = qs
        qs.__getitem__.return_value = []
        return qs

    @pytest.mark.asyncio
    async def test_list_recent_no_args_applies_no_filter(self):
        from unittest.mock import AsyncMock, patch
        qs = self._mock_qs()
        with (
            patch("core.services.memory_service.Memory") as MockMem,
            patch("core.services.memory_service.sync_to_async",
                  return_value=AsyncMock(return_value=[])),
        ):
            MockMem.objects = qs
            await memory_service.list_recent()

            qs.order_by.assert_called_once_with("-created_at")
            qs.filter.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_recent_tags_applies_tags_contains(self):
        from unittest.mock import AsyncMock, patch
        qs = self._mock_qs()
        with (
            patch("core.services.memory_service.Memory") as MockMem,
            patch("core.services.memory_service.sync_to_async",
                  return_value=AsyncMock(return_value=[])),
        ):
            MockMem.objects = qs
            await memory_service.list_recent(tags=["domain:qa"])

            calls = qs.filter.call_args_list
            assert any(
                c.kwargs == {"tags__contains": ["domain:qa"]} for c in calls
            ), f"Expected tags__contains filter; got {calls}"
            assert not any("source" in c.kwargs for c in calls)

    @pytest.mark.asyncio
    async def test_list_recent_source_only_does_not_apply_tags_filter(self):
        from unittest.mock import AsyncMock, patch
        qs = self._mock_qs()
        with (
            patch("core.services.memory_service.Memory") as MockMem,
            patch("core.services.memory_service.sync_to_async",
                  return_value=AsyncMock(return_value=[])),
        ):
            MockMem.objects = qs
            await memory_service.list_recent(source="aegis")

            calls = qs.filter.call_args_list
            assert any(c.kwargs == {"source": "aegis"} for c in calls)
            assert not any("tags__contains" in c.kwargs for c in calls)

    @pytest.mark.asyncio
    async def test_list_recent_source_and_tags_applies_both_filters(self):
        from unittest.mock import AsyncMock, patch
        qs = self._mock_qs()
        with (
            patch("core.services.memory_service.Memory") as MockMem,
            patch("core.services.memory_service.sync_to_async",
                  return_value=AsyncMock(return_value=[])),
        ):
            MockMem.objects = qs
            await memory_service.list_recent(
                source="aegis", tags=["domain:qa"]
            )

            calls = qs.filter.call_args_list
            assert qs.filter.call_count == 2
            assert any(c.kwargs == {"source": "aegis"} for c in calls)
            assert any(
                c.kwargs == {"tags__contains": ["domain:qa"]} for c in calls
            )

    @pytest.mark.asyncio
    async def test_list_recent_empty_tags_list_skipped(self):
        """Defensive: tags=[] is falsy, so no tags filter should be added."""
        from unittest.mock import AsyncMock, patch
        qs = self._mock_qs()
        with (
            patch("core.services.memory_service.Memory") as MockMem,
            patch("core.services.memory_service.sync_to_async",
                  return_value=AsyncMock(return_value=[])),
        ):
            MockMem.objects = qs
            await memory_service.list_recent(tags=[])

            qs.filter.assert_not_called()
