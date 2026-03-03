# Handoff Cycle: Intelligence Layer — Plan Review

- **Phase:** intelligence-layer
- **Type:** plan
- **Started:** 2026-03-03
- **Lead:** claude
- **Reviewer:** codex
- **Reference:** [docs/phases/intelligence-layer.md](../phases/intelligence-layer.md)

---

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Phase 6 (Intelligence Layer) plan created at `docs/phases/intelligence-layer.md`. Summary of the design:

**New Django app `intelligence/`** — no new models, writes to existing `Memory.tags`, `Memory.metadata`, `Memory.importance`, and `Memory.decay_factor` fields.

**Four modules:**
1. `llm_client.py` — shared Ollama chat completion helper (`POST /api/chat`), configurable via `OLLAMA_CHAT_MODEL` setting (default `llama3.2:3b`). Raises `OllamaUnavailableError` for callers to catch.
2. `auto_tagger.py` — extracts 3-8 tags via LLM structured prompt. Falls back to TF-IDF keyword extraction (tokenize → remove stop words → top 5 by frequency). No external NLP dependencies. Merge strategy: union of existing + extracted tags.
3. `entity_extractor.py` — extracts people, projects, organizations, technologies via LLM JSON prompt. Falls back to regex heuristics (capitalized sequences, known tech terms). Stores in `metadata["entities"]`. Merges per category.
4. `memory_decay.py` — pure function: `decay_factor = importance × recency_factor × access_factor × age_penalty`. Recency half-life ~30 days, access saturates at 10, gentle annual age penalty. Clamped `[0.0, 1.0]`.
5. `report_generator.py` — Markdown weekly digest: summary stats, top tags, top entities, most accessed, decay alerts (`< 0.2`).

**Three management commands:**
- `manage.py enrich` — `--id`, `--all`, `--source`, `--tags-only`, `--entities-only`
- `manage.py decay` — `--dry-run`
- `manage.py report` — `--days N`, `--output PATH`

**Service integration:** Optional `AUTO_ENRICH_ON_CREATE` setting (default `False`) in `memory_service.create_memory` — calls `enrich_tags` + `enrich_entities` after save.

**Settings additions:** `OLLAMA_CHAT_MODEL`, `AUTO_ENRICH_ON_CREATE`.

**Tests:** 4 test files covering tagger, entities, decay, and report generation.

**No new dependencies** — uses only `httpx` (already installed), `re`, `collections`, `datetime`.

### Reviewer

**Action:** REQUEST_CHANGES

Plan is close, but there are three blocking gaps to resolve before implementation starts.

**Blocking issues:**
1. **Packaging gap for new Django app**
   - Current setuptools package include filter in `pyproject.toml` is explicit (`openbrain*`, `core*`, `embeddings*`, `mcp_server*`, `api*`).
   - The plan creates a new top-level `intelligence/` package but does not include `pyproject.toml` updates to add `intelligence*`.
   - Without this, install/package flows can omit the new app.

2. **`AUTO_ENRICH_ON_CREATE` failure isolation is not specified**
   - Proposed hook in `memory_service.create_memory` awaits enrichment directly.
   - If enrichment raises (prompt parsing edge case, unexpected runtime error, timeout), memory creation would fail even though enrichment is non-critical.
   - Plan should explicitly require fail-open behavior: create succeeds, enrichment failures are caught/logged.

3. **Decay “ranked retrieval” integration is underspecified**
   - Scope says decay is exposed for ranked retrieval, but file list/approach does not specify where ranking is actually affected (e.g., search SQL/manager/service layer).
   - This needs an explicit decision: either integrate `decay_factor` into retrieval ranking with a concrete implementation target, or narrow scope text to “compute/store/report only”.

**Required changes:**
1. Add `pyproject.toml` to Files with explicit `intelligence*` package include update.
2. Update service-integration section to require fail-open enrichment behavior (`try/except` around auto-enrich, with logging and no create failure).
3. Clarify decay ranking behavior with concrete implementation details and files to modify, or explicitly remove ranked-retrieval claim from scope/success criteria.

Please revise the phase plan and resubmit.

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

All 3 blocking gaps addressed in `docs/phases/intelligence-layer.md`:

1. **Packaging (`pyproject.toml`)**: Added `pyproject.toml` to the Files table with action "Modify" — will add `intelligence*` to the packages include list alongside existing entries (`openbrain*`, `core*`, `embeddings*`, `mcp_server*`, `api*`).

2. **Fail-open auto-enrichment**: Updated the Service Integration section. The auto-enrich hook now wraps both `enrich_tags` and `enrich_entities` in a `try/except Exception` block with `logger.warning(..., exc_info=True)`. Memory creation always succeeds regardless of enrichment outcome.

3. **Decay scope narrowed**: Updated Scope bullet from "Expose as a queryset method for ranked retrieval" to "Compute and store only; no changes to search ranking in this phase." Decay scoring is strictly compute/store/report — no modifications to `core/managers.py`, `search_service.py`, or any retrieval paths. Integrating decay into search ranking can be a follow-up if desired.

### Reviewer

**Action:** APPROVE

Approved. Round 2 addresses all prior blockers:
- `pyproject.toml` modification is explicitly included to add `intelligence*` package discovery.
- Service integration now requires fail-open auto-enrichment with `try/except` + logging so memory creation does not fail on enrichment errors.
- Decay scope is explicitly narrowed to compute/store/report only, with no retrieval-ranking changes in this phase.

No additional blocking plan issues identified.

---

<!-- CYCLE_STATUS -->
```
READY_FOR: lead
ROUND: 2
STATE: approved
```
