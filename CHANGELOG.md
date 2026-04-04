# Changelog

All notable changes to Engram will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-04-04

### Added
- **Hybrid Search** — Vector similarity (pgvector HNSW) + PostgreSQL full-text BM25, fused via Reciprocal Rank Fusion
- **MCP Server** — FastMCP server for integration with Claude Desktop, Claude Code, Cursor, Windsurf, and any MCP-compatible client
- **REST API** — Full CRUD + search with OpenAPI documentation at `/api/docs/`
- **Multi-format Ingestion** — Ingest PDFs, DOCX, TXT, Markdown, URLs, and Obsidian vaults
- **Auto-enrichment** — LLM-powered tagging, entity extraction, and memory report generation
- **Memory Decay** — Automatic relevance management: unused memories fade, important ones persist
- **React Dashboard** — Browse, search, and manage memories through a web UI
- **Pluggable Embeddings** — Ollama (default, free, local) or OpenRouter (cloud fallback)
- **Docker Compose** — One-command deployment for both development and production
- **API Authentication** — Token-based auth with throttling for production use
- **MCP Authentication** — Secure MCP connections with API key verification
- **Batch Processing** — Bulk ingestion for large document collections
