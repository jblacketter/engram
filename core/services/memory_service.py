import logging
from datetime import datetime, timezone
from uuid import UUID

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db.models import F

from core.models import Memory
from embeddings.registry import embed

logger = logging.getLogger(__name__)


async def create_memory(
    content: str,
    source: str = "manual",
    tags: list[str] | None = None,
    metadata: dict | None = None,
    importance: float = 0.5,
) -> Memory:
    vector = await embed(content)
    memory = await sync_to_async(Memory.objects.create)(
        content=content,
        embedding=vector,
        source=source,
        tags=tags or [],
        metadata=metadata or {},
        importance=importance,
    )

    if getattr(settings, "AUTO_ENRICH_ON_CREATE", False):
        try:
            from intelligence.auto_tagger import enrich_tags
            from intelligence.entity_extractor import enrich_entities

            await enrich_tags(memory.id)
            await enrich_entities(memory.id)
        except Exception:
            logger.warning("Auto-enrichment failed for memory %s", memory.id, exc_info=True)

    return memory


async def get_memory(memory_id: UUID) -> Memory:
    """Retrieve a memory and atomically increment access_count."""
    await sync_to_async(
        Memory.objects.filter(pk=memory_id).update
    )(access_count=F("access_count") + 1, last_accessed=datetime.now(timezone.utc))
    return await sync_to_async(Memory.objects.get)(pk=memory_id)


async def update_memory(memory_id: UUID, **fields) -> Memory:
    """Update a memory. Re-embeds if content changes."""
    memory = await sync_to_async(Memory.objects.get)(pk=memory_id)

    if "content" in fields:
        fields["embedding"] = await embed(fields["content"])

    for attr, value in fields.items():
        setattr(memory, attr, value)

    await sync_to_async(memory.save)()
    return memory


async def delete_memory(memory_id: UUID) -> None:
    count, _ = await sync_to_async(
        Memory.objects.filter(pk=memory_id).delete
    )()
    if count == 0:
        raise Memory.DoesNotExist


async def list_recent(limit: int = 20, source: str | None = None) -> list[Memory]:
    qs = Memory.objects.order_by("-created_at")
    if source is not None:
        qs = qs.filter(source=source)
    return await sync_to_async(list)(qs[:limit])
