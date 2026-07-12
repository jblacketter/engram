# Phase: Automations and Polish

## Summary

The closing phase of the revival roadmap: scheduled maintenance (decay +
weekly digest), the identity-directory container wiring promised in Phase
11, a config-driven embedding registry, verifiable Docker image pins, and
the Windows/WSL2 LAN deployment package. Everything here is
low-risk plumbing — no new data contracts, no auth changes, no schema
changes.

**Deployment reality note:** the WSL2 deployment itself requires hands-on
access to the Windows GPU box (hardware, LAN, GPU drivers). This phase
delivers the complete, tested deployment package (compose wiring, checklist,
preflight) and verifies everything demonstrable on the Mac; the physical
deployment run is a user-assisted step executed against that checklist and
recorded in the adoption log when it happens. The phase does not claim the
box is running.

## Scope

1. **`maintenance` management command** (`intelligence/management/
   commands/maintenance.py`): one entry point for scheduled upkeep.
   - Always: runs memory decay (`memory_decay.run_decay`) and prints the
     summary.
   - `--digest [--days N]` (default 7): generates the report
     (`report_generator.generate_report`) and **stores it as a memory**
     tagged `["type:digest"]` (source `"maintenance"`, no domain tag —
     owner-surface only under agent scoping), so digests are searchable
     and the dashboard/owner sees them; also printed to stdout.
     Digest storage embeds locally-only (`allow_cloud_fallback=False`) —
     digests aggregate private content.
   - Exit non-zero on failure so cron/launchd surface errors.
2. **Scheduling (documented host cron + optional compose service).**
   - `docs/workflows.md` "Automations" section with copy-paste crontab
     (WSL/Linux) and launchd (macOS) entries: daily decay, weekly digest.
   - `docker-compose.prod.yml` gains an optional `scheduler` service
     (profile `scheduler`, same Django image) running a simple daily loop
     (`maintenance` daily; `--digest` on Mondays). Off by default;
     `--profile scheduler` enables it.
3. **Identity-directory container wiring** (the Phase 11 contract):
   `docker-compose.prod.yml` mounts `${ENGRAM_IDENTITY_HOST_DIR:-~/.engram/identity}`
   read-only at `/identity` into `django`, `mcp`, and `scheduler`, with
   `ENGRAM_IDENTITY_DIR=/identity`.
4. **Config-driven embedding registry**: `EMBEDDING_PROVIDER` setting
   (env, default `ollama`; `openrouter` selects the cloud provider as
   primary; unknown values raise ImproperlyConfigured at call time with a
   clear message). `get_fallback_provider` unchanged (fallback only ever
   applies when the primary is Ollama). Local-only identity embedding is
   unaffected: with a cloud PRIMARY, identity sync must refuse rather
   than silently upload — sync checks the provider and errors unless
   `ENGRAM_IDENTITY_CLOUD_EMBED=true`.
5. **Image pinning** (tags verified against Docker Hub on 2026-07-12):
   - `pgvector/pgvector:pg16` → `pgvector/pgvector:0.8.5-pg16` (both files)
   - `ollama/ollama` → `ollama/ollama:0.31.2` (both files)
   - `nginx:alpine` → `nginx:1.29.4-alpine` (prod)
6. **Prod-compose polish**: fix the MCP healthcheck (a bare GET against
   the streamable-HTTP endpoint does not return 200; replace with a TCP
   connect check).
7. **WSL2 deployment package**: `docs/deploy-windows-lan.md` gains a
   "Deployment checklist (revival roadmap)" section — preflight env
   (`DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`),
   identity repo clone + mount, agent-key creation for each connecting
   tool, model pull, scheduler profile, and the LAN verification steps
   (the roadmap's verify line). Execution is user-assisted per the
   deployment reality note.

Out of scope: running the deployment on the Windows box (user-assisted,
post-phase); celery/redis or any new runtime dependency; automatic
identity sync scheduling (the identity repo is human-edited; syncing
stays a deliberate action); frontend changes; PyPI packaging.

## Technical Approach

- `maintenance` composes the existing, already-tested `run_decay` and
  `generate_report` services — no new business logic; the only new
  behavior is storing the digest as a memory via
  `memory_service.create_memory(..., allow_cloud_fallback=False)`.
- Registry: `get_provider()` reads `settings.EMBEDDING_PROVIDER`; tests
  cover ollama default, openrouter selection, unknown value error, and
  the identity-sync refusal path with a cloud primary.
- Scheduler service: `profiles: ["scheduler"]`, command is a POSIX shell
  loop calling `python manage.py maintenance` daily and adding `--digest`
  when `date +%u` is 1 — no new images.
- Compose changes are lint-verified with `docker compose config` for both
  files (no container start required).

## Files

- `intelligence/management/commands/maintenance.py` (new)
- `embeddings/registry.py`, `engram/settings/base.py`, `.env.example`
- `core/services/identity_service.py` (cloud-primary refusal)
- `docker-compose.yml`, `docker-compose.prod.yml`
- `tests/test_maintenance.py`, `tests/test_embeddings.py` (additions)
- `docs/workflows.md`, `docs/deploy-windows-lan.md`, `docs/setup-docker.md`
  (pin notes), `docs/roadmap.md` on completion

## Success Criteria

1. Full backend suite green with new tests: maintenance decay path,
   digest stored as a `type:digest` memory with local-only embedding
   asserted, failure exit codes; provider selection matrix (default /
   openrouter / unknown / identity-sync refusal with cloud primary).
2. Live on the Mac: `python manage.py maintenance --digest` runs decay
   and stores a real digest memory (id transcribed); the digest is
   retrievable via the owner surface and invisible to an agent key.
3. `docker compose config` passes for both files with pinned images,
   identity mounts, scheduler profile, and the fixed MCP healthcheck; all
   three pinned tags verified to exist on Docker Hub (HTTP 200,
   transcribed).
4. Deployment checklist complete enough that the Windows/WSL2 run needs
   no further research — every step is a copy-paste command with its
   preflight; the user-assisted execution is explicitly tracked in the
   adoption log as the remaining step.
5. All work committed intentionally on the active branch per repo
   workflow.
