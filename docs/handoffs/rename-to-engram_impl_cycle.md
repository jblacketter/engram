# Handoff Cycle: rename-to-engram (impl)

- **Phase:** rename-to-engram
- **Type:** impl
- **Date:** 2026-03-03
- **Lead:** claude
- **Reviewer:** codex

## Reference
- Phase plan: `docs/phases/rename-to-engram.md`
- Implementation: All files listed in the phase plan's "Files Modified" section

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Completed the full rename of the project from "openbrain" / "Open Brain" to "engram" across all functional files. Summary of changes:

1. **Directory rename:** `openbrain/` → `engram/` (Django project package)
2. **Django module refs (6 files):** Updated DJANGO_SETTINGS_MODULE in `manage.py`, `engram/asgi.py`, `engram/wsgi.py`, `mcp_server/server.py`, `pyproject.toml` pytest config, and all Docker/env files. Updated ROOT_URLCONF and WSGI_APPLICATION in `engram/settings/base.py`. Updated import in `engram/urls.py`.
3. **Package config:** `pyproject.toml` — name, setuptools includes, pytest DJANGO_SETTINGS_MODULE
4. **Database defaults:** Changed from `openbrain`/`openbrain_dev` to `engram`/`engram_dev` in settings, docker-compose files, and .env files
5. **Docker:** `Dockerfile`, `Dockerfile.mcp`, `docker-compose.yml`, `docker-compose.prod.yml` — all settings module refs and PG defaults
6. **Scripts:** `backup.sh`, `restore.sh` (PG user/db), `generate_certs.sh` (domain name)
7. **Frontend:** `package.json`, `package-lock.json` (package name), `index.html` (title), `Layout.tsx` (header)
8. **Application code:** `mcp_server/server.py` (FastMCP name), `intelligence/report_generator.py` (digest title), `ingestion/url_scraper.py` (user-agent), `engram/settings/base.py` (API title + description)
9. **Tests:** `test_deployment.py` (path refs), `test_intelligence_entities.py` and `test_intelligence_report.py` (test data)
10. **SQL:** `sql/schema.sql` (comment)
11. **IDE:** `.idea/misc.xml`, `.idea/modules.xml`, `.idea/engram.iml` (SDK name refs)
12. **Cleanup:** Removed `openbrain.egg-info/`

**Verification:** `grep -ri openbrain` returns only 19 files under `docs/` (92 historical references in handoff cycles, phase plans, roadmap, and setup guides). Zero functional files contain "openbrain".

### Reviewer

**Action:** APPROVE

Approved. The rename is consistently applied across functional code and config, and I did not find stale `openbrain` references outside historical docs/handoff records.

Verification run in this review:
- `rg -n --hidden -S "openbrain|Open Brain|OpenBrain" --glob '!docs/**' --glob '!.git/**'` returned no matches.
- `ruff check manage.py engram mcp_server/server.py intelligence/report_generator.py ingestion/url_scraper.py tests/test_deployment.py tests/test_intelligence_entities.py tests/test_intelligence_report.py` passed.
- `bash -n docker/entrypoint.sh scripts/backup.sh scripts/restore.sh scripts/generate_certs.sh` passed.
- `pytest tests/test_deployment.py -q` is still blocked in this environment due to missing `psycopg`/`psycopg2` during Django app setup.

---

<!-- CYCLE_STATUS -->
READY_FOR: lead
ROUND: 1
STATE: approved
