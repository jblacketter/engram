<p align="center">
  <img src="docs/assets/engram-banner.svg" alt="Engram — Personal Semantic Memory for AI" width="800" />
</p>

<p align="center">
  <strong>A self-hosted semantic memory layer that gives any AI tool persistent, searchable recall.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white" alt="Python 3.12+" />
  <img src="https://img.shields.io/badge/django-5.1-092E20?logo=django&logoColor=white" alt="Django 5" />
  <img src="https://img.shields.io/badge/postgresql-16+pgvector-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL + pgvector" />
  <img src="https://img.shields.io/badge/MCP-compatible-6c63ff" alt="MCP Compatible" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT" />
</p>

---

## What is Engram?

Engram is a personal knowledge base that stores your notes, conversations, documents, and web pages as vector embeddings — then lets any MCP-compatible AI assistant (Claude, Cursor, Windsurf, etc.) search and recall them by *meaning*, not just keywords. Everything lives in a PostgreSQL database you control, runs locally or in the cloud, and costs near-zero to self-host.

## Features

- **Hybrid Search** — Combines vector similarity (pgvector HNSW) with PostgreSQL full-text BM25, fused via Reciprocal Rank Fusion
- **MCP Server** — Any MCP-compatible client can store, search, and manage memories over HTTP
- **REST API** — Full CRUD + search, with OpenAPI docs at `/api/docs/`
- **Multi-format Ingestion** — Ingest PDFs, DOCX, TXT, Markdown, URLs, and Obsidian vaults
- **Auto-Enrichment** — Optional LLM-powered tagging, entity extraction, and memory decay
- **React Dashboard** — Browse, search, and visualize your memory graph
- **Privacy-First** — Runs 100% locally with Ollama; no data leaves your machine
- **Pluggable Embeddings** — Ollama (default, free), OpenRouter, or bring your own provider

## Architecture

```
┌──────────────────────────────┐
│  AI Clients                  │
│  (Claude, Cursor, Windsurf)  │
└─────────────┬────────────────┘
              │ MCP / REST
              ▼
┌──────────────────────────────────────┐
│  MCP Server (FastMCP :8080)          │
│  REST API   (Django DRF :8000)       │
│  Dashboard  (React + Vite :5173)     │
└─────────────┬────────────────────────┘
              │
   ┌──────────┴──────────┐
   │  Application Layer   │
   │  Embedder ─→ Ollama  │
   │  Auto-Tagger         │
   │  Entity Extractor    │
   │  Memory Decay        │
   └──────────┬──────────┘
              │
   ┌──────────▼──────────┐
   │  PostgreSQL 16       │
   │  + pgvector (768d)   │
   │  + Full-text search  │
   │  + HNSW index        │
   └──────────────────────┘
```

## Quick Start

**Prerequisites:** Python 3.12+, PostgreSQL 16 with pgvector, Ollama (or Docker)

```bash
# 1. Clone and enter
git clone https://github.com/jblacketter/engram.git && cd engram

# 2. Start database + Ollama via Docker
docker compose up -d

# 3. Pull the embedding model
ollama pull nomic-embed-text

# 4. Install Python dependencies
pip install -e ".[dev]"

# 5. Copy environment config
cp .env.example .env

# 6. Run migrations and start the server
python manage.py migrate
python manage.py runserver
```

The API is now live at `http://localhost:8000/api/` and docs at `http://localhost:8000/api/docs/`.

**Start the MCP server** (separate terminal):

```bash
python -m mcp_server
```

**Start the frontend** (separate terminal):

```bash
cd frontend && npm install && npm run dev
```

Dashboard at `http://localhost:5173`.

## Connecting AI Clients

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "engram": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

### Claude Code

```bash
claude mcp add engram http://localhost:8080/sse
```

### Cursor / Windsurf

Add to your MCP settings:

```json
{
  "mcpServers": {
    "engram": {
      "url": "http://localhost:8080/sse"
    }
  }
}
```

See [docs/connecting-clients.md](docs/connecting-clients.md) for authenticated setups and advanced config.

## API Reference

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health/` | Health check |
| `GET` | `/api/memories/` | List memories (paginated) |
| `POST` | `/api/memories/` | Create a memory |
| `GET` | `/api/memories/<id>/` | Get memory by UUID |
| `PATCH` | `/api/memories/<id>/` | Update memory |
| `DELETE` | `/api/memories/<id>/` | Delete memory |
| `POST` | `/api/search/` | Hybrid semantic + keyword search |
| `GET` | `/api/stats/` | Memory statistics |
| `GET` | `/api/tags/` | List all tags |
| `POST` | `/api/ingest/file/` | Ingest a file (PDF, DOCX, TXT, etc.) |
| `POST` | `/api/ingest/url/` | Scrape and ingest a URL |
| `POST` | `/api/ingest/batch/` | Batch ingest files and URLs |

Auth: `Authorization: Bearer <REST_API_KEY>` (disabled when env var is empty).

### MCP Tools

| Tool | Description |
|------|-------------|
| `store_memory` | Store a new memory with optional tags and importance |
| `get_memory` | Retrieve a memory by UUID |
| `update_memory` | Update content, tags, or importance |
| `delete_memory` | Delete a memory |
| `search_brain` | Hybrid search with configurable semantic/keyword weight |
| `find_related` | Find semantically similar memories |
| `list_recent_memories` | List recent memories, optionally filtered by source |
| `store_from_url` | Fetch and ingest a URL |
| `ingest_file` | Ingest a base64-encoded file |
| `get_stats` | System statistics |

## Project Structure

```
engram/
├── api/                # REST API (DRF views, serializers, auth)
├── core/               # Data models, services (memory CRUD, search)
├── embeddings/         # Embedding providers (Ollama, OpenRouter)
├── intelligence/       # Auto-tagger, entity extraction, decay, reports
├── ingestion/          # File, URL, batch, and Obsidian importers
├── mcp_server/         # FastMCP server with tool definitions
├── engram/             # Django project settings and URL config
├── frontend/           # React + TypeScript + Tailwind SPA
├── docker/             # Entrypoint scripts, pgvector init SQL
├── nginx/              # Reverse proxy config (production)
├── docs/               # Extended documentation
├── tests/              # Test suite
├── Dockerfile          # Django production image
├── Dockerfile.mcp      # MCP server image
├── docker-compose.yml  # Dev: PostgreSQL + Ollama
└── pyproject.toml      # Python package config
```

## Configuration

Key environment variables (see [`.env.example`](.env.example) for the full list):

| Variable | Default | Description |
|----------|---------|-------------|
| `DJANGO_SECRET_KEY` | — | Django secret key |
| `DJANGO_SETTINGS_MODULE` | `engram.settings.development` | Settings module |
| `POSTGRES_DB` | `engram` | Database name |
| `POSTGRES_HOST` | `localhost` | Database host |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `OLLAMA_CHAT_MODEL` | `llama3.2:3b` | Chat model for enrichment |
| `OPENROUTER_API_KEY` | — | Fallback embedding provider |
| `MCP_API_KEY` | — | MCP auth token (empty = open) |
| `REST_API_KEY` | — | REST auth token (empty = open) |
| `AUTO_ENRICH_ON_CREATE` | `false` | Auto-tag and extract entities |

## Production Deployment

```bash
docker compose -f docker-compose.prod.yml up -d
```

This starts PostgreSQL, Ollama (with GPU support), Django (gunicorn), the MCP server, and nginx with TLS. See [docs/setup-docker.md](docs/setup-docker.md) for full production setup and [docs/setup-supabase.md](docs/setup-supabase.md) for cloud-hosted PostgreSQL.

## Tech Stack

**Backend:** Django 5.1 &#8226; Django REST Framework &#8226; FastMCP 2.0 &#8226; PostgreSQL 16 + pgvector &#8226; Ollama
**Frontend:** React 18 &#8226; TypeScript &#8226; Vite &#8226; Tailwind CSS &#8226; D3 &#8226; Recharts
**Infra:** Docker &#8226; nginx &#8226; gunicorn &#8226; uvicorn

## Documentation

| Guide | Description |
|-------|-------------|
| [Connecting Clients](docs/connecting-clients.md) | Claude Desktop, Claude Code, Cursor setup |
| [Embedding Providers](docs/embedding-providers.md) | Ollama, OpenRouter, OpenAI, Cohere comparison |
| [Docker Setup](docs/setup-docker.md) | Local and production Docker guide |
| [Supabase Setup](docs/setup-supabase.md) | Cloud PostgreSQL with Supabase |
| [Schema](docs/schema.md) | Database schema deep dive |
| [Workflows](docs/workflows.md) | Daily capture and search patterns |
| [Extending](docs/extending.md) | Adding providers, tools, and importers |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and fixes |
| [Roadmap](docs/roadmap.md) | Feature roadmap |

## License

MIT
