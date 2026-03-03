# Phase 2: Core Memory Engine

## Summary

Embedding provider abstraction (Ollama primary, OpenRouter fallback), memory CRUD service layer, and hybrid search combining pgvector cosine similarity with PostgreSQL BM25 via Reciprocal Rank Fusion (RRF). This phase builds the shared service layer that both the MCP server and REST API will consume.

## Scope

- Pluggable embedding provider abstraction with async interface
- Ollama provider (primary, 768-dim `nomic-embed-text`)
- OpenRouter provider (fallback, using existing `embedder.py` as reference)
- Provider registry with automatic fallback
- Memory CRUD service (`create`, `get`, `update`, `delete`, `list_recent`)
- Hybrid search service: vector similarity + BM25 full-text, merged via RRF
- Filtering by tags, source, and date range
- Access tracking (increment `access_count`, update `last_accessed` on reads)
- Test suite for embedding providers, memory service, and search service

## Technical Approach

### Embedding Provider Abstraction (`embeddings/`)

Abstract base class defining the async embedding interface. Two concrete implementations.

```python
# embeddings/base.py
class EmbeddingProvider(ABC):
    async def embed(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
```

**OllamaProvider** (`embeddings/ollama_provider.py`):
- Calls `POST {OLLAMA_BASE_URL}/api/embed` with model `nomic-embed-text`
- Uses `httpx.AsyncClient` with connection pooling
- Returns 768-dim vectors
- Raises on connection failure (triggers fallback)

**OpenRouterProvider** (`embeddings/openrouter_provider.py`):
- Calls `POST https://openrouter.ai/api/v1/embeddings` (adapted from existing `embedder.py`)
- Uses `httpx.AsyncClient` with API key auth
- **Pinned to `openai/text-embedding-3-small` with explicit `dimensions: 768` parameter** to guarantee output matches `settings.VECTOR_DIMENSIONS`. The OpenAI embeddings API (proxied by OpenRouter) supports the `dimensions` parameter for truncation to any size ≤ native dim.

**Registry** (`embeddings/registry.py`):
- `get_provider() -> EmbeddingProvider` — returns OllamaProvider
- `get_fallback_provider() -> EmbeddingProvider | None` — returns OpenRouterProvider if API key configured
- `embed(text) -> list[float]` — tries primary, falls back to secondary on connection error
- **Dimension validation:** after receiving a vector from any provider, asserts `len(vector) == settings.VECTOR_DIMENSIONS` before returning. Raises `ValueError` on mismatch. This is the single enforcement point — callers never need to check dimensions.

### Embedding Dimension Contract

All providers MUST return vectors of exactly `settings.VECTOR_DIMENSIONS` (768) dimensions. This is enforced at three levels:

1. **Provider config:** Ollama's `nomic-embed-text` natively produces 768-dim. OpenRouter is called with `dimensions: 768` to truncate output.
2. **Registry validation:** `registry.embed()` asserts `len(vector) == settings.VECTOR_DIMENSIONS` before returning. Raises `ValueError` on mismatch — this is the single enforcement point.
3. **Database schema:** `VectorField(768)` in the `Memory` model rejects mismatched vectors at the DB layer as a final safety net.

If a new provider is added, it must either natively produce 768-dim vectors or use provider-specific truncation/projection to match.

### Memory Service (`core/services/memory_service.py`)

Stateless async service functions operating on the `Memory` model. **Execution model: fully async.** All ORM access uses `sync_to_async` wrappers (Django's async ORM support is incomplete for operations like `F()` updates and `bulk_create`). This ensures safe use from ASGI/MCP async entrypoints without `SynchronousOnlyOperation` errors.

Specifically:
- All public service functions are `async def`
- ORM reads: `await sync_to_async(queryset.method)()` (e.g., `.get()`, `.filter()`, `.order_by()`)
- ORM writes: `await sync_to_async(Model.objects.create)()`, `await sync_to_async(instance.save)()`
- `F()` expressions for atomic updates: wrap the entire `.update()` call in `sync_to_async`
- Raw SQL (search): `await sync_to_async(cursor.execute)()` within `connection.cursor()`
- No mixing of sync ORM calls within async functions — all paths are explicitly async

```python
async def create_memory(content: str, source: str = "manual", tags: list[str] = None,
                        metadata: dict = None, importance: float = 0.5) -> Memory
async def get_memory(memory_id: UUID) -> Memory  # increments access_count
async def update_memory(memory_id: UUID, **fields) -> Memory  # re-embeds if content changes
async def delete_memory(memory_id: UUID) -> None
async def list_recent(limit: int = 20, source: str = None) -> list[Memory]
```

- `create_memory` generates embedding via registry, then creates the `Memory` row
- `get_memory` uses `F()` expression to atomically increment `access_count` and set `last_accessed`
- `update_memory` re-generates embedding if `content` is in the updated fields
- All functions raise `Memory.DoesNotExist` for missing records (let callers handle)

### Search Service (`core/services/search_service.py`)

Hybrid search combining two retrieval signals with Reciprocal Rank Fusion.

**Vector search leg:**
- Uses pgvector `<=>` (cosine distance) via raw SQL or Django ORM annotation
- Returns top-N candidates ranked by cosine similarity

**BM25 search leg:**
- Uses PostgreSQL `ts_rank_cd(content_tsv, plainto_tsquery('english', query))`
- Returns top-N candidates ranked by BM25 score

**Reciprocal Rank Fusion (RRF):**
```
RRF_score(doc) = Σ 1 / (k + rank_i(doc))
```
where `k = 60` (standard constant) and `rank_i` is the rank of the document in retrieval leg `i`.

```python
async def search(
    query: str,
    limit: int = 10,
    tags: list[str] = None,        # filter: memory must have ALL of these tags
    source: str = None,             # filter: exact source match
    after: datetime = None,         # filter: created_at >= after
    before: datetime = None,        # filter: created_at <= before
    semantic_weight: float = 0.5,   # 0.0 = pure keyword, 1.0 = pure semantic
) -> list[dict]  # returns dicts with memory fields + rrf_score
```

**Implementation approach:**
- Use `core/managers.py` for a custom manager with raw SQL for the hybrid query
- Single SQL query using CTEs: one CTE for vector results, one for BM25 results, combined with RRF scoring
- Apply tag/source/date filters as WHERE clauses inside both CTEs
- Return results ordered by RRF score descending

### Custom Manager (`core/managers.py`)

Raw SQL implementation of the hybrid search query using CTEs for performance. The query produces **one row per memory id** with a canonical, explicit column set.

**Design:** The two retrieval CTEs select only `id` and rank. A third CTE fuses ranks by `id` via `FULL OUTER JOIN`. The final `SELECT` joins the fused result back to `core_memory` once to pick up all payload columns — no ambiguous NULLs from duplicated payload fields.

```sql
WITH vector_leg AS (
    SELECT id,
           ROW_NUMBER() OVER (ORDER BY embedding <=> %(query_vec)s) AS v_rank
    FROM core_memory
    WHERE [filters]
    ORDER BY embedding <=> %(query_vec)s
    LIMIT %(pool_size)s
),
bm25_leg AS (
    SELECT id,
           ROW_NUMBER() OVER (ORDER BY ts_rank_cd(content_tsv, plainto_tsquery('english', %(query_text)s)) DESC) AS t_rank
    FROM core_memory
    WHERE content_tsv @@ plainto_tsquery('english', %(query_text)s)
      AND [filters]
    LIMIT %(pool_size)s
),
fused AS (
    SELECT COALESCE(v.id, b.id) AS id,
           v.v_rank,
           b.t_rank,
           (COALESCE(1.0 / (60 + v.v_rank), 0) * %(sem_weight)s +
            COALESCE(1.0 / (60 + b.t_rank), 0) * %(kw_weight)s
           ) AS rrf_score
    FROM vector_leg v
    FULL OUTER JOIN bm25_leg b ON v.id = b.id
)
SELECT m.id, m.content, m.source, m.tags, m.metadata,
       m.importance, m.decay_factor, m.access_count,
       m.last_accessed, m.created_at, m.updated_at,
       f.rrf_score
FROM fused f
JOIN core_memory m ON m.id = f.id
ORDER BY f.rrf_score DESC
LIMIT %(limit)s;
```

**Key properties:**
- `fused` CTE guarantees exactly one row per memory `id` (COALESCE resolves the FULL OUTER JOIN)
- Payload columns come from a single `JOIN core_memory` — no ambiguous NULLs
- Output schema is explicit: 11 memory fields + `rrf_score`
- `pool_size` defaults to `limit * 3` to ensure adequate coverage

### Test Suite

Tests use `pytest-django` with a test PostgreSQL database (requires Docker DB running).

- `tests/test_embeddings.py` — Mock httpx to test Ollama/OpenRouter providers and fallback logic
- `tests/test_memory_service.py` — CRUD operations, access tracking, re-embedding on content update
- `tests/test_search_service.py` — Vector search, BM25 search, RRF fusion, filtering

## Files to Create/Modify

| Action | File | Description |
|--------|------|-------------|
| Create | `embeddings/__init__.py` | Package init |
| Create | `embeddings/base.py` | Abstract EmbeddingProvider |
| Create | `embeddings/ollama_provider.py` | Ollama embedding provider |
| Create | `embeddings/openrouter_provider.py` | OpenRouter fallback provider |
| Create | `embeddings/registry.py` | Provider factory + fallback logic |
| Create | `core/services/__init__.py` | Services package |
| Create | `core/services/memory_service.py` | Memory CRUD operations |
| Create | `core/services/search_service.py` | Hybrid search with RRF |
| Create | `core/managers.py` | Custom manager with raw SQL hybrid query |
| Create | `tests/__init__.py` | Tests package |
| Create | `tests/test_embeddings.py` | Embedding provider tests |
| Create | `tests/test_memory_service.py` | Memory service tests |
| Create | `tests/test_search_service.py` | Search service tests |

## Success Criteria

1. Embedding providers: Ollama returns 768-dim vectors; OpenRouter returns 768-dim vectors (via `dimensions` param); registry validates `len(vector) == settings.VECTOR_DIMENSIONS` before returning; fallback triggers on Ollama connection failure
2. Memory CRUD: create stores content + embedding, get increments access_count, update re-embeds on content change, delete removes row
3. Hybrid search: vector leg finds semantically similar memories, BM25 leg finds keyword matches that vector misses, RRF combines both into a single ranked list
4. Filtering: tag, source, and date range filters narrow results correctly
5. Tests pass with mocked embedding providers (no live Ollama/OpenRouter required for CI)
