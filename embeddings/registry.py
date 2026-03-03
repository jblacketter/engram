import logging

import httpx
from django.conf import settings

from embeddings.base import EmbeddingProvider
from embeddings.ollama_provider import OllamaProvider
from embeddings.openrouter_provider import OpenRouterProvider

logger = logging.getLogger(__name__)


def get_provider() -> EmbeddingProvider:
    return OllamaProvider()


def get_fallback_provider() -> EmbeddingProvider | None:
    if settings.OPENROUTER_API_KEY:
        return OpenRouterProvider()
    return None


def _validate_dimensions(vector: list[float]) -> list[float]:
    expected = settings.VECTOR_DIMENSIONS
    if len(vector) != expected:
        raise ValueError(
            f"Embedding dimension mismatch: got {len(vector)}, expected {expected}"
        )
    return vector


def _validate_dimensions_batch(vectors: list[list[float]]) -> list[list[float]]:
    for v in vectors:
        _validate_dimensions(v)
    return vectors


async def embed(text: str) -> list[float]:
    """Embed text using primary provider with fallback. Validates dimensions."""
    provider = get_provider()
    try:
        vector = await provider.embed(text)
    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        fallback = get_fallback_provider()
        if fallback is None:
            raise
        logger.warning("Ollama unavailable (%s), falling back to OpenRouter", exc)
        vector = await fallback.embed(text)
    return _validate_dimensions(vector)


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed multiple texts using primary provider with fallback. Validates dimensions."""
    provider = get_provider()
    try:
        vectors = await provider.embed_batch(texts)
    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        fallback = get_fallback_provider()
        if fallback is None:
            raise
        logger.warning("Ollama unavailable (%s), falling back to OpenRouter", exc)
        vectors = await fallback.embed_batch(texts)
    return _validate_dimensions_batch(vectors)
