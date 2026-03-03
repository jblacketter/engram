import logging
from datetime import datetime, timezone

from asgiref.sync import sync_to_async

from core.models import Memory

logger = logging.getLogger(__name__)


def compute_decay_factor(
    importance: float,
    created_at: datetime,
    last_accessed: datetime | None,
    access_count: int,
    now: datetime | None = None,
) -> float:
    """Pure function: returns decay_factor between 0.0 and 1.0."""
    now = now or datetime.now(timezone.utc)

    age_days = (now - created_at).total_seconds() / 86400
    recency_days = (now - (last_accessed or created_at)).total_seconds() / 86400

    recency_factor = 1.0 / (1.0 + recency_days / 30.0)
    access_factor = min(1.0, 0.5 + access_count * 0.05)
    age_penalty = 1.0 / (1.0 + age_days / 365.0)

    decay_factor = importance * recency_factor * access_factor * age_penalty
    return max(0.0, min(1.0, decay_factor))


async def run_decay(dry_run: bool = False) -> list[dict]:
    """Recompute decay_factor for all memories. Returns list of {id, old, new} diffs."""
    memories = await sync_to_async(list)(Memory.objects.all())
    now = datetime.now(timezone.utc)

    changes: list[dict] = []
    to_update: list[Memory] = []

    for memory in memories:
        old_decay = memory.decay_factor
        new_decay = compute_decay_factor(
            importance=memory.importance,
            created_at=memory.created_at,
            last_accessed=memory.last_accessed,
            access_count=memory.access_count,
            now=now,
        )

        if abs(new_decay - old_decay) > 1e-6:
            changes.append({
                "id": str(memory.id),
                "old": round(old_decay, 4),
                "new": round(new_decay, 4),
            })
            if not dry_run:
                memory.decay_factor = new_decay
                to_update.append(memory)

    if to_update:
        await sync_to_async(Memory.objects.bulk_update)(to_update, ["decay_factor"])
        logger.info("Updated decay_factor for %d memories", len(to_update))

    return changes
