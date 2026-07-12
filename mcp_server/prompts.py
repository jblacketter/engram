"""MCP prompts for the daily-driver workflows.

Each prompt is a template that walks the model through an exact tool
sequence. Writes are always suggestion-first: draft, show the user, store
only after explicit confirmation.
"""

from mcp_server.server import mcp

STATUS_CONTRACT = """A project-status memory is a FULL SNAPSHOT, never a delta, in this exact
Markdown shape (carry forward unchanged sections from the previous snapshot):

# Status: <domain>
Goal: <one-line project goal>
State: <current state, 1-3 lines>
Recent: <progress since last snapshot>
Blockers: <blockers / open questions, or "none">
Next: <next actions>
Updated: <YYYY-MM-DD> | Evidence: <checkpoint memory id(s) or "manual">

Store it with tags ["domain:<domain>", "type:project-status"]."""


@mcp.prompt()
def start_day(domains: list[str] | None = None) -> str:
    """Morning orientation: surface each project's status, blockers, and
    next actions."""
    if domains:
        discovery = (
            "Use these domains: " + ", ".join(domains) + "."
        )
    else:
        discovery = (
            "First call `list_domains` to enumerate all project domains."
        )
    return f"""Give me a start-of-day briefing across my projects.

{discovery}

For each domain:
1. Fetch the latest status snapshot:
   `list_recent_memories(tags=["domain:<d>", "type:project-status"], limit=1)`
2. Fetch recent activity:
   `list_recent_memories(tags=["domain:<d>"], limit=3)`

Then produce a compact briefing: per project — current state, blockers,
and the single most valuable next action. Order projects by urgency
(blockers first). End with a suggested focus for today. Do not store
anything."""


@mcp.prompt()
def switch_project(domain: str) -> str:
    """Load context for switching to a specific project."""
    return f"""I'm switching to the project `{domain}`. Load its context:

1. Latest status snapshot:
   `list_recent_memories(tags=["domain:{domain}", "type:project-status"], limit=1)`
2. Recent checkpoints:
   `list_recent_memories(tags=["domain:{domain}", "type:checkpoint"], limit=3)`
3. If I mention a specific topic, search it:
   `search_brain(query=<topic>, tags=["domain:{domain}"])`

Summarize where the project stands and restate the next actions from the
status snapshot, so I can pick up exactly where I left off. Do not store
anything."""


@mcp.prompt()
def end_session(domain: str) -> str:
    """Suggestion-first session checkpoint: draft, confirm, then store."""
    return f"""We're wrapping up a session on `{domain}`. Run the checkpoint flow:

1. Fetch the previous status snapshot:
   `list_recent_memories(tags=["domain:{domain}", "type:project-status"], limit=1)`
2. Draft TWO items and SHOW THEM TO ME — do not store yet:
   a) A session checkpoint (what we decided, learned, and left open), to be
      tagged ["domain:{domain}", "type:checkpoint"].
   b) An updated FULL status snapshot per the contract below.
3. Wait for my explicit confirmation. I may approve both, one, or neither,
   and may edit the drafts first.
4. Store only what I approved, via `store_memory` (source "mcp").
   Store the checkpoint first, then reference its returned id in the
   snapshot's Evidence field.

{STATUS_CONTRACT}"""


@mcp.prompt()
def weekly_review(domains: list[str] | None = None, days: int = 7) -> str:
    """Weekly review: aggregate checkpoints per project, propose status
    updates (confirm before storing)."""
    if domains:
        discovery = "Use these domains: " + ", ".join(domains) + "."
    else:
        discovery = "First call `list_domains` to enumerate all project domains."
    return f"""Run my weekly review covering the last {days} days.

{discovery}

Compute the cutoff date ({days} days ago, ISO format), then for each domain:
1. Fetch the period's checkpoints:
   `list_recent_memories(tags=["domain:<d>", "type:checkpoint"], after=<cutoff>, limit=20)`
2. Fetch the current status snapshot:
   `list_recent_memories(tags=["domain:<d>", "type:project-status"], limit=1)`

Then:
- Summarize the week per project: what moved, what stalled, what's blocked.
- For each project whose snapshot is out of date, DRAFT an updated FULL
  snapshot per the contract below and SHOW it to me.
- Store only the snapshots I explicitly approve, via `store_memory`
  (source "mcp").
- Close with cross-project observations: overcommitted areas, quick wins,
  and anything untouched for over a week.

{STATUS_CONTRACT}"""
