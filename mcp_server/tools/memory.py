import json
from uuid import UUID

import httpx

from core.models import Memory
from core.services import memory_service
from mcp_server.server import mcp


@mcp.tool()
async def store_memory(
    content: str,
    source: str = "mcp",
    tags: list[str] | None = None,
    importance: float = 0.5,
) -> str:
    """Store a new memory in the brain. Returns the memory ID."""
    try:
        mem = await memory_service.create_memory(
            content=content,
            source=source,
            tags=tags,
            importance=importance,
        )
        return json.dumps({"id": str(mem.id), "status": "stored"})
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return "Embedding service unavailable. Please check Ollama is running."


@mcp.tool()
async def get_memory(memory_id: str) -> str:
    """Retrieve a specific memory by its UUID."""
    try:
        uid = UUID(memory_id)
    except ValueError:
        return "Invalid memory ID format."
    try:
        mem = await memory_service.get_memory(uid)
        return json.dumps({
            "id": str(mem.id),
            "content": mem.content,
            "source": mem.source,
            "tags": mem.tags,
            "metadata": mem.metadata,
            "importance": mem.importance,
            "access_count": mem.access_count,
            "created_at": mem.created_at.isoformat(),
            "updated_at": mem.updated_at.isoformat(),
        })
    except Memory.DoesNotExist:
        return f"Memory {memory_id} not found."


@mcp.tool()
async def update_memory(
    memory_id: str,
    content: str | None = None,
    tags: list[str] | None = None,
    importance: float | None = None,
) -> str:
    """Update an existing memory. Only provided fields are changed.
    Updating content re-generates the embedding."""
    try:
        uid = UUID(memory_id)
    except ValueError:
        return "Invalid memory ID format."

    fields = {}
    if content is not None:
        fields["content"] = content
    if tags is not None:
        fields["tags"] = tags
    if importance is not None:
        fields["importance"] = importance

    if not fields:
        return "No fields to update."

    try:
        mem = await memory_service.update_memory(uid, **fields)
        return json.dumps({"id": str(mem.id), "status": "updated"})
    except Memory.DoesNotExist:
        return f"Memory {memory_id} not found."
    except (httpx.ConnectError, httpx.ConnectTimeout):
        return "Embedding service unavailable. Please check Ollama is running."


@mcp.tool()
async def delete_memory(memory_id: str) -> str:
    """Delete a memory by its UUID."""
    try:
        uid = UUID(memory_id)
    except ValueError:
        return "Invalid memory ID format."
    try:
        await memory_service.delete_memory(uid)
        return f"Deleted memory {memory_id}."
    except Memory.DoesNotExist:
        return f"Memory {memory_id} not found."
