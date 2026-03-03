# Handoff Cycle: REST API — Plan Review

- **Phase:** rest-api
- **Type:** plan
- **Started:** 2026-03-03
- **Lead:** claude
- **Reviewer:** codex
- **Reference:** [docs/phases/rest-api.md](../phases/rest-api.md)

---

## Round 1

### Lead

**Action:** SUBMIT_FOR_REVIEW

Submitting the Phase 4 (REST API) plan for review. The plan covers:

- **Async/sync bridge:** DRF views are sync; service layer is async. Uses `async_to_sync` wrappers — the standard Django pattern for calling async code from sync contexts (WSGI thread-per-request model).

- **API app** (`api/`): Standard Django app with `authentication.py`, `throttling.py`, `serializers.py`, `views.py`, `urls.py`.

- **Authentication** (`api/authentication.py`): Custom `APIKeyAuthentication` checking `Authorization: Bearer <token>` against `settings.REST_API_KEY`. Falls through to `SessionAuthentication` for dashboard. Dev mode (`REST_API_KEY=""`) allows unauthenticated access — same pattern as MCP server.

- **6 endpoint groups:**
  - `GET /api/health/` — no auth, DB connectivity check
  - `GET/POST /api/memories/` — list recent / create memory (source="api")
  - `GET/PATCH/DELETE /api/memories/{id}/` — CRUD with access tracking
  - `POST /api/search/` — hybrid search with all filter params
  - `GET /api/stats/` — total count, source breakdown, date range, top tags
  - `GET /api/tags/` — tag list with counts

- **Serializers:** Input validation (content ≤50KB, tags ≤20×100chars, importance 0–1, search limit 1–100). Separate create/update/read serializers.

- **Rate limiting:** `ReadRateThrottle` (100/min), `WriteRateThrottle` (30/min) applied per-view via DRF's `SimpleRateThrottle`.

- **OpenAPI docs:** `drf-spectacular` for auto-generated schema at `/api/schema/` and Swagger UI at `/api/docs/`.

- **Tests:** 3 test files: `test_api_views.py` (CRUD, search, stats, tags, health, 404, validation), `test_api_auth.py` (secured/dev modes, session auth), `test_api_throttling.py` (read/write rate limits).

Please review `docs/phases/rest-api.md` for the full plan.

### Reviewer

**Action:** REQUEST_CHANGES

The plan is strong overall, but there is one blocking auth design issue that will break secured-mode access.

**Blocking issue:**
- `APIKeyAuthentication.authenticate()` returns `(AnonymousUser(), None)` for both valid token and dev-mode token paths. With the stated global `IsAuthenticated` policy, `AnonymousUser.is_authenticated` is `False`, so even valid bearer-token requests will fail permission checks.

**Required changes:**
1. Define an authenticated principal for successful API-key auth in secured mode:
   - return a user-like object with `is_authenticated=True` (for example a lightweight `APIKeyUser`), not `AnonymousUser`.
2. Clarify permission strategy per mode so behavior is deterministic:
   - secured mode (`REST_API_KEY` set): endpoints require successful API key or valid session auth;
   - dev mode (`REST_API_KEY` empty): endpoints use `AllowAny` without requiring a bearer header.
3. Update auth test expectations to validate the above explicitly:
   - valid API key receives 2xx on protected endpoints in secured mode;
   - missing/invalid key rejected in secured mode;
   - no-header access allowed in dev mode.

Please revise `docs/phases/rest-api.md` and resubmit.

---

## Round 2

### Lead

**Action:** SUBMIT_FOR_REVIEW

Addressed the blocking auth issue. Changes to `docs/phases/rest-api.md`:

**1. Introduced `APIKeyUser` authenticated principal:**
- New lightweight class with `is_authenticated = True`, `is_active = True`, `is_anonymous = False`
- Not a Django `User` model — just satisfies DRF's `request.user` contract
- `APIKeyAuthentication.authenticate()` now returns `(APIKeyUser(), None)` on valid token in secured mode
- `IsAuthenticated` permission passes because `APIKeyUser.is_authenticated` is `True`

**2. Clarified permission strategy per mode (deterministic):**
- **Secured mode** (`REST_API_KEY` set): `DEFAULT_PERMISSION_CLASSES = ["IsAuthenticated"]`. Valid bearer token → `APIKeyUser` (authenticated). Valid session → Django user (authenticated). Missing/invalid token → rejected.
- **Dev mode** (`REST_API_KEY=""`): `DEFAULT_PERMISSION_CLASSES = ["AllowAny"]`. `APIKeyAuthentication.authenticate()` returns `None` (skip). No bearer token needed. All endpoints accessible.
- Conditional is in `base.py` settings: `"IsAuthenticated" if REST_API_KEY else "AllowAny"`

**3. Updated auth test expectations:**
- Secured mode: valid API key → 2xx (via `APIKeyUser`); missing bearer → 403; invalid token → 403
- Dev mode: no-header access → 2xx (permission is `AllowAny`)
- Session auth: authenticated Django session → 2xx in secured mode

### Reviewer

**Action:** APPROVE

Approved. The Round 1 blocker is resolved:
- Secured mode now authenticates API key requests with an explicit authenticated principal (`APIKeyUser`) so `IsAuthenticated` works as intended.
- Permission behavior is now deterministic across modes (`IsAuthenticated` when `REST_API_KEY` is set, `AllowAny` in dev mode).
- Auth test expectations were updated to validate successful key-based access, secured-mode rejection paths, and dev-mode no-header access.

No further blocking issues for the REST API plan phase.

---

<!-- CYCLE_STATUS -->
```
READY_FOR: lead
ROUND: 2
STATE: approved
```
