# Phase: Revive and Verify

## Summary

Engram shipped v1.0.0 in April and has sat idle since early May. This phase
brings the stack back up on the Mac, re-establishes the test baseline, and
proves the full store → search → recall loop live from Claude Code over MCP.
It also lands the small documentation corrections surfaced by the 2026-07-11
revival analysis (see `SHARED_BRAIN_REVIVAL.md` and the Revival Roadmap
section of `docs/roadmap.md`). No new features.

Decisions already locked with the human (2026-07-11), recorded here so the
reviewer has context:

- **Deploy target:** Mac now for development and verification. Windows/WSL2
  LAN hosting is the intended personal deployment (not optional); it is
  scheduled in `automations-and-polish`, after the daily workflow is proven.
- **Scoping:** per-agent API keys + soft domain tags for authorization
  (implemented later in `agent-scoping`, not here). Whether soft tags remain
  the long-term *project* model is a separate question: `agent-scoping`
  includes an explicit decision checkpoint on first-class
  projects/workspaces, informed by daily-driver experience.
- **PyPI:** deprioritized — source/Docker is the supported install path.
  Documentation-only fix in this phase; no packaging work.
- **Usage model:** ambient recall via Claude Code hooks, with
  suggestion-first capture (session proposes, user confirms) during
  development and automatic capture as the trusted end-state; plus MCP
  resources for canonical identity/project context and MCP prompts for
  recurring workflows. Built in `daily-driver`/`identity-and-onboarding`,
  not here.

## Scope

In scope:

1. **Environment up.** Start Postgres 16 + pgvector via `docker-compose.yml`.
   Use the Mac's **native** Ollama (already running on :11434) instead of the
   compose `ollama` service to avoid a port collision — start only the `db`
   service. Pull `nomic-embed-text` (~270MB, not currently present locally).
2. **Python environment repair (known first blocker).** The existing `.venv`
   runs a native arm64 Python 3.12.11 but contains x86_64 NumPy extension
   modules (verified: `numpy/linalg/*.so` are `Mach-O x86_64` while the
   interpreter is arm64), so pytest fails before test collection. Recreate
   the venv with a native ARM Python 3.12, install `.[dev]`, and verify
   interpreter and compiled-package architecture match before running tests.
3. **Test baseline.** Run the full backend suite (287 tests; requires
   `DJANGO_SECRET_KEY` set and pgvector-enabled Postgres on :5432). Fix the
   one known-broken test, `TestGetStats::test_get_stats_with_data`
   (pre-existing failure on main, not a regression). Run the frontend vitest
   suite (2 files).
4. **Live MCP round-trip.** Start Django (`runserver`) and the MCP server
   (`python -m mcp_server`), connect Claude Code
   (`claude mcp add --transport http engram http://localhost:8080/mcp` —
   without `--transport http` the CLI registers a broken stdio server, as
   discovered during implementation), and verify:
   `store_memory` → `search_brain` finds it semantically → `find_related`
   returns sensible neighbors → `list_recent_memories` with a
   `domain:<name>` tag filter behaves per the scoping convention.
5. **Documentation corrections:**
   - README Quick Start: make git-clone + Docker the primary path; note the
     PyPI wheel does not ship `manage.py`/frontend and is suitable only for
     importing the Python modules (the current
     `pip install engram-semantic` → `python manage.py migrate` sequence
     cannot work from the wheel).
   - Document prod-compose boot requirements: `DJANGO_SECRET_KEY` and
     `DJANGO_ALLOWED_HOSTS` must be present in `.env` (settings read them
     with no defaults; compose files do not set them). `CORS_ALLOWED_ORIGINS`
     has an empty default — it doesn't block boot but should be set for the
     intended browser/LAN configuration. Add a short preflight note to
     `docs/setup-docker.md`.
   - Correct stale claims: `SHARED_BRAIN_REVIVAL.md`'s "frontend TODOs in
     MemoryForm/SearchPage" is unsubstantiated — both are complete.
6. **Housekeeping.** Commit the roadmap status updates (phases 1–8 →
   Complete, new Revival Roadmap section), `SHARED_BRAIN_REVIVAL.md`, and
   this phase doc. Append the four locked decisions to
   `docs/decision_log.md`.

Out of scope (later phases): hooks/skills (`daily-driver`), identity files
and `onboard_agent` (`identity-and-onboarding`), per-agent keys and closing
unscoped read surfaces (`agent-scoping`), scheduler/decay automation, Docker
image pinning, config-driven embedding registry, Windows deployment
(`automations-and-polish`).

## Technical Approach

- `docker compose up -d db` — only the database; native Ollama serves
  embeddings at `http://localhost:11434` (matches the `OLLAMA_BASE_URL`
  default, so no `.env` change needed).
- `ollama pull nomic-embed-text`.
- Venv rebuild: remove `.venv`, recreate with a native ARM Python 3.12
  (pyenv 3.12.11 is arm64 — verified), `pip install -e ".[dev]"`. Verify
  before pytest: `python -c "import platform; print(platform.machine())"`
  → `arm64`, and `file` on a NumPy `.so` → `arm64` (or simply
  `python -c "import numpy"` succeeding, since the current failure mode is
  an architecture ImportError).
- `.env` from `.env.example` if absent; ensure `DJANGO_SECRET_KEY` is set
  (base settings raise `KeyError` without it).
- `python manage.py migrate` then `pytest`. Triage failures: expected
  categories are environment drift (dependency versions since May) and the
  known stats test. Anything structural gets fixed and noted in the impl
  submission.
- Stats test fix: diagnose `TestGetStats::test_get_stats_with_data` first;
  fix the test if it encodes a wrong expectation, fix the code if the stats
  service is actually wrong.
- MCP verification is manual but scripted in the impl submission (exact tool
  calls and observed results recorded), so the reviewer can replay it.
- Doc edits are plain markdown; no code changes outside the possible stats
  fix and any environment-drift fixes the test run forces.

## Files

- `docs/roadmap.md` — already updated (commit)
- `docs/phases/revive-and-verify.md` — this plan
- `docs/decision_log.md` — four new decision entries
- `README.md` — Quick Start / install-path corrections
- `docs/setup-docker.md` — prod env preflight note
- `SHARED_BRAIN_REVIVAL.md` — correct the frontend-TODO claim; commit
- `tests/test_mcp_tools.py` (or the stats service under `core/`/
  `mcp_server/tools/stats.py`) — stats test fix, location depends on
  diagnosis
- `.env` (local only, not committed)

## Success Criteria

1. `docker compose up -d db` + native Ollama + `nomic-embed-text` pulled;
   `python manage.py migrate` clean.
2. `.venv` rebuilt on native ARM Python 3.12; interpreter and compiled
   packages verified arm64 (`import numpy` succeeds) before the test run.
3. Backend: full pytest suite green, including
   `TestGetStats::test_get_stats_with_data`. Frontend: vitest green.
4. Live round-trip from a real Claude Code session over MCP: store, search
   (semantic hit), find_related, domain-tag-filtered list — all verified and
   transcribed in the impl submission.
5. README no longer documents a broken install path; prod env requirements
   documented.
6. Roadmap, revival doc, phase doc, and decision log committed intentionally
   on the active branch per the repository workflow (branch-then-merge if
   preferred; no requirement to commit directly to `main`).
