---
name: engram
description: Store, search, and checkpoint project memory in engram. Subcommands - checkpoint (suggestion-first session summary + status snapshot), status (show/update project status), search <query>, store <text>. All writes are drafted and confirmed before storing.
---

# Skill: /engram

Interact with the engram semantic memory via its MCP tools
(`mcp__engram__*`). Every write is **suggestion-first**: draft, show the
user, store only after explicit confirmation.

## Domain resolution

Resolve the current project domain, in order:
1. `ENGRAM_DOMAIN` environment variable
2. A `.engram` file at the repository root (one line: `domain=<slug>`)
3. The repository root directory name, normalized to `[a-z0-9-]`

Use `domain:<slug>` in tags for every read and write below.

## Data contracts

**Status snapshot** (`type:project-status`) — always a FULL snapshot, never
a delta. The newest one per domain is canonical:

```markdown
# Status: <domain>
Goal: <one-line project goal>
State: <current state, 1-3 lines>
Recent: <progress since last snapshot>
Blockers: <blockers / open questions, or "none">
Next: <next actions>
Updated: <YYYY-MM-DD> | Evidence: <checkpoint memory id(s) or "manual">
```

**Checkpoint** (`type:checkpoint`) — a session delta: decisions made,
things learned, threads left open.

## Subcommands

### /engram checkpoint
1. Fetch the previous snapshot:
   `list_recent_memories(tags=["domain:<d>", "type:project-status"], limit=1)`
2. Draft BOTH, from this session's conversation:
   a) a checkpoint (session delta), tags `["domain:<d>", "type:checkpoint"]`
   b) an updated FULL status snapshot per the contract (carry forward
      unchanged sections from the previous snapshot)
3. Show both drafts. **Wait for confirmation.** The user may approve both,
   one, or neither, and may edit first.
4. Store only what was approved via `store_memory` (source `"mcp"`). Store
   the checkpoint first and put its returned id in the snapshot's
   `Evidence:` field.

### /engram status
Show the latest snapshot:
`list_recent_memories(tags=["domain:<d>", "type:project-status"], limit=1)`.
If the user asks for an update, draft a new FULL snapshot, confirm, store.

### /engram search <query>
`search_brain(query=<query>, tags=["domain:<d>"])`. Present the hits with
ids, dates, and content. No writes.

### /engram store <text>
Draft the memory (content, tags `["domain:<d>", "type:note"]` plus any the
user named, source `"mcp"`), show it, confirm, then `store_memory`.

## Rules

- Never store without showing the draft and getting a yes.
- Never write a status delta — snapshots are always complete.
- If the engram MCP tools are unavailable, say so and stop; do not fall
  back to writing files.
