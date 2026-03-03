# Option B: Supabase Cloud Setup

This approach uses Supabase's free tier as your hosted database and runs your MCP server locally or as an edge function. This is the approach Nate Jones uses in his Open Brain concept — the paid guide covers his specific implementation, but here's how to build the same thing yourself.

## Step 1: Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a free account.
2. Create a new project. Note your project URL and API keys.
3. The free tier gives you a 500MB PostgreSQL database — more than enough for tens of thousands of memories.

## Step 2: Enable pgvector and Create Schema

In the Supabase SQL editor, run the schema setup script:

> See [`sql/schema.sql`](../sql/schema.sql) for the full SQL schema, including the `memories` table, HNSW index, and `search_memories` function.

The vector dimension (1536) matches OpenAI's `text-embedding-3-small` model. If you use a different embedding model, adjust this number accordingly. Common dimensions:

- **768** — many open-source models
- **1024** — Cohere
- **1536** — OpenAI small
- **3072** — OpenAI large

## Step 3: Build Your MCP Server

Create a Python MCP server that connects to Supabase. This is the bridge between your AI tools and your brain.

Project structure:

```
open-brain-server/
├── server.py          # MCP server (FastMCP)
├── embedder.py        # Embedding generation
├── requirements.txt   # Dependencies
└── .env               # Configuration
```

The source files are extracted to the project root:

- [`server.py`](../server.py) — the MCP server itself
- [`embedder.py`](../embedder.py) — handles turning text into vectors
- [`requirements.txt`](../requirements.txt) — dependencies
- `.env` — configuration (create from template below)

### .env template

```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=your_service_role_key
OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxxxxxx
EMBEDDING_MODEL=openai/text-embedding-3-small
```

## Step 4: Run and Connect

```bash
# Install dependencies
pip install -r requirements.txt

# Test the server locally
python server.py
```

Configure Claude Desktop to connect to it (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "open-brain": {
      "command": "python",
      "args": ["/path/to/open-brain-server/server.py"],
      "env": {
        "SUPABASE_URL": "https://xxxxx.supabase.co",
        "SUPABASE_KEY": "your_service_role_key",
        "OPENROUTER_API_KEY": "sk-or-xxxxxxxx"
      }
    }
  }
}
```
