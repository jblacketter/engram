import httpx
from django.conf import settings

from embeddings.base import EmbeddingProvider


class OllamaProvider(EmbeddingProvider):
    def __init__(self):
        self._base_url = settings.OLLAMA_BASE_URL
        self._model = settings.OLLAMA_EMBED_MODEL

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model, "input": text},
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()["embeddings"][0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model, "input": texts},
                timeout=60.0,
            )
            resp.raise_for_status()
            return resp.json()["embeddings"]
