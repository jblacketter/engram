# Phase 1: Foundation

## Summary

Django project scaffolding with split settings, Docker infrastructure (PostgreSQL 16 + pgvector, Ollama), and the core Memory model with vector and full-text search fields.

## Scope

- Django project setup with split settings (base, development, production)
- `pyproject.toml` replacing `requirements.txt` for dependency management
- Docker Compose for local development (PostgreSQL 16 + pgvector, Ollama)
- Core `Memory` Django model with pgvector `VectorField(768)`, `content_tsv` tsvector, dual timestamps, decay fields
- Initial migration creating the memories table with HNSW vector index and GIN indexes
- Updated `sql/schema.sql` for 768-dim vectors, tsvector, decay columns
- `.gitignore`, updated `.env.example` with all config variables

## Technical Approach

### Django Project Structure

Create the Django project under `openbrain/` with split settings:

- `openbrain/settings/base.py` — Shared config: installed apps, middleware, database config (reading from `.env`), vector dimensions constant (768), timezone, static files
- `openbrain/settings/development.py` — DEBUG=True, permissive CORS, console email backend
- `openbrain/settings/production.py` — DEBUG=False, secure cookies, HTTPS redirect, production logging

The `DJANGO_SETTINGS_MODULE` env var selects the settings file (default: `development`).

### Dependency Management

Replace `requirements.txt` with `pyproject.toml` using standard PEP 621 format. Key dependencies:

- Django 5.x, djangorestframework, django-cors-headers
- pgvector (Django integration), psycopg[binary] (PostgreSQL driver)
- fastmcp (MCP server)
- python-dotenv (env loading)
- gunicorn, uvicorn (production servers)

### Docker Infrastructure

`docker-compose.yml` for local dev:

- **PostgreSQL 16 + pgvector**: `pgvector/pgvector:pg16` image, port 5432, persistent volume, creates `openbrain` database with `vector` extension enabled via init script
- **Ollama**: `ollama/ollama` image, port 11434, persistent volume for models, pulls `nomic-embed-text` on startup

### Memory Model

The `core` Django app contains the `Memory` model:

| Field | Type | Purpose |
|-------|------|---------|
| `id` | UUIDField (pk) | Unique identifier |
| `content` | TextField | Raw memory text |
| `embedding` | VectorField(768) | nomic-embed-text vector |
| `content_tsv` | SearchVectorField | PostgreSQL tsvector for BM25 |
| `source` | CharField | Origin (mcp, api, import, manual) |
| `tags` | JSONField | List of tag strings |
| `metadata` | JSONField | Arbitrary key-value data |
| `importance` | FloatField | Base importance score (0-1) |
| `decay_factor` | FloatField | Decay multiplier |
| `access_count` | IntegerField | Read access counter |
| `last_accessed` | DateTimeField | Last read timestamp |
| `created_at` | DateTimeField | Creation timestamp |
| `updated_at` | DateTimeField | Last modification timestamp |

Indexes:
- HNSW index on `embedding` for fast approximate nearest neighbor search (cosine distance)
- GIN index on `content_tsv` for full-text search
- GIN index on `tags` for tag filtering
- B-tree index on `created_at` for temporal queries

### SQL Schema

Update `sql/schema.sql` to serve as the reference DDL matching the Django model — 768-dim vectors, tsvector column with trigger, decay columns, all indexes.

## Files to Create/Modify

| Action | File | Description |
|--------|------|-------------|
| Create | `pyproject.toml` | Python project config + dependencies |
| Create | `docker-compose.yml` | Dev infrastructure (Postgres+pgvector, Ollama) |
| Create | `docker/init-pgvector.sql` | Init script to enable vector extension |
| Create | `openbrain/__init__.py` | Django project package |
| Create | `openbrain/settings/__init__.py` | Settings package |
| Create | `openbrain/settings/base.py` | Shared Django settings |
| Create | `openbrain/settings/development.py` | Dev settings |
| Create | `openbrain/settings/production.py` | Prod settings |
| Create | `openbrain/urls.py` | Root URL config |
| Create | `openbrain/wsgi.py` | WSGI entry point |
| Create | `openbrain/asgi.py` | ASGI entry point |
| Create | `manage.py` | Django management script |
| Create | `core/__init__.py` | Core app package |
| Create | `core/apps.py` | Core app config |
| Create | `core/models.py` | Memory model |
| Create | `core/admin.py` | Admin registration |
| Create | `core/migrations/0001_initial.py` | Initial migration (auto-generated) |
| Modify | `sql/schema.sql` | Update to 768-dim, tsvector, decay |
| Modify | `.env.example` | Add all config variables |
| Create | `.gitignore` | Standard Django + Node gitignore |

## Success Criteria

1. `docker compose up -d` starts PostgreSQL (with pgvector extension) and Ollama without errors
2. `python manage.py migrate` creates the memories table with all fields and indexes
3. From Django shell: can create, read, update, delete a Memory instance
4. Settings split works: `DJANGO_SETTINGS_MODULE=openbrain.settings.development` vs `production`
5. `sql/schema.sql` matches the Django migration output
6. `.env.example` documents all required environment variables
