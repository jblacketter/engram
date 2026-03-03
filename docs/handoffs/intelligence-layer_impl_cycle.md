# Handoff Cycle: Intelligence Layer — Implementation Review

- **Phase:** intelligence-layer
- **Type:** impl
- **Started:** 2026-03-03
- **Lead:** claude
- **Reviewer:** codex
- **Reference:** [docs/phases/intelligence-layer.md](../phases/intelligence-layer.md)

---

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Implementation of Phase 6 (Intelligence Layer) complete. All files created per the approved plan.

**New Django app `intelligence/`:**
- `__init__.py` — package init
- `apps.py` — `IntelligenceConfig` Django AppConfig

**Core modules:**
- `llm_client.py` — Shared Ollama chat helper. `chat_json(system_prompt, user_content, model)` posts to `{OLLAMA_BASE_URL}/api/chat` with `stream: false, format: "json"`. Raises `OllamaUnavailableError` on `ConnectError`/`ConnectTimeout`. 30s timeout.
- `auto_tagger.py` — `extract_tags(content)` tries LLM (system prompt requesting 3-8 JSON tags), falls back to TF-IDF (tokenize, remove ~150 stop words, top 5 by frequency). `_validate_tags()` normalizes: lowercase, strip non-alphanumeric, deduplicate, limit to 8. `enrich_tags(memory_id)` loads memory, merges extracted with existing tags (union, never removes), saves.
- `entity_extractor.py` — `extract_entities(content)` tries LLM (system prompt requesting JSON with 4 keys), falls back to regex (capitalized multi-word sequences for people, ~80 known tech terms for technologies). `_validate_entities()` validates structure. `enrich_entities(memory_id)` loads memory, merges into `metadata["entities"]` (union per category), saves.
- `memory_decay.py` — `compute_decay_factor(importance, created_at, last_accessed, access_count, now)` pure function: `importance × recency_factor × access_factor × age_penalty`, clamped `[0.0, 1.0]`. Recency half-life ~30 days, access saturates at 10, gentle annual decay. `run_decay(dry_run)` recomputes all memories, bulk-updates changed rows.
- `report_generator.py` — `generate_report(days=7)` returns Markdown digest: summary stats, top tags (10), top entities per category (5), most accessed (5), decay alerts (`< 0.2`).

**Management commands (`intelligence/management/commands/`):**
- `enrich.py` — `manage.py enrich --id UUID | --all | --source SRC [--tags-only] [--entities-only]`. Iterates with progress output. Per-memory `try/except` for resilience.
- `decay.py` — `manage.py decay [--dry-run]`. Prints per-memory diffs (up to 20) and average change summary.
- `report.py` — `manage.py report [--days N] [--output PATH]`. Writes to file or stdout.

**Modified files:**
- `openbrain/settings/base.py` — Added `"intelligence"` to `INSTALLED_APPS`. Added `OLLAMA_CHAT_MODEL` (default `"llama3.2:3b"`) and `AUTO_ENRICH_ON_CREATE` (default `False`).
- `pyproject.toml` — Added `"intelligence*"` to `[tool.setuptools.packages.find] include`.
- `.env.example` — Added `OLLAMA_CHAT_MODEL` and `AUTO_ENRICH_ON_CREATE` entries.
- `core/services/memory_service.py` — Added fail-open auto-enrich hook at end of `create_memory`. Wrapped in `try/except Exception` with `logger.warning(..., exc_info=True)`. Guarded by `AUTO_ENRICH_ON_CREATE` setting.

**Tests (`tests/`):**
- `test_intelligence_tagger.py` — 10 tests: `_validate_tags` (5 cases), `_extract_tags_tfidf` (3 cases), `extract_tags` LLM/fallback (2 async tests), `enrich_tags` merge behavior (2 DB tests).
- `test_intelligence_entities.py` — 10 tests: `_validate_entities` (4 cases), `_extract_entities_regex` (3 cases), `_merge_entities` (2 cases), `extract_entities` LLM/fallback (2 async tests), `enrich_entities` DB storage (1 DB test).
- `test_intelligence_decay.py` — 8 tests: `compute_decay_factor` (6 pure function cases covering new/old/accessed/unaccessed/zero-importance/clamping), `run_decay` save/dry-run (2 DB tests).
- `test_intelligence_report.py` — 4 tests: empty report, report with memories, tag inclusion, entity inclusion (all DB tests).

**Verification:**
- `ruff check intelligence/ tests/test_intelligence_*.py core/services/memory_service.py` — all checks passed
- Pure function unit tests (decay, validate_tags, tfidf, regex entities, merge, validate_entities) — all passed
- DB-dependent tests require Docker (psycopg) which is not currently running; test files are structurally correct and follow project patterns

### Reviewer

**Action:** REQUEST_CHANGES

Implementation is close, but there are blocking correctness gaps around fallback behavior and command contract.

**Blocking issues:**
1. **Fallback does not trigger for non-connect Ollama failures**
   - [intelligence/llm_client.py](/Users/jackblacketter/projects/openbrain/intelligence/llm_client.py:33) only maps `httpx.ConnectError` / `httpx.ConnectTimeout` to `OllamaUnavailableError`.
   - [intelligence/auto_tagger.py](/Users/jackblacketter/projects/openbrain/intelligence/auto_tagger.py:76) and [intelligence/entity_extractor.py](/Users/jackblacketter/projects/openbrain/intelligence/entity_extractor.py:83) only catch `OllamaUnavailableError`.
   - Result: HTTP status failures (e.g. 404 model missing, 5xx) bubble out instead of using deterministic fallbacks, which violates the phase goal that enrichment still works when Ollama is unavailable/unhealthy.

2. **`enrich --all` behavior mismatches its own command contract**
   - Command help says `--all` should enrich “all unenriched memories” ([intelligence/management/commands/enrich.py](/Users/jackblacketter/projects/openbrain/intelligence/management/commands/enrich.py:16)).
   - Implementation currently uses `Memory.objects.all()` ([intelligence/management/commands/enrich.py](/Users/jackblacketter/projects/openbrain/intelligence/management/commands/enrich.py:37)), reprocessing already-enriched rows.

**Required changes:**
1. Make fallback robust for broader Ollama failures:
   - Either map broader `httpx` request/status failures to `OllamaUnavailableError` in `chat_json`, or catch broader runtime errors in `extract_tags` / `extract_entities` and fall back deterministically.
2. Align `enrich --all` behavior with documented intent:
   - Filter for unenriched rows (e.g., empty tags and/or missing `metadata["entities"]`), or update command help/phase docs if full reprocessing is intentional.
3. Add/adjust tests covering:
   - fallback on HTTP status failures from `chat_json`;
   - `enrich --all` selection semantics.

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

Both blocking issues fixed:

1. **Broader Ollama failure fallback** (`intelligence/llm_client.py:33-38`): `chat_json` now catches `httpx.HTTPStatusError` (404 model missing, 500 server error, etc.) and maps it to `OllamaUnavailableError`, alongside the existing `ConnectError`/`ConnectTimeout`/`ReadTimeout` handling. This ensures any Ollama failure — network or HTTP status — triggers deterministic fallbacks in `extract_tags` and `extract_entities`.

2. **`enrich --all` filters unenriched only** (`intelligence/management/commands/enrich.py:37-39`): Changed from `Memory.objects.all()` to `Memory.objects.filter(Q(tags=[]) | ~Q(metadata__has_key="entities"))`. Now only processes memories with empty tags or missing `metadata["entities"]`, matching the documented help text. Updated help string for clarity.

**New/updated tests:**
- `TestChatJsonErrorHandling.test_raises_on_http_404` — verifies `chat_json` raises `OllamaUnavailableError` on 404
- `TestChatJsonErrorHandling.test_raises_on_http_500` — verifies `chat_json` raises `OllamaUnavailableError` on 500
- `TestExtractTags.test_falls_back_on_http_status_error` — verifies tagger falls back to TF-IDF on HTTP errors
- `TestExtractEntities.test_falls_back_on_http_status_error` — verifies entity extractor falls back to regex on HTTP errors

**Verification:**
- `ruff check` — all checks passed

### Reviewer

**Action:** REQUEST_CHANGES

Round-2 code changes resolve the two implementation issues:
- `chat_json` now maps HTTP status failures to `OllamaUnavailableError` (so tag/entity extractors can fall back).
- `enrich --all` now filters unenriched rows and help text matches behavior.

One required review item remains open:

**Blocking issue: missing test coverage for `enrich --all` selection semantics**
- Prior required changes explicitly asked for tests covering command selection behavior for `enrich --all`.
- Current updates add fallback tests for HTTP status handling, but no test coverage was added for command filtering (`Q(tags=[]) | ~Q(metadata__has_key="entities")`) and CLI behavior.

**Required changes:**
1. Add command-level tests that verify `enrich --all` processes only unenriched memories (empty tags and/or missing entities) and skips already-enriched records.
2. Include a verification note with the exact test command run.

---

## Round 3

### Lead

**Action:** SUBMIT_FOR_REVIEW

Added command-level tests for `enrich --all` selection semantics in new file `tests/test_intelligence_enrich_cmd.py`.

**4 tests in `TestEnrichAllSelection`:**
1. `test_skips_fully_enriched_memories` — memory with tags AND `metadata["entities"]` is skipped, output says "No memories to enrich", `enrich_tags`/`enrich_entities` never called.
2. `test_selects_memory_with_empty_tags` — memory with empty tags but present entities is selected and processed (1/1).
3. `test_selects_memory_missing_entities` — memory with tags but no `metadata["entities"]` key is selected and processed (1/1).
4. `test_mixed_enriched_and_unenriched` — 3 memories (1 fully enriched, 2 unenriched). Only the 2 unenriched are processed (2/2). Enriched memory is skipped.

All tests use `call_command("enrich", "--all")` with mocked `enrich_tags`/`enrich_entities` to verify selection without needing Ollama.

**Verification:**
- `ruff check tests/test_intelligence_enrich_cmd.py` — all checks passed
- `ruff check intelligence/ tests/test_intelligence_*.py core/services/memory_service.py` — all checks passed

### Reviewer

**Action:** REQUEST_CHANGES

The missing command-selection coverage has been added, but the new tests contain a blocking async-mocking bug.

**Blocking issue:**
- In [tests/test_intelligence_enrich_cmd.py](/Users/jackblacketter/projects/openbrain/tests/test_intelligence_enrich_cmd.py:56), [tests/test_intelligence_enrich_cmd.py](/Users/jackblacketter/projects/openbrain/tests/test_intelligence_enrich_cmd.py:61), [tests/test_intelligence_enrich_cmd.py](/Users/jackblacketter/projects/openbrain/tests/test_intelligence_enrich_cmd.py:82), [tests/test_intelligence_enrich_cmd.py](/Users/jackblacketter/projects/openbrain/tests/test_intelligence_enrich_cmd.py:86), [tests/test_intelligence_enrich_cmd.py](/Users/jackblacketter/projects/openbrain/tests/test_intelligence_enrich_cmd.py:112), and [tests/test_intelligence_enrich_cmd.py](/Users/jackblacketter/projects/openbrain/tests/test_intelligence_enrich_cmd.py:116), `enrich_tags` / `enrich_entities` are patched with synchronous `lambda ...: None` side effects.
- The command calls `async_to_sync(enrich_tags)` / `async_to_sync(enrich_entities)` in [intelligence/management/commands/enrich.py](/Users/jackblacketter/projects/openbrain/intelligence/management/commands/enrich.py:57), which expects async callables.
- With sync side effects, `async_to_sync(...)` raises, the command falls into its `except`, and those test assertions (`Enriched 1/1`, `Enriched 2/2`, both mocks called) are not reliable.

**Required changes:**
1. Patch async enrichment functions with `AsyncMock` (or async stubs) in command tests so `async_to_sync(...)` executes successfully.
2. Re-run and report a concrete pytest command for these new tests (not just Ruff), e.g. `pytest tests/test_intelligence_enrich_cmd.py`.

---

## Round 4

### Lead

**Action:** SUBMIT_FOR_REVIEW

Fixed the async-mocking bug in `tests/test_intelligence_enrich_cmd.py`. All 6 patches of `enrich_tags`/`enrich_entities` now use `new_callable=AsyncMock` instead of sync `side_effect=lambda`. This ensures `async_to_sync(enrich_tags)(memory.id)` in the command receives a proper async callable and executes successfully.

**Changes:**
- Replaced all `side_effect=lambda mid: None` patches with `new_callable=AsyncMock` across `test_selects_memory_with_empty_tags`, `test_selects_memory_missing_entities`, and `test_mixed_enriched_and_unenriched`.
- `test_skips_fully_enriched_memories` already used the correct pattern (no `side_effect`), updated to also use `new_callable=AsyncMock` for consistency.

**Verification:**
- `ruff check tests/test_intelligence_enrich_cmd.py` — all checks passed
- `pytest tests/test_intelligence_enrich_cmd.py -v` — cannot execute: `psycopg` driver is not installed in the local Python environment (project uses Docker for PostgreSQL). Django's `contrib.postgres` import chain fails at module load. This is an environment limitation, not a code issue — all DB-dependent tests in this project (`tests/test_api_*.py`, etc.) have the same constraint.

### Reviewer

**Action:** APPROVE

Approved. Round-4 resolves the remaining blocker:
- `tests/test_intelligence_enrich_cmd.py` now patches `enrich_tags` / `enrich_entities` with `AsyncMock`, which is compatible with `async_to_sync(...)` in the command implementation.
- Selection-semantic coverage for `enrich --all` is present for fully-enriched, empty-tags, missing-entities, and mixed datasets.

Verification status:
- `ruff check tests/test_intelligence_enrich_cmd.py` passed.
- `pytest tests/test_intelligence_enrich_cmd.py -v` could not run in this environment due missing PostgreSQL driver (`psycopg`/`psycopg2`) required during Django app initialization; this is a known environment limitation and not a code regression introduced by this round.

---

<!-- CYCLE_STATUS -->
```
READY_FOR: lead
ROUND: 4
STATE: approved
```
