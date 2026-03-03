import json
import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class OllamaUnavailableError(Exception):
    """Raised when the Ollama chat endpoint is unreachable."""


async def chat_json(
    system_prompt: str,
    user_content: str,
    model: str | None = None,
) -> dict:
    """Send a chat completion to Ollama and parse JSON from the response."""
    model = model or settings.OLLAMA_CHAT_MODEL
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "format": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise OllamaUnavailableError(
            f"Ollama returned HTTP {exc.response.status_code} at {url}"
        ) from exc
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
        raise OllamaUnavailableError(f"Cannot reach Ollama at {url}") from exc

    body = resp.json()
    content = body.get("message", {}).get("content", "")

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        logger.warning("Ollama returned non-JSON content: %s", content[:200])
        return {}
