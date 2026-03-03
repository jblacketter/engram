# Decision Log

This log tracks important decisions made during the project.

<!-- Add new decisions at the top in reverse chronological order -->

---

## 2026-03-03: Use Django + DRF instead of FastAPI

**Decision:** Use Django with Django REST Framework as the backend instead of FastAPI/Streamlit.

**Context:** The original prototype used a flat FastMCP + Supabase architecture. The new plan needs a structured backend with ORM, migrations, admin interface, and a service layer shared between MCP and REST API.

**Alternatives Considered:**
- FastAPI: Lighter weight, async-native, but lacks built-in ORM, migrations, admin. Would need SQLAlchemy + Alembic + manual wiring.
- Django + DRF: Full-featured ORM, migrations, admin, auth system, battle-tested ecosystem. Slightly more boilerplate but much more structured for a growing project.

**Rationale:** Django's ORM with pgvector support (`django-pgvector`), built-in migrations, and admin interface reduce the amount of infrastructure code needed. DRF provides serialization, viewsets, and auto-generated OpenAPI docs. The service layer pattern cleanly separates business logic from both the MCP server and REST API.

**Decided By:** Consensus (planning phase)

**Phase:** Architecture / Phase 1

**Follow-ups:**
- MCP server runs as a separate process but imports Django's service layer via `django.setup()`

---

## 2026-03-03: Use Ollama local-first with nomic-embed-text (768 dimensions)

**Decision:** Use Ollama with `nomic-embed-text` as the primary embedding provider, with OpenRouter as a fallback.

**Context:** The original prototype used OpenRouter's cloud API for embeddings. The new plan prioritizes privacy and local-first operation.

**Alternatives Considered:**
- OpenRouter/OpenAI cloud embeddings: Higher quality models available, but data leaves the network. Cost scales with usage.
- Ollama local (`nomic-embed-text`, 768-dim): Free, private, fast with GPU. Quality is sufficient for personal knowledge management.
- Sentence-transformers: Good quality, but requires more Python dependency management vs. Ollama's single binary.

**Rationale:** Ollama provides a clean HTTP API, easy model management, and GPU acceleration. `nomic-embed-text` at 768 dimensions offers a good balance of quality and performance. OpenRouter fallback ensures the system works even when Ollama is unavailable.

**Decided By:** Consensus (planning phase)

**Phase:** Architecture / Phase 2

**Follow-ups:**
- Embedding provider abstraction allows swapping providers without code changes
- Vector dimension (768) is configured centrally in Django settings

---

## 2026-03-03: Replace Supabase with local PostgreSQL + pgvector

**Decision:** Replace Supabase cloud database with a local PostgreSQL 16 + pgvector instance running in Docker.

**Context:** The original prototype used Supabase for storage and vector search. The new plan requires full data ownership and LAN-only access.

**Alternatives Considered:**
- Supabase: Easy setup, managed infrastructure, but data lives on external servers. Free tier has 500MB limit.
- Local PostgreSQL + pgvector: Full control, no data egress, no size limits. Requires Docker setup.
- SQLite + sqlite-vss: Simpler, single-file, but limited concurrent access and fewer indexing options.
- Dedicated vector DB (Qdrant, Milvus): Purpose-built for vectors but adds another service. PostgreSQL handles both relational and vector data in one place.

**Rationale:** PostgreSQL + pgvector keeps everything in one database with mature tooling, ACID transactions, and full SQL capabilities. HNSW indexing provides fast approximate nearest neighbor search. Docker makes it reproducible across dev (macOS) and prod (Windows/WSL).

**Decided By:** Consensus (planning phase)

**Phase:** Architecture / Phase 1

**Follow-ups:**
- Docker Compose manages PostgreSQL + pgvector container
- Schema includes tsvector column for hybrid BM25 search alongside vector search

---

## 2026-03-03: Hybrid search with Reciprocal Rank Fusion (RRF)

**Decision:** Implement hybrid search combining pgvector cosine similarity with PostgreSQL full-text search (BM25), merged using Reciprocal Rank Fusion.

**Context:** Pure vector search misses exact keyword matches; pure keyword search misses semantic similarity. Hybrid search combines both strengths.

**Alternatives Considered:**
- Vector-only search: Simple, but misses exact keyword/acronym matches.
- Keyword-only search: Fast, but misses semantic similarity.
- Hybrid with simple score averaging: Doesn't account for rank ordering well.
- Hybrid with RRF: Rank-based fusion that works well even when score scales differ between methods.

**Rationale:** RRF is a proven fusion method that doesn't require score normalization. It combines ranked lists by `1/(k+rank)` weighting, naturally handling the different score scales of cosine similarity and BM25. A configurable weight slider lets users adjust the vector/keyword balance.

**Decided By:** Consensus (planning phase)

**Phase:** Phase 2

**Follow-ups:**
- Search service implements both retrieval methods and RRF fusion
- React dashboard exposes a weight slider for vector vs. keyword balance

---

## 2026-03-03: MCP server as separate process sharing Django service layer

**Decision:** Run the FastMCP server as a separate process that imports and uses Django's service layer, rather than embedding it in Django or duplicating logic.

**Context:** The MCP server needs to expose tools to AI clients, while the REST API serves the dashboard. Both need identical business logic.

**Alternatives Considered:**
- Embed MCP in Django (e.g., as middleware): Tight coupling, conflicts between Django's request/response cycle and MCP's streaming protocol.
- Duplicate logic in MCP server: Simple but creates maintenance burden and divergence risk.
- Shared service layer: MCP process calls `django.setup()` to access models and services. Both interfaces use the same code.

**Rationale:** A shared service layer ensures consistent behavior between MCP and REST endpoints. The MCP server initializes Django's ORM without running the full web server, keeping the processes independent but logic-unified.

**Decided By:** Consensus (planning phase)

**Phase:** Architecture / Phase 3

**Follow-ups:**
- `mcp_server/server.py` calls `django.setup()` at startup
- All business logic lives in `core/services/`, never in views or MCP tools directly

---

## 2026-03-03: React + Vite + Tailwind for dashboard (replacing Streamlit)

**Decision:** Use React + TypeScript + Vite + Tailwind CSS for the dashboard instead of Streamlit.

**Context:** The original plan mentioned Streamlit for the dashboard. The new plan requires interactive visualizations (D3.js knowledge graph), complex filtering UI, and production-quality frontend.

**Alternatives Considered:**
- Streamlit: Rapid prototyping, Python-only, but limited interactivity and hard to customize.
- React + Vite: Full control over UI, rich ecosystem (D3.js, Tailwind), production-ready builds. More setup but much more capable.
- Django templates + HTMX: Server-rendered, simpler, but limited for complex interactive visualizations.

**Rationale:** The knowledge graph, analytics charts, and interactive search interface require a proper SPA framework. React + Vite provides fast dev iteration, TypeScript ensures type safety, and Tailwind enables rapid styling. Django serves the built frontend in production.

**Decided By:** Consensus (planning phase)

**Phase:** Phase 5

**Follow-ups:**
- `frontend/` directory with Vite project
- Django serves built static files in production
- CORS configuration for dev server proxy
