# Handoff Cycle: Production Deployment — Implementation Review

- **Phase:** production-deployment
- **Type:** impl
- **Started:** 2026-03-03
- **Lead:** claude
- **Reviewer:** codex
- **Reference:** [docs/phases/production-deployment.md](../phases/production-deployment.md)

---

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Implementation of Phase 8 (Production Deployment) complete. All files created per the approved plan.

**New files created:**

1. `Dockerfile` — Multi-stage build. Builder stage: `COPY . .` then `pip install ".[prod]"`. Production stage: copies installed packages + source, uses `docker/entrypoint.sh` as `ENTRYPOINT`, runs Gunicorn (3 workers, 120s timeout) on port 8000.

2. `Dockerfile.mcp` — Single-stage build. `COPY . .` then `pip install "."`. Runs `python -m mcp_server.server` on port 8080. Sets `DJANGO_SETTINGS_MODULE=openbrain.settings.production`.

3. `docker/entrypoint.sh` — `set -e`, runs `python manage.py collectstatic --noinput` into the shared named volume, then `exec "$@"` to hand off to Gunicorn. Made executable (`chmod +x`).

4. `docker-compose.prod.yml` — 5 services:
   - `nginx` — only service with host ports (80, 443). Mounts `nginx.conf`, `certs/`, shared `staticfiles` volume (`:ro`).
   - `django` — built from `Dockerfile`. Internal port 8000 (`expose` only). `env_file: .env`. `POSTGRES_HOST=db`, `OLLAMA_BASE_URL=http://ollama:11434`. Shared `staticfiles` volume (writable). Depends on `db` health check.
   - `mcp` — built from `Dockerfile.mcp`. Internal port 8080 (`expose` only). Same env config. Depends on `db` health check.
   - `db` — `pgvector/pgvector:pg16`. Internal port 5432 only. Health check: `pg_isready -U openbrain`. Mounts `pgdata` volume + `init-pgvector.sql`. `POSTGRES_PASSWORD` required (no default).
   - `ollama` — `ollama/ollama`. GPU reservation via `deploy.resources.reservations.devices` (nvidia, count 1, capabilities [gpu]). Internal port 11434 only.
   - 3 named volumes: `pgdata`, `ollama_models`, `staticfiles`.

5. `nginx/nginx.conf` — HTTP→HTTPS redirect (port 80). SSL termination (port 443) with certs from `/etc/nginx/certs/`. Static files: `location /static/` aliased to `/app/staticfiles/` with 30d expiry. Django proxy: `location /` → `http://django:8000` with `X-Forwarded-Proto`, `X-Real-IP`, `X-Forwarded-For`, `client_max_body_size 10m`. MCP proxy: `location /mcp/` → `http://mcp:8080/` with path stripping.

6. `scripts/generate_certs.sh` — `openssl req -x509` with RSA 2048, 365-day validity, SAN for `openbrain.local`, `localhost`, `127.0.0.1`. Output to `certs/`. Made executable.

7. `scripts/backup.sh` — `pg_dump -U openbrain -Fc openbrain` via `docker compose exec -T db`. Timestamped filenames in configurable `$BACKUP_DIR` (default `./backups`). Made executable.

8. `scripts/restore.sh` — `pg_restore -U openbrain -d openbrain --clean --if-exists` from backup file argument. Made executable.

9. `.dockerignore` — Excludes `.git`, `.env`, `certs/`, `backups/`, `frontend/node_modules/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`.

**Modified files:**

10. `openbrain/settings/production.py` — Added `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` (prevents redirect loops behind Nginx) and `CONN_MAX_AGE = int(os.getenv("CONN_MAX_AGE", "600"))` (database connection pooling).

11. `.env.example` — Added production env var examples: `DJANGO_SETTINGS_MODULE`, `POSTGRES_PASSWORD`, `MCP_API_KEY`, `REST_API_KEY`, `CONN_MAX_AGE` (commented out with instructions).

12. `.gitignore` — Added `certs/`, `backups/`, `*.dump` under "Production artifacts" section.

**Deleted files:**

13. `server.py` — Obsolete Supabase MCP prototype (superseded by `mcp_server/server.py`).

14. `embedder.py` — Obsolete embedding helper (superseded by `embeddings/`).

**Tests:**

15. `tests/test_deployment.py` — 35 tests across 10 test classes:
   - `TestDockerfile` (6): exists, multi-stage, source-before-install ordering, entrypoint, expose 8000, gunicorn.
   - `TestDockerfileMcp` (4): exists, source-before-install ordering, expose 8080, mcp server.
   - `TestEntrypoint` (4): exists, collectstatic, exec, executable permission.
   - `TestDockerComposeProd` (6): exists, all 5 services, only-nginx-exposes-ports, GPU config, healthcheck, staticfiles volume.
   - `TestNginxConfig` (8): exists, SSL, HTTP redirect, Django proxy, MCP proxy, static files, forwarded-proto, client_max_body_size.
   - `TestScripts` (6): generate_certs exists/executable/content, backup exists/executable/pg_dump, restore exists/executable/pg_restore.
   - `TestProductionSettings` (5): exists, SECURE_PROXY_SSL_HEADER, CONN_MAX_AGE, DEBUG=False, SSL redirect.
   - `TestDockerignore` (3): exists, excludes secrets, excludes .git.
   - `TestCleanup` (2): server.py removed, embedder.py removed.
   - `TestGitignore` (3): certs/, backups/, *.dump.

**Verification:**
- `ruff check openbrain/settings/production.py tests/test_deployment.py` — all checks passed
- `pytest tests/test_deployment.py` — cannot execute locally due to missing `psycopg` driver (Django's `contrib.postgres` import chain fails at module load). Tests are file-reading only (no DB needed) but pytest-django triggers Django setup. This is the same known environment limitation affecting all test files in this project.

### Reviewer

**Action:** APPROVE

Approved. Implementation matches the round-2 plan corrections and covers the production-deployment phase deliverables:
- Docker build ordering is correct for local project installs in both `Dockerfile` and `Dockerfile.mcp`.
- Static asset flow is consistent via `docker/entrypoint.sh` (`collectstatic`) into shared `staticfiles` volume consumed by Nginx.
- `docker-compose.prod.yml` isolates internal services (only Nginx exposes host ports) and keeps GPU reservation config for Ollama.
- Nginx proxy, cert/backup/restore scripts, production settings updates, `.dockerignore`/`.gitignore` updates, and cleanup deletions are present.

Verification run in this review:
- `ruff check openbrain/settings/production.py tests/test_deployment.py` passed.
- `bash -n docker/entrypoint.sh scripts/generate_certs.sh scripts/backup.sh scripts/restore.sh` passed.
- `docker compose -f docker-compose.prod.yml config` parsed successfully.
- `pytest tests/test_deployment.py` remains blocked in this environment by missing `psycopg`/`psycopg2` during Django setup.

---

<!-- CYCLE_STATUS -->
```
READY_FOR: lead
ROUND: 1
STATE: approved
```
