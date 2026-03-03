# Phase 4: REST API

## Summary

Django REST Framework API mirroring MCP tools, with API key + session authentication, OpenAPI/Swagger docs, rate limiting, and CORS configuration for the React dashboard. Consumes the shared `core/services/` layer — no logic duplication with the MCP server.

## Scope

- DRF API app at `/api/` with 6 endpoint groups
- API key authentication (bearer token) + Django session auth (for dashboard)
- OpenAPI schema generation and Swagger UI at `/api/docs/`
- Rate limiting: 100 read/min, 30 write/min
- CORS configured for React dev server
- Health check endpoint
- Test suite for views, auth, and serializers

## Technical Approach

### Async/Sync Bridge

The `core/services/` layer is fully async. DRF does not fully support async views. **Strategy: use `async_to_sync` wrappers in sync DRF views.** This is safe because Django's WSGI server runs each request in its own thread, and `async_to_sync` creates an event loop per call to run the async service function.

```python
from asgiref.sync import async_to_sync
from core.services import memory_service

# In a DRF view:
memory = async_to_sync(memory_service.create_memory)(content="hello", source="api")
```

This is the standard Django pattern for calling async code from sync contexts.

### API App Structure

```
api/
├── __init__.py
├── apps.py              # Django AppConfig
├── authentication.py    # API key auth backend
├── throttling.py        # Read/write rate limiting
├── serializers.py       # Input/output serializers
├── views.py             # DRF views
└── urls.py              # URL routing
```

The `api` app is a standard Django app registered in `INSTALLED_APPS`.

### Authentication (`api/authentication.py`)

Custom DRF authentication backend with an authenticated user principal for successful API key validation.

**`APIKeyUser` — lightweight authenticated principal:**
```python
class APIKeyUser:
    """Represents a successfully authenticated API key holder."""
    is_authenticated = True
    is_active = True
    is_anonymous = False
    username = "api-key-user"
```

Not a Django `User` model instance — just satisfies DRF's `request.user` contract. `is_authenticated = True` ensures `IsAuthenticated` permission passes.

**`APIKeyAuthentication`:**
```python
class APIKeyAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith(f"{self.keyword} "):
            return None  # Fall through to next auth class
        token = auth_header[len(self.keyword) + 1:]
        expected = settings.REST_API_KEY
        if not expected:
            return None  # Dev mode: skip API key auth entirely
        if token != expected:
            raise AuthenticationFailed("Invalid API key.")
        return (APIKeyUser(), None)  # Authenticated principal
```

**Two auth classes configured in DRF settings:**
1. `APIKeyAuthentication` — for programmatic access (curl, scripts, external tools)
2. `SessionAuthentication` — for the React dashboard (CSRF-protected)

**Permission strategy per mode:**

- **Secured mode** (`REST_API_KEY` set): Global `DEFAULT_PERMISSION_CLASSES = ["rest_framework.permissions.IsAuthenticated"]`. Requests must pass either `APIKeyAuthentication` (bearer token → `APIKeyUser` with `is_authenticated=True`) or `SessionAuthentication` (logged-in Django user). Missing/invalid bearer tokens are rejected. Health endpoint overrides to `AllowAny`.

- **Dev mode** (`REST_API_KEY=""`): Global `DEFAULT_PERMISSION_CLASSES` is set to `["rest_framework.permissions.AllowAny"]` via a conditional in settings. `APIKeyAuthentication.authenticate()` returns `None` (skip), so no bearer token is needed. All endpoints are accessible without auth. This matches the MCP server's dev-mode pattern.

**Settings conditional:**
```python
REST_API_KEY = os.getenv("REST_API_KEY", "")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.authentication.APIKeyAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated"
        if REST_API_KEY
        else "rest_framework.permissions.AllowAny"
    ],
    ...
}
```

### Serializers (`api/serializers.py`)

```python
class MemorySerializer(serializers.ModelSerializer):
    """Read serializer — full memory representation."""
    class Meta:
        model = Memory
        fields = ["id", "content", "source", "tags", "metadata",
                  "importance", "decay_factor", "access_count",
                  "last_accessed", "created_at", "updated_at"]
        read_only_fields = fields

class MemoryCreateSerializer(serializers.Serializer):
    """Write serializer — create a new memory."""
    content = serializers.CharField(max_length=50000)
    source = serializers.CharField(max_length=50, default="api")
    tags = serializers.ListField(child=serializers.CharField(max_length=100),
                                  max_length=20, required=False)
    metadata = serializers.JSONField(required=False)
    importance = serializers.FloatField(min_value=0.0, max_value=1.0, default=0.5)

class MemoryUpdateSerializer(serializers.Serializer):
    """Write serializer — partial update."""
    content = serializers.CharField(max_length=50000, required=False)
    tags = serializers.ListField(child=serializers.CharField(max_length=100),
                                  max_length=20, required=False)
    metadata = serializers.JSONField(required=False)
    importance = serializers.FloatField(min_value=0.0, max_value=1.0, required=False)

class SearchRequestSerializer(serializers.Serializer):
    """Input for hybrid search."""
    query = serializers.CharField()
    limit = serializers.IntegerField(min_value=1, max_value=100, default=10)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    source = serializers.CharField(required=False)
    after = serializers.DateTimeField(required=False)
    before = serializers.DateTimeField(required=False)
    semantic_weight = serializers.FloatField(min_value=0.0, max_value=1.0, default=0.5)

class SearchResultSerializer(serializers.Serializer):
    """Output for hybrid search — memory fields + rrf_score."""
    id = serializers.UUIDField()
    content = serializers.CharField()
    source = serializers.CharField()
    tags = serializers.ListField()
    metadata = serializers.JSONField()
    importance = serializers.FloatField()
    rrf_score = serializers.FloatField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
```

**Input validation enforced in serializers:**
- Content max 50KB (50,000 chars)
- Tags max 20 items, each max 100 chars
- Importance 0.0–1.0
- Search limit 1–100

### Views (`api/views.py`)

All views call the service layer via `async_to_sync`.

**MemoryListCreateView** (`GET /api/memories/`, `POST /api/memories/`):
- GET: calls `memory_service.list_recent()`, returns `MemorySerializer(many=True)`
- POST: validates with `MemoryCreateSerializer`, calls `memory_service.create_memory()`, returns 201

**MemoryDetailView** (`GET /api/memories/{id}/`, `PATCH /api/memories/{id}/`, `DELETE /api/memories/{id}/`):
- GET: calls `memory_service.get_memory()` (increments access_count), returns `MemorySerializer`
- PATCH: validates with `MemoryUpdateSerializer`, calls `memory_service.update_memory()`, returns `MemorySerializer`
- DELETE: calls `memory_service.delete_memory()`, returns 204

**SearchView** (`POST /api/search/`):
- Validates with `SearchRequestSerializer`, calls `search_service.search()`, returns `SearchResultSerializer(many=True)`

**StatsView** (`GET /api/stats/`):
- Uses `sync_to_async` wrapped ORM aggregation (same logic as MCP stats tool), returns JSON dict

**TagsView** (`GET /api/tags/`):
- Aggregates tag counts from all memories, returns list of `{tag, count}` sorted by count desc

**HealthView** (`GET /api/health/`):
- Returns `{"status": "ok", "database": true/false}` — checks DB connectivity
- Permission: `AllowAny` (no auth required)

### Rate Limiting (`api/throttling.py`)

```python
class ReadRateThrottle(SimpleRateThrottle):
    scope = "read"
    rate = "100/min"

class WriteRateThrottle(SimpleRateThrottle):
    scope = "write"
    rate = "30/min"
```

Applied per-view:
- GET views use `ReadRateThrottle`
- POST/PATCH/DELETE views use `WriteRateThrottle`
- Health endpoint: no throttling

### URL Routing (`api/urls.py`)

```python
urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("memories/", MemoryListCreateView.as_view(), name="memory-list"),
    path("memories/<uuid:pk>/", MemoryDetailView.as_view(), name="memory-detail"),
    path("search/", SearchView.as_view(), name="search"),
    path("stats/", StatsView.as_view(), name="stats"),
    path("tags/", TagsView.as_view(), name="tags"),
]
```

Included in `openbrain/urls.py` as `path("api/", include("api.urls"))`.

### OpenAPI Documentation

Uses `drf-spectacular` for automatic OpenAPI 3.0 schema generation:
- Schema endpoint: `GET /api/schema/`
- Swagger UI: `GET /api/docs/`

**New dependency:** `drf-spectacular` added to `pyproject.toml`.
**Settings:** Added to `INSTALLED_APPS` and configured in `REST_FRAMEWORK` settings.

### DRF Settings (added to `base.py`)

```python
REST_API_KEY = os.getenv("REST_API_KEY", "")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.authentication.APIKeyAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated"
        if REST_API_KEY
        else "rest_framework.permissions.AllowAny"
    ],
    "DEFAULT_THROTTLE_CLASSES": [],  # Applied per-view
    "DEFAULT_THROTTLE_RATES": {
        "read": "100/min",
        "write": "30/min",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Open Brain API",
    "DESCRIPTION": "Personal semantic memory system API",
    "VERSION": "1.0.0",
}
```

### Error Handling

Views catch service exceptions and return appropriate HTTP responses:
- `Memory.DoesNotExist` → 404
- `ValueError` (invalid UUID) → 400
- `httpx.ConnectError` / `httpx.ConnectTimeout` → 503 with error message
- Validation errors → 400 (handled by DRF serializer validation)

### Test Suite

- `tests/test_api_views.py` — Integration tests using DRF's `APIClient`:
  - CRUD: create memory (201), get memory (200 + access_count incremented), update memory (200), delete memory (204), list memories (200)
  - Search: POST /api/search/ returns results with rrf_score
  - Stats: GET /api/stats/ returns counts
  - Tags: GET /api/tags/ returns tag counts
  - Health: GET /api/health/ returns ok (no auth required)
  - 404: get/update/delete non-existent memory
  - Validation: content too long, importance out of range
- `tests/test_api_auth.py` — Auth tests:
  - Secured mode: valid API key receives 2xx on protected endpoints (via `APIKeyUser` with `is_authenticated=True`); missing bearer header returns 403; invalid token returns 403
  - Dev mode: no-header access returns 2xx (permission is `AllowAny`)
  - Session auth: authenticated Django session can access protected endpoints in secured mode
- `tests/test_api_throttling.py` — Throttle tests:
  - Read endpoint exceeding 100/min returns 429
  - Write endpoint exceeding 30/min returns 429

## Files to Create/Modify

| Action | File | Description |
|--------|------|-------------|
| Create | `api/__init__.py` | Package init |
| Create | `api/apps.py` | Django AppConfig |
| Create | `api/authentication.py` | API key auth backend |
| Create | `api/throttling.py` | Read/write rate throttles |
| Create | `api/serializers.py` | Input/output serializers |
| Create | `api/views.py` | DRF views |
| Create | `api/urls.py` | URL routing |
| Create | `tests/test_api_views.py` | View integration tests |
| Create | `tests/test_api_auth.py` | Auth tests |
| Create | `tests/test_api_throttling.py` | Throttle tests |
| Modify | `openbrain/urls.py` | Include api.urls + drf-spectacular |
| Modify | `openbrain/settings/base.py` | Add REST_API_KEY, REST_FRAMEWORK, SPECTACULAR_SETTINGS, api to INSTALLED_APPS |
| Modify | `.env.example` | Add REST_API_KEY |
| Modify | `pyproject.toml` | Add drf-spectacular dependency, api to packages |

## Success Criteria

1. `GET /api/health/` returns `{"status": "ok"}` without auth
2. `POST /api/memories/` creates a memory with source="api", returns 201
3. `GET /api/memories/{id}/` returns memory and increments access_count
4. `PATCH /api/memories/{id}/` updates fields, re-embeds on content change
5. `DELETE /api/memories/{id}/` returns 204
6. `POST /api/search/` returns ranked results with rrf_score
7. `GET /api/stats/` returns total count, source breakdown, date range
8. `GET /api/tags/` returns tag list with counts
9. Bearer token auth rejects invalid/missing tokens when `REST_API_KEY` is set
10. Auth is permissive when `REST_API_KEY` is empty (dev mode)
11. Swagger UI accessible at `/api/docs/`
12. Rate limiting returns 429 when exceeded
13. Input validation rejects content > 50KB, importance outside 0–1
14. Tests pass with mocked embedding providers
