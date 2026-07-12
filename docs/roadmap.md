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
- **Status:** Complete
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
- **Status:** Complete
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
- **Status:** Complete
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
- **Status:** Complete
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
- **Status:** Complete
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
- **Status:** Complete
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
- **Status:** Complete
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
- **Status:** Complete
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

## Revival Roadmap (v1.1 — Shared Brain)

Phases 1–8 shipped as v1.0.0. The phases below revive the project and turn it
into the memory pillar of a personal agent OS (see `SHARED_BRAIN_REVIVAL.md`
for background and the AgentOS comparison).

**Core product direction:** the user's central pain is tracking many
concurrent projects, research, and learning. Engram therefore carries
canonical per-project status/context — not just episodic memories — with a
safe proposed-update workflow: sessions *propose* status updates, the user
confirms, engram records. Tagteam remains the handoff/review engine; engram
stores and surfaces project continuity (e.g. approved cycle summaries feed
proposed status updates). The two systems integrate at that boundary and are
not merged.

Decisions recorded 2026-07-11:

- **Deploy target:** Mac for development and verification now; Windows/WSL2
  LAN hosting is the intended personal deployment (explicit deliverable in
  `automations-and-polish`, after the daily workflow is proven).
- **Scoping/auth:** per-agent API keys + soft domain tags for authorization.
  Whether soft tags remain the long-term *project* model is deliberately
  left open — `agent-scoping` includes a decision checkpoint on first-class
  projects/workspaces, informed by daily-driver experience.
- **PyPI:** deprioritized; source/Docker is the supported install path.
- **Usage model:** ambient recall via Claude Code hooks; capture is
  suggestion-first during development (session proposes, user confirms),
  with fully automatic capture as the trusted end-state.

### Phase 9: Revive and Verify
- **Status:** Complete
- **Dependencies:** None
- **Description:** Bring the stack back up on the Mac, re-establish the test baseline, and verify the full store→search→recall loop live from Claude Code over MCP.
- **Key Deliverables:**
  - Dev stack running locally (Postgres+pgvector container, native Mac Ollama with `nomic-embed-text`)
  - Full backend test suite green, including the known-broken `TestGetStats::test_get_stats_with_data`
  - Live MCP round-trip from Claude Code: store_memory → search_brain → find_related
  - README install docs corrected: source/Docker is the supported path; PyPI caveats documented
  - Prod-compose env requirements documented (`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`)
- **Key Files:** `docker-compose.yml`, `README.md`, `.env.example`, `tests/`
- **Verify:** `pytest` all green → live MCP round-trip from a real Claude Code session

---

### Phase 10: Daily Driver
- **Status:** Complete
- **Dependencies:** Phase 9
- **Description:** Ambient recall and suggestion-first capture from Claude Code — engram becomes part of every session without getting in the way.
- **Key Deliverables:**
  - SessionStart hook: query engram for memories and project status relevant to the current project, inject as context
  - **Manual suggestion-first checkpoint** (`/engram checkpoint` or the `end_session` MCP prompt — user-invoked, no automatic session-end write): drafts a session delta plus a **full project-status snapshot** for confirmation before storing, tagged `domain:<project>`; fully automatic capture is an end-state capability once trust is established
  - Project status/context tracking (v1): full-snapshot `type:project-status` memories (newest per domain is canonical) with a propose→confirm→record workflow; deterministic scoped retrieval via tag/source/limit filters on `GET /api/memories/` plus a `list_domains` MCP tool
  - MCP prompts for the recurring workflows: start-day, switch-project, end-session, weekly-review
  - Per-project domain conventions documented
  - A skill for explicit store/search on top of the ambient layer
- **Key Files:** new hooks/skill/prompt assets, `docs/workflows.md`
- **Verify:** one week of real daily use across at least two projects; recall surfaces relevant prior context; at least one confirmed project-status update flows through the propose→confirm→record path

---

### Phase 11: Identity and Onboarding
- **Status:** Complete
- **Dependencies:** Phase 10
- **Description:** The AgentOS identity pillar — portable identity/context markdown files, canonical per-project status/context, and an `onboard_agent` MCP tool so any new agent is productive in minutes.
- **Key Deliverables:**
  - `identity.md` + `context/*.md` structure (git as source of truth)
  - Canonical per-project status/context files, exposed as **read-only MCP resources** (alongside identity), so any client can load them without a tool call
  - Identity/project file ingestion into engram (tagged for retrieval)
  - `onboard_agent` MCP tool: who the user is, house rules, domain assignment, connection info
  - Tagteam integration boundary: ingest approved cycle summaries into engram; use them as evidence when proposing project-status updates (tagteam stays the handoff/review engine — no merging of the systems)
- **Key Files:** `mcp_server/tools/`, MCP resource definitions, identity/project file structure, `ingestion/`
- **Verify:** fresh agent session calls `onboard_agent`, reads identity/project resources, and can immediately store/search correctly scoped memories; an approved tagteam cycle summary appears in engram and informs a proposed status update

---

### Phase 12: Agent Scoping
- **Status:** Complete
- **Dependencies:** Phase 11
- **Description:** Per-agent API keys with domain binding; close the unscoped read surfaces. Opens with a decision checkpoint on the long-term project model.
- **Key Deliverables:**
  - **Decision checkpoint (first deliverable):** evaluate — with daily-driver usage data — whether soft `domain:` tags suffice as the long-term project model or a first-class project/workspace column is warranted. **Gate:** requires either the human's confirmation of meaningful daily-driver use across ≥2 projects (recorded in `docs/adoption-log.md`) or an explicit "insufficient evidence — decision deferred" entry; a single demo does not satisfy it. Per-agent authorization and project organization solve different problems; decide and log before implementing. The auth work below proceeds either way.
  - API-key table: key hash, agent name, default domain, allowed domains
  - Server-side domain tag injection on write; domain filtering on the currently-unscoped reads (`GET /api/memories/`, `/stats/`, `/tags/`, MCP `get_memory`/`get_stats`)
  - Key management commands (create/revoke/list)
- **Key Files:** `api/authentication.py`, `mcp_server/auth.py`, `core/`, new migration, `docs/decision_log.md`
- **Verify:** two keys with different domains cannot see each other's memories on any surface; project-model decision recorded in the decision log

---

### Phase 13: Automations and Polish
- **Status:** Complete
- **Dependencies:** Phase 12
- **Description:** Windows/WSL2 LAN deployment (the intended personal hosting target), scheduled maintenance, and remaining cleanups.
- **Key Deliverables:**
  - **Windows/WSL2 LAN deployment** of the prod compose stack with GPU-accelerated Ollama — the personal deployment target, now that the daily workflow is proven
  - Identity-directory container wiring: mount the user's identity repo read-only into the Django/MCP services (`~/.engram/identity:/identity:ro`, `ENGRAM_IDENTITY_DIR=/identity`) per the contract documented in Phase 11
  - Scheduled decay runs and weekly digest report
  - Embedding registry made config-driven (currently hardcodes Ollama)
  - Docker image pinning (`ollama/ollama`, `nginx`)
- **Key Files:** `docker-compose.prod.yml`, `docs/deploy-windows-lan.md`, `intelligence/`, `embeddings/registry.py`
- **Verify:** stack running on the Windows/WSL2 box, reachable and used from the Mac over LAN with GPU embeddings; decay + digest run unattended; stack reproducible from pinned images

---

### Phase 14: Status Dashboard & Usability (candidate — not yet planned)
- **Status:** Not Started
- **Dependencies:** Phase 13; shaped by adoption-trial feedback
- **Description:** Surface the agent-OS layer in the UI. The existing React dashboard shows raw memories/analytics but none of the revival-layer concepts. Captured from the human's feedback 2026-07-12: "md documents in locations outside the project are awkward — we might have to build some kind of dashboard to make this more useful."
- **Key Deliverables (sketch, to be planned via /handoff):**
  - Project-status view: latest snapshot + checkpoint timeline per domain
  - Identity/context management: view (and possibly edit) `~/.engram/identity` files from the dashboard, addressing the out-of-project-markdown friction
  - Agent-key and digest visibility; adoption-log surfacing
- **Verify:** daily status review happens in the dashboard instead of raw file/tool spelunking

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
