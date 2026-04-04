# Docker Setup (Engram)

Run Engram locally using Docker Compose. Everything runs on your machine — your data never leaves it.

## Prerequisites

- Docker Desktop installed and running
- Git
- ~4 GB of free RAM (Ollama needs memory for embedding models)

## Step 1: Clone and Configure

```bash
git clone https://github.com/jblacketter/engram.git
cd engram
cp .env.example .env
```

The defaults in `.env.example` work for local development — no edits needed for the dev flow.

For **production**, update these values in `.env`:

```bash
DJANGO_SECRET_KEY=<generate-a-random-string>
DJANGO_SETTINGS_MODULE=engram.settings.production
DJANGO_ALLOWED_HOSTS=<server-ip>,localhost
POSTGRES_PASSWORD=<strong-random-password>
```

## Step 2: Launch with Docker Compose

### Development

```bash
docker compose up -d
```

This starts two containers:

| Container | Port | Purpose |
|-----------|------|---------|
| db | 5432 | PostgreSQL 16 with pgvector extension |
| ollama | 11434 | Ollama for local embeddings |

Then pull the embedding model and run Django + MCP locally:

```bash
pip install -e ".[dev]"
docker compose exec ollama ollama pull nomic-embed-text
python manage.py migrate
python manage.py runserver        # REST API on :8000
python -m mcp_server              # MCP server on :8080
```

### Production

```bash
docker compose -f docker-compose.prod.yml up -d
```

This starts five containers:

| Container | Port | Purpose |
|-----------|------|---------|
| nginx | 80, 443 | Reverse proxy with TLS |
| django | 8000 (internal) | REST API (Gunicorn) with OpenAPI docs at `/api/docs/` |
| mcp | 8080 (internal) | MCP server (FastMCP) for AI tool connections |
| db | 5432 (internal) | PostgreSQL 16 with pgvector |
| ollama | 11434 (internal) | Ollama for local embeddings |

Verify everything is running:

```bash
docker compose -f docker-compose.prod.yml ps
# All five containers should show "running" (healthy)

# Test the API (nginx redirects HTTP to HTTPS; use -k for self-signed certs)
curl -k https://localhost/api/health/
```

## Step 3: Pull the Embedding Model (Production)

The dev flow above already pulls the model. For production:

```bash
docker compose -f docker-compose.prod.yml exec ollama ollama pull nomic-embed-text
```

## Step 4: Connect Claude Desktop

Edit your Claude Desktop MCP config file:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

**Development** (Django + MCP running locally):
```json
{
  "mcpServers": {
    "engram": {
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

**Production** (Docker Compose with nginx — MCP is proxied through nginx, not exposed directly):
```json
{
  "mcpServers": {
    "engram": {
      "url": "https://localhost/mcp/"
    }
  }
}
```
Replace `localhost` with your server IP for remote access.

Restart Claude Desktop. You should see the Engram tools available in the MCP tools menu (the hammer icon).

## Step 5: Connect Claude Code

**Development:**
```bash
claude mcp add engram http://localhost:8080/mcp
```

**Production:**
```bash
claude mcp add engram https://<server-ip>/mcp/
```

## Step 6: Test It

In Claude Desktop or Claude Code, try:

> "Store this memory: I'm building a personal knowledge system using PostgreSQL and pgvector. My goal is to have all my AI tools share context."

Then in a new conversation:

> "Search my memories for anything about knowledge systems."

If it returns your stored memory, everything is working.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| pgvector extension not found | The `pgvector/pgvector:pg16` image includes it. Run `docker compose down -v && docker compose up -d` to rebuild. |
| Ollama model not found | Run `ollama pull nomic-embed-text` (or exec into the container for prod). |
| MCP connection refused | Check that port 8080 is accessible: `curl http://localhost:8080/mcp` |
| Django migration errors | Run `docker compose exec django python manage.py migrate` |
