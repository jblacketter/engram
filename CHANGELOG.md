# Changelog

All notable changes to Engram will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Tag-based domain scoping** — A single Engram instance can now host
  memories from multiple domains (e.g. QA tooling and personal use) without
  cross-contamination, using the `domain:<name>` tag convention. See the
  README section "Scoping memories across domains" for the full convention,
  the list of scoped read surfaces, and the named residual-surface list.
- `find_related` MCP tool accepts optional `tags` and `source` filters,
  matching the behavior of `search_brain`. Default behavior (no filters) is
  preserved.
- `list_recent_memories` MCP tool accepts an optional `tags` filter (in
  addition to the existing `source` filter).
- `memory_service.list_recent()` accepts a `tags` parameter, applying the
  same JSONB containment match (`tags @> [...]`) used by hybrid search.

### Changed
- Self-exclusion in `find_related` is now verified under filter combinations
  (the queried memory is never returned even when matching the requested
  `tags`/`source`).

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
