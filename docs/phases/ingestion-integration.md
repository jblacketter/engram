# Phase 7: Ingestion & Integration

## Summary

Batch import of content from files (PDF, Markdown, DOCX, plain text), URLs, and Obsidian vaults into the memory system. Includes text chunking for long documents, progress-tracked batch processing, and integration with both the MCP server and REST API.

## Scope

- **File ingestor** — parse and chunk PDF, Markdown, DOCX, and plain text files into memories. Configurable chunk size with overlap.
- **URL scraper** — fetch web pages, extract main content (strip nav/ads/boilerplate), store as memories. Internal IP validation to prevent SSRF.
- **Obsidian importer** — walk an Obsidian vault directory, parse frontmatter (tags, aliases), preserve `[[wikilinks]]` in content, map Obsidian tags to memory tags.
- **Batch processor** — process a list of items (files, URLs) with progress tracking and error resilience. Returns per-item success/failure results.
- **MCP tools** — `store_from_url`, `ingest_file` (base64 content).
- **REST endpoints** — `POST /api/ingest/file/` (multipart file upload), `POST /api/ingest/url/`, `POST /api/ingest/batch/`.
- **Management command** — `manage.py ingest` for CLI-driven import.

## Technical Approach

### Django App: `ingestion`

New Django app registered in `INSTALLED_APPS`. No new models — ingestion creates `Memory` records via `memory_service.create_memory()`.

### Module Layout

```
ingestion/
├── __init__.py
├── apps.py
├── chunker.py              # Text chunking with overlap
├── file_ingestor.py        # PDF, Markdown, DOCX, text parsing
├── url_scraper.py          # Web page content extraction
├── obsidian_importer.py    # Obsidian vault import
├── batch_processor.py      # Progress-tracked batch pipeline
└── management/
    └── commands/
        └── ingest.py       # manage.py ingest
```

### `chunker.py` — Text Chunking

```python
def chunk_text(
    text: str,
    max_chars: int = 2000,
    overlap: int = 200,
) -> list[str]:
    """Split text into chunks with overlap. Breaks at paragraph/sentence boundaries."""
```

Strategy: split on double-newlines (paragraphs) first. If a paragraph exceeds `max_chars`, split on sentence boundaries (`. `, `? `, `! `). Overlap copies the last N characters from the previous chunk to the start of the next. Returns at least one chunk even for short text.

Settings:
- `INGEST_CHUNK_SIZE` — default 2000 characters
- `INGEST_CHUNK_OVERLAP` — default 200 characters

### `file_ingestor.py` — File Parsing

```python
async def ingest_file(
    file_path: str | None = None,
    file_bytes: bytes | None = None,
    filename: str = "",
    source: str = "import",
    tags: list[str] | None = None,
    importance: float = 0.5,
) -> list[dict]:
    """Parse a file, chunk content, create memories. Returns list of {id, chunk_index, status}."""
```

**Supported formats:**
- `.txt` — read as UTF-8
- `.md` — read as UTF-8 (preserves Markdown formatting in content)
- `.pdf` — extract text page-by-page using Python stdlib `zipfile` for basic extraction, or the lightweight `pdfminer.six` library. **Decision: use `pdfminer.six`** as it handles most PDF layouts correctly without heavy dependencies.
- `.docx` — extract text from `word/document.xml` inside the DOCX zip archive using `xml.etree.ElementTree` (stdlib). No external dependency.

Each chunk becomes a separate memory with:
- `source`: provided source or `"import"`
- `tags`: provided tags plus `["ingested", format_tag]` (e.g., `"pdf"`, `"markdown"`)
- `metadata`: `{"ingestion": {"filename": "...", "chunk_index": N, "total_chunks": N}}`

File size limit: 10MB (validated before processing).

### `url_scraper.py` — URL Content Extraction

```python
async def scrape_url(
    url: str,
    source: str = "url",
    tags: list[str] | None = None,
    importance: float = 0.5,
) -> list[dict]:
    """Fetch URL, extract content, chunk, create memories. Returns list of {id, chunk_index, status}."""
```

**SSRF prevention (extracted into `_validate_url(url)` helper):**
- **Allowed schemes:** `http`, `https` only. Reject `file://`, `ftp://`, `gopher://`, etc.
- **Allowed ports:** `80`, `443`, or no explicit port (default). All other ports are rejected.
- **Blocked IP ranges:** After resolving the hostname via `socket.getaddrinfo`, reject:
  - Loopback: `127.0.0.0/8`, `::1`
  - RFC1918 private: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
  - Link-local: `169.254.0.0/16`, `fe80::/10`
  - Cloud metadata: `169.254.169.254` explicitly
- **Redirect validation:** Do NOT use `httpx` `follow_redirects`. Instead, manually follow up to 5 redirects, calling `_validate_url()` on each `Location` header before following. This prevents open-redirect SSRF bypasses.

**Content extraction:**
- Fetch with `httpx.AsyncClient` (30s timeout, `follow_redirects=False`, User-Agent header)
- Parse HTML, extract text from `<article>`, `<main>`, or `<body>` (in priority order)
- Strip `<script>`, `<style>`, `<nav>`, `<header>`, `<footer>`, `<aside>` elements
- Extract `<title>` for metadata
- Use stdlib `html.parser.HTMLParser` — no BeautifulSoup dependency

Each chunk becomes a memory with:
- `source`: `"url"`
- `tags`: provided tags plus `["ingested", "web"]`
- `metadata`: `{"ingestion": {"url": "...", "title": "...", "chunk_index": N, "total_chunks": N}}`

### `obsidian_importer.py` — Obsidian Vault Import

```python
async def import_vault(
    vault_path: str,
    source: str = "obsidian",
    importance: float = 0.5,
) -> list[dict]:
    """Walk an Obsidian vault, import all .md files. Returns list of {file, id, status}."""
```

**Processing per note:**
- Parse YAML frontmatter (between `---` delimiters) using stdlib `yaml`-like parsing (split on `---`, parse key-value lines). No PyYAML dependency — simple regex-based parser for flat frontmatter keys (`tags`, `aliases`, `title`).
- Extract Obsidian `#tags` from content body
- Preserve `[[wikilinks]]` in content text (useful for semantic search)
- Map frontmatter `tags` + body `#tags` to memory tags
- Chunk if note exceeds chunk size

Each note becomes one or more memories with:
- `source`: `"obsidian"`
- `tags`: union of frontmatter tags, body `#tags`, and `["obsidian"]`
- `metadata`: `{"ingestion": {"filename": "...", "vault_path": "..."}, "obsidian": {"aliases": [...], "frontmatter": {...}}}`

### `batch_processor.py` — Batch Pipeline

```python
async def process_batch(
    items: list[dict],
    on_progress: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """Process a batch of ingestion items. Returns per-item results."""
```

Each item is a dict with `type` (`"file"`, `"url"`) and relevant parameters. Items are processed sequentially (not parallel, to avoid overwhelming the embedding service). `on_progress(completed, total)` callback for progress tracking.

Returns: `[{"index": 0, "type": "file", "status": "ok", "memories_created": 3}, ...]` or `{"index": 1, "type": "url", "status": "error", "error": "..."}`.

### REST API Endpoints

Add to `api/views.py` and `api/urls.py`:

**`POST /api/ingest/file/`** — multipart file upload
- Accepts: `file` (multipart), `source` (str), `tags` (JSON array), `importance` (float)
- Validates file size (10MB), file extension
- Returns: `{"memories_created": N, "results": [...]}`

**`POST /api/ingest/url/`** — URL scraping
- Accepts: `url` (str), `source` (str), `tags` (JSON array), `importance` (float)
- Returns: `{"memories_created": N, "results": [...]}`

**`POST /api/ingest/batch/`** — batch processing
- Accepts: `items` (array of `{type, ...}`)
- Returns: `{"total": N, "succeeded": N, "failed": N, "results": [...]}`

### MCP Tools

Add to `mcp_server/tools/`:

**`store_from_url`**
```python
@mcp.tool()
async def store_from_url(url: str, tags: list[str] | None = None, importance: float = 0.5) -> str:
    """Fetch a URL and store its content as memories."""
```

**`ingest_file`**
```python
@mcp.tool()
async def ingest_file(content_base64: str, filename: str, tags: list[str] | None = None, importance: float = 0.5) -> str:
    """Ingest a base64-encoded file and store its content as memories."""
```

### Management Command

**`manage.py ingest`**
- `--file PATH` — ingest a single file
- `--url URL` — ingest a URL
- `--vault PATH` — import an Obsidian vault
- `--source SOURCE` — override source (default per type)
- `--tags TAG1,TAG2` — comma-separated additional tags
- Prints progress: `Ingested 5/10 files (23 memories created)`

### Settings Additions

```python
# Ingestion
INGEST_CHUNK_SIZE = int(os.getenv("INGEST_CHUNK_SIZE", "2000"))
INGEST_CHUNK_OVERLAP = int(os.getenv("INGEST_CHUNK_OVERLAP", "200"))
INGEST_MAX_FILE_SIZE = int(os.getenv("INGEST_MAX_FILE_SIZE", str(10 * 1024 * 1024)))  # 10MB
```

### New Dependency

`pdfminer.six` for PDF text extraction. Add to `pyproject.toml`:
```
"pdfminer.six>=20231228,<20260101",
```

## Files

| File | Action | Description |
|------|--------|-------------|
| `ingestion/__init__.py` | Create | Package init |
| `ingestion/apps.py` | Create | Django AppConfig |
| `ingestion/chunker.py` | Create | Text chunking with overlap |
| `ingestion/file_ingestor.py` | Create | File parsing (PDF, MD, DOCX, TXT) |
| `ingestion/url_scraper.py` | Create | URL content extraction with SSRF prevention |
| `ingestion/obsidian_importer.py` | Create | Obsidian vault import |
| `ingestion/batch_processor.py` | Create | Progress-tracked batch pipeline |
| `ingestion/management/__init__.py` | Create | Package init |
| `ingestion/management/commands/__init__.py` | Create | Package init |
| `ingestion/management/commands/ingest.py` | Create | `manage.py ingest` |
| `api/views.py` | Modify | Add ingest views (file upload, URL, batch) |
| `api/serializers.py` | Modify | Add ingest serializers |
| `api/urls.py` | Modify | Add ingest URL patterns |
| `mcp_server/tools/ingest.py` | Create | MCP tools (store_from_url, ingest_file) |
| `mcp_server/tools/__init__.py` | Modify | Import ingest tools |
| `openbrain/settings/base.py` | Modify | Add `ingestion` to INSTALLED_APPS, new settings |
| `pyproject.toml` | Modify | Add `ingestion*` to packages, add `pdfminer.six` dependency |
| `.env.example` | Modify | Add `INGEST_CHUNK_SIZE`, `INGEST_CHUNK_OVERLAP`, `INGEST_MAX_FILE_SIZE` |
| `tests/test_ingestion_chunker.py` | Create | Chunker tests |
| `tests/test_ingestion_file.py` | Create | File ingestor tests |
| `tests/test_ingestion_url.py` | Create | URL scraper tests (with SSRF checks) |
| `tests/test_ingestion_obsidian.py` | Create | Obsidian importer tests |
| `tests/test_ingestion_batch.py` | Create | Batch processor tests |
| `tests/test_ingestion_api.py` | Create | REST endpoint tests (file upload, URL, batch) |
| `tests/test_ingestion_mcp.py` | Create | MCP tool tests (store_from_url, ingest_file) |

## Success Criteria

1. `manage.py ingest --file doc.pdf` creates chunked memories from a PDF
2. `manage.py ingest --url https://example.com` scrapes and stores web content
3. `manage.py ingest --vault ~/obsidian-vault` imports all notes with tags preserved
4. `POST /api/ingest/file/` accepts multipart upload and returns memory IDs
5. `POST /api/ingest/url/` scrapes URL and returns memory IDs
6. `POST /api/ingest/batch/` processes mixed batch and returns per-item results
7. MCP `store_from_url` tool fetches URL and creates memories
8. MCP `ingest_file` tool decodes base64 file and creates memories
9. SSRF prevention rejects internal IPs, non-standard ports, and unsafe redirects
10. All tests pass: `pytest tests/test_ingestion_*.py tests/test_ingestion_api.py tests/test_ingestion_mcp.py`
11. Ruff lint passes on all new files
12. No new dependencies except `pdfminer.six`
