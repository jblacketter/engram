# Phase: Identity and Onboarding

## Summary

The AgentOS identity pillar: portable identity/context files (git as source
of truth), canonical per-project context exposed as **read-only MCP
resources**, an `onboard_agent` MCP tool that makes any new agent
productive in minutes, and the tagteam→engram integration boundary
(approved cycle summaries become citable evidence). After this phase, a
fresh agent session can learn who the user is, the house rules, and the
current state of any project in one tool call — from any MCP-capable
client.

Trust posture (carried from daily-driver review): identity content is
private and authoritative — it is never invented by tooling, never
silently cloud-embedded, and injected into agent context with the same
envelope discipline as ambient recall.

## Data contracts

**Identity directory.** Configurable via `ENGRAM_IDENTITY_DIR`
(default `~/.engram/identity/`). Plain markdown, user-owned, intended to be
a git repository. Engram writes here only via the explicit `init_identity`
scaffold:

```
identity/
  identity.md          # who the user is, working preferences, house rules
  context/<topic>.md   # standing knowledge (e.g. infrastructure.md)
  projects/<domain>.md # canonical long-form project context per domain
```

**Authoritative content is human-supplied.** `init_identity` creates
commented placeholder templates only (never overwrites); tooling never
invents or populates real identity content. All automated tests AND the
in-cycle live verification run against a fixture identity directory
(`tmp_path` / a dedicated fixture tree) — the real `~/.engram/identity` is
populated by the human after the phase, unless the human explicitly
approves exact content during it.

**Local-only embedding for identity sync.** The embedding registry gains
an `allow_cloud_fallback` parameter (default `True`, preserving current
behavior for all existing callers). Identity sync calls with
`allow_cloud_fallback=False`: on local-provider (Ollama) failure the sync
reports a clear per-file error, the OpenRouter fallback is **not** called,
and any existing memory is left byte-for-byte unchanged (update is
all-or-nothing under a transaction). Cloud embedding of identity content
requires the explicit opt-in setting `ENGRAM_IDENTITY_CLOUD_EMBED=true`.
Tests assert the fallback provider is never invoked by default and that a
failed re-sync cannot corrupt an existing record.

**Canonical provenance key (shared by all synced external artifacts).**
Synced memories carry:

```json
metadata.provenance = {
  "system": "identity_sync" | "tagteam",
  "key":    "<canonical unique string, see below>",
  "sha256": "<content hash>"
}
```

- identity_sync key: `"identity:<relative path>"` (e.g.
  `identity:projects/engram.md`) — same basename in different folders
  yields distinct keys.
- tagteam key: `"tagteam:<resolved repo path>:<relative source file>"` —
  cycles with identical filenames in different repositories cannot
  collide.

Lookup is a **direct ORM query with no recency limit**, scoped by **both**
`provenance.system` AND `provenance.key`:
`Memory.objects.filter(metadata__provenance__system=<system>,
metadata__provenance__key=<key>)` — the key namespace is a convention, not
an integrity boundary, so an organic or other-importer record carrying the
same key must never be touched. The same (system, key) pair scopes orphan
detection, updates, dedup, and prune. Never `list_recent` with its default
limit. Sync semantics: no match → create; match with equal sha256 → skip;
match with different sha256 → update in place (re-embed) inside a
transaction. Tests cover >20 files, repeated sync idempotency,
same-basename files in different folders, and a same-key record under a
*different* system remaining byte-for-byte untouched.

**Duplicate policy (prevention vs repair — distinct contracts).** Ordinary
sync *prevents new duplicates* (the (system, key) lookup + update-in-place
guarantees repeated syncs never create a second row — asserted by tests).
When ordinary sync finds a pre-existing duplicate set (multiple rows for
one (system, key)), it **reports the set and skips ALL mutation for that
file** — no row is updated, nothing is deleted — until the admin runs
`--repair-duplicates`. Repair retains the deterministic canonical row
(most recent `updated_at`; ties broken by newest `created_at`, then id)
and deletes only the extra `identity_sync`-provenance rows; a subsequent
normal sync then performs any needed content update on the canonical row.
This full sequence (duplicates present → sync skips-and-reports → repair
→ sync updates) is part of the duplicate test contract. Ordinary sync
never deletes.

**Stale-file lifecycle.** Default sync is non-destructive: files deleted
from the identity dir are reported as orphaned. An explicit
`--prune` flag (management command **only**) deletes orphaned records,
restricted to `metadata.provenance.system == "identity_sync"` rows — it
can never touch organic memories. **The MCP `sync_identity` tool has no
prune capability in this phase**: a boolean supplied by an autonomous
client is not human confirmation, and the suggestion-first posture applies
while the system is being developed. MCP sync reports orphans; deletion is
a deliberate host/admin action via the management command. Tests cover
report-only (both surfaces) and management-command prune.

**Input-size contract (before any disk read is embedded or served).**
Per-file limit: 256 KiB = **262,144 UTF-8 bytes exactly** — a file of
262,144 bytes is accepted; 262,145 or more is rejected before decoding,
embedding, or serving. `sync_identity` rejects oversized or non-UTF-8
files with a per-file error — the file is skipped, counted in the report,
and any existing memory for it is left unchanged. MCP resources apply the
same bound: an oversized/undecodable file yields a clear error message,
never partial content or an exception. Tests: exactly 262,144 bytes
(accepted), 262,145 bytes (rejected), invalid UTF-8, and
failed-update-preserves-existing.

**Slug and path validation.** Domain slugs: `[a-z0-9-]+` (matches the
established convention); context topic slugs: `[a-z0-9_-]+`. Invalid slugs
are **rejected** at the resource/tool boundary, not normalized.
Containment uses `Path.resolve().is_relative_to(identity_root.resolve())`
— never string-prefix comparison. Tests: sibling-prefix directories
(`/identity-evil` vs `/identity`), symlink escapes, encoded traversal
(`%2e%2e`), absolute-path injection, invalid Unicode and path separators
in slugs.

## Scope

1. **Scaffold + sync.**
   - `python manage.py init_identity` — placeholder templates per the
     human-supplied-content contract; idempotent; never overwrites.
   - `python manage.py sync_identity [--prune] [--repair-duplicates]` —
     the sync contract above; prints created/updated/skipped/orphaned/
     duplicate/rejected counts. Also an MCP tool `sync_identity()`
     (report-only: same sync + orphan/duplicate reporting, **no prune, no
     repair**) sharing the same service code.

2. **Read-only MCP resources** (FastMCP `@mcp.resource`):
   - `engram://identity` — identity.md content
   - `engram://context` — list of available context topics
   - `engram://context/{topic}` — one context file
   - `engram://projects` — list of domains with a projects/ file
   - `engram://projects/{domain}` — one project context file
   Read from disk at request time; validation contract above; missing file
   → clear "not found" message, never an exception.

3. **`onboard_agent` MCP tool.** Args: `domain: str | None = None`,
   `client_name: str | None = None`. Returns one markdown document:
   - identity.md — presented as the **user's trusted instructions**
     (house rules apply to the agent)
   - tag/scoping conventions + status-snapshot contract (embedded
     constant, works without repo access)
   - connection info from two new **non-secret** settings:
     `ENGRAM_PUBLIC_REST_URL` (default `http://localhost:8000/api`) and
     `ENGRAM_PUBLIC_MCP_URL` (default `http://localhost:8080/mcp`),
     overridable for LAN/WSL/nginx deployments; the tool never returns API
     keys or other secrets (asserted by test against a settings object
     with keys configured)
   - if `domain` given: `projects/<domain>.md` + latest
     `type:project-status` snapshot + 3 latest checkpoints — all labeled
     **reference data** with the same no-tool/no-secret caution as ambient
     recall, structural delimiters escaped via the recall sanitizer
     approach
   - explicit next steps; missing pieces degrade gracefully with guidance.
   **Output bounds:** per-section character budgets (identity 6000,
   project file 4000, status 1500, checkpoints 200 each) and a total cap
   (16 KB); fixed sections (conventions, cautions, next steps) are never
   truncated; variable sections shrink multibyte-safe. Adversarial tests:
   delimiter-bearing, instruction-like, oversized, and multibyte content.

4. **Tagteam export ingestion.** Management command
   `ingest_tagteam_cycles --repo <path> [--domain <slug>]`:
   - **Source contract:** consumes tagteam's *rendered JSONL exports*
     (`docs/handoffs/*_rounds.jsonl`). These are export artifacts, not
     tagteam's source of truth (`.tagteam/tagteam.db` is — and is never
     parsed; SQLite internals are not a public API). Documented
     prerequisite (exact command): refresh exports with
     `tagteam cycle render --phase <phase> --type <plan|impl>` from the
     target repo before ingesting;
     failure mode: no/missing export files → the command lists what it
     found and warns exports may be absent or stale, exit non-zero only on
     unreadable `--repo`.
   - For each cycle whose final round is `APPROVE`: store ONE memory
     (phase, cycle type, lead's final submission, approval text), tags
     `["domain:<slug>", "type:cycle-summary"]` (domain defaults to repo
     directory slug, validated), provenance per the canonical-key contract
     — update when the **content hash** changes (not merely round count).
   - Parse line-by-line, `json.loads` per line in try/except, tolerate
     unknown keys; skip malformed lines with a count.
   - Non-approved cycles ignored. Engram never writes tagteam state.
   - Tests: real-format fixtures; approved-only; dedup; hash-change
     update with unchanged round count; same-named cycle files ingested
     from two different repo paths remain distinct memories; malformed
     lines tolerated.

5. **Docs + deployment contract.**
   - `docs/workflows.md`: "Identity & onboarding" section — layout, sync
     semantics (incl. local-only embedding and prune), resource URIs,
     onboarding flow, tagteam export contract.
   - `integrations/claude-code/README.md`: new-machine pointer
     (`init_identity` → human fills content → `sync_identity` →
     `onboard_agent`).
   - Trust note: identity files are user-authored instructions injected
     into agent context — keep the identity repo private; treat
     `projects/<domain>.md` files copied from elsewhere with the same
     caution as any untrusted content.
   - **Container access contract (documented now, wired in Phase 13):**
     the prod compose stack mounts the identity repo read-only
     (`~/.engram/identity:/identity:ro`) with `ENGRAM_IDENTITY_DIR=/identity`;
     `init_identity` remains a deliberate host/admin action. Recorded in
     `docs/setup-docker.md` and added as an explicit Phase 13 roadmap
     deliverable.
   - `.env.example`: `ENGRAM_IDENTITY_DIR`, `ENGRAM_PUBLIC_REST_URL`,
     `ENGRAM_PUBLIC_MCP_URL`, `ENGRAM_IDENTITY_CLOUD_EMBED`.

Out of scope: per-agent keys and closing unscoped reads (Phase 12);
scheduled/automatic sync and the actual compose wiring (Phase 13); any
write to identity files beyond the scaffold; parsing tagteam's SQLite; MCP
resource subscriptions.

## Technical Approach

- `core/services/identity_service.py`: pure functions over (identity_root,
  memory service) — shared by management commands and MCP tools; testable
  against `tmp_path` with mocked local embed.
- Embedding flag: `registry.embed(text, allow_cloud_fallback=True)`
  threaded through `memory_service.create_memory`/`update_memory` as an
  optional parameter defaulting to current behavior; only identity sync
  passes `False` (or honors `ENGRAM_IDENTITY_CLOUD_EMBED`).
- Provenance lookups: `Memory.objects.filter(
  metadata__provenance__system=system, metadata__provenance__key=k)` —
  always both fields, matching the Data Contract — via Django JSONField
  nested lookups (Postgres `@>`-backed); update inside
  `transaction.atomic()` (sync_to_async wrapped).
- Resources in `mcp_server/resources.py`; onboard tool in
  `mcp_server/tools/onboard.py`; registration via existing import chain;
  tests use `.fn` + `mcp.get_resources()`/`get_resource_templates()`.
- Tagteam fixtures: copies of this repo's real
  `docs/handoffs/*_rounds.jsonl` committed under `tests/fixtures/`.
- Live verification: fixture identity dir for identity mechanics; this
  repo's real exports for tagteam ingestion (they exist and contain four
  approved cycles).

## Files

- `core/services/identity_service.py` (new)
- `embeddings/registry.py` (allow_cloud_fallback), `core/services/memory_service.py`
- `core/management/commands/init_identity.py`, `sync_identity.py`,
  `ingest_tagteam_cycles.py` (new)
- `mcp_server/resources.py`, `mcp_server/tools/onboard.py` (new);
  `mcp_server/server.py` registration
- `engram/settings/base.py` (+ `.env.example`): ENGRAM_IDENTITY_DIR,
  ENGRAM_PUBLIC_REST_URL, ENGRAM_PUBLIC_MCP_URL, ENGRAM_IDENTITY_CLOUD_EMBED
- `tests/test_identity_service.py`, `tests/test_mcp_resources.py`,
  `tests/test_onboard_tool.py`, `tests/test_tagteam_ingest.py`,
  `tests/fixtures/` (new)
- `docs/workflows.md`, `docs/setup-docker.md`,
  `integrations/claude-code/README.md`, `docs/roadmap.md`

## Success Criteria

1. Full backend suite green with new tests covering every contract above:
   scaffold idempotency; sync create/update/skip/orphan paths; duplicate
   **prevention** (repeated syncs and >20 files never create a second row
   per (system, key)) tested separately from duplicate **repair**
   (`--repair-duplicates` retains the canonical row and deletes only extra
   identity_sync rows; ordinary sync only reports); (system, key) scoping
   (a same-key record under a different provenance system remains
   untouched by update, orphan detection, dedup, repair, and prune);
   local-only embedding (fallback provider never called by default;
   failed re-sync leaves the record unchanged); orphan report-only on
   both surfaces vs management-command-only prune, restricted to
   identity_sync provenance (MCP tool has no prune/repair arguments);
   input-size contract (256 KB boundary, oversized and invalid-UTF-8
   rejected per file with existing memories preserved, resources bounded
   identically); slug rejection
   and containment (sibling-prefix, symlink, encoded traversal, absolute
   path, invalid Unicode); resource reads (present/missing/list);
   onboard_agent with/without domain, graceful degradation, no-secrets
   assertion, output bounds + adversarial content; tagteam ingestion
   (approved-only, canonical-key dedup across two repo paths,
   hash-change update at unchanged round count, malformed-line tolerance).
2. Live (fixture identity dir): `init_identity` scaffolds; fixture
   identity.md + projects/engram.md synced; re-sync all-skip; edit →
   update without duplicate; delete → orphan report; `--prune` removes it.
   The real `~/.engram/identity` is left for the human to populate
   (documented next step), per the human-supplied-content contract.
3. Live from a fresh MCP client session: resources listed and readable;
   `onboard_agent(domain="engram")` returns identity (fixture) +
   conventions + project context + latest status + checkpoints in one
   bounded call, transcribed in the submission.
4. Live: `ingest_tagteam_cycles --repo .` ingests this repo's four
   approved cycles; re-run all-skip; scoped retrieval surfaces them as
   citable evidence.
5. Docs updated (workflows, setup-docker mount contract, README pointer,
   .env.example); Phase 13 roadmap deliverable added for the compose
   wiring; boundary statement present.
6. All work committed intentionally on the active branch per repo workflow.
