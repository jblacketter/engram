# Handoff Cycle: MCP Server — Plan Review

- **Phase:** mcp-server
- **Type:** plan
- **Started:** 2026-03-03
- **Lead:** claude
- **Reviewer:** codex
- **Reference:** [docs/phases/mcp-server.md](../phases/mcp-server.md)

---

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Submitting the Phase 3 (MCP Server) plan for review. The plan covers:

- **FastMCP server** (`mcp_server/server.py`): Standalone process (not a Django app). Bootstraps Django via `django.setup()` at module level, then creates `FastMCP("open-brain")` instance with Streamable HTTP transport on `0.0.0.0:8080` at path `/mcp`.

- **Authentication** (`mcp_server/auth.py`): Uses FastMCP's built-in `DebugTokenVerifier` with a custom `verify_api_key()` function. Compares bearer token against `settings.MCP_API_KEY` (new env var). Open access when key is empty (dev mode).

- **8 MCP tools** in `mcp_server/tools/`:
  - `memory.py`: `store_memory` (default source="mcp"), `get_memory`, `update_memory`, `delete_memory`
  - `search.py`: `search_brain` (hybrid search with semantic_weight), `find_related` (pure semantic via target memory's content), `list_recent_memories`
  - `stats.py`: `get_stats` (total count, source breakdown, tag frequency, date range)

- **Tool registration pattern**: `mcp` instance in `server.py`, imported by tool modules for `@mcp.tool()` decorators, tool modules imported in `server.py` after instance creation.

- **Error handling**: Service exceptions caught and returned as readable text in tool results (not raised).

- **Client configs**: Template configs for Claude Desktop, Claude Code, and Cursor.

- **Tests**: `test_mcp_tools.py` with mocked service layer for all 8 tools + error cases.

Please review `docs/phases/mcp-server.md` for the full plan.

### Reviewer

**Action:** REQUEST_CHANGES

The plan is close, but there is a blocking auth behavior mismatch that will fail the stated success criteria.

**Blocking issue:**
- **Dev-mode open access is incompatible with the chosen auth primitive.** The plan uses `DebugTokenVerifier(validate=verify_api_key)` and states that when `MCP_API_KEY` is empty, access is open. In FastMCP, `DebugTokenVerifier` rejects empty/missing bearer tokens before `validate` runs, so requests without `Authorization` will still be denied. This conflicts with Success Criterion #8.

**Required changes:**
1. Make auth wiring conditional in `server.py`:
   - If `MCP_API_KEY` is set: configure `DebugTokenVerifier(validate=verify_api_key)`.
   - If `MCP_API_KEY` is empty: disable auth (`auth=None`) so unauthenticated local dev requests are accepted.
2. Update the authentication section to document this behavior explicitly (dev mode truly no-header required; secured mode requires `Authorization: Bearer <api-key>`).
3. Add one explicit test case to the plan for each mode:
   - secure mode rejects missing/invalid token;
   - dev mode accepts request without auth header.

Please revise `docs/phases/mcp-server.md` and resubmit.

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

Addressed the blocking auth issue. Changes to `docs/phases/mcp-server.md`:

**1. Auth wiring is now conditional via `build_auth()` factory:**
- New `build_auth() -> DebugTokenVerifier | None` function in `mcp_server/auth.py`
- When `MCP_API_KEY` is set: returns `DebugTokenVerifier(validate=verify_api_key)` — bearer token required
- When `MCP_API_KEY` is empty (default): returns `None` — no auth middleware applied at all, no header required
- `server.py` calls `mcp = FastMCP("open-brain", auth=build_auth())`

**2. Authentication section explicitly documents both modes:**
- **Dev mode**: `auth=None`, no `Authorization` header needed, requests accepted without any auth
- **Secured mode**: `DebugTokenVerifier` active, `Authorization: Bearer <token>` required, missing/invalid tokens rejected before tools run

**3. Added explicit auth test cases:**
- New `tests/test_mcp_auth.py` with two test categories:
  - Secured mode: `build_auth()` returns `DebugTokenVerifier` when key set; verifier rejects invalid tokens, accepts valid
  - Dev mode: `build_auth()` returns `None` when key empty

### Reviewer

**Action:** APPROVE

Approved. The blocking auth mismatch from Round 1 is resolved:
- Auth wiring is now conditional (`build_auth()`): secured mode uses `DebugTokenVerifier`, dev mode uses `auth=None`.
- The plan now explicitly documents real behavior for both modes, including no-header dev access and bearer-token enforcement in secured mode.
- Auth-specific test coverage has been added to the phase plan (`tests/test_mcp_auth.py`).

No further blocking issues for the MCP Server plan phase.

---

<!-- CYCLE_STATUS -->
```
READY_FOR: lead
ROUND: 2
STATE: approved
```
