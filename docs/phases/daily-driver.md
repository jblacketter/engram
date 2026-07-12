# Phase: Daily Driver

## Summary

Make engram part of every Claude Code session without getting in the way:
automatic recall at session start, a **manual suggestion-first checkpoint**
(user-invoked, always confirmed before writing), and a v1
propose→confirm→record flow for project status. This is the adoption phase —
everything later (identity, scoping, automations) only matters if this
sticks.

Locked context (see decision log 2026-07-11): ambient **recall** is
automatic; **capture** is suggestion-first and in v1 explicitly *manual*
(`/engram checkpoint` or the `end_session` MCP prompt — there is no
automatic session-end write, and no hook conducts interactive confirmation).
Fully-automatic capture remains an end-state capability. MCP *resources*
and identity files are Phase 11, not here.

## Data contracts

**Project status = full snapshot, never a delta.** A `type:project-status`
memory's content is a complete, self-contained status document in Markdown
with fixed sections:

```markdown
# Status: <domain>
Goal: <one-line project goal>
State: <current state, 1-3 lines>
Recent: <progress since last snapshot>
Blockers: <blockers / open questions, or "none">
Next: <next actions>
Updated: <YYYY-MM-DD> | Evidence: <checkpoint memory id(s) or "manual">
```

Tags: `["domain:<d>", "type:project-status"]`. The newest such memory per
domain is canonical. Every confirmed status write contains the complete
current snapshot (the drafting flow reads the previous snapshot and carries
forward unchanged sections).

**Checkpoint = session delta.** `type:checkpoint` memories record what a
session decided/learned/left open, plus evidence links; they never stand in
for status. Tags: `["domain:<d>", "type:checkpoint"]`.

**Domain resolution precedence** (used by hook and skill):
`ENGRAM_DOMAIN` env var → `.engram` marker file → repository root
directory name → cwd basename. The `.engram` marker is a one-line file
(`domain=<slug>`) found by a **bounded upward walk** from the hook
payload's `cwd` (≤20 levels, stopping at the filesystem root) — cwd may be
a subdirectory, and one repository must resolve to one domain regardless
of where the session starts. If no marker exists, the nearest ancestor
containing `.git` supplies its directory name; otherwise the cwd basename
is used. Slugs are normalized to `[a-z0-9-]` (lowercased; other characters
→ `-`); invalid/empty resolution falls back to the next source.

## Scope

1. **Deterministic scoped retrieval (small backend addition).**
   `GET /api/memories/` gains optional query params: `tags` (comma-separated,
   ALL-of, e.g. `tags=domain:engram,type:project-status`), `exclude_tags`
   (comma-separated, ANY-of exclusion, ≤5 tags — a memory carrying any
   excluded tag is omitted), `source`, and `limit` (default 20, max 100),
   passed through to `memory_service.list_recent` (created-at ordering —
   already chronological and tag-filterable at the service layer;
   `exclude_tags` adds a `.exclude(tags__contains=[t])` per tag). Read-only,
   no schema change, unit-tested. The hook fetches **exactly**: latest
   status via `tags=domain:<d>,type:project-status&limit=1`, and recents
   via `tags=domain:<d>&exclude_tags=type:project-status,ingested&limit=5`
   — the API itself returns non-status, non-ingested records; no
   client-side filtering, no completeness caveats. *(As built: the
   `ingested` exclusion was added during impl-review hardening — raw
   ingested web/file chunks are the highest prompt-injection risk in
   ambient injection and stay reachable via explicit search.)* RRF search
   remains for relevance queries only.

2. **`list_domains` MCP tool (small backend addition).** Returns the
   distinct `domain:*` tags with memory counts (derived the same way as the
   existing tags aggregation), so `start_day` / `weekly_review` can
   enumerate projects deterministically. Read-only, unit-tested via `.fn`.

3. **SessionStart recall hook.** `integrations/claude-code/engram_recall.py`,
   stdlib-only, registered as a Claude Code `SessionStart` hook. Contract:
   - Reads the hook JSON from **stdin**; derives the project from the
     payload's `cwd` (never the process cwd); applies the domain precedence
     above.
   - Runs on `startup` and `clear` sources; exits silently on `compact`
     (context already present) and on `resume` (avoid duplicate injection).
   - Fetches via the new list filters: latest `type:project-status` (limit
     1) + latest 5 non-status, non-ingested memories for the domain
     (ambient recall never injects raw ingested chunks); prints a compact
     context block (≤4 KB, truncating memory bodies) to stdout.
   - Fail-soft everywhere: malformed/missing stdin, missing cwd, HTTP or
     auth errors, invalid JSON responses, timeouts, empty results → print
     nothing, exit 0. Budget: 1.5 s per request, 3 s total, no retries.
   - Config: `ENGRAM_API_URL` (default `http://localhost:8000/api`),
     optional `ENGRAM_REST_API_KEY`.
   - Tests (`tests/test_recall_hook.py`) cover every bullet above by
     invoking the script with controlled stdin/env against a stubbed HTTP
     layer.

4. **`/engram` skill** (`integrations/claude-code/skills/engram/SKILL.md`):
   - `/engram checkpoint` — **manual, user-invoked.** Drafts (a) a
     `type:checkpoint` session delta and (b) a **full status snapshot** per
     the contract above (reading the previous snapshot first); shows both;
     stores only what the user confirms, via MCP `store_memory`.
   - `/engram status` — fetch + show the latest snapshot for the current
     domain; propose an updated full snapshot on request.
   - `/engram search <query>` — domain-scoped `search_brain`.
   - `/engram store <text>` — explicit store with domain tags.

5. **Four MCP prompts** (`mcp_server/prompts.py`), each specifying its
   arguments and exact tool sequence, referencing only tools that exist
   after item 2:
   - `start_day(domains: list[str] | None)` — default: `list_domains`;
     then latest status per domain via `list_recent_memories(tags=[...])`;
     summarize, surface blockers/next actions.
   - `switch_project(domain: str)` — required arg; latest status + recent
     checkpoints for that domain; restate next actions.
   - `end_session(domain: str)` — required arg; mirrors the checkpoint
     flow: draft delta + full snapshot, require explicit confirmation,
     store via `store_memory`.
   - `weekly_review(domains: list[str] | None, days: int = 7)` — default
     `list_domains`; computes the cutoff and fetches each domain's
     checkpoints via `list_recent_memories(tags=[...], after=<ISO date>)`;
     proposes per-project full-snapshot updates (confirm before storing).
     Requires a new optional `after` argument on the `list_recent_memories`
     MCP tool, backed by a `created_at >= after` filter in
     `memory_service.list_recent` — without it `days` is unenforceable and
     a global limit could silently omit in-window checkpoints. Both the
     service filter and the tool argument are unit-tested.
   Unit tests (`tests/test_mcp_prompts.py`) render each template via `.fn`
   and assert the referenced tool names exist on the server.

6. **Docs + adoption gate.**
   - `docs/workflows.md` "Daily driver" section: contracts above, hook/skill
     installation (including **merging** hook JSON into an existing
     `~/.claude/settings.json`, not overwriting), MCP registration at user
     scope, the daily loop.
   - `integrations/claude-code/README.md`: step-by-step install for any
     repository.
   - `docs/adoption-log.md` (new): dated usage notes per project. **Gate:**
     the Phase 12 project-model decision checkpoint requires either the
     human's confirmation of meaningful use across ≥2 projects (recorded in
     this log) or an explicit "insufficient evidence — decision deferred"
     entry. A single in-cycle demo proves mechanics only; the roadmap's
     one-week adoption criterion is tracked here, not silently dropped.

Out of scope: identity files, `onboard_agent`, MCP resources (Phase 11);
per-agent keys, closing remaining unscoped reads beyond the list-filter
addition (Phase 12); schedulers, stack auto-start, Windows deployment
(Phase 13); any write without explicit confirmation; any automatic
session-end capture.

## Technical Approach

- List filters: extend `MemoryListCreateView.get` + a small query-param
  serializer; `memory_service.list_recent` already accepts `source` and
  `tags` — only the HTTP surface is new. Validate `limit` bounds and tag
  count (≤10).
- `list_domains`: single query over `tags` JSONB (same aggregation style as
  `/api/tags/`), filtered to `domain:` prefix, returned as
  `{domain, count}` list.
- Prompts: FastMCP `@mcp.prompt()`; tests via `prompt.fn(...)`.
- Hook: no engram imports; `urllib.request` with explicit timeouts;
  arguments come only from stdin JSON + env.
- Second-repo verification: install per the README in a second real
  repository (e.g. `~/projects/tagteam`), user-scope MCP registration,
  confirm domain resolution and recall/search there.

## Files

- `api/views.py`, `api/serializers.py` — list filters (incl. `exclude_tags`)
- `core/services/memory_service.py` — `exclude_tags` + `after` filters in
  `list_recent`
- `mcp_server/tools/` — `list_domains`; `after` argument on
  `list_recent_memories`
- `mcp_server/prompts.py` (+ registration import)
- `integrations/claude-code/engram_recall.py`
- `integrations/claude-code/README.md`
- `integrations/claude-code/skills/engram/SKILL.md`
- `tests/test_api_views.py` (list filters), `tests/test_mcp_tools.py`
  (list_domains), `tests/test_mcp_prompts.py`, `tests/test_recall_hook.py`
- `docs/workflows.md`, `docs/adoption-log.md`, `docs/roadmap.md`

## Success Criteria

1. Full backend suite green including new tests for: list filters
   (tags/source/limit/`exclude_tags`, bounds, chronological order),
   `list_recent` `after` filter + `list_recent_memories(after=...)`,
   `list_domains`, all four prompts, and the hook's failure modes
   (malformed stdin, missing cwd, HTTP/auth errors, invalid JSON, timeout,
   empty results, size cap, success path) plus domain resolution from a
   subdirectory (marker found by upward walk, git-root fallback, cwd
   basename fallback).
2. Live demo in this repo: SessionStart hook injects the context block
   (status snapshot + recents) in a real session; with the API stopped the
   session starts normally with no output.
3. `/engram checkpoint` demonstrated end-to-end: drafted delta + full
   snapshot shown, user-confirmed, stored; memory IDs in the submission;
   the stored status is a complete snapshot per the contract.
4. All four prompts listed by a live MCP client; `start_day` executes using
   `list_domains` (no hardcoded domain list).
5. **Second repository end-to-end:** following the README verbatim in
   another repo — settings merged (not overwritten), skill installed, MCP
   registered for that scope, domain resolved correctly, recall + scoped
   search working there. Transcribed in the submission.
6. `docs/adoption-log.md` exists with the trial's opening entry and the
   Phase 12 gate documented; roadmap Phase 12 references the gate.
7. All work committed intentionally on the active branch per repo workflow.
