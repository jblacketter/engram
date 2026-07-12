import json
from collections import Counter

from asgiref.sync import sync_to_async

from core.models import Memory
from core.services import scoping
from mcp_server.auth import current_agent
from mcp_server.server import mcp


@mcp.tool()
async def list_domains() -> str:
    """List all project domains (memories tagged `domain:<name>`) with
    memory counts. Use this to enumerate projects before start-of-day or
    weekly-review workflows. Agent principals see only their allowed
    domains."""
    try:
        agent = await current_agent()
    except scoping.ScopeError as exc:
        return f"Scope error: {exc}"
    allowed = scoping.allowed_domains(agent)
    all_tags = await sync_to_async(list)(Memory.objects.values_list("tags", flat=True))
    counter = Counter()
    for tags in all_tags:
        if isinstance(tags, list):
            counter.update(
                t for t in tags if isinstance(t, str) and t.startswith("domain:")
            )
    if not counter:
        return "No domains found."
    data = [
        {"domain": tag[len("domain:"):], "count": count}
        for tag, count in counter.most_common()
        if allowed is None or tag[len("domain:"):] in allowed
    ]
    if not data:
        return "No domains found."

    return json.dumps(data, indent=2)
