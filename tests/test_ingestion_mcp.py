"""Tests for MCP ingestion tools — store_from_url and ingest_file."""

import base64
import json
from unittest.mock import AsyncMock, patch

import pytest


class TestStoreFromUrl:
    """MCP store_from_url tool."""

    @pytest.mark.asyncio
    async def test_stores_url_content(self):
        with patch(
            "mcp_server.tools.ingest.scrape_url", new_callable=AsyncMock
        ) as mock_scrape:
            mock_scrape.return_value = [
                {"id": "mem-1", "chunk_index": 0, "status": "ok"},
                {"id": "mem-2", "chunk_index": 1, "status": "ok"},
            ]
            from mcp_server.tools.ingest import store_from_url

            result = await store_from_url("https://example.com", tags=["test"])

        data = json.loads(result)
        assert data["status"] == "ok"
        assert data["memories_created"] == 2
        mock_scrape.assert_called_once_with(
            url="https://example.com", tags=["test"], importance=0.5
        )

    @pytest.mark.asyncio
    async def test_returns_ssrf_error(self):
        from ingestion.url_scraper import SSRFError

        with patch(
            "mcp_server.tools.ingest.scrape_url", new_callable=AsyncMock
        ) as mock_scrape:
            mock_scrape.side_effect = SSRFError("Loopback blocked")
            from mcp_server.tools.ingest import store_from_url

            result = await store_from_url("http://localhost/admin")

        assert "SSRF validation failed" in result

    @pytest.mark.asyncio
    async def test_returns_generic_error(self):
        with patch(
            "mcp_server.tools.ingest.scrape_url", new_callable=AsyncMock
        ) as mock_scrape:
            mock_scrape.side_effect = RuntimeError("Connection failed")
            from mcp_server.tools.ingest import store_from_url

            result = await store_from_url("https://failing.example.com")

        assert "Error ingesting URL" in result


class TestIngestFileMcp:
    """MCP ingest_file tool."""

    @pytest.mark.asyncio
    async def test_ingests_base64_file(self):
        content = b"Hello, this is a test file."
        content_b64 = base64.b64encode(content).decode()

        with patch(
            "mcp_server.tools.ingest._ingest_file", new_callable=AsyncMock
        ) as mock_ingest:
            mock_ingest.return_value = [
                {"id": "mem-1", "chunk_index": 0, "status": "ok"},
            ]
            from mcp_server.tools.ingest import ingest_file

            result = await ingest_file(
                content_base64=content_b64,
                filename="test.txt",
                tags=["unit-test"],
            )

        data = json.loads(result)
        assert data["status"] == "ok"
        assert data["memories_created"] == 1
        mock_ingest.assert_called_once()
        call_kwargs = mock_ingest.call_args[1]
        assert call_kwargs["file_bytes"] == content
        assert call_kwargs["filename"] == "test.txt"

    @pytest.mark.asyncio
    async def test_returns_error_on_invalid_base64(self):
        from mcp_server.tools.ingest import ingest_file

        result = await ingest_file(
            content_base64="!!!not-valid-base64!!!",
            filename="test.txt",
        )
        assert "invalid base64" in result

    @pytest.mark.asyncio
    async def test_returns_error_on_ingest_failure(self):
        content_b64 = base64.b64encode(b"data").decode()

        with patch(
            "mcp_server.tools.ingest._ingest_file", new_callable=AsyncMock
        ) as mock_ingest:
            mock_ingest.side_effect = ValueError("Unsupported file type")
            from mcp_server.tools.ingest import ingest_file

            result = await ingest_file(
                content_base64=content_b64,
                filename="file.exe",
            )

        assert "Error ingesting file" in result
