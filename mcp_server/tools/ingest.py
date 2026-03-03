"""MCP tools for ingestion — store_from_url and ingest_file."""

import base64
import json

from ingestion.file_ingestor import ingest_file as _ingest_file
from ingestion.url_scraper import SSRFError, scrape_url
from mcp_server.server import mcp


@mcp.tool()
async def store_from_url(
    url: str,
    tags: list[str] | None = None,
    importance: float = 0.5,
) -> str:
    """Fetch a URL and store its content as memories."""
    try:
        results = await scrape_url(url=url, tags=tags, importance=importance)
        return json.dumps({
            "status": "ok",
            "memories_created": len(results),
            "results": results,
        })
    except SSRFError as exc:
        return f"SSRF validation failed: {exc}"
    except Exception as exc:
        return f"Error ingesting URL: {exc}"


@mcp.tool()
async def ingest_file(
    content_base64: str,
    filename: str,
    tags: list[str] | None = None,
    importance: float = 0.5,
) -> str:
    """Ingest a base64-encoded file and store its content as memories."""
    try:
        file_bytes = base64.b64decode(content_base64)
    except Exception:
        return "Error: invalid base64 content"

    try:
        results = await _ingest_file(
            file_bytes=file_bytes,
            filename=filename,
            tags=tags,
            importance=importance,
        )
        return json.dumps({
            "status": "ok",
            "memories_created": len(results),
            "results": results,
        })
    except Exception as exc:
        return f"Error ingesting file: {exc}"
