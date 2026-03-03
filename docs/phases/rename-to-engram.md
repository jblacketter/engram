# Phase: Rename OpenBrain to Engram

## Summary
Rename the project from "openbrain" / "Open Brain" to "engram" across all functional code, configuration, and project files. Historical documentation (handoff cycles, phase plans) retains old references for context.

## Scope
- Rename `openbrain/` Django package directory to `engram/`
- Update all Python module references (DJANGO_SETTINGS_MODULE, imports, ROOT_URLCONF, WSGI_APPLICATION)
- Update `pyproject.toml` package name and discovery config
- Update all Docker and docker-compose configuration
- Update `.env` and `.env.example` defaults
- Update shell scripts (backup, restore, cert generation)
- Update frontend package name and HTML title
- Update user-agent string, MCP server name, API title
- Update test files referencing old name in paths or test data
- Update `.idea/` PyCharm config files
- Clean up `openbrain.egg-info/` generated metadata
- Leave `docs/` historical references intact (92 references across 19 files)

## Technical Approach
Systematic find-and-replace across all functional file types, with manual verification that no functional references remain. Directory rename handled first, then module references, config files, and finally cleanup.

## Files Modified
- **Renamed:** `openbrain/` → `engram/` (directory)
- **Removed:** `openbrain.egg-info/`
- **Django core:** `manage.py`, `engram/asgi.py`, `engram/wsgi.py`, `engram/urls.py`, `engram/settings/base.py`
- **Config:** `pyproject.toml`, `Dockerfile`, `Dockerfile.mcp`, `docker-compose.yml`, `docker-compose.prod.yml`, `.env`, `.env.example`
- **Scripts:** `scripts/backup.sh`, `scripts/restore.sh`, `scripts/generate_certs.sh`
- **Frontend:** `frontend/package.json`, `frontend/package-lock.json`, `frontend/index.html`, `frontend/src/components/Layout.tsx`
- **Python:** `mcp_server/server.py`, `intelligence/report_generator.py`, `ingestion/url_scraper.py`
- **Tests:** `tests/test_deployment.py`, `tests/test_intelligence_entities.py`, `tests/test_intelligence_report.py`
- **SQL:** `sql/schema.sql`
- **IDE:** `.idea/misc.xml`, `.idea/modules.xml`, `.idea/engram.iml`

## Success Criteria
1. `grep -ri openbrain` returns ONLY docs/ files (historical references)
2. All functional code, config, Docker, scripts, and frontend reference "engram"
3. No broken imports or module references
4. Database defaults use "engram" / "engram_dev"
5. MCP server name, API title, user-agent, report title all say "Engram"
