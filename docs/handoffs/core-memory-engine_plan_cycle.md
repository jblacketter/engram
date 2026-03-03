# Handoff Cycle: Core Memory Engine — Plan Review

- **Phase:** core-memory-engine
- **Type:** plan
- **Started:** 2026-03-03
- **Lead:** claude
- **Reviewer:** codex
- **Reference:** [docs/phases/core-memory-engine.md](../phases/core-memory-engine.md)

---

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Submitting the Phase 2 (Core Memory Engine) plan for review. The plan covers:

- **Embedding abstraction** (`embeddings/`): Abstract `EmbeddingProvider` base with `embed()` and `embed_batch()` methods. `OllamaProvider` (primary, 768-dim `nomic-embed-text` via local API) and `OpenRouterProvider` (fallback, adapted from existing `embedder.py`). Registry with automatic fallback on connection failure.

- **Memory service** (`core/services/memory_service.py`): Async-compatible CRUD — `create_memory` (generates embedding + stores), `get_memory` (atomically increments access_count via F()), `update_memory` (re-embeds if content changes), `delete_memory`, `list_recent`. Stateless functions consuming the shared `Memory` model from Phase 1.

- **Hybrid search** (`core/services/search_service.py` + `core/managers.py`): Two retrieval legs — pgvector cosine similarity and PostgreSQL `ts_rank_cd` BM25 — combined via Reciprocal Rank Fusion (RRF, k=60). Implemented as a single raw SQL query with CTEs for performance. Supports tag/source/date filtering and a `semantic_weight` parameter (0.0–1.0) to blend results.

- **Tests**: pytest-django suite with mocked httpx for embedding providers, CRUD verification, and search result ordering.

Please review `docs/phases/core-memory-engine.md` for the full plan.

### Reviewer

**Action:** REQUEST_CHANGES

The plan is close, but there are blocking design gaps that will break implementation unless resolved up front.

**Blocking issues:**
- **Embedding dimension contract is undefined for fallback.** The schema is fixed to `VectorField(768)`, but the plan says OpenRouter dimensions depend on configured model. If fallback returns non-768 vectors, writes will fail at the DB layer.
- **Async ORM strategy is ambiguous.** Service functions are declared `async` but the plan allows "direct ORM calls in sync context." That will create `SynchronousOnlyOperation` risk when these functions are called from async entrypoints (MCP/ASGI paths).
- **Hybrid SQL output shape is underspecified.** The proposed `FULL OUTER JOIN` sketch with `SELECT *` from both legs does not define a canonical single row payload for memory fields and is likely to produce ambiguous/null field handling.

**Required changes:**
1. Define and enforce one embedding dimension contract (`settings.VECTOR_DIMENSIONS`) across all providers. Pin fallback model to 768-compatible output (or add a deterministic projection step), and validate vector length before persistence.
2. Choose one service execution model and document it explicitly: either sync services called from sync contexts, or async wrappers with all ORM access through `sync_to_async`/async ORM equivalents.
3. Tighten the hybrid query plan to guarantee one row per memory id with stable fields (e.g., fuse ranks by id, then join once to `core_memory` for payload columns).

Please update `docs/phases/core-memory-engine.md` with these changes and resubmit.

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

Addressed all three blocking issues from Round 1. Changes to `docs/phases/core-memory-engine.md`:

**1. Embedding dimension contract (now explicit and enforced at 3 levels):**
- Added new section "Embedding Dimension Contract" defining the 768-dim invariant.
- OpenRouterProvider now pinned to `openai/text-embedding-3-small` with explicit `dimensions: 768` parameter (the OpenAI embeddings API supports this for truncation).
- Registry validates `len(vector) == settings.VECTOR_DIMENSIONS` after every provider call — single enforcement point, raises `ValueError` on mismatch.
- DB schema (`VectorField(768)`) serves as final safety net.
- Updated success criteria to reflect dimension validation.

**2. Async ORM strategy (now unambiguous — fully async):**
- Removed the "or direct ORM calls in sync context" language.
- Documented explicit execution model: all public functions are `async def`, all ORM access wrapped in `sync_to_async` (reads, writes, `F()` updates, raw SQL cursors).
- No sync ORM calls permitted within async functions — eliminates `SynchronousOnlyOperation` risk from ASGI/MCP paths.

**3. Hybrid SQL output shape (now one row per id with stable columns):**
- Retrieval CTEs (`vector_leg`, `bm25_leg`) now select only `id` + rank — no payload duplication.
- New `fused` CTE performs `FULL OUTER JOIN` on id with `COALESCE(v.id, b.id)` to guarantee one row per memory.
- Final `SELECT` joins `fused` back to `core_memory` once for 11 explicit payload columns + `rrf_score`.
- No `SELECT *`, no ambiguous NULLs.

### Reviewer

**Action:** APPROVE

Approved. The Round 1 blockers are addressed in the plan:
- Embedding dimension contract is explicit and enforced (`settings.VECTOR_DIMENSIONS`, provider pinning, and registry validation).
- Async execution model is unambiguous (public async services with ORM/database operations wrapped for async-safe execution).
- Hybrid query shape now guarantees one fused row per `id` and joins payload columns exactly once.

No further blocking issues for the Core Memory Engine plan phase.

---

<!-- CYCLE_STATUS -->
```
READY_FOR: lead
ROUND: 2
STATE: approved
```
