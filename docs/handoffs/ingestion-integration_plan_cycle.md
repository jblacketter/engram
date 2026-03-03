# Handoff Cycle: Ingestion & Integration — Plan Review

- **Phase:** ingestion-integration
- **Type:** plan
- **Started:** 2026-03-03
- **Lead:** claude
- **Reviewer:** codex
- **Reference:** [docs/phases/ingestion-integration.md](../phases/ingestion-integration.md)

---

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Phase 7 (Ingestion & Integration) plan created at `docs/phases/ingestion-integration.md`. Summary:

**New Django app `ingestion/`** — no new models, creates `Memory` records via `memory_service.create_memory()`.

**Core modules:**
1. `chunker.py` — `chunk_text(text, max_chars=2000, overlap=200)`. Splits on paragraph then sentence boundaries. Configurable via `INGEST_CHUNK_SIZE` / `INGEST_CHUNK_OVERLAP` settings.
2. `file_ingestor.py` — `ingest_file(file_path, file_bytes, filename, source, tags, importance)`. Supports `.txt`, `.md`, `.pdf` (via `pdfminer.six`), `.docx` (stdlib XML parsing). 10MB file size limit. Each chunk → memory with `metadata.ingestion` tracking filename, chunk index, total.
3. `url_scraper.py` — `scrape_url(url, source, tags, importance)`. SSRF prevention (reject private IPs, non-standard ports). Content extraction via stdlib `html.parser` (strip nav/script/style, prefer `<article>`/`<main>`). 30s timeout.
4. `obsidian_importer.py` — `import_vault(vault_path, source, importance)`. Walks `.md` files, parses YAML frontmatter (simple regex-based, no PyYAML), extracts `#tags`, preserves `[[wikilinks]]`. Maps to memory tags/metadata.
5. `batch_processor.py` — `process_batch(items, on_progress)`. Sequential processing with per-item error resilience. Returns `[{index, type, status, memories_created}]`.

**REST API (3 new endpoints):**
- `POST /api/ingest/file/` — multipart upload with file size/extension validation
- `POST /api/ingest/url/` — URL scraping
- `POST /api/ingest/batch/` — batch processing

**MCP tools (2 new):**
- `store_from_url(url, tags, importance)` — fetch URL → store as memories
- `ingest_file(content_base64, filename, tags, importance)` — base64 file → parse → store

**Management command:**
- `manage.py ingest --file PATH | --url URL | --vault PATH [--source SRC] [--tags TAG1,TAG2]`

**New dependency:** `pdfminer.six` for PDF text extraction.

**Settings:** `INGEST_CHUNK_SIZE`, `INGEST_CHUNK_OVERLAP`, `INGEST_MAX_FILE_SIZE`.

**Tests:** 5 test files covering chunker, file ingestor, URL scraper (with SSRF), Obsidian importer, batch processor.

### Reviewer

**Action:** REQUEST_CHANGES

Plan is solid overall, but there are blocking gaps before implementation.

**Blocking issues:**
1. **SSRF policy is incomplete and partly incorrect**
   - Current text says “reject non-standard ports below 80,” which is not a meaningful SSRF control and leaves risky explicit ports unaddressed.
   - URL fetching follows redirects, but the plan does not require re-validating each redirect target host/IP/port after resolution.
   - Private/internal coverage should explicitly include link-local and metadata-service ranges (e.g., `169.254.169.254`) in addition to RFC1918 and loopback.

2. **Missing explicit test plan for new API + MCP surfaces**
   - Scope adds 3 REST ingestion endpoints and 2 MCP tools, but Files/Success Criteria only include ingestion-module tests (`tests/test_ingestion_*.py`).
   - There is no explicit integration test coverage planned for:
     - `POST /api/ingest/file|url|batch`
     - MCP `store_from_url` and `ingest_file`

**Required changes:**
1. Revise URL security design to:
   - enforce allowed schemes and allowed ports (default `80/443`, or explicit safe allowlist),
   - re-validate redirect destinations before each hop,
   - explicitly block loopback, RFC1918, link-local, and metadata endpoints.
2. Add test files/criteria for ingestion API endpoints and MCP ingest tools (or explicitly scope them out, with rationale).
3. Update success criteria to include those API/MCP verification checks.

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

Both blocking issues addressed:

**1. SSRF policy revised** (`url_scraper.py` section in plan):
- **Allowed schemes:** `http`, `https` only. All others (`file://`, `ftp://`, `gopher://`, etc.) rejected.
- **Allowed ports:** `80`, `443`, or no explicit port (default). All other ports rejected.
- **Blocked IP ranges:** After resolving hostname via `socket.getaddrinfo`, reject:
  - Loopback: `127.0.0.0/8`, `::1`
  - RFC1918 private: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
  - Link-local: `169.254.0.0/16`, `fe80::/10`
  - Cloud metadata: `169.254.169.254` explicitly
- **Redirect validation:** Do NOT use `httpx` `follow_redirects`. Instead, manually follow up to 5 redirects, calling `_validate_url()` on each `Location` header before following. This prevents open-redirect SSRF bypasses.
- Extracted into `_validate_url(url)` helper called before initial fetch and before every redirect hop.

**2. API/MCP test coverage added** (Files table + Success Criteria):
- Added `tests/test_ingestion_api.py` — REST endpoint tests covering `POST /api/ingest/file/` (multipart upload, file size/extension validation), `POST /api/ingest/url/` (URL scraping), `POST /api/ingest/batch/` (mixed batch with success/failure results).
- Added `tests/test_ingestion_mcp.py` — MCP tool tests covering `store_from_url` (URL fetch → memories) and `ingest_file` (base64 decode → parse → memories).
- Updated Success Criteria with per-endpoint verification (items 4-8) and expanded SSRF criterion to include ports and redirects (item 9).

### Reviewer

**Action:** APPROVE

Approved. Round 2 resolves prior blockers:
- SSRF policy is now concrete (scheme/port allowlist, blocked internal/link-local/metadata ranges, and redirect hop re-validation).
- Explicit test coverage is planned for new REST ingestion endpoints and MCP ingestion tools.
- Success criteria now include API/MCP verification and strengthened SSRF checks.

No additional blocking plan gaps identified for this phase.

---

<!-- CYCLE_STATUS -->
```
READY_FOR: lead
ROUND: 2
STATE: approved
```
