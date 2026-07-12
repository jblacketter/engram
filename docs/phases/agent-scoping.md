# Phase: Agent Scoping

## Summary

Per-agent API keys with domain binding, closing the unscoped read surfaces
for agent principals. After this phase, each tool/agent (Claude Code,
Cursor, Aegis, an ollama agent on the LAN) can hold its own key bound to
the domains it may touch; two agents with different domains cannot see
each other's memories on any surface. The single-user owner surfaces
(global key, dashboard session) keep full visibility — this is per-agent
scoping, not multi-tenancy.

The phase opens with the **project-model decision checkpoint** required by
the roadmap gate.

## Decision checkpoint (first deliverable)

The roadmap gates the "soft tags vs first-class workspace column" decision
on `docs/adoption-log.md` evidence: the human's confirmation of meaningful
daily-driver use across ≥2 projects, or an explicit deferral. The adoption
trial opened 2026-07-11 — **less than the one-week criterion by
definition** — so unless the human states otherwise during this plan
review, the checkpoint records: **"insufficient evidence — project-model
decision deferred; soft `domain:` tags remain the project model pending
trial data"** in both `docs/adoption-log.md` and `docs/decision_log.md`,
with the revisit condition (human confirmation after the trial). The
per-agent authorization work below explicitly does not depend on that
outcome: keys bind to domain *tags* today and would bind to workspace
values identically if the model later hardens.

## Data contracts

**AgentKey model** (`core/models.py`, new table; no change to `memories`):

| field | contract |
|---|---|
| `id` | UUID pk |
| `name` | unique agent slug `[a-z0-9-]+` (e.g. `claude-code`, `aegis`) |
| `key_hash` | unique SHA-256 hex of the secret; plaintext never stored |
| `default_domain` | domain slug; injected on writes when the caller supplies no `domain:` tag |
| `allowed_domains` | JSON list of domain slugs; must contain `default_domain`; a key may only read/write these |
| `is_active` | revocation flag |
| `created_at`, `last_used_at` | timestamps; `last_used_at` updated on successful auth |

**Key format:** `egk_` + 43 urlsafe-base64 chars from
`secrets.token_urlsafe(32)`. Shown exactly once at creation. Lookup is by
SHA-256 hash equality (indexed unique column — no timing oracle beyond
hash lookup).

**Principal model.** Three principal classes, decided at auth time:
- **Owner** — global `REST_API_KEY`/`MCP_API_KEY` or dashboard session:
  full visibility, no injection, unchanged behavior (single-user owner
  surface; README documents this explicitly).
- **Agent** — a valid active AgentKey: enforcement below.
- **Anonymous** — only when auth is disabled (empty keys, dev mode):
  unchanged open behavior. Agent enforcement never weakens the existing
  modes; with no AgentKey rows the system behaves exactly as today
  (asserted by tests).

**Agent enforcement semantics** (identical on REST and MCP):
- *Writes* (`store_memory`, `POST /api/memories/`, ingest endpoints/tools):
  if the request carries no `domain:` tag → inject
  `domain:<default_domain>`; if it carries any `domain:` tag outside
  `allowed_domains` → reject with an explicit error (HTTP 403 / tool error
  string). Never silently rewrite a caller-supplied domain.
- *Scoped reads* (`search_brain`, `find_related`, `list_recent_memories`,
  `POST /api/search/`, `GET /api/memories/` with filters): a requested
  `domain:` tag outside `allowed_domains` → reject (same as writes); no
  domain filter supplied → constrain to `domain:<default_domain>`
  (deterministic; the existing ALL-of tag filters implement it — reading a
  different allowed domain requires naming it).
- *Formerly unscoped reads*:
  - `GET /api/memories/<id>` and MCP `get_memory`: served only if the
    memory carries at least one allowed `domain:` tag; otherwise **404 /
    "not found"** (never 403 — no existence oracle).
  - `GET /api/stats/` and MCP `get_stats`: computed over the union of
    `allowed_domains` only.
  - `GET /api/tags/`: enumerated over the union of `allowed_domains` only.
  - `update_memory` / `delete_memory` / `PATCH` / `DELETE`: same
    visibility rule as `get_memory` — you cannot mutate what you cannot
    see (404).
  - Memories carrying **no** `domain:` tag are invisible to agent
    principals (they are outside every agent's scope; the owner surface
    still sees them).

**MCP principal transport.** A custom FastMCP `TokenVerifier` replaces the
debug verifier: it accepts the global `MCP_API_KEY` (→ owner) or an agent
key (→ agent claims: name + allowed/default domains), rejecting inactive
keys. Tools obtain the principal via FastMCP's access-token dependency;
when MCP auth is disabled entirely (no global key AND no agent keys), the
server stays open exactly as today.

## Scope

1. **Model + migration + management commands.** `AgentKey` per the
   contract; `python manage.py agent_keys create <name> --default-domain
   <slug> [--allow <slug> ...]` (prints the plaintext key once),
   `agent_keys revoke <name>`, `agent_keys list` (never prints secrets).
2. **REST auth.** Extend `APIKeyAuthentication`: global key → owner
   principal (existing `APIKeyUser`); otherwise AgentKey hash lookup →
   agent principal carrying the key record; inactive/unknown → 403 as
   today. Session auth unchanged (owner).
3. **REST enforcement.** A small enforcement helper used by the views:
   write injection/rejection on memories + ingest endpoints; scoped-read
   constraint on list/search; allowed-domain filtering on detail, stats,
   tags, update, delete per the contract.
4. **MCP verifier + enforcement.** Custom `TokenVerifier` in
   `mcp_server/auth.py`; the same enforcement helper applied in
   `store_memory`, `get_memory`, `update_memory`, `delete_memory`,
   `search_brain`, `find_related`, `list_recent_memories`, `get_stats`,
   ingest tools. `list_domains` returns only allowed domains for agents.
5. **Docs.** README "Scoping memories across domains": residual-surfaces
   table updated — closed for agent principals, owner surface documented
   as intentionally unscoped; key management + connection examples
   (`Authorization: Bearer egk_...`); `docs/workflows.md` cross-reference;
   `.env.example` note. Decision checkpoint entries in adoption log +
   decision log.
6. **Out of scope:** workspace/tenant column (deferred by the checkpoint),
   per-key throttling/quotas, key rotation UX beyond revoke+create,
   dashboard multi-user auth, agent-gate integration, MCP auth for the
   resources added in Phase 11 beyond what the verifier provides
   (resources serve identity files — owner data — and MCP-level auth
   already gates the whole server when enabled).

## Technical Approach

- Enforcement lives in one module (`core/services/scoping.py`): pure
  functions `check_write_tags(principal, tags) -> tags | error`,
  `constrain_read_tags(principal, tags) -> tags | error`,
  `visible(principal, memory) -> bool`, `allowed_domains(principal) ->
  list | None` (None = unrestricted) — used by both REST views and MCP
  tools so the two surfaces cannot drift.
- Stats/tags aggregation for agents: OR-across-allowed-domains via
  `tags__contains=[f"domain:{d}"]` per domain unioned with `Q` objects —
  no raw SQL changes.
- The hybrid-search path already takes an ALL-of tag list; agent
  constraint supplies `["domain:<one allowed domain>"]` per the
  deterministic default rule, so `core/managers.py` is untouched.
- REST principal: attach the AgentKey to `request.auth`; DRF views read it
  from there. MCP principal: FastMCP `get_access_token()` claims.
- Auth back-compat is a hard test: with zero AgentKey rows, the full
  existing test suite semantics hold (global-key mode and open dev mode
  bit-for-bit unchanged).

## Files

- `core/models.py` + new migration (AgentKey)
- `core/services/scoping.py` (new)
- `core/management/commands/agent_keys.py` (new)
- `api/authentication.py`, `api/views.py`
- `mcp_server/auth.py`, `mcp_server/tools/*.py` (enforcement call sites)
- `tests/test_agent_keys.py`, `tests/test_scoping_rest.py`,
  `tests/test_scoping_mcp.py` (new)
- `README.md`, `docs/workflows.md`, `.env.example`,
  `docs/adoption-log.md`, `docs/decision_log.md`, `docs/roadmap.md`

## Success Criteria

1. Decision checkpoint recorded (deferral or human-confirmed decision) in
   adoption log + decision log before implementation lands.
2. Full backend suite green with new tests covering: key lifecycle
   (create/revoke/list; plaintext shown once; hash-only storage asserted);
   auth (valid/revoked/unknown agent keys, global key unchanged, open dev
   mode unchanged with zero rows); write injection and out-of-domain
   rejection (REST + MCP, memories + ingest); scoped-read default
   constraint and explicit-domain selection; detail/update/delete 404-not-
   403 for out-of-scope ids; stats/tags/list_domains restricted to allowed
   unions; untagged memories invisible to agents but visible to owner;
   MCP verifier accept/reject matrix.
3. **The roadmap's verify line, demonstrated live:** two keys bound to
   different domains — memories stored with key A are not visible to key B
   on ANY surface (REST list/detail/search/stats/tags and MCP
   get_memory/search_brain/list_recent/get_stats/list_domains),
   transcribed in the impl submission; owner surface still sees both.
4. README scoping section updated (residual table now shows agent-closed
   surfaces; owner surface documented); key management documented.
5. All work committed intentionally on the active branch per repo workflow.
