# Project Roadmap

## Overview

Open Brain is a local, privacy-focused personal semantic memory system that any AI tool (Claude Desktop, Claude Code, Cursor) can read/write via MCP. The system stores thoughts, notes, and knowledge as vector embeddings in PostgreSQL, enabling semantic search across all your AI interactions. Development starts on macOS; production deploys to a Windows machine with GPU on LAN.

**Tech Stack:**
- **Database:** PostgreSQL 16 + pgvector (Docker)
- **Embeddings:** Ollama local-first (`nomic-embed-text`, 768 dimensions)
- **Backend:** Django 5 + Django REST Framework
- **Frontend:** React + TypeScript + Vite + Tailwind CSS
- **MCP:** FastMCP (separate process, shares Django's service layer)
- **Security:** API key auth, HTTPS on LAN, no data leaves your network

**Workflow:** Lead (claude) / Reviewer (codex) with Human Arbiter (see ai-handoff.yaml)

## Architecture

```
AI Clients (Claude Desktop, Claude Code, Cursor)
        │
        │  MCP Protocol (Streamable HTTP)
        ▼
┌───────────────────────────────────────┐
│  MCP Server  (FastMCP :8080)          │──┐
│  REST API    (Django DRF :8000)       │  │ shared service layer
│  Dashboard   (React/Vite :5173)       │  │
└───────────────┬───────────────────────┘  │
                │                          │
    ┌───────────┴────────────┐             │
    │  core/services/        │◄────────────┘
    │  • memory_service.py   │
    │  • search_service.py   │
    │  • embeddings/         │ → Ollama (primary) / OpenRouter (fallback)
    │  • intelligence/       │
    │  • ingestion/          │
    └───────────┬────────────┘
                │
    ┌───────────┴────────────┐
    │  PostgreSQL + pgvector │  (port 5432)
    │  • memories table      │
    │  • HNSW vector index   │
    │  • GIN tsvector index  │
    └────────────────────────┘
```

**Architectural note:** The MCP server and Django REST API are separate processes but share the same `core/services/` layer. This prevents logic duplication and ensures both interfaces behave identically.

## Project Structure

```
openbrain/
├── docker-compose.yml           # Dev: PostgreSQL+pgvector, Ollama
├── docker-compose.prod.yml      # Prod: full stack with Nginx+HTTPS
├── Dockerfile / Dockerfile.mcp  # Container builds
├── pyproject.toml               # Python dependencies (replaces requirements.txt)
├── manage.py                    # Django management
├── .env.example                 # Config template
│
├── openbrain/                   # Django project settings
│   ├── settings/
│   │   ├── base.py              # Shared config (DB, apps, vector dimensions)
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py, wsgi.py, asgi.py
│
├── core/                        # Django app: memory engine
│   ├── models.py                # Memory model (pgvector field, tsvector, decay fields)
│   ├── managers.py              # Raw SQL for hybrid search
│   └── services/
│       ├── memory_service.py    # CRUD operations
│       └── search_service.py    # Hybrid vector+BM25 search with RRF
│
├── embeddings/                  # Pluggable embedding providers
│   ├── base.py                  # Abstract EmbeddingProvider
│   ├── ollama_provider.py       # Primary (768-dim nomic-embed-text)
│   ├── openrouter_provider.py   # Fallback
│   └── registry.py              # Provider factory
│
├── mcp_server/                  # Standalone FastMCP server (NOT a Django app)
│   ├── server.py                # FastMCP app, port 8080
│   └── tools/                   # store, search, delete, stats, ingest tools
│
├── api/                         # Django app: REST API (DRF)
│   ├── serializers.py, views.py, urls.py
│   ├── authentication.py        # API key auth
│   └── throttling.py            # Rate limiting
│
├── frontend/                    # React + Vite + TypeScript
│   └── src/
│       ├── pages/               # Home, Search, Graph, Analytics, Settings
│       └── components/          # MemoryBrowser, KnowledgeGraph (D3.js), TagCloud
│
├── intelligence/                # Django app: auto-enrichment
│   ├── auto_tagger.py           # Tag extraction via Ollama LLM
│   ├── entity_extractor.py      # NER for people, projects, tech
│   ├── memory_decay.py          # Importance decay scoring
│   └── report_generator.py      # Weekly digests
│
├── ingestion/                   # Django app: batch import
│   ├── file_ingestor.py         # PDF, Markdown, DOCX, text
│   ├── url_scraper.py           # Web page content extraction
│   ├── obsidian_importer.py     # Obsidian vault import
│   └── batch_processor.py       # Progress-tracked batch pipeline
│
├── sql/schema.sql               # Reference SQL (768-dim, tsvector, decay)
├── nginx/nginx.conf             # Production reverse proxy
└── scripts/                     # backup.sh, restore.sh, generate_certs.sh
```

## Dependency Graph

```
Phase 1: Foundation
    │
    ▼
Phase 2: Core Memory Engine
    │              │
    ▼              ▼
Phase 3: MCP    Phase 6: Intelligence    ← can run in parallel
    │              │
    ▼              ▼
Phase 4: REST   Phase 7: Ingestion       ← can run in parallel
    │
    ▼
Phase 5: React Dashboard
    │
    ▼ (all phases feed into)
Phase 8: Production Deployment
```

---

## Phases

### Phase 1: Foundation `[Medium]`
- **Status:** Not Started
- **Dependencies:** None
- **Description:** Django project scaffolding with split settings, Docker infrastructure, and the core Memory model.
- **Key Deliverables:**
  - `pyproject.toml` with all Python dependencies (Django, DRF, pgvector, FastMCP, etc.)
  - `docker-compose.yml` for PostgreSQL 16 + pgvector and Ollama
  - Django project with split settings (`base.py`, `development.py`, `production.py`)
  - `Memory` Django model with `VectorField(768)`, `content_tsv` (tsvector), dual timestamps, decay fields
  - `.gitignore`, updated `.env.example` with all config variables
  - Updated `sql/schema.sql` for 768-dim vectors, tsvector, decay columns
  - Initial migration creating memories table + HNSW index + GIN indexes
- **Key Files:** `pyproject.toml`, `docker-compose.yml`, `openbrain/settings/`, `core/models.py`, `sql/schema.sql`
- **Verify:** `docker compose up -d` → `python manage.py migrate` → create Memory from Django shell

---

### Phase 2: Core Memory Engine `[Large]`
- **Status:** Not Started
- **Dependencies:** Phase 1
- **Description:** Embedding provider abstraction, memory CRUD service layer, and hybrid search combining pgvector cosine similarity with PostgreSQL BM25 via Reciprocal Rank Fusion.
- **Key Deliverables:**
  - Embedding provider abstraction (`base.py` → `ollama_provider.py` → `registry.py`)
  - OpenRouter fallback provider
  - Memory CRUD service layer (`memory_service.py`)
  - Hybrid search: pgvector cosine similarity + PostgreSQL `ts_rank_cd` BM25, combined with RRF
  - Tag/source/date filtering, access tracking
  - Test suite for services and search
- **Key Files:** `embeddings/`, `core/services/memory_service.py`, `core/services/search_service.py`, `core/managers.py`
- **Verify:** Store memories → search semantically → confirm BM25 catches keyword matches vector misses → RRF combines results

---

### Phase 3: MCP Server `[Medium]`
- **Status:** Not Started
- **Dependencies:** Phase 2
- **Description:** FastMCP server exposing the memory system to AI clients over Streamable HTTP.
- **Key Deliverables:**
  - FastMCP server on port 8080 with Streamable HTTP transport
  - Tools: `store_memory`, `search_brain`, `list_recent`, `get_memory`, `update_memory`, `delete_memory`, `find_related`, `get_stats`
  - API key authentication middleware
  - Config files for Claude Desktop, Claude Code, Cursor
- **Key Files:** `mcp_server/server.py`, `mcp_server/tools/`, `mcp_server/auth.py`
- **Verify:** Start MCP server → configure Claude Desktop → "Store a memory: testing" → "Search my brain for testing" → returns result

---

### Phase 4: REST API `[Medium]`
- **Status:** Not Started
- **Dependencies:** Phase 2
- **Description:** Django REST Framework API mirroring MCP tools, with auth, docs, and rate limiting.
- **Key Deliverables:**
  - DRF viewsets mirroring MCP tools
  - API key + session authentication
  - OpenAPI/Swagger docs auto-generated at `/api/docs/`
  - CORS config for React dev server
  - Rate limiting (100 read/min, 30 write/min)
  - Health check endpoint
- **Key Files:** `api/serializers.py`, `api/views.py`, `api/urls.py`, `api/authentication.py`
- **API Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health/` | Health check |
| GET/POST | `/api/memories/` | List/Create |
| GET/PATCH/DELETE | `/api/memories/{id}/` | Read/Update/Delete |
| POST | `/api/search/` | Hybrid search |
| GET | `/api/stats/` | Statistics |
| GET | `/api/tags/` | Tag list with counts |

- **Verify:** `curl` CRUD operations → Swagger UI at `/api/docs/` → auth rejects unauthenticated writes

---

### Phase 5: React Dashboard `[Large]`
- **Status:** Not Started
- **Dependencies:** Phase 4
- **Description:** Full-featured React dashboard for browsing, searching, and visualizing memories.
- **Key Deliverables:**
  - React + TypeScript + Vite + Tailwind CSS project
  - Pages: Home (recent feed), Search (filters + weight slider), Graph, Analytics, Settings
  - Knowledge graph visualization with D3.js (force-directed, interactive)
  - Analytics charts (memory count timeline, tag/source distribution)
  - Memory browser with sort/filter/pagination
  - Django serves built frontend in production
- **Key Files:** `frontend/src/pages/`, `frontend/src/components/KnowledgeGraph.tsx`, `dashboard/views.py`
- **Verify:** `npm run dev` → browse memories → search with weight slider → view knowledge graph → build and serve from Django

---

### Phase 6: Intelligence Layer `[Medium]`
- **Status:** Not Started
- **Dependencies:** Phase 2 (can run parallel with Phases 3-5)
- **Description:** Automatic enrichment of memories with tags, entities, and decay scoring.
- **Key Deliverables:**
  - Auto-tagging via Ollama LLM (falls back to TF-IDF keyword extraction)
  - Entity extraction: people, projects, organizations, technologies
  - Memory decay: `score = base_importance × recency_factor × access_factor`
  - Weekly digest report generation
  - Management commands: `manage.py enrich`, `manage.py decay`, `manage.py report`
- **Key Files:** `intelligence/auto_tagger.py`, `intelligence/entity_extractor.py`, `intelligence/memory_decay.py`
- **Verify:** Store "Meeting with Sarah about Q3 Django migration" → auto-tags `["meeting", "django", "migration"]` → entities `{"people": ["Sarah"]}`

---

### Phase 7: Ingestion & Integration `[Medium]`
- **Status:** Not Started
- **Dependencies:** Phase 2, Phase 6
- **Description:** Batch import from files, URLs, and Obsidian vaults.
- **Key Deliverables:**
  - File upload: PDF, Markdown, DOCX, text (with text chunking)
  - URL scraping with content extraction
  - Obsidian vault import (preserves frontmatter, links, tags)
  - Batch processor with progress tracking
  - MCP tools: `store_from_url`, `ingest_file`
  - REST endpoints for file upload and batch import
- **Key Files:** `ingestion/file_ingestor.py`, `ingestion/url_scraper.py`, `ingestion/obsidian_importer.py`
- **Verify:** Upload PDF → memories created with chunks → import Obsidian vault → MCP "Store this URL as a memory"

---

### Phase 8: Production Deployment `[Large]`
- **Status:** Not Started
- **Dependencies:** All previous phases (3, 5, 7)
- **Description:** Production-ready deployment to Windows/WSL machine with GPU on LAN.
- **Key Deliverables:**
  - Production Docker Compose for Windows/WSL Ubuntu
  - Nginx reverse proxy with HTTPS (self-signed certs for LAN)
  - Gunicorn (Django) + Uvicorn (MCP)
  - Ollama GPU acceleration (NVIDIA Container Toolkit)
  - Database backup/restore scripts
  - Structured JSON logging
  - LAN security: API keys, rate limiting, no exposed internal ports
- **Key Files:** `docker-compose.prod.yml`, `Dockerfile`, `nginx/nginx.conf`, `scripts/`, `openbrain/settings/production.py`
- **Verify:** `docker compose -f docker-compose.prod.yml up -d` on WSL → access from LAN → GPU embeddings → backup/restore cycle

---

## Security Throughout

- **Secrets:** `.env` gitignored, API keys stored as bcrypt hashes, Django `SECRET_KEY` per environment
- **Database:** Parameterized queries (Django ORM), PostgreSQL not exposed on host network in production
- **Input validation:** Content length limits (50KB), tag limits (20 tags × 100 chars), file size limits (10MB)
- **Auth:** API key for MCP/REST, session auth for dashboard, CSRF protection
- **Network:** HTTPS on LAN, Nginx rate limiting, no SSRF via URL scraping (internal IP validation)
- **LLM safety:** Hardcoded prompt templates for entity extraction (no user-controlled prompts)

## End-to-End Verification

After all phases:
1. Store a memory via Claude Desktop MCP → auto-enriched with tags and entities
2. Search from Claude Code on another machine → finds it semantically
3. Browse in React dashboard → see knowledge graph, analytics
4. Import Obsidian vault → all notes searchable
5. GPU-accelerated embeddings on Windows → sub-10ms per embedding
6. Backup and restore database → data integrity preserved

## Decision Log
See `docs/decision_log.md`

## Getting Started
1. Use `/handoff-phase` to check current phase
2. Use `/handoff-plan create [phase]` to start planning
3. Use `/handoff-status` for project overview
