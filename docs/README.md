# Build Your Own Open Brain

**A Personal Semantic Memory System for AI**

PostgreSQL + pgvector + MCP + Embeddings

---

## 1. What Is an Open Brain?

Every AI chat you start begins from zero. Claude, ChatGPT, Cursor — none of them remember who you are, what you're working on, or what you've discussed before. An Open Brain solves this by creating a personal semantic memory system that any AI tool can read from and write to through a single open protocol (MCP).

Think of it as a shared long-term memory layer that sits between you and all your AI tools. When you capture a thought, note, or piece of information, it gets automatically embedded as a vector, tagged with metadata, and stored in a database. Any MCP-compatible AI client can then search this database by meaning — not just keywords — to retrieve relevant context.

### Core Principles

- **You own your data:** Everything lives in a PostgreSQL database you control — no SaaS middlemen, no vendor lock-in.
- **Tool-agnostic:** Any AI client that supports MCP (Claude Desktop, Claude Code, Cursor, Windsurf, custom apps) can connect.
- **Semantic search:** Content is stored as vector embeddings, so search works by meaning, not exact keywords.
- **Near-zero cost:** Self-hosted with free-tier embedding APIs, this runs at roughly $0.10–$0.30/month.
- **Automatic enrichment:** Topics, entities, and tags are extracted automatically when you store information.

## 2. Architecture Overview

The system has three layers:

| Layer | Purpose | Technology |
|-------|---------|------------|
| Storage | Persistent data + vector similarity search | PostgreSQL + pgvector |
| Application | Embedding generation, entity extraction, tagging, analytics | Python (FastAPI) |
| Interface | Protocol bridge for AI tools + human dashboard | FastMCP (MCP server) + REST API + Streamlit |

### How Data Flows

When you (or an AI acting on your behalf) stores a thought:

1. Text is sent to the MCP server or REST API.
2. The application layer generates a vector embedding via your chosen provider (OpenRouter, OpenAI, Ollama, etc.).
3. Automatic entity extraction identifies people, projects, topics, and tags.
4. The text, embedding vector, and metadata are stored in PostgreSQL with pgvector.
5. When any AI client needs context, it queries the MCP server, which performs a cosine similarity search against all stored embeddings to find semantically relevant memories.

### Component Diagram

```
AI Clients (Claude, Cursor, etc.)
        │
        │  MCP Protocol (stdio or HTTP)
        ▼
┌───────────────────────────────────┐
│  MCP Server (FastMCP :8080)       │
│  REST API  (FastAPI  :8000)       │
│  Dashboard (Streamlit :8501)      │
└───────────────┬───────────────────┘
                │
    ┌───────────┴────────────┐
    │  Application Layer     │
    │  • Embedder            │ → OpenRouter / OpenAI / Ollama
    │  • Entity Extractor    │
    │  • Auto-Tagger         │
    │  • Analytics           │
    └───────────┬────────────┘
                │
    ┌───────────┴────────────┐
    │  PostgreSQL + pgvector │  (port 5432)
    │  • memories table      │
    │  • vector index (HNSW) │
    └────────────────────────┘
```

## 3. Choose Your Approach

There are two main ways to build this. Choose based on your comfort level and needs:

| | Option A: Docker (Local) | Option B: Supabase (Cloud) |
|---|---|---|
| **Difficulty** | Easier — just `docker compose up` | Moderate — more manual setup |
| **Cost** | $0 (runs on your machine) | $0 on free tier (500MB DB) |
| **Privacy** | 100% local, nothing leaves your machine | Data on Supabase servers |
| **Access** | Only from your local network | Accessible from anywhere |
| **Maintenance** | You manage Docker containers | Supabase manages infra |
| **Best for** | Personal use, privacy-focused | Multi-device, always-on access |

- [Option A: Local Docker Setup](setup-docker.md)
- [Option B: Supabase Cloud Setup](setup-supabase.md)

## Further Reading

- [Embedding Providers](embedding-providers.md)
- [Connecting Multiple AI Tools](connecting-clients.md)
- [Database Schema Deep Dive](schema.md)
- [Daily Workflows and Capture Patterns](workflows.md)
- [Extending Your Brain](extending.md)
- [Troubleshooting](troubleshooting.md)
- [Resources and Links](resources.md)
