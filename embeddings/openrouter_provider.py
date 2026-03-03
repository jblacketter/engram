import httpx
from django.conf import settings

from embeddings.base import EmbeddingProvider


class OpenRouterProvider(EmbeddingProvider):
    def __init__(self):
        self._api_key = settings.OPENROUTER_API_KEY
        self._model = settings.OPENROUTER_EMBED_MODEL

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "input": text,
                    "dimensions": settings.VECTOR_DIMENSIONS,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "input": texts,
                    "dimensions": settings.VECTOR_DIMENSIONS,
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            return [item["embedding"] for item in sorted(data, key=lambda d: d["index"])]
