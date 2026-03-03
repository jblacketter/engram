import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID

import httpx

from core.models import Memory
from core.services import memory_service, search_service
from mcp_server.server import mcp


def _serialize_results(results: list[dict]) -> str:
    """Serialize search results to JSON, handling datetime, UUID, and Decimal objects."""
    for r in results:
        for key, value in r.items():
            if isinstance(value, UUID):
                r[key] = str(value)
            elif isinstance(value, datetime):
                r[key] = value.isoformat()
            elif isinstance(value, Decimal):
                r[key] = float(value)
    return json.dumps(results, indent=2)


@mcp.tool()
async def search_brain(
    query: str,
    limit: int = 10,
    tags: list[str] | None = None,
    source: str | None = None,
    semantic_weight: float = 0.5,
) -> str:
    """Search the brain using hybrid semantic + keyword search.

    semantic_weight controls the blend: 0.0 = pure keyword, 1.0 = pure semantic,
    0.5 = balanced (default). Returns ranked results with relevance scores."""
    try:
        results = await search_service.search(
            query=query,
            limit=limit,
            tags=tags,
            source=source,
            semantic_weight=semantic_weight,
        )
        if not results:
            return "No matching memories found."
        return _serialize_results(results)
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return "Embedding service unavailable. Please check Ollama is running."


@mcp.tool()
async def find_related(memory_id: str, limit: int = 5) -> str:
    """Find memories related to a specific memory. Uses the memory's content
    as a search query with pure semantic search (weight=1.0)."""
    try:
        uid = UUID(memory_id)
    except ValueError:
        return "Invalid memory ID format."
    try:
        mem = await memory_service.get_memory(uid)
    except Memory.DoesNotExist:
        return f"Memory {memory_id} not found."

    try:
        results = await search_service.search(
            query=mem.content,
            limit=limit + 1,  # fetch extra to exclude self
            semantic_weight=1.0,
        )
        # Exclude the source memory from results
        results = [r for r in results if str(r["id"]) != memory_id][:limit]
        if not results:
            return "No related memories found."
        return _serialize_results(results)
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return "Embedding service unavailable. Please check Ollama is running."


@mcp.tool()
async def list_recent_memories(limit: int = 20, source: str | None = None) -> str:
    """List the most recently created memories, optionally filtered by source."""
    memories = await memory_service.list_recent(limit=limit, source=source)
    if not memories:
        return "No memories found."
    data = [
        {
            "id": str(m.id),
            "content": m.content,
            "source": m.source,
            "tags": m.tags,
            "importance": m.importance,
            "created_at": m.created_at.isoformat(),
        }
        for m in memories
    ]
    return json.dumps(data, indent=2)
