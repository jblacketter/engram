# Option A: Local Docker Setup (Open Brain)

This uses the open-source [benclawbot/open-brain](https://github.com/benclawbot/open-brain) project on GitHub. It runs everything in Docker containers on your machine.

## Prerequisites

- Docker Desktop installed and running
- Git
- An OpenRouter account (free tier works) — sign up at [openrouter.ai](https://openrouter.ai)
- ~2 GB of free RAM

## Step 1: Clone and Configure

```bash
git clone https://github.com/benclawbot/open-brain.git
cd open-brain
cp .env.example .env
```

Edit the `.env` file with your settings:

```bash
# .env file
DB_PASSWORD=your_secure_password_here
OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxxxxx

# Optional: Telegram notifications
# TELEGRAM_BOT_TOKEN=your_bot_token
# TELEGRAM_CHAT_ID=your_chat_id
```

### Get your OpenRouter API key:

1. Go to [openrouter.ai](https://openrouter.ai) and create a free account.
2. Navigate to **Keys** in the dashboard.
3. Create a new key. The free tier gives you access to embedding models at no cost.

## Step 2: Launch with Docker Compose

```bash
docker compose up -d
```

This starts four containers:

| Container | Port | Purpose |
|-----------|------|---------|
| postgres | 5432 | PostgreSQL database with pgvector extension |
| api | 8000 | REST API (FastAPI) for HTTP access |
| mcp | 8080 | MCP server (FastMCP) for AI tool connections |
| dashboard | 8501 | Streamlit web UI for browsing your brain |

Verify everything is running:

```bash
docker compose ps
# All four containers should show "running"

# Test the API
curl http://localhost:8000/health
```

## Step 3: Connect Claude Desktop

Edit your Claude Desktop MCP config file:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

Add the open-brain MCP server:

```json
{
  "mcpServers": {
    "open-brain": {
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

Restart Claude Desktop. You should see the Open Brain tools available in the MCP tools menu (the hammer icon).

## Step 4: Test It

In Claude Desktop, try saying:

> "Store this memory: I'm building a personal knowledge system using PostgreSQL and pgvector. My goal is to have all my AI tools share context."

Then in a new conversation:

> "Search my brain for anything about knowledge systems."

If it returns your stored memory, everything is working.

## Step 5: CLI Usage

The project also includes CLI commands for direct interaction:

```bash
# Store a memory
python -m openbrain store "Meeting with Sarah about Q2 roadmap" \
  --source "meeting_notes" --tags "planning,q2"

# Search semantically
python -m openbrain search "quarterly planning"

# View stats
python -m openbrain stats

# Generate a weekly report
python -m openbrain report
```
