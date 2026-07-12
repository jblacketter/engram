# Shared Brain Revival — Handoff Document

**Date:** 2026-07-11
**Author:** Claude (analysis session in harness-engineering; portfolio survey + AgentOS comparison)
**Purpose:** Context handoff for a new session working in `~/Projects/engram`. Read this first; it explains why engram is being revived, what state it's in, and what to build next.

---

## 1. The goal

Jack wants a portable, personal "shared brain" / agent OS: identity files, persistent context/memory, skills, and connections that any agentic tool (Claude Code, Cursor, ollama-based agents, etc.) can onboard against in minutes — and that survives switching tools. Inspiration: https://aidbagentos.ai/ (AgentOS).

New enabling factor: Jack's Windows machine with a GPU is now actively running **Ollama** — engram's default embedding provider (`nomic-embed-text`) runs free and local on it.

## 2. What AgentOS is (and isn't)

AgentOS is **not software** — it's a free, self-paced 12-project curriculum in four phases. Everything it produces is plain text files. Its prescribed components:

| AgentOS pillar | What it is |
|---|---|
| Identity files | Who you are, preferences |
| Context files | Knowledge/expertise |
| Skills | Repeated workflows |
| Memory | Persist info across sessions (as text files) |
| Connections | Access to external tools/systems |
| Automations | Autonomous operation |

Build order: **Phase 1** identity + context → **Phase 2** skills, memory, connections → **Phase 3** first agent → **Phase 4** agent team + automations + playbook. Tool-agnostic by design ("it's all text files").

**Decision made:** Do not start a new project following AgentOS from scratch. Use AgentOS as the *blueprint and build order*; use engram as the *memory infrastructure* — engram's memory pillar (vector DB + hybrid search + MCP) is far beyond AgentOS's flat-text-file memory. The only AgentOS pillar engram lacks is identity/onboarding, which is cheap to add.

## 3. State of engram (as surveyed 2026-07-11)

Engram is ~90% complete and was the strongest candidate across the entire `~/Projects` portfolio.

**What it is:** self-hosted semantic memory layer for any MCP-compatible AI tool. Notes, conversations, documents, and web pages stored as vector embeddings in Postgres you control.

**Architecture (verified from source):**
- **Storage:** PostgreSQL 16 + pgvector (768-dim, HNSW cosine index); `memories` table with content, embedding, source, tags JSONB, metadata JSONB, importance, decay_factor, access_count (`core/models.py`). Full-text `tsvector` column maintained by trigger + GIN index.
- **Search:** hybrid — vector similarity fused with Postgres full-text via Reciprocal Rank Fusion (`core/services/search_service.py`).
- **API:** Django 5.1 + DRF; CRUD, search, ingest, stats; OpenAPI at `/api/docs/`; token bearer auth + throttling.
- **MCP server:** FastMCP 2.0, separate process (`mcp_server/`), 10 tools: `store_memory`, `search_brain`, `find_related`, `list_recent_memories`, `store_from_url`, `ingest_file`, `get_stats`, etc. MCP and REST share the same `core/services/` layer.
- **Embeddings:** pluggable registry — Ollama (`nomic-embed-text`, default) or OpenRouter fallback (`embeddings/`).
- **Intelligence:** LLM auto-tagger, entity extractor, memory-decay scoring, report generator (`intelligence/`).
- **Ingestion:** PDF/DOCX/TXT/Markdown, URL scraper, batch processor, Obsidian vault importer (`ingestion/`).
- **Frontend:** React 18 + TypeScript + Vite + Tailwind SPA — Home, Search, Analytics, Graph (D3), Settings.
- **Infra:** Dockerfiles (app + MCP), dev/prod docker-compose, nginx TLS, gunicorn/uvicorn. Python 3.12, ~3,000 LOC backend.

**Maturity signals:** tagged v1.0.0 (2026-04-04), published to PyPI as `engram-semantic`, 287 backend tests across 22 files, frontend Vitest tests, zero TODO/FIXME/stub markers in backend, clean working tree. Last commit 2026-05-03 added **tag-based domain scoping** (`domain:<name>`) so one instance serves multiple tools/projects without cross-contamination. Note: `docs/roadmap.md` "Not Started" labels are stale planning artifacts — the code exists and is tested.

**Known gaps (the remaining ~10%):**
1. **No identity/onboarding layer** — engram is memory + retrieval only. No "who you are" files, no bootstrap for onboarding a new agent in minutes. This is the main new work.
2. **Single-user auth only** — global API key; README names residual unscoped surfaces that leak across domains: `GET /api/memories/`, `/stats/`, `/tags/`, MCP `get_memory`/`get_stats`, dashboard.
3. ~~Minor frontend TODOs in `MemoryForm.tsx` and `SearchPage.tsx`.~~
   *Correction (2026-07-11, revive-and-verify): not substantiated — both
   files are fully implemented; there are zero TODO/FIXME/stub markers in
   backend or frontend.*
4. PyPI package never smoke-tested end-to-end from a clean install.
   *Update (2026-07-11): verified worse than untested — the wheel ships no
   `manage.py`, console script, or frontend, so the documented pip install
   path cannot work. Decision: PyPI deprioritized; source/Docker is the
   supported path.*

## 4. Companion projects (pillar mapping)

These existing, finished projects of Jack's map onto the remaining AgentOS pillars — integrate rather than rebuild:

| Pillar | Project | State |
|---|---|---|
| Memory | **engram** (this repo) | ~90%, v1.0 released |
| Identity + permissions | **~/Projects/agent-gate** (PyPI: `agent-gatekeeper`) | Complete. Cryptographic agent identity, deny-by-default YAML permission policies, human-approval escalation. |
| Multi-agent orchestration / handoff | **~/Projects/tagteam** (PyPI, v0.7.1) | Jack's most actively maintained project (commits through 2026-07-02). Structured AI-to-AI handoffs, shared state in `handoff-state.json` + JSONL rounds. Several of Jack's repos already use its workflow. |
| Connections | `~/Projects/integration-grafana` (Fly.io logs MCP), `~/Projects/mcp_debug_tool` (Chrome DevTools MCP), Aegis (`~/Projects/QA`) | Pluggable MCP servers. Aegis is already designed to write into engram (see domain-scoping README references to `aegis`/`qaagent`). |

Other notes from the portfolio survey:
- **~/Projects/unified** ("AI Control Plane": registry/router/memory/evaluator/audit) overlaps but its memory is unfinished JSON files with a reserved-but-unwired embedding field. Borrow ideas (router, audit log), don't build on it.
- **~/Projects/brainstormer** contains Jack's own strategy doc on triaging/monetizing the portfolio — worth rereading for prioritization context.
- **~/Projects/agent-ledger** (PyPI: `agent-audit-trail`) — hash-chained audit logs; optional governance bolt-on later.

## 5. Recommended plan

Follow the AgentOS phase order, with engram as the memory backend:

**Phase A — Revive & verify (first session):**
1. Smoke-test the stack end-to-end: docker-compose up, Postgres + pgvector, Ollama embeddings (point at the Windows GPU box or local), store → search → find_related round-trip via a real MCP client (Claude Code).
2. Verify the PyPI `engram-semantic` install path works clean.
3. Decide: keep tag-based domain scoping vs. add a hard `workspace` column; close the unscoped read surfaces either way.

**Phase B — Identity/onboarding layer (the new work):**
4. Add an AgentOS-style identity/context file structure (plain markdown, portable) that lives alongside engram — e.g. `identity.md`, `context/*.md` — plus an onboarding bootstrap (a doc or MCP tool like `onboard_agent`) that gives any new agent: who Jack is, how to connect to engram, which domain to write to, and house rules. Target: new agent productive in minutes.
5. Consider `store_memory` conventions for identity vs. episodic memory (tags or memory types).

**Phase C — Integrate pillars:**
6. Wire agent-gate for per-agent identity/permissions (also addresses the multi-user auth gap).
7. Use tagteam for multi-agent workflows on top; register Aegis and the MCP connectors as connections.

**Phase D — Polish:**
8. Finish the two frontend TODOs; automations (scheduled ingestion, decay runs) last.

## 6. First-session checklist

- [ ] Read this doc, then `README.md` and `docs/roadmap.md` (remember: roadmap status labels are stale).
- [ ] Confirm environment: Postgres 16 + pgvector available, Ollama reachable, `nomic-embed-text` pulled.
- [ ] Run backend test suite (287 tests) to confirm baseline.
- [ ] Run the Docker stack; do a live store/search round-trip through the MCP server from Claude Code.
- [ ] Report what broke (if anything), then start Phase B design: the identity/onboarding layer.
