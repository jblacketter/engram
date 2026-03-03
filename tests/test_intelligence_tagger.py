from unittest.mock import AsyncMock, patch

import httpx
import pytest

from intelligence.auto_tagger import (
    _extract_tags_tfidf,
    _validate_tags,
    enrich_tags,
    extract_tags,
)
from intelligence.llm_client import OllamaUnavailableError, chat_json

FAKE_768 = [0.1] * 768


class TestValidateTags:
    def test_normalizes_and_deduplicates(self):
        assert _validate_tags(["Python", "DJANGO", "python"]) == ["python", "django"]

    def test_strips_invalid_characters(self):
        assert _validate_tags(["hello!", "world@test"]) == ["hello", "worldtest"]

    def test_limits_to_eight(self):
        tags = [f"tag{i}" for i in range(12)]
        assert len(_validate_tags(tags)) == 8

    def test_rejects_single_char_tags(self):
        assert _validate_tags(["a", "ab", "abc"]) == ["ab", "abc"]

    def test_rejects_non_strings(self):
        assert _validate_tags([123, None, "valid"]) == ["valid"]


class TestTfidfFallback:
    def test_extracts_frequent_words(self):
        content = "python django python framework django python testing"
        tags = _extract_tags_tfidf(content)
        assert "python" in tags
        assert "django" in tags

    def test_excludes_stop_words(self):
        content = "the and for are but not you all can had"
        tags = _extract_tags_tfidf(content)
        assert tags == []

    def test_returns_top_five(self):
        content = " ".join(f"word{i} " * (10 - i) for i in range(8))
        tags = _extract_tags_tfidf(content)
        assert len(tags) <= 5


@pytest.mark.asyncio
class TestExtractTags:
    async def test_uses_llm_when_available(self):
        with patch("intelligence.auto_tagger.chat_json", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = {"tags": ["python", "django", "testing"]}
            tags = await extract_tags("Building a Django app with testing")
            assert tags == ["python", "django", "testing"]
            mock_chat.assert_called_once()

    async def test_falls_back_to_tfidf_on_unavailable(self):
        from intelligence.llm_client import OllamaUnavailableError

        with patch("intelligence.auto_tagger.chat_json", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = OllamaUnavailableError("offline")
            tags = await extract_tags("python django python framework django python")
            assert "python" in tags
            assert "django" in tags

    async def test_falls_back_on_invalid_llm_response(self):
        with patch("intelligence.auto_tagger.chat_json", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = {"tags": []}
            tags = await extract_tags("python django python framework django python")
            assert "python" in tags

    async def test_falls_back_on_http_status_error(self):
        """Ollama returning 404 (model missing) or 500 triggers fallback."""
        from intelligence.llm_client import OllamaUnavailableError

        with patch("intelligence.auto_tagger.chat_json", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = OllamaUnavailableError("HTTP 404")
            tags = await extract_tags("python django python framework django python")
            assert "python" in tags
            assert "django" in tags


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestEnrichTags:
    async def test_merges_with_existing_tags(self):
        with patch("core.services.memory_service.embed", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = FAKE_768
            from core.services import memory_service

            memory = await memory_service.create_memory(
                content="Python and Django framework",
                tags=["existing-tag"],
            )

        with patch("intelligence.auto_tagger.chat_json", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = {"tags": ["python", "django"]}
            result = await enrich_tags(memory.id)
            assert "existing-tag" in result
            assert "python" in result
            assert "django" in result

    async def test_does_not_duplicate_existing(self):
        with patch("core.services.memory_service.embed", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = FAKE_768
            from core.services import memory_service

            memory = await memory_service.create_memory(
                content="Python development",
                tags=["python"],
            )

        with patch("intelligence.auto_tagger.chat_json", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = {"tags": ["python", "development"]}
            result = await enrich_tags(memory.id)
            assert result.count("python") == 1


@pytest.mark.asyncio
class TestChatJsonErrorHandling:
    async def test_raises_on_http_404(self):
        """chat_json raises OllamaUnavailableError on HTTP 404 (model not found)."""
        mock_response = httpx.Response(404, request=httpx.Request("POST", "http://test/api/chat"))
        with patch("intelligence.llm_client.httpx.AsyncClient") as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(OllamaUnavailableError, match="HTTP 404"):
                await chat_json("system", "user")

    async def test_raises_on_http_500(self):
        """chat_json raises OllamaUnavailableError on HTTP 500."""
        mock_response = httpx.Response(500, request=httpx.Request("POST", "http://test/api/chat"))
        with patch("intelligence.llm_client.httpx.AsyncClient") as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(OllamaUnavailableError, match="HTTP 500"):
                await chat_json("system", "user")
