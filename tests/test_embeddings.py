from unittest.mock import AsyncMock, patch

import httpx
import pytest

from embeddings.ollama_provider import OllamaProvider
from embeddings.openrouter_provider import OpenRouterProvider
from embeddings.registry import embed, embed_batch


FAKE_768 = [0.1] * 768
FAKE_BATCH_768 = [[0.1] * 768, [0.2] * 768]


@pytest.fixture
def ollama_response():
    """Mock httpx response for Ollama embed API."""
    resp = AsyncMock(spec=httpx.Response)
    resp.status_code = 200
    resp.raise_for_status = lambda: None
    resp.json.return_value = {"embeddings": [FAKE_768]}
    return resp


@pytest.fixture
def ollama_batch_response():
    resp = AsyncMock(spec=httpx.Response)
    resp.status_code = 200
    resp.raise_for_status = lambda: None
    resp.json.return_value = {"embeddings": FAKE_BATCH_768}
    return resp


@pytest.fixture
def openrouter_response():
    resp = AsyncMock(spec=httpx.Response)
    resp.status_code = 200
    resp.raise_for_status = lambda: None
    resp.json.return_value = {"data": [{"embedding": FAKE_768, "index": 0}]}
    return resp


@pytest.fixture
def openrouter_batch_response():
    resp = AsyncMock(spec=httpx.Response)
    resp.status_code = 200
    resp.raise_for_status = lambda: None
    resp.json.return_value = {
        "data": [
            {"embedding": FAKE_BATCH_768[0], "index": 0},
            {"embedding": FAKE_BATCH_768[1], "index": 1},
        ]
    }
    return resp


class TestOllamaProvider:
    @pytest.mark.asyncio
    async def test_embed(self, ollama_response):
        with patch("embeddings.ollama_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = ollama_response
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            provider = OllamaProvider()
            result = await provider.embed("hello")

            assert result == FAKE_768
            assert len(result) == 768
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_batch(self, ollama_batch_response):
        with patch("embeddings.ollama_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = ollama_batch_response
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            provider = OllamaProvider()
            result = await provider.embed_batch(["hello", "world"])

            assert len(result) == 2
            assert len(result[0]) == 768

    @pytest.mark.asyncio
    async def test_connection_error_raises(self):
        with patch("embeddings.ollama_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection refused")
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            provider = OllamaProvider()
            with pytest.raises(httpx.ConnectError):
                await provider.embed("hello")


class TestOpenRouterProvider:
    @pytest.mark.asyncio
    async def test_embed(self, openrouter_response, settings):
        settings.OPENROUTER_API_KEY = "test-key"
        settings.OPENROUTER_EMBED_MODEL = "openai/text-embedding-3-small"

        with patch("embeddings.openrouter_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = openrouter_response
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            provider = OpenRouterProvider()
            result = await provider.embed("hello")

            assert result == FAKE_768
            # Verify dimensions param is sent
            call_kwargs = mock_client.post.call_args
            assert call_kwargs.kwargs["json"]["dimensions"] == 768

    @pytest.mark.asyncio
    async def test_embed_batch(self, openrouter_batch_response, settings):
        settings.OPENROUTER_API_KEY = "test-key"
        settings.OPENROUTER_EMBED_MODEL = "openai/text-embedding-3-small"

        with patch("embeddings.openrouter_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = openrouter_batch_response
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            provider = OpenRouterProvider()
            result = await provider.embed_batch(["hello", "world"])

            assert len(result) == 2


class TestRegistry:
    @pytest.mark.asyncio
    async def test_embed_uses_primary(self):
        with patch("embeddings.registry.get_provider") as mock_get:
            mock_provider = AsyncMock()
            mock_provider.embed.return_value = FAKE_768
            mock_get.return_value = mock_provider

            result = await embed("hello")
            assert result == FAKE_768
            mock_provider.embed.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_embed_falls_back_on_connect_error(self, settings):
        settings.OPENROUTER_API_KEY = "test-key"

        with (
            patch("embeddings.registry.get_provider") as mock_get,
            patch("embeddings.registry.get_fallback_provider") as mock_fallback,
        ):
            primary = AsyncMock()
            primary.embed.side_effect = httpx.ConnectError("Connection refused")
            mock_get.return_value = primary

            fallback = AsyncMock()
            fallback.embed.return_value = FAKE_768
            mock_fallback.return_value = fallback

            result = await embed("hello")
            assert result == FAKE_768
            fallback.embed.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_embed_raises_on_no_fallback(self):
        with (
            patch("embeddings.registry.get_provider") as mock_get,
            patch("embeddings.registry.get_fallback_provider", return_value=None),
        ):
            primary = AsyncMock()
            primary.embed.side_effect = httpx.ConnectError("Connection refused")
            mock_get.return_value = primary

            with pytest.raises(httpx.ConnectError):
                await embed("hello")

    @pytest.mark.asyncio
    async def test_dimension_validation_rejects_wrong_size(self):
        with patch("embeddings.registry.get_provider") as mock_get:
            mock_provider = AsyncMock()
            mock_provider.embed.return_value = [0.1] * 512  # wrong dim
            mock_get.return_value = mock_provider

            with pytest.raises(ValueError, match="dimension mismatch"):
                await embed("hello")

    @pytest.mark.asyncio
    async def test_embed_batch_with_fallback(self, settings):
        settings.OPENROUTER_API_KEY = "test-key"

        with (
            patch("embeddings.registry.get_provider") as mock_get,
            patch("embeddings.registry.get_fallback_provider") as mock_fallback,
        ):
            primary = AsyncMock()
            primary.embed_batch.side_effect = httpx.ConnectTimeout("timeout")
            mock_get.return_value = primary

            fallback = AsyncMock()
            fallback.embed_batch.return_value = FAKE_BATCH_768
            mock_fallback.return_value = fallback

            result = await embed_batch(["hello", "world"])
            assert len(result) == 2
            assert len(result[0]) == 768
