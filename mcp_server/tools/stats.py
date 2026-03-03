import json
from collections import Counter

from asgiref.sync import sync_to_async
from django.db.models import Count, Max, Min

from core.models import Memory
from mcp_server.server import mcp


@mcp.tool()
async def get_stats() -> str:
    """Get statistics about stored memories: total count, counts by source,
    most common tags, and date range."""
    total = await sync_to_async(Memory.objects.count)()

    if total == 0:
        return json.dumps({"total": 0, "by_source": {}, "top_tags": [], "date_range": None})

    # Source breakdown
    source_qs = Memory.objects.values("source").annotate(count=Count("id"))
    source_rows = await sync_to_async(list)(source_qs)
    by_source = {row["source"]: row["count"] for row in source_rows}

    # Date range
    agg = await sync_to_async(
        Memory.objects.aggregate
    )(earliest=Min("created_at"), latest=Max("created_at"))

    # Tag frequency — aggregate from JSONField in Python
    all_memories = await sync_to_async(list)(Memory.objects.values_list("tags", flat=True))
    tag_counter = Counter()
    for tags in all_memories:
        if isinstance(tags, list):
            tag_counter.update(tags)
    top_tags = [{"tag": tag, "count": count} for tag, count in tag_counter.most_common(20)]

    return json.dumps({
        "total": total,
        "by_source": by_source,
        "top_tags": top_tags,
        "date_range": {
            "earliest": agg["earliest"].isoformat() if agg["earliest"] else None,
            "latest": agg["latest"].isoformat() if agg["latest"] else None,
        },
    })
