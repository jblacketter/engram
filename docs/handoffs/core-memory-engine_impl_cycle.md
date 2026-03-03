# Handoff Cycle: Core Memory Engine — Implementation Review

- **Phase:** core-memory-engine
- **Type:** impl
- **Started:** 2026-03-03
- **Lead:** claude
- **Reviewer:** codex
- **Reference:** [docs/phases/core-memory-engine.md](../phases/core-memory-engine.md)

---

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Implementation of Phase 2 (Core Memory Engine) complete. All files created per the approved plan.

**Embedding providers (`embeddings/`):**
- `base.py` — `EmbeddingProvider` ABC with `embed()` and `embed_batch()` abstract methods
- `ollama_provider.py` — Calls `POST {OLLAMA_BASE_URL}/api/embed` with `nomic-embed-text`, uses `httpx.AsyncClient`, returns 768-dim vectors
- `openrouter_provider.py` — Calls OpenRouter embeddings API with `dimensions: 768` parameter to enforce dimension contract. Sorts batch results by index.
- `registry.py` — `embed()` and `embed_batch()` functions with primary→fallback on `ConnectError`/`ConnectTimeout`. Validates `len(vector) == settings.VECTOR_DIMENSIONS` after every call. Single enforcement point.
- `__init__.py` — Re-exports `embed` and `embed_batch` from registry

**Memory service (`core/services/memory_service.py`):**
- Fully async execution model — all ORM access via `sync_to_async`
- `create_memory()` — generates embedding via registry, creates `Memory` row
- `get_memory()` — atomically increments `access_count` and `last_accessed` via `F()` expression wrapped in `sync_to_async`
- `update_memory()` — re-embeds if `content` field changes, uses `setattr` loop + `save()`
- `delete_memory()` — filter/delete pattern, raises `DoesNotExist` if count==0
- `list_recent()` — ordered by `-created_at`, optional source filter

**Hybrid search (`core/managers.py` + `core/services/search_service.py`):**
- `managers.py` — Raw SQL with 3 CTEs: `vector_leg` (id + v_rank only), `bm25_leg` (id + t_rank only), `fused` (FULL OUTER JOIN with COALESCE for one row per id, RRF score). Final SELECT joins to `core_memory` for 11 explicit payload columns + `rrf_score`. Dynamic filter clauses for tags (jsonb `@>`), source, after/before dates. Pool size = limit × 3.
- `search_service.py` — Async wrapper: embeds query, serializes tags for jsonb, calls `build_hybrid_query` via `sync_to_async`

**Test suite (`tests/`):**
- `test_embeddings.py` — 10 tests: Ollama embed/batch, OpenRouter embed/batch (verifies `dimensions` param sent), connection error, registry primary/fallback/no-fallback, dimension validation, batch fallback
- `test_memory_service.py` — 10 tests: create with defaults, create with tags/metadata, get increments access_count, get nonexistent raises, update re-embeds, update non-content skips embed, update tags, delete, delete nonexistent raises, list_recent ordered/filtered/limited
- `test_search_service.py` — 8 tests: basic search, empty DB, limit, source filter, tag filter, date filter, result schema, semantic_weight extremes

**Other changes:**
- `pyproject.toml` — Added `pytest-asyncio` to dev deps, added `embeddings*` to setuptools packages, added `asyncio_mode = "auto"` to pytest config

### Reviewer

**Action:** APPROVE

Approved. The implementation aligns with the approved phase plan and resolves the prior plan-phase constraints:
- Embedding dimension contract is enforced across providers and registry validation.
- Memory service is consistently async-facing with synchronous ORM/database calls wrapped for async-safe execution.
- Hybrid search query shape is stable (rank legs by id, fused scoring, single payload join).
- Coverage includes embedding behavior, CRUD behavior, and hybrid search/filter paths.

No blocking issues found for Core Memory Engine implementation.

---

<!-- CYCLE_STATUS -->
```
READY_FOR: lead
ROUND: 1
STATE: approved
```
