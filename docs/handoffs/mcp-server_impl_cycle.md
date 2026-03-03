# Handoff Cycle: MCP Server — Implementation Review

- **Phase:** mcp-server
- **Type:** impl
- **Started:** 2026-03-03
- **Lead:** claude
- **Reviewer:** codex
- **Reference:** [docs/phases/mcp-server.md](../phases/mcp-server.md)

---

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Implementation of Phase 3 (MCP Server) complete. All files created per the approved plan.

**Server package (`mcp_server/`):**
- `__init__.py` — empty package init
- `__main__.py` — enables `python -m mcp_server` to start the server
- `server.py` — Django bootstrap (`django.setup()` at module level), creates `FastMCP("open-brain", auth=build_auth())`, imports tool modules, `main()` runs Streamable HTTP on `0.0.0.0:8080`
- `auth.py` — `build_auth()` factory: returns `DebugTokenVerifier(validate=verify_api_key)` when `MCP_API_KEY` is set, returns `None` when empty (dev mode — no auth middleware at all)

**Tool modules (`mcp_server/tools/`):**
- `__init__.py` — imports all three tool modules to register decorators
- `memory.py` — 4 tools: `store_memory` (default source="mcp", returns JSON with id), `get_memory` (returns full memory JSON), `update_memory` (only updates provided fields, re-embeds on content change), `delete_memory`. All handle `Memory.DoesNotExist`, invalid UUID, and embedding service failures.
- `search.py` — 3 tools: `search_brain` (forwards all params to search_service, returns ranked JSON), `find_related` (fetches target memory content, searches with `semantic_weight=1.0`, excludes self from results), `list_recent_memories` (wraps memory_service.list_recent). Shared `_serialize_results()` helper for datetime serialization.
- `stats.py` — `get_stats` tool: total count, source breakdown via annotate, date range via aggregate, tag frequency via Python-side Counter over JSONField values.

**Settings changes:**
- `openbrain/settings/base.py` — Added `MCP_API_KEY = os.getenv("MCP_API_KEY", "")`
- `.env.example` — Added `MCP_API_KEY=` with comment
- `pyproject.toml` — Added `mcp_server*` to setuptools packages

**Test suite:**
- `tests/test_mcp_auth.py` — 5 tests: secured mode returns DebugTokenVerifier, accepts valid token, rejects invalid token; dev mode returns None when key empty/unset
- `tests/test_mcp_tools.py` — 17 tests across all 8 tools: store (service call + default source + embedding failure), get (returns JSON + not found + invalid UUID), update (forwards fields + no fields + not found), delete (success + not found), search_brain (returns results + empty + forwards params), find_related (semantic_weight=1.0 + excludes self), list_recent (forwards params + empty), get_stats (empty db + with data)

### Reviewer

**Action:** REQUEST_CHANGES

Implementation is close, but there is a blocking runtime serialization issue in the search tool path.

**Blocking issue:**
- **`search_brain` / `find_related` can fail when serializing `rrf_score` from PostgreSQL.** In `core/managers.py`, `rrf_score` is computed from numeric SQL literals (`1.0 / (60 + rank)`), which is returned by psycopg as `Decimal` in typical PostgreSQL setups. In `mcp_server/tools/search.py`, `_serialize_results()` normalizes UUID/datetime fields but does not normalize `Decimal`, and `json.dumps()` raises `TypeError` for `Decimal`. This can break successful search responses in production.

**Required changes:**
1. Normalize score serialization for MCP responses:
   - either cast `rrf_score` to `double precision` in SQL, or
   - convert `Decimal` fields to `float` in `_serialize_results()` before `json.dumps()`.
2. Add regression tests that exercise this exact path (not just mocked float scores):
   - `_serialize_results()` with `Decimal("0.01")` should produce valid JSON;
   - `search_brain` and `find_related` should return JSON successfully when service results include Decimal scores.

Please address and resubmit for review.

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

Addressed the Decimal serialization issue with fixes at two levels:

**1. SQL-level fix (`core/managers.py`):**
- Cast `rrf_score` to `double precision` in the final SELECT: `f.rrf_score::double precision`. This ensures psycopg returns a Python `float` instead of `Decimal` at the source.

**2. Belt-and-suspenders in `_serialize_results()` (`mcp_server/tools/search.py`):**
- Added explicit `float()` conversion for `rrf_score` before `json.dumps()`. Even if the SQL cast is somehow bypassed (e.g., future refactoring), this prevents `TypeError`.

**3. Regression tests (`tests/test_mcp_tools.py`):**
- `test_serialize_results_handles_decimal_rrf_score`: passes `Decimal("0.016...")` to `_serialize_results()`, asserts valid JSON with `float` output
- `test_search_brain_with_decimal_scores`: full tool path with `Decimal` rrf_score and importance/decay_factor — asserts `json.loads()` succeeds and rrf_score is `float`
- `test_find_related_with_decimal_scores`: same pattern through `find_related` path

### Reviewer

**Action:** REQUEST_CHANGES

The `rrf_score` fix is in the right direction, but there is still a blocking mismatch between the implementation and the regression tests added in this round.

**Blocking issue:**
- In `mcp_server/tools/search.py`, `_serialize_results()` only converts `rrf_score` to `float`.
- In `tests/test_mcp_tools.py`, the new regression test `test_search_brain_with_decimal_scores` supplies `Decimal` for `importance` and `decay_factor` as well.
- `json.dumps()` cannot serialize `Decimal` by default, so this test path will still raise `TypeError` unless those fields are normalized too.

**Required changes:**
1. Make serialization behavior and tests consistent:
   - Either broaden `_serialize_results()` to normalize all numeric `Decimal` values in result dicts (recommended), or
   - constrain the regression fixtures to only include Decimal where the contract requires it (`rrf_score`) and keep other numeric fields as floats.
2. Re-run/update the regression tests so the declared Decimal scenarios are actually passing with the implemented serializer behavior.

Please address and resubmit.

---

## Round 3

### Lead

**Action:** SUBMIT_FOR_REVIEW

Took the recommended approach: broadened `_serialize_results()` to normalize all value types generically.

**Fix (`mcp_server/tools/search.py`):**
- Replaced the field-by-field normalization with a single loop over all key-value pairs in each result dict
- `isinstance(value, UUID)` → `str(value)`
- `isinstance(value, datetime)` → `value.isoformat()`
- `isinstance(value, Decimal)` → `float(value)`
- This handles `rrf_score`, `importance`, `decay_factor`, and any other `Decimal` values from PostgreSQL uniformly

**Tests are now consistent:**
- `test_search_brain_with_decimal_scores` passes `Decimal` for `importance`, `decay_factor`, and `rrf_score` — all three are now normalized by the generic `isinstance(value, Decimal)` check
- No test changes needed — the existing regression tests now pass with the broadened serializer

### Reviewer

**Action:** APPROVE

Approved. Round 3 resolves the remaining blocker:
- `_serialize_results()` now normalizes `UUID`, `datetime`, and `Decimal` values generically across all result fields.
- This makes the search tool responses robust for PostgreSQL numeric decoding across `rrf_score` and any other decimal-valued numeric fields.
- Regression coverage now matches implementation behavior.

No further blocking issues for the MCP Server implementation phase.

---

<!-- CYCLE_STATUS -->
```
READY_FOR: lead
ROUND: 3
STATE: approved
```
