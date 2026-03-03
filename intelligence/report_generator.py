from collections import Counter
from datetime import datetime, timedelta, timezone

from asgiref.sync import sync_to_async
from django.db.models import Min, Max

from core.models import Memory


async def generate_report(days: int = 7) -> str:
    """Generate a Markdown weekly digest covering the last N days."""
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    total_count = await sync_to_async(Memory.objects.count)()
    recent_qs = Memory.objects.filter(created_at__gte=since)
    recent_memories = await sync_to_async(list)(recent_qs.order_by("-created_at"))
    recent_count = len(recent_memories)

    # Source breakdown
    source_counts: dict[str, int] = Counter()
    for m in recent_memories:
        source_counts[m.source] += 1

    # Top tags across new memories
    tag_counts: Counter = Counter()
    for m in recent_memories:
        for tag in (m.tags or []):
            tag_counts[tag] += 1
    top_tags = tag_counts.most_common(10)

    # Top entities across new memories
    entity_counts: dict[str, Counter] = {
        "people": Counter(),
        "projects": Counter(),
        "organizations": Counter(),
        "technologies": Counter(),
    }
    for m in recent_memories:
        entities = (m.metadata or {}).get("entities", {})
        for cat, counter in entity_counts.items():
            for entity in entities.get(cat, []):
                counter[entity] += 1

    # Most accessed in period
    most_accessed = await sync_to_async(list)(
        recent_qs.order_by("-access_count")[:5]
    )

    # Decay alerts: all memories with low decay
    decay_alerts = await sync_to_async(list)(
        Memory.objects.filter(decay_factor__lt=0.2).order_by("decay_factor")[:10]
    )

    # Date range
    agg = await sync_to_async(
        Memory.objects.aggregate
    )(earliest=Min("created_at"), latest=Max("created_at"))

    # Build report
    lines = [
        "# Engram Weekly Digest",
        "",
        f"**Period:** {since.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}",
        "",
        "## Summary",
        "",
        f"- **Total memories:** {total_count}",
        f"- **New in period:** {recent_count}",
    ]

    if source_counts:
        lines.append(f"- **Sources:** {', '.join(f'{s} ({c})' for s, c in source_counts.most_common())}")

    if agg.get("earliest") and agg.get("latest"):
        lines.append(
            f"- **Date range:** {agg['earliest'].strftime('%Y-%m-%d')} to "
            f"{agg['latest'].strftime('%Y-%m-%d')}"
        )

    lines.append("")

    # Top tags
    if top_tags:
        lines.append("## Top Tags")
        lines.append("")
        for tag, count in top_tags:
            lines.append(f"- `{tag}` ({count})")
        lines.append("")

    # Top entities
    has_entities = any(c for c in entity_counts.values())
    if has_entities:
        lines.append("## Top Entities")
        lines.append("")
        for cat, counter in entity_counts.items():
            top = counter.most_common(5)
            if top:
                lines.append(f"### {cat.title()}")
                for entity, count in top:
                    lines.append(f"- {entity} ({count})")
                lines.append("")

    # Most accessed
    if most_accessed:
        lines.append("## Most Accessed")
        lines.append("")
        for m in most_accessed:
            preview = m.content[:80].replace("\n", " ")
            lines.append(f"- **{m.access_count} views** — {preview}...")
        lines.append("")

    # Decay alerts
    if decay_alerts:
        lines.append("## Decay Alerts")
        lines.append("")
        lines.append("Memories with low relevance scores that may need review:")
        lines.append("")
        for m in decay_alerts:
            preview = m.content[:60].replace("\n", " ")
            lines.append(f"- `{m.decay_factor:.3f}` — {preview}...")
        lines.append("")

    return "\n".join(lines)
