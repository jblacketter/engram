from unittest.mock import AsyncMock, patch

import pytest

from intelligence.entity_extractor import (
    _extract_entities_regex,
    _merge_entities,
    _validate_entities,
    enrich_entities,
    extract_entities,
)

FAKE_768 = [0.1] * 768


class TestValidateEntities:
    def test_validates_correct_structure(self):
        raw = {
            "people": ["Alice", "Bob"],
            "projects": ["Engram"],
            "organizations": ["Anthropic"],
            "technologies": ["Python"],
        }
        result = _validate_entities(raw)
        assert result["people"] == ["Alice", "Bob"]
        assert result["technologies"] == ["Python"]

    def test_handles_missing_categories(self):
        raw = {"people": ["Alice"]}
        result = _validate_entities(raw)
        assert result["people"] == ["Alice"]
        assert result["projects"] == []
        assert result["organizations"] == []
        assert result["technologies"] == []

    def test_rejects_non_list_values(self):
        raw = {"people": "Alice", "projects": 123}
        result = _validate_entities(raw)
        assert result["people"] == []
        assert result["projects"] == []

    def test_deduplicates(self):
        raw = {"people": ["Alice", "Alice", "Bob"]}
        result = _validate_entities(raw)
        assert result["people"] == ["Alice", "Bob"]


class TestRegexFallback:
    def test_extracts_technologies(self):
        content = "We're using Python with Django and PostgreSQL"
        entities = _extract_entities_regex(content)
        assert "python" in entities["technologies"]
        assert "django" in entities["technologies"]
        assert "postgresql" in entities["technologies"]

    def test_extracts_capitalized_names(self):
        content = "Meeting with Sarah Johnson about the Q3 plan"
        entities = _extract_entities_regex(content)
        assert "Sarah Johnson" in entities["people"]

    def test_handles_empty_content(self):
        entities = _extract_entities_regex("")
        assert all(v == [] for v in entities.values())


class TestMergeEntities:
    def test_merges_union(self):
        existing = {"people": ["Alice"], "projects": [], "organizations": [], "technologies": []}
        new = {"people": ["Bob"], "projects": ["Engram"], "organizations": [], "technologies": []}
        result = _merge_entities(existing, new)
        assert set(result["people"]) == {"Alice", "Bob"}
        assert result["projects"] == ["Engram"]

    def test_deduplicates_on_merge(self):
        existing = {"people": ["Alice"], "projects": [], "organizations": [], "technologies": []}
        new = {"people": ["Alice", "Bob"], "projects": [], "organizations": [], "technologies": []}
        result = _merge_entities(existing, new)
        assert sorted(result["people"]) == ["Alice", "Bob"]


@pytest.mark.asyncio
class TestExtractEntities:
    async def test_uses_llm_when_available(self):
        with patch("intelligence.entity_extractor.chat_json", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = {
                "people": ["Sarah"],
                "projects": ["Engram"],
                "organizations": ["Anthropic"],
                "technologies": ["Python"],
            }
            result = await extract_entities("Sarah works on Engram at Anthropic using Python")
            assert result["people"] == ["Sarah"]
            assert result["technologies"] == ["Python"]

    async def test_falls_back_on_unavailable(self):
        from intelligence.llm_client import OllamaUnavailableError

        with patch("intelligence.entity_extractor.chat_json", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = OllamaUnavailableError("offline")
            result = await extract_entities("Using Python and Django for development")
            assert "python" in result["technologies"]
            assert "django" in result["technologies"]

    async def test_falls_back_on_http_status_error(self):
        """Ollama returning 404 (model missing) or 500 triggers fallback."""
        from intelligence.llm_client import OllamaUnavailableError

        with patch("intelligence.entity_extractor.chat_json", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = OllamaUnavailableError("HTTP 500")
            result = await extract_entities("Using Python and Django for development")
            assert "python" in result["technologies"]
            assert "django" in result["technologies"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestEnrichEntities:
    async def test_stores_entities_in_metadata(self):
        with patch("core.services.memory_service.embed", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = FAKE_768
            from core.services import memory_service

            memory = await memory_service.create_memory(
                content="Sarah works on Engram",
            )

        with patch("intelligence.entity_extractor.chat_json", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = {
                "people": ["Sarah"],
                "projects": ["Engram"],
                "organizations": [],
                "technologies": [],
            }
            result = await enrich_entities(memory.id)
            assert "Sarah" in result["people"]
            assert "Engram" in result["projects"]

        from asgiref.sync import sync_to_async
        from core.models import Memory

        refreshed = await sync_to_async(Memory.objects.get)(pk=memory.id)
        assert "entities" in refreshed.metadata
        assert "Sarah" in refreshed.metadata["entities"]["people"]
