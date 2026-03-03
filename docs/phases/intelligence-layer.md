# Phase 6: Intelligence Layer

## Summary

Automatic enrichment of memories with extracted tags, named entities, and time-decay scoring, plus a weekly digest report. All enrichment runs through Ollama LLM with deterministic fallbacks so the system works even when Ollama is unavailable.

## Scope

- **Auto-tagger** — extract 3-8 concise tags from memory content via Ollama chat completion; falls back to TF-IDF keyword extraction.
- **Entity extractor** — identify people, projects, organizations, and technologies via Ollama structured-output prompt; falls back to regex/heuristic NER.
- **Memory decay** — score each memory: `effective_score = importance × recency_factor × access_factor`. Update `decay_factor` column. Compute and store only; no changes to search ranking in this phase.
- **Report generator** — weekly digest: new memory count, top tags, top entities, most-accessed, most-decayed.
- **Management commands** — `manage.py enrich`, `manage.py decay`, `manage.py report`.
- **Service integration** — optionally auto-enrich on create in `memory_service.create_memory`.

## Technical Approach

### Django App: `intelligence`

New Django app registered in `INSTALLED_APPS`. No models — enrichment writes to existing `Memory.tags`, `Memory.metadata`, `Memory.importance`, and `Memory.decay_factor` fields.

### Module Layout

```
intelligence/
├── __init__.py
├── apps.py
├── auto_tagger.py          # Tag extraction
├── entity_extractor.py     # Named entity recognition
├── memory_decay.py         # Decay scoring
├── report_generator.py     # Weekly digest
├── llm_client.py           # Shared Ollama chat completion helper
└── management/
    └── commands/
        ├── enrich.py       # manage.py enrich [--id UUID] [--all] [--source SRC]
        ├── decay.py        # manage.py decay [--dry-run]
        └── report.py       # manage.py report [--days 7] [--output PATH]
```

### `llm_client.py` — Shared Ollama Chat Helper

Thin wrapper around `httpx.AsyncClient` calling `POST {OLLAMA_BASE_URL}/api/chat` with a configurable model. Parses JSON from the response content. Used by both auto-tagger and entity extractor.

```python
async def chat_json(system_prompt: str, user_content: str, model: str | None = None) -> dict:
    """Send a chat completion to Ollama and parse JSON from the response."""
```

Settings:
- `OLLAMA_CHAT_MODEL` — new setting, default `"llama3.2:3b"` (small, fast for extraction tasks)
- Timeout: 30 seconds
- On connection failure: raises `OllamaUnavailableError` so callers can fall back

### `auto_tagger.py`

```python
async def extract_tags(content: str) -> list[str]:
    """Extract 3-8 tags from content. Tries Ollama LLM, falls back to TF-IDF."""
```

**LLM strategy:** System prompt instructs the model to return a JSON array of 3-8 lowercase single-word or hyphenated tags. Parse and validate (lowercase, strip, deduplicate, limit to 8).

**TF-IDF fallback:** When Ollama is unavailable, tokenize content with `re.findall(r"\b[a-z]{3,}\b", content.lower())`, remove English stop words (hardcoded set of ~150), count frequencies, return top 5 by TF score. No external NLP dependencies.

```python
async def enrich_tags(memory_id: UUID) -> list[str]:
    """Load memory, extract tags, merge with existing tags, save. Returns final tag list."""
```

Merge strategy: union of existing tags and extracted tags. Never removes user-set tags.

### `entity_extractor.py`

```python
async def extract_entities(content: str) -> dict[str, list[str]]:
    """Extract named entities. Returns {"people": [...], "projects": [...], "organizations": [...], "technologies": [...]}."""
```

**LLM strategy:** System prompt requests a JSON object with four keys. Validate each value is a list of strings.

**Fallback:** Regex heuristics — capitalized multi-word sequences for people/orgs, known tech terms list for technologies. Returns best-effort dict.

```python
async def enrich_entities(memory_id: UUID) -> dict[str, list[str]]:
    """Load memory, extract entities, store in metadata['entities'], save. Returns entities dict."""
```

Storage: `memory.metadata["entities"] = {"people": [...], ...}`. Merges with existing entities (union per category).

### `memory_decay.py`

```python
def compute_decay_factor(
    importance: float,
    created_at: datetime,
    last_accessed: datetime | None,
    access_count: int,
    now: datetime | None = None,
) -> float:
    """Pure function: returns decay_factor between 0.0 and 1.0."""
```

Formula:
```
age_days = (now - created_at).total_seconds() / 86400
recency_days = (now - (last_accessed or created_at)).total_seconds() / 86400

recency_factor = 1.0 / (1.0 + recency_days / 30.0)      # half-life ~30 days
access_factor = min(1.0, 0.5 + access_count * 0.05)       # saturates at 10 accesses
age_penalty = 1.0 / (1.0 + age_days / 365.0)              # gentle annual decay

decay_factor = importance * recency_factor * access_factor * age_penalty
```

Clamped to `[0.0, 1.0]`. High-importance, recently-accessed memories decay slowly.

```python
async def run_decay(dry_run: bool = False) -> list[dict]:
    """Recompute decay_factor for all memories. Returns list of {id, old, new} diffs."""
```

Uses `sync_to_async` to iterate all memories, compute new decay_factor, bulk-update changed rows. Returns summary of changes.

### `report_generator.py`

```python
async def generate_report(days: int = 7) -> str:
    """Generate a Markdown weekly digest covering the last N days."""
```

Report sections:
1. **Summary** — total memories, new in period, sources breakdown
2. **Top Tags** — most common tags across new memories
3. **Top Entities** — most mentioned people/projects/tech (from `metadata["entities"]`)
4. **Most Accessed** — top 5 by `access_count` in period
5. **Decay Alerts** — memories with `decay_factor < 0.2` that might need review

Returns Markdown string. Management command can write to file or stdout.

### Management Commands

**`manage.py enrich`**
- `--id UUID` — enrich a single memory
- `--all` — enrich all memories missing `metadata["entities"]` or with empty tags
- `--source SOURCE` — enrich all memories from a specific source
- `--tags-only` / `--entities-only` — limit enrichment scope
- Prints progress: `Enriched 42/100 memories`

**`manage.py decay`**
- `--dry-run` — compute but don't save; print changes
- Prints summary: `Updated 150 memories. Avg decay: 0.65 → 0.62`

**`manage.py report`**
- `--days N` — period (default 7)
- `--output PATH` — write to file (default: stdout)

### Service Integration

Add optional auto-enrichment hook in `memory_service.create_memory`. **Fail-open behavior is required** — enrichment failures must never cause memory creation to fail.

```python
# At end of create_memory, after embed + save:
if getattr(settings, "AUTO_ENRICH_ON_CREATE", False):
    try:
        from intelligence.auto_tagger import enrich_tags
        from intelligence.entity_extractor import enrich_entities
        await enrich_tags(memory.id)
        await enrich_entities(memory.id)
    except Exception:
        logger.warning("Auto-enrichment failed for memory %s", memory.id, exc_info=True)
```

Guarded by `AUTO_ENRICH_ON_CREATE` setting (default `False`) so it doesn't slow creates or break when Ollama chat model is unavailable. Users opt in. The `try/except` with logging ensures the memory is always returned successfully regardless of enrichment outcome.

### Settings Additions

```python
# Intelligence Layer
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2:3b")
AUTO_ENRICH_ON_CREATE = os.getenv("AUTO_ENRICH_ON_CREATE", "").lower() in ("1", "true", "yes")
```

## Files

| File | Action | Description |
|------|--------|-------------|
| `intelligence/__init__.py` | Create | Package init |
| `intelligence/apps.py` | Create | Django AppConfig |
| `intelligence/llm_client.py` | Create | Ollama chat completion helper |
| `intelligence/auto_tagger.py` | Create | Tag extraction (LLM + TF-IDF fallback) |
| `intelligence/entity_extractor.py` | Create | Entity extraction (LLM + regex fallback) |
| `intelligence/memory_decay.py` | Create | Decay scoring |
| `intelligence/report_generator.py` | Create | Weekly digest generator |
| `intelligence/management/__init__.py` | Create | Package init |
| `intelligence/management/commands/__init__.py` | Create | Package init |
| `intelligence/management/commands/enrich.py` | Create | `manage.py enrich` |
| `intelligence/management/commands/decay.py` | Create | `manage.py decay` |
| `intelligence/management/commands/report.py` | Create | `manage.py report` |
| `openbrain/settings/base.py` | Modify | Add `intelligence` to INSTALLED_APPS, new settings |
| `pyproject.toml` | Modify | Add `intelligence*` to packages include list |
| `.env.example` | Modify | Add `OLLAMA_CHAT_MODEL`, `AUTO_ENRICH_ON_CREATE` |
| `core/services/memory_service.py` | Modify | Optional auto-enrich hook (fail-open) |
| `tests/test_intelligence_tagger.py` | Create | Auto-tagger tests |
| `tests/test_intelligence_entities.py` | Create | Entity extractor tests |
| `tests/test_intelligence_decay.py` | Create | Decay scoring tests |
| `tests/test_intelligence_report.py` | Create | Report generator tests |

## Success Criteria

1. `manage.py enrich --all` enriches all memories with tags and entities (LLM or fallback)
2. `manage.py decay` updates all `decay_factor` values with sensible scores
3. `manage.py report` produces a readable Markdown digest
4. All tests pass: `pytest tests/test_intelligence_*.py`
5. Fallbacks work when Ollama chat endpoint is unavailable
6. No new Python dependencies beyond what's in `pyproject.toml`
7. `AUTO_ENRICH_ON_CREATE=true` auto-enriches on memory creation
