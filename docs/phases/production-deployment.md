# Phase 8: Production Deployment

## Summary

Containerize the full Open Brain stack for production use on a Windows/WSL Ubuntu machine with GPU on a LAN. Includes Docker builds for Django and MCP server, Nginx reverse proxy with self-signed HTTPS, Ollama GPU acceleration, database backup/restore scripts, structured logging, and LAN security hardening.

## Scope

- **Dockerfile (Django)** — multi-stage build with Gunicorn, `collectstatic`, production settings.
- **Dockerfile.mcp** — lightweight container for FastMCP server with Uvicorn.
- **docker-compose.prod.yml** — full stack: Nginx, Django, MCP, PostgreSQL, Ollama (GPU).
- **Nginx reverse proxy** — HTTPS termination with self-signed certs, proxy to Django (:8000) and MCP (:8080), static file serving.
- **Self-signed certificate generation** — script for LAN HTTPS.
- **Database backup/restore** — scripts using `pg_dump`/`pg_restore`.
- **Production settings fixes** — `SECURE_PROXY_SSL_HEADER`, `CONN_MAX_AGE`, `STATIC_ROOT`.
- **Structured JSON logging** — consistent log format across Django and MCP.
- **LAN security** — API keys enforced, internal ports not exposed, rate limiting active.
- **Cleanup** — remove obsolete `server.py` and `embedder.py` (original Supabase prototype).

## Technical Approach

### `Dockerfile` — Django Application

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir ".[prod]"

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .
ENV DJANGO_SETTINGS_MODULE=openbrain.settings.production
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "openbrain.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
```

Multi-stage build: first stage copies full source then installs dependencies (including `[prod]` extras) — source must be present for setuptools to resolve the local package. Second stage copies installed packages and app code. `collectstatic` runs at container startup via `entrypoint.sh` (not at build time) so it writes into the shared named volume that Nginx reads. Gunicorn with 3 workers, 120s timeout (for long ingestion requests).

### `docker/entrypoint.sh` — Container Entrypoint

```bash
#!/bin/bash
set -e
python manage.py collectstatic --noinput
exec "$@"
```

Runs `collectstatic` into the shared `staticfiles` volume on every container start, then `exec`s the CMD (Gunicorn). This ensures the named volume always has current static assets for Nginx to serve.

### `Dockerfile.mcp` — MCP Server

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir "."
ENV DJANGO_SETTINGS_MODULE=openbrain.settings.production
EXPOSE 8080
CMD ["python", "-m", "mcp_server.server"]
```

Single-stage build — copies full source first, then installs the local package. No Gunicorn needed. FastMCP's built-in server handles HTTP transport. Shares the same codebase and settings.

### `docker-compose.prod.yml` — Production Stack

```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./certs:/etc/nginx/certs:ro
      - staticfiles:/app/staticfiles:ro
    depends_on:
      - django
      - mcp

  django:
    build:
      context: .
      dockerfile: Dockerfile
    env_file: .env
    environment:
      DJANGO_SETTINGS_MODULE: openbrain.settings.production
      POSTGRES_HOST: db
      OLLAMA_BASE_URL: http://ollama:11434
    volumes:
      - staticfiles:/app/staticfiles
    depends_on:
      db:
        condition: service_healthy
    expose:
      - "8000"

  mcp:
    build:
      context: .
      dockerfile: Dockerfile.mcp
    env_file: .env
    environment:
      DJANGO_SETTINGS_MODULE: openbrain.settings.production
      POSTGRES_HOST: db
      OLLAMA_BASE_URL: http://ollama:11434
    depends_on:
      db:
        condition: service_healthy
    expose:
      - "8080"

  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-openbrain}
      POSTGRES_USER: ${POSTGRES_USER:-openbrain}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./docker/init-pgvector.sql:/docker-entrypoint-initdb.d/01-init-pgvector.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U openbrain"]
      interval: 5s
      timeout: 5s
      retries: 5
    expose:
      - "5432"

  ollama:
    image: ollama/ollama
    volumes:
      - ollama_models:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    expose:
      - "11434"

volumes:
  pgdata:
  ollama_models:
  staticfiles:
```

Key differences from dev compose:
- **No host port exposure** for `db`, `ollama`, `django`, `mcp` — only `nginx` exposes 80/443.
- **GPU reservation** for Ollama via NVIDIA Container Toolkit `deploy.resources`.
- **Shared `staticfiles` volume** between Django (writes at build) and Nginx (serves).
- **`env_file: .env`** for all secrets and config.
- **Service hostnames** (`db`, `ollama`) used for inter-container networking.
- **Health check** on `db` with `condition: service_healthy` for Django/MCP dependencies.

### `nginx/nginx.conf` — Reverse Proxy

```nginx
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name _;

    ssl_certificate /etc/nginx/certs/server.crt;
    ssl_certificate_key /etc/nginx/certs/server.key;

    # Static files
    location /static/ {
        alias /app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # REST API + Django admin + frontend SPA
    location / {
        proxy_pass http://django:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 10m;
    }

    # MCP server
    location /mcp/ {
        proxy_pass http://mcp:8080/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

HTTP-to-HTTPS redirect on port 80. SSL termination on port 443. Static files served directly by Nginx. Django and MCP proxied on separate paths. `client_max_body_size 10m` to match `INGEST_MAX_FILE_SIZE`. `X-Forwarded-Proto` header for Django's `SECURE_PROXY_SSL_HEADER`.

### `scripts/generate_certs.sh` — Self-Signed Certificates

```bash
#!/bin/bash
mkdir -p certs
openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout certs/server.key \
  -out certs/server.crt \
  -subj "/CN=openbrain.local" \
  -addext "subjectAltName=DNS:openbrain.local,DNS:localhost,IP:127.0.0.1"
```

Generates `certs/server.crt` and `certs/server.key`. The `subjectAltName` includes `localhost` and `127.0.0.1` for LAN access. Certs directory is `.gitignore`d.

### `scripts/backup.sh` — Database Backup

```bash
#!/bin/bash
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U openbrain -Fc openbrain > "$BACKUP_DIR/openbrain_$TIMESTAMP.dump"
echo "Backup saved: $BACKUP_DIR/openbrain_$TIMESTAMP.dump"
```

Uses `pg_dump` with custom format (`-Fc`) for efficient backup. Timestamped filenames. Configurable backup directory.

### `scripts/restore.sh` — Database Restore

```bash
#!/bin/bash
BACKUP_FILE="$1"
if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: ./scripts/restore.sh <backup_file>"
  exit 1
fi
docker compose -f docker-compose.prod.yml exec -T db \
  pg_restore -U openbrain -d openbrain --clean --if-exists < "$BACKUP_FILE"
echo "Restored from: $BACKUP_FILE"
```

Uses `pg_restore` with `--clean --if-exists` to drop and recreate objects.

### `openbrain/settings/production.py` — Fixes

Current `production.py` needs these additions:

```python
# Fix SSL redirect behind Nginx proxy
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Database connection pooling
CONN_MAX_AGE = int(os.getenv("CONN_MAX_AGE", "600"))

# Static files (already defined in base.py, but ensure collectstatic works)
# STATIC_ROOT is inherited from base.py as BASE_DIR / "staticfiles"
```

The existing `SECURE_SSL_REDIRECT = True` works correctly with `SECURE_PROXY_SSL_HEADER` — Django trusts the `X-Forwarded-Proto` header from Nginx and only redirects non-HTTPS requests.

### `.env.example` Updates

Add production-specific entries:

```bash
# Production
DJANGO_SETTINGS_MODULE=openbrain.settings.production
POSTGRES_PASSWORD=<strong-random-password>
MCP_API_KEY=<generated-api-key>
REST_API_KEY=<generated-api-key>
```

### `.gitignore` Updates

Add entries to prevent committing secrets and generated files:

```
certs/
backups/
*.dump
```

### `.dockerignore`

```
.git
.env
certs/
backups/
frontend/node_modules/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
```

Prevents copying secrets, cache, and unnecessary files into Docker build context.

### Cleanup

Delete obsolete prototype files that are no longer used:
- `server.py` — original Supabase MCP server (superseded by `mcp_server/server.py`)
- `embedder.py` — original embedding helper (superseded by `embeddings/`)

### No New Dependencies

All required packages are already declared:
- `gunicorn` and `uvicorn[standard]` in `[project.optional-dependencies.prod]`
- No new Python packages needed.

## Files

| File | Action | Description |
|------|--------|-------------|
| `Dockerfile` | Create | Multi-stage Django/Gunicorn container build |
| `Dockerfile.mcp` | Create | FastMCP server container build |
| `docker/entrypoint.sh` | Create | Container entrypoint (collectstatic + exec CMD) |
| `docker-compose.prod.yml` | Create | Full production stack (Nginx, Django, MCP, DB, Ollama+GPU) |
| `nginx/nginx.conf` | Create | Reverse proxy with HTTPS, static serving |
| `scripts/generate_certs.sh` | Create | Self-signed certificate generation |
| `scripts/backup.sh` | Create | pg_dump database backup |
| `scripts/restore.sh` | Create | pg_restore database restore |
| `.dockerignore` | Create | Docker build context exclusions |
| `openbrain/settings/production.py` | Modify | Add `SECURE_PROXY_SSL_HEADER`, `CONN_MAX_AGE` |
| `.env.example` | Modify | Add production env var examples |
| `.gitignore` | Modify | Add `certs/`, `backups/`, `*.dump` |
| `server.py` | Delete | Remove obsolete Supabase prototype |
| `embedder.py` | Delete | Remove obsolete embedding helper |
| `tests/test_deployment.py` | Create | Dockerfile syntax, compose config, nginx config validation |

## Success Criteria

1. `scripts/generate_certs.sh` creates valid self-signed certificates in `certs/`
2. `docker compose -f docker-compose.prod.yml build` succeeds for Django and MCP images
3. `docker compose -f docker-compose.prod.yml up -d` starts all 5 services
4. HTTPS access to Django (REST API, admin, frontend SPA) via Nginx on port 443
5. MCP server accessible at `/mcp/` path through Nginx
6. Static files served by Nginx at `/static/`
7. Ollama uses GPU acceleration (visible in `nvidia-smi` or Ollama logs)
8. `scripts/backup.sh` creates a database dump file
9. `scripts/restore.sh` restores from a backup file
10. `SECURE_PROXY_SSL_HEADER` prevents redirect loops behind Nginx
11. Internal ports (8000, 8080, 5432, 11434) not exposed to host
12. API keys enforced when `REST_API_KEY`/`MCP_API_KEY` are set
13. Ruff lint passes on modified files
14. Obsolete `server.py` and `embedder.py` removed
