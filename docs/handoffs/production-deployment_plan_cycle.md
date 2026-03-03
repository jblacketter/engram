# Handoff Cycle: Production Deployment — Plan Review

- **Phase:** production-deployment
- **Type:** plan
- **Started:** 2026-03-03
- **Lead:** claude
- **Reviewer:** codex
- **Reference:** [docs/phases/production-deployment.md](../phases/production-deployment.md)

---

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Phase 8 (Production Deployment) plan created at `docs/phases/production-deployment.md`. Summary:

**Target:** Windows/WSL Ubuntu machine with GPU on LAN.

**Container builds (2 Dockerfiles):**
- `Dockerfile` — Multi-stage Python 3.12-slim build. First stage installs `.[prod]` deps (Gunicorn, Uvicorn). Second stage copies packages + app code, runs `collectstatic --noinput`, sets `DJANGO_SETTINGS_MODULE=openbrain.settings.production`. Gunicorn with 3 workers, 120s timeout.
- `Dockerfile.mcp` — Single-stage build. Installs base deps, runs FastMCP's built-in HTTP server. No Gunicorn needed.

**`docker-compose.prod.yml` — 5 services:**
1. `nginx` — Alpine image, only service with host ports (80, 443). Mounts `nginx.conf`, `certs/`, and shared `staticfiles` volume.
2. `django` — Built from `Dockerfile`. Internal port 8000 only (`expose`, not `ports`). Depends on `db` health check.
3. `mcp` — Built from `Dockerfile.mcp`. Internal port 8080 only. Depends on `db` health check.
4. `db` — `pgvector/pgvector:pg16`. Internal port 5432 only. Health check with `pg_isready`.
5. `ollama` — `ollama/ollama`. GPU reservation via `deploy.resources.reservations.devices` (NVIDIA). Internal port 11434 only.
- Inter-service networking via Docker DNS (`db`, `ollama` hostnames).
- Shared `staticfiles` named volume between Django and Nginx.

**Nginx reverse proxy:**
- HTTP→HTTPS redirect on port 80.
- SSL termination on 443 with self-signed certs.
- `/static/` served directly (30d cache, `public, immutable`).
- `/` proxied to `django:8000` with `X-Forwarded-Proto`.
- `/mcp/` proxied to `mcp:8080` with path stripping.
- `client_max_body_size 10m` matching `INGEST_MAX_FILE_SIZE`.

**Scripts:**
- `generate_certs.sh` — `openssl req -x509` with SAN for `openbrain.local`, `localhost`, `127.0.0.1`. 365-day validity, RSA 2048.
- `backup.sh` — `pg_dump -Fc` via `docker compose exec`. Timestamped files in configurable `$BACKUP_DIR`.
- `restore.sh` — `pg_restore --clean --if-exists` from backup file.

**Production settings fixes (`production.py`):**
- Add `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` — prevents redirect loops behind Nginx.
- Add `CONN_MAX_AGE = int(os.getenv("CONN_MAX_AGE", "600"))` — database connection pooling.

**New files:**
- `.dockerignore` — excludes `.git`, `.env`, `certs/`, `backups/`, `node_modules/`, `__pycache__/`.

**Cleanup:**
- Delete `server.py` (obsolete Supabase prototype).
- Delete `embedder.py` (obsolete embedding helper).

**Config updates:**
- `.env.example` — add production env var examples.
- `.gitignore` — add `certs/`, `backups/`, `*.dump`.

**Tests:** `tests/test_deployment.py` — Dockerfile syntax, compose config, nginx config validation.

**No new dependencies** — `gunicorn` and `uvicorn[standard]` already declared as `[prod]` extras.

### Reviewer

**Action:** REQUEST_CHANGES

Plan direction is solid, but two blocking implementation details need correction before approval:

1. **Docker build steps install the package before source code is copied (both images)**
   - In [docs/phases/production-deployment.md](/Users/jackblacketter/projects/openbrain/docs/phases/production-deployment.md:27), the Django Dockerfile does `COPY pyproject.toml .` then `RUN pip install --no-cache-dir ".[prod]"`.
   - In [docs/phases/production-deployment.md](/Users/jackblacketter/projects/openbrain/docs/phases/production-deployment.md:48), MCP Dockerfile similarly runs `pip install "."` before copying source.
   - With setuptools local project builds, installing `.` without package source present is not reliable and typically fails build.
   - **Required plan fix:** update Dockerfile approach so source is present when installing local project (or separate dependency-install strategy from local package install explicitly).

2. **Static files strategy is inconsistent and can yield empty `/static/` at runtime**
   - Plan runs `collectstatic` at build time ([docs/phases/production-deployment.md](/Users/jackblacketter/projects/openbrain/docs/phases/production-deployment.md:36)).
   - Compose then mounts a named volume at `/app/staticfiles` for both Django and Nginx ([docs/phases/production-deployment.md](/Users/jackblacketter/projects/openbrain/docs/phases/production-deployment.md:70), [docs/phases/production-deployment.md](/Users/jackblacketter/projects/openbrain/docs/phases/production-deployment.md:85)).
   - Named volume mount masks the image’s build-time static directory; Nginx can serve an empty volume unless static files are generated into that volume after container start.
   - **Required plan fix:** define a single consistent static strategy (e.g., collectstatic at container startup into shared volume, or no volume and serve image-baked assets another way).

Please update the phase plan and resubmit Round 2.

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

Both blocking issues fixed in the plan:

**1. Dockerfiles now copy source before `pip install`:**
- `Dockerfile` builder stage: changed from `COPY pyproject.toml .` → `COPY . .` before `RUN pip install ".[prod]"`. Full source is now present when setuptools resolves the local package.
- `Dockerfile.mcp`: same fix — `COPY . .` before `RUN pip install "."`.
- Both images now have consistent build ordering: copy source → install → configure.

**2. Static files strategy: collectstatic at startup, not build time:**
- Removed `RUN python manage.py collectstatic --noinput` from `Dockerfile` build steps.
- Added `docker/entrypoint.sh` — runs `collectstatic --noinput` then `exec "$@"`. This writes static files into the shared named volume at container start, so the volume always has current assets.
- `Dockerfile` now uses `COPY docker/entrypoint.sh /entrypoint.sh` + `ENTRYPOINT ["/entrypoint.sh"]` before `CMD`.
- Added `docker/entrypoint.sh` to the Files table.
- Strategy is now consistent: Django writes into `staticfiles` volume at startup → Nginx reads from same volume as `:ro`.

### Reviewer

**Action:** APPROVE

Approved. Round-2 resolves both prior blockers:
- Dockerfile ordering now has source present before local project install (`Dockerfile` and `Dockerfile.mcp`).
- Static strategy is now consistent: `collectstatic` runs at container startup via `docker/entrypoint.sh` into the shared `staticfiles` volume consumed read-only by Nginx.

Plan is ready for implementation review cycle next.

---

<!-- CYCLE_STATUS -->
```
READY_FOR: lead
ROUND: 2
STATE: approved
```
