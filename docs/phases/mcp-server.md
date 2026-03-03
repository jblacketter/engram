# Phase 3: MCP Server

## Summary

FastMCP server exposing the memory system to AI clients (Claude Desktop, Claude Code, Cursor) over Streamable HTTP. Consumes the shared `core/services/` layer from Phase 2 — no logic duplication. Includes API key authentication and client config files.

## Scope

- FastMCP server on port 8080 with Streamable HTTP transport at `/mcp`
- 8 MCP tools: `store_memory`, `search_brain`, `list_recent`, `get_memory`, `update_memory`, `delete_memory`, `find_related`, `get_stats`
- Conditional API key authentication: `DebugTokenVerifier` when `MCP_API_KEY` is set, `auth=None` in dev mode
- Django bootstrapping (settings init before importing services)
- Client config files for Claude Desktop, Claude Code, Cursor
- Test suite for tool functions with mocked services

## Technical Approach

### Server Entry Point (`mcp_server/server.py`)

Standalone FastMCP process (not a Django app). Bootstraps Django settings at module level, then defines tools.

```python
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "openbrain.settings.development")
django.setup()

from fastmcp import FastMCP
from mcp_server.auth import build_auth

mcp = FastMCP(
    "open-brain",
    auth=build_auth(),  # DebugTokenVerifier when MCP_API_KEY set, None otherwise
)
```

**Django bootstrapping:** `django.setup()` at top of module ensures ORM, settings, and apps are available before any tool imports. This is the standard pattern for standalone Django scripts.

**Transport:** Streamable HTTP on `0.0.0.0:8080` at path `/mcp`. Run via:
```python
mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)
```

### Authentication (`mcp_server/auth.py`)

**Conditional auth wiring.** `DebugTokenVerifier` rejects requests with missing/empty bearer tokens before the `validate` callback runs. Therefore auth must be wired conditionally at server startup — not inside the validator.

```python
from django.conf import settings
from fastmcp.server.auth.providers.debug import DebugTokenVerifier


def build_auth() -> DebugTokenVerifier | None:
    """Build auth provider. Returns None (no auth) when MCP_API_KEY is empty."""
    api_key = settings.MCP_API_KEY
    if not api_key:
        return None  # Dev mode: no auth, no header required

    async def verify_api_key(token: str) -> bool:
        return token == api_key

    return DebugTokenVerifier(validate=verify_api_key)
```

**Two distinct modes:**
- **Dev mode** (`MCP_API_KEY=""`, the default): `auth=None` — FastMCP applies no authentication middleware. Requests without an `Authorization` header are accepted. No header required at all.
- **Secured mode** (`MCP_API_KEY="some-secret"`): `auth=DebugTokenVerifier(validate=...)` — FastMCP's `BearerAuthBackend` requires `Authorization: Bearer <token>`. The `verify_api_key` callback compares the token to the configured key. Missing or invalid tokens are rejected before any tool runs.

**Settings addition:** `MCP_API_KEY = os.getenv("MCP_API_KEY", "")` in `base.py`.

### MCP Tools (`mcp_server/tools/`)

All tools are thin wrappers calling `core/services/` functions. Each tool is an `async def` decorated with `@mcp.tool()`. Tools return JSON strings (MCP protocol expects text content).

**Package structure:**
```
mcp_server/
├── __init__.py
├── server.py          # FastMCP app, Django bootstrap, run()
├── auth.py            # API key verification
└── tools/
    ├── __init__.py    # Registers all tool modules
    ├── memory.py      # store, get, update, delete
    ├── search.py      # search_brain, find_related, list_recent
    └── stats.py       # get_stats
```

#### Memory Tools (`mcp_server/tools/memory.py`)

```python
@mcp.tool()
async def store_memory(
    content: str,
    source: str = "mcp",
    tags: list[str] | None = None,
    importance: float = 0.5,
) -> str:
    """Store a new memory in the brain. Returns the memory ID."""

@mcp.tool()
async def get_memory(memory_id: str) -> str:
    """Retrieve a specific memory by its UUID."""

@mcp.tool()
async def update_memory(
    memory_id: str,
    content: str | None = None,
    tags: list[str] | None = None,
    importance: float | None = None,
) -> str:
    """Update an existing memory. Only provided fields are changed.
    Updating content re-generates the embedding."""

@mcp.tool()
async def delete_memory(memory_id: str) -> str:
    """Delete a memory by its UUID."""
```

- `memory_id` is `str` (not UUID) because MCP tool parameters are JSON primitives; parse to UUID inside.
- `store_memory` defaults `source="mcp"` to distinguish MCP-originated memories.
- All tools return JSON-formatted strings for structured data, plain text for confirmations.

#### Search Tools (`mcp_server/tools/search.py`)

```python
@mcp.tool()
async def search_brain(
    query: str,
    limit: int = 10,
    tags: list[str] | None = None,
    source: str | None = None,
    semantic_weight: float = 0.5,
) -> str:
    """Search the brain using hybrid semantic + keyword search.

    semantic_weight controls the blend: 0.0 = pure keyword, 1.0 = pure semantic,
    0.5 = balanced (default). Returns ranked results with relevance scores."""

@mcp.tool()
async def find_related(memory_id: str, limit: int = 5) -> str:
    """Find memories related to a specific memory. Uses the memory's content
    as a search query with pure semantic search (weight=1.0)."""

@mcp.tool()
async def list_recent_memories(limit: int = 20, source: str | None = None) -> str:
    """List the most recently created memories, optionally filtered by source."""
```

- `find_related` fetches the target memory, then calls `search_service.search()` with its content and `semantic_weight=1.0`.
- `list_recent_memories` (renamed to avoid collision with the service function name) wraps `memory_service.list_recent()`.

#### Stats Tool (`mcp_server/tools/stats.py`)

```python
@mcp.tool()
async def get_stats() -> str:
    """Get statistics about stored memories: total count, counts by source,
    most common tags, and date range."""
```

Implementation uses `sync_to_async` wrapped ORM aggregation queries:
- `Memory.objects.count()` for total
- `Memory.objects.values("source").annotate(count=Count("id"))` for source breakdown
- `Memory.objects.aggregate(Min("created_at"), Max("created_at"))` for date range
- Tag frequency via a raw SQL query or Python-side aggregation of the JSONField

### Tool Registration Pattern

Tools are defined in separate modules but need access to the `mcp` instance. Pattern: define the `mcp` instance in `server.py`, import it in tool modules, and import tool modules in `server.py` after `mcp` is created (circular import avoidance via deferred import).

```python
# server.py
mcp = FastMCP("open-brain", auth=build_auth())

# Import tool modules to register decorators
import mcp_server.tools  # noqa: F401, E402

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8080)
```

```python
# tools/__init__.py
import mcp_server.tools.memory   # noqa: F401
import mcp_server.tools.search   # noqa: F401
import mcp_server.tools.stats    # noqa: F401
```

```python
# tools/memory.py
from mcp_server.server import mcp

@mcp.tool()
async def store_memory(...): ...
```

### Client Configuration Files

Create template config files in `docs/` for users to copy:

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "open-brain": {
      "url": "http://localhost:8080/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}
```

**Claude Code** (via CLI):
```bash
claude mcp add open-brain http://localhost:8080/mcp --header "Authorization: Bearer YOUR_API_KEY"
```

**Cursor** (`.cursor/mcp.json`):
```json
{
  "mcpServers": {
    "open-brain": {
      "url": "http://localhost:8080/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}
```

### Error Handling

All tools catch service-layer exceptions and return user-friendly error messages:
- `Memory.DoesNotExist` → `"Memory {id} not found."`
- `ValueError` (e.g., invalid UUID) → `"Invalid memory ID format."`
- `httpx.ConnectError` (embedding failure) → `"Embedding service unavailable. Please check Ollama is running."`

Errors are returned as tool result text, not raised as exceptions — MCP clients need readable error messages.

### Test Suite

Tests mock the service layer (not the database) to test tool logic in isolation.

- `tests/test_mcp_tools.py` — Tests for all 8 tools:
  - `store_memory`: verifies service call, default source="mcp", returns ID
  - `search_brain`: verifies search params forwarded, results formatted
  - `get_memory` / `update_memory` / `delete_memory`: CRUD forwarding
  - `find_related`: verifies it fetches memory content, searches with weight=1.0
  - `list_recent_memories`: verifies limit/source forwarding
  - `get_stats`: verifies aggregation results formatted
  - Error cases: not-found, invalid UUID, embedding service down
- `tests/test_mcp_auth.py` — Auth mode tests:
  - **Secured mode**: `build_auth()` returns a `DebugTokenVerifier` when `MCP_API_KEY` is set; verifier rejects invalid tokens and accepts valid ones
  - **Dev mode**: `build_auth()` returns `None` when `MCP_API_KEY` is empty, confirming no auth middleware is applied

## Files to Create/Modify

| Action | File | Description |
|--------|------|-------------|
| Create | `mcp_server/__init__.py` | Package init |
| Create | `mcp_server/server.py` | FastMCP app, Django bootstrap, entry point |
| Create | `mcp_server/auth.py` | API key verification function |
| Create | `mcp_server/tools/__init__.py` | Tool module registration |
| Create | `mcp_server/tools/memory.py` | store, get, update, delete tools |
| Create | `mcp_server/tools/search.py` | search_brain, find_related, list_recent |
| Create | `mcp_server/tools/stats.py` | get_stats tool |
| Create | `tests/test_mcp_tools.py` | Tool function tests |
| Create | `tests/test_mcp_auth.py` | Auth mode tests (secured + dev) |
| Modify | `openbrain/settings/base.py` | Add `MCP_API_KEY` setting |
| Modify | `.env.example` | Add `MCP_API_KEY` variable |

## Success Criteria

1. `python -m mcp_server.server` starts FastMCP on port 8080 with Streamable HTTP
2. All 8 tools are discoverable via MCP protocol
3. `store_memory` creates a memory with source="mcp" and returns the ID
4. `search_brain` returns ranked results using hybrid search
5. `find_related` finds semantically similar memories
6. `get_stats` returns memory count, source breakdown, and date range
7. API key authentication rejects requests without valid bearer token (when `MCP_API_KEY` is set)
8. Auth is permissive when `MCP_API_KEY` is empty (dev mode)
9. Tests pass with mocked service layer
