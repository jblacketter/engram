# Engram Getting Started Guide

A practical guide for first-time setup and usage.

---

## How Engram Works (Mental Model)

Engram is a **server** that runs in the background. It has three parts:

1. **PostgreSQL + pgvector** -- the database that stores your memories as text + vector embeddings
2. **Django REST API** (port 8000) -- CRUD and search endpoints, plus a web dashboard
3. **MCP Server** (port 8080) -- the interface that AI tools (Claude, Cursor, etc.) talk to

Nothing gets stored automatically. Memories are only created when:
- An AI client calls `store_memory` through the MCP connection
- You manually call the REST API
- You ingest a file or URL

The AI clients connected via MCP can also **search** your memories (`search_brain`), which is where the real value is -- your AI tools gain long-term recall across sessions.

---

## Where to Host: Mac vs Windows Server

**Recommendation: Start on your Mac for initial testing, then move to your Windows server for regular use.**

Why:
- Engram needs to be **always running** for AI tools to use it. Your Windows server is already set up for that.
- The services (PostgreSQL, Ollama, Django, MCP server) use moderate resources that you don't want eating into your Mac's limited space.
- Once it's on the server, every device on your LAN can connect -- your Mac, any other machine, Claude Desktop, etc.

### For tonight's testing (Mac, quick start)

Run everything locally to get familiar. No commitment, easy to tear down.

### For regular use (Windows server)

Deploy with Docker. In production, nginx proxies the MCP server at `/mcp/` on port 443 — all your AI tools point to `https://<server-ip>/mcp/` instead of `localhost:8080`. One-time setup, always available.

The guide below covers both paths.

---

## Phase 1: Local Testing on Mac

### Prerequisites

- Python 3.12+
- Docker Desktop (for PostgreSQL + Ollama containers)

### Step 1: Start the infrastructure

```bash
cd ~/projects/engram

# Start PostgreSQL (with pgvector) and Ollama
docker compose up -d

# Pull the embedding model (this downloads ~270MB the first time)
docker exec -it engram-ollama-1 ollama pull nomic-embed-text
```

Verify they're running:
```bash
docker compose ps
# Both db and ollama should show "running"
```

### Step 2: Set up Python environment

```bash
cd ~/projects/engram

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment config
cp .env.example .env
# The defaults work fine for local dev -- no edits needed
```

### Step 3: Initialize the database

```bash
python manage.py migrate
```

### Step 4: Start the servers

You need two terminal windows (or tabs):

**Terminal 1 -- Django REST API:**
```bash
cd ~/projects/engram
source .venv/bin/activate
python manage.py runserver
```
API is now at http://localhost:8000/api/

**Terminal 2 -- MCP Server:**
```bash
cd ~/projects/engram
source .venv/bin/activate
python -m mcp_server
```
MCP server is now at http://localhost:8080/mcp

### Step 5: Verify it works

```bash
# Health check
curl http://localhost:8000/api/health/

# Store a test memory via REST API
curl -X POST http://localhost:8000/api/memories/ \
  -H "Content-Type: application/json" \
  -d '{"content": "This is my first test memory", "source": "manual", "tags": ["test"]}'

# Search for it
curl -X POST http://localhost:8000/api/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "first test"}'

# Check stats
curl http://localhost:8000/api/stats/
```

---

## Phase 2: Connect AI Tools

### Claude Code (this CLI)

```bash
# Add for a specific project (recommended for scoping)
cd ~/projects/some-project
claude mcp add engram http://localhost:8080/mcp --scope project

# OR add globally for all projects
claude mcp add engram http://localhost:8080/mcp --scope user
```

After adding, restart Claude Code. You can then ask Claude things like:
- "Store a memory: the auth system uses JWT tokens with 24h expiry"
- "Search the brain for anything about authentication"
- "What do you remember about the database schema?"

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "engram": {
      "url": "http://localhost:8080/mcp"
    }
  }
}
```
Restart Claude Desktop after saving.

### Cursor / Windsurf

Create `.cursor/mcp.json` in your project root:
```json
{
  "mcpServers": {
    "engram": {
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

---

## Phase 3: Learning the MCP Tools

These are the tools your AI clients can use once connected:

### Storing memories

| Tool | What it does |
|------|-------------|
| `store_memory` | Save a piece of knowledge. Fields: `content`, `source`, `tags`, `importance` (0-1) |
| `store_from_url` | Fetch a URL, extract text, chunk it, and store as memories |
| `ingest_file` | Store a file's contents (PDF, DOCX, TXT, etc.) |

**Tips for storing:**
- Use `source` to track where it came from: `"mcp"`, `"manual"`, `"cursor"`, `"meeting-notes"`, etc.
- Use `tags` to categorize: `["auth", "backend"]`, `["project-x", "decision"]`
- Set `importance` higher (0.7-1.0) for things you always want surfaced, lower (0.1-0.3) for incidental notes

### Searching memories

| Tool | What it does |
|------|-------------|
| `search_brain` | Hybrid semantic + keyword search. The main tool. |
| `find_related` | Given a memory ID, find similar memories |
| `list_recent_memories` | List recent memories, optionally filtered by source |

**`search_brain` parameters:**
- `query` -- what to search for (by meaning, not just exact words)
- `tags` -- filter to specific tags
- `source` -- filter to a specific source
- `semantic_weight` -- 0.0 = pure keyword, 1.0 = pure meaning, 0.5 = balanced (default)
- `limit` -- max results (default 10)

### Management

| Tool | What it does |
|------|-------------|
| `get_memory` | Retrieve a specific memory by UUID |
| `update_memory` | Update content, tags, or importance |
| `delete_memory` | Delete a memory |
| `get_stats` | Total count, breakdown by source, top tags, date range |

---

## Phase 4: Deploy to Windows Server

When you're ready to make Engram always-available on your LAN.

### Step 1: Clone to your Windows server

```bash
git clone https://github.com/jblacketter/engram.git
cd engram
```

### Step 2: Configure environment

```bash
copy .env.example .env
```

Edit `.env` with production-appropriate values:
```env
DJANGO_SECRET_KEY=<generate-a-random-string>
DJANGO_SETTINGS_MODULE=engram.settings.production
DJANGO_ALLOWED_HOSTS=<server-ip>,engram.local,localhost

POSTGRES_PASSWORD=<strong-random-password>

# Keep Ollama defaults
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_EMBED_MODEL=nomic-embed-text

# Optional: set API keys for security on LAN
MCP_API_KEY=<generate-a-key>
REST_API_KEY=<generate-a-key>
```

### Step 3: Start with Docker Compose

```bash
docker compose -f docker-compose.prod.yml up -d
```

This starts PostgreSQL, Ollama, Django (gunicorn), MCP server, and nginx.

**Note:** The prod compose file reserves an NVIDIA GPU for Ollama. If your Windows server doesn't have one, edit `docker-compose.prod.yml` and remove the `deploy.resources.reservations` block from the `ollama` service. CPU inference works fine for embeddings, just slower.

### Step 4: Pull the embedding model

```bash
docker exec -it engram-ollama-1 ollama pull nomic-embed-text
```

### Step 5: Run migrations

```bash
docker exec -it engram-django-1 python manage.py migrate
```

### Step 6: Update AI client configs

On your Mac (and any other machine), point to the server. In production, nginx proxies MCP at `/mcp/` on port 443:

```bash
# Claude Code
claude mcp add engram https://<server-ip>/mcp/ --scope user
```

For Claude Desktop, update the config to:
```json
{
  "mcpServers": {
    "engram": {
      "url": "https://<server-ip>/mcp/"
    }
  }
}
```

If you set `MCP_API_KEY` in `.env`, you'll need to include auth. Check `docs/connecting-clients.md` for authenticated setup.

---

## Controlling Scope (What Gets Stored)

Since nothing is automatic, you have several levers:

1. **MCP connection per project** -- Only add the MCP server to projects where you want shared memory. Use `--scope project` in Claude Code.

2. **Source field** -- Always set a meaningful `source` when storing. This lets you filter searches later. Example: `source: "project-x"`.

3. **Tags** -- Tag memories by project, topic, or category. Search can filter by tags.

4. **Be explicit with your AI** -- You can tell Claude "store this in the brain" or "don't store this." The AI won't save anything without calling `store_memory`.

5. **CLAUDE.md instructions** -- Add instructions to a project's `CLAUDE.md` like:
   ```
   When working in this project, tag all memories stored in engram
   with "project-x". Only store architectural decisions, not routine code changes.
   ```

---

## Quick Reference

| What | URL (local dev) | URL (production/server) |
|------|-------------|-------------|
| REST API | http://localhost:8000/api/ | https://\<server-ip\>/api/ |
| API docs | http://localhost:8000/api/docs/ | https://\<server-ip\>/api/docs/ |
| MCP endpoint | http://localhost:8080/mcp | https://\<server-ip\>/mcp/ |
| Dashboard | http://localhost:5173 | (needs frontend deploy) |

| Action | Command |
|--------|---------|
| Start infra (dev) | `docker compose up -d` |
| Start Django | `python manage.py runserver` |
| Start MCP | `python -m mcp_server` |
| Stop infra | `docker compose down` |
| Start prod (server) | `docker compose -f docker-compose.prod.yml up -d` |
| View logs | `docker compose logs -f` |
| Check memory count | `curl http://localhost:8000/api/stats/` |

---

## Troubleshooting

**"Embedding service unavailable"** -- Ollama isn't running or the model isn't pulled.
```bash
docker compose ps          # check ollama is up
curl http://localhost:11434 # should return "Ollama is running"
docker exec -it engram-ollama-1 ollama list  # should show nomic-embed-text
```

**"relation core_memory does not exist"** -- Migrations haven't been run.
```bash
python manage.py migrate
```

**Can't connect from another machine** -- Django/MCP need to bind to `0.0.0.0`, not just `localhost`. The dev server does this by default via `ALLOWED_HOSTS = ["*"]` in development settings. For prod, ensure your server IP is in `DJANGO_ALLOWED_HOSTS`.

**Search returns nothing** -- The database might be empty. Check with `curl http://localhost:8000/api/stats/`. Store some test memories first.
