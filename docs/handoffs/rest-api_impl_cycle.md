# Handoff Cycle: REST API — Implementation Review

- **Phase:** rest-api
- **Type:** impl
- **Started:** 2026-03-03
- **Lead:** claude
- **Reviewer:** codex
- **Reference:** [docs/phases/rest-api.md](../phases/rest-api.md)

---

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Implementation of Phase 4 (REST API) complete. All files created per the approved plan.

**API app (`api/`):**
- `__init__.py` — empty package init
- `apps.py` — Django `ApiConfig` AppConfig
- `authentication.py` — `APIKeyUser` (lightweight principal with `is_authenticated=True`, `is_active=True`, `is_anonymous=False`) and `APIKeyAuthentication` (checks `Authorization: Bearer <token>` against `settings.REST_API_KEY`; returns `(APIKeyUser(), None)` on valid token in secured mode; returns `None` in dev mode or when no bearer header; raises `AuthenticationFailed` on invalid token)
- `throttling.py` — `ReadRateThrottle` (scope="read") and `WriteRateThrottle` (scope="write") using `SimpleRateThrottle` with IP-based cache keys
- `serializers.py` — `MemorySerializer` (ModelSerializer, read-only, excludes `embedding`/`content_tsv`), `MemoryCreateSerializer` (content ≤50K chars, tags ≤20×100 chars, importance 0–1, default source="api"), `MemoryUpdateSerializer` (partial update, all fields optional), `SearchRequestSerializer` (query required, limit 1–100, semantic_weight 0–1), `SearchResultSerializer` (output with rrf_score)
- `views.py` — 6 views using `async_to_sync` to call the async service layer:
  - `HealthView` — `AllowAny` permission, no throttling, checks DB connectivity via `connection.ensure_connection()`
  - `MemoryListCreateView` — GET calls `memory_service.list_recent()`, POST validates + calls `memory_service.create_memory()` (201). Dynamic throttle: read for GET, write for POST.
  - `MemoryDetailView` — GET calls `memory_service.get_memory()` (increments access_count), PATCH validates + calls `memory_service.update_memory()`, DELETE calls `memory_service.delete_memory()` (204). Handles `Memory.DoesNotExist` → 404, `httpx.Connect*` → 503.
  - `SearchView` — POST validates with `SearchRequestSerializer`, calls `search_service.search()`, returns `SearchResultSerializer(many=True)`. Write throttle.
  - `StatsView` — Direct ORM: count, source breakdown via `annotate(Count)`, date range via `aggregate(Min/Max)`, tag frequency via Python `Counter`. Read throttle.
  - `TagsView` — Direct ORM: tag frequency from JSONField `values_list`, sorted by count desc. Read throttle.
- `urls.py` — 6 URL patterns matching plan spec

**Settings changes (`openbrain/settings/base.py`):**
- Added `REST_API_KEY = os.getenv("REST_API_KEY", "")`
- Added `REST_FRAMEWORK` dict with conditional `DEFAULT_PERMISSION_CLASSES`: `IsAuthenticated` when `REST_API_KEY` is set, `AllowAny` when empty
- Added `SPECTACULAR_SETTINGS` for OpenAPI metadata
- Added `"drf_spectacular"` and `"api"` to `INSTALLED_APPS`

**URL routing (`openbrain/urls.py`):**
- Added `path("api/", include("api.urls"))` for API endpoints
- Added `path("api/schema/", SpectacularAPIView)` for OpenAPI schema
- Added `path("api/docs/", SpectacularSwaggerView)` for Swagger UI

**Dependencies (`pyproject.toml`):**
- Added `drf-spectacular>=0.28,<1.0` to dependencies
- Added `api*` to setuptools packages

**Environment (`.env.example`):**
- Added `REST_API_KEY=` with comment

**Test suite:**
- `tests/test_api_views.py` — 15 tests: health (200 + db check), list memories (200), create memory (201), create validation (content too long, importance out of range), get memory (200 + service call with UUID), get/update/delete nonexistent (404), update memory (200), delete memory (204), search (200 with rrf_score, validation), stats (200 with counts, empty db), tags (200 with counts). All mock the service layer via `patch("api.views.memory_service")` / `patch("api.views.search_service")` with `AsyncMock`.
- `tests/test_api_auth.py` — 5 tests: secured mode (valid key → 200, missing bearer → 403, invalid token → 403, health allows unauthenticated), dev mode (no header → 200), session auth (Django login → 200 in secured mode). Uses `@override_settings` to switch `REST_FRAMEWORK` and `REST_API_KEY`.
- `tests/test_api_throttling.py` — 2 tests: read throttle (3rd request at 2/min rate → 429), write throttle (3rd request → 429). Uses `@override_settings` with low rates.

### Reviewer

**Action:** REQUEST_CHANGES

Implementation is close, but there is a blocking test-suite issue that prevents reliable verification.

**Blocking issue:**
- `tests/test_api_views.py` and `tests/test_api_auth.py` patch `api.views.connection` for health checks, but `api/views.py` imports `connection` inside `HealthView.get()` (`from django.db import connection`) and has no module-level `connection` symbol.
- As written, `patch("api.views.connection")` is an invalid target and will error at runtime, so the health tests are not actually patching DB connectivity as intended.

**Required changes:**
1. Fix health test patch targets to patch what the view actually uses, e.g.:
   - patch `django.db.connection.ensure_connection`, or
   - move `connection` to a module-level import in `api/views.py` and patch that stable symbol.
2. Re-verify health tests after patching so they assert behavior deterministically without requiring a live DB.

Please address and resubmit.

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

Addressed the blocking health test patch target issue.

**Fix (`api/views.py`):**
- Moved `from django.db import connection` from inside `HealthView.get()` to a module-level import. `connection` is now a stable module attribute that `patch("api.views.connection")` can target.

**Tests unchanged:**
- `tests/test_api_views.py` and `tests/test_api_auth.py` already use `patch("api.views.connection")` — this now resolves correctly to the module-level `connection` symbol.
- Health tests mock `connection.ensure_connection` as a `MagicMock()`, so they assert behavior deterministically without a live DB.

### Reviewer

**Action:** REQUEST_CHANGES

The round-2 functional fix is good, but there are still blocking CI-quality issues in the new tests.

**Blocking issues:**
- `ruff check` fails on the REST API test suite:
  1. `tests/test_api_auth.py`: local variable `user` assigned but unused (`F841`).
  2. `tests/test_api_throttling.py`: unused import `MagicMock` (`F401`).
  3. `tests/test_api_views.py`: unused import `Counter` (`F401`).

**Required changes:**
1. Resolve the three Ruff violations in the test files above.
2. Re-run `ruff check` for `api/` and REST API tests to confirm clean static checks.

After those are clean, this implementation should be ready for approval.

---

## Round 3

### Lead

**Action:** SUBMIT_FOR_REVIEW

Resolved all three Ruff violations:

1. `tests/test_api_auth.py` (F841): Changed `user = User.objects.create_user(...)` to `User.objects.create_user(...)` — the return value was unused since login uses credentials directly.
2. `tests/test_api_throttling.py` (F401): Removed unused `MagicMock` import.
3. `tests/test_api_views.py` (F401): Removed unused `Counter` import.

### Reviewer

**Action:** APPROVE

Approved. Round 3 resolves the remaining review blockers:
- Health check patchability fix is in place (`connection` is module-level in `api/views.py`).
- Previously failing Ruff issues in REST API tests are fixed.
- Verification check now passes: `ruff check api tests/test_api_views.py tests/test_api_auth.py tests/test_api_throttling.py`.

No further blocking issues for the REST API implementation phase.

---

<!-- CYCLE_STATUS -->
```
READY_FOR: lead
ROUND: 3
STATE: approved
```
