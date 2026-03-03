"""Tests for ingestion.batch_processor — batch ingestion pipeline."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ingestion.batch_processor import process_batch


class TestProcessBatch:
    """Batch processing behavior."""

    @pytest.mark.asyncio
    async def test_processes_url_items(self):
        mock_memory = MagicMock()
        mock_memory.id = "batch-mem-1"

        with patch("ingestion.batch_processor.scrape_url", new_callable=AsyncMock) as mock_scrape:
            mock_scrape.return_value = [
                {"id": "mem-1", "chunk_index": 0, "status": "ok"},
            ]
            results = await process_batch([
                {"type": "url", "url": "https://example.com"},
            ])

        assert len(results) == 1
        assert results[0]["status"] == "ok"
        assert results[0]["type"] == "url"
        assert results[0]["memories_created"] == 1

    @pytest.mark.asyncio
    async def test_processes_file_items(self):
        with patch("ingestion.batch_processor.ingest_file", new_callable=AsyncMock) as mock_ingest:
            mock_ingest.return_value = [
                {"id": "mem-1", "chunk_index": 0, "status": "ok"},
                {"id": "mem-2", "chunk_index": 1, "status": "ok"},
            ]
            results = await process_batch([
                {"type": "file", "file_bytes": b"content", "filename": "test.txt"},
            ])

        assert len(results) == 1
        assert results[0]["status"] == "ok"
        assert results[0]["memories_created"] == 2

    @pytest.mark.asyncio
    async def test_handles_unknown_type(self):
        results = await process_batch([
            {"type": "unknown"},
        ])
        assert len(results) == 1
        assert results[0]["status"] == "error"
        assert "Unknown item type" in results[0]["error"]

    @pytest.mark.asyncio
    async def test_handles_item_errors_gracefully(self):
        with patch("ingestion.batch_processor.scrape_url", new_callable=AsyncMock) as mock_scrape:
            mock_scrape.side_effect = ValueError("Network error")
            results = await process_batch([
                {"type": "url", "url": "https://bad.example.com"},
            ])

        assert len(results) == 1
        assert results[0]["status"] == "error"
        assert "Network error" in results[0]["error"]

    @pytest.mark.asyncio
    async def test_mixed_batch_with_partial_failure(self):
        with (
            patch("ingestion.batch_processor.scrape_url", new_callable=AsyncMock) as mock_scrape,
            patch("ingestion.batch_processor.ingest_file", new_callable=AsyncMock) as mock_ingest,
        ):
            mock_scrape.return_value = [{"id": "m1", "chunk_index": 0, "status": "ok"}]
            mock_ingest.side_effect = ValueError("Bad file")

            results = await process_batch([
                {"type": "url", "url": "https://example.com"},
                {"type": "file", "file_bytes": b"bad", "filename": "bad.txt"},
            ])

        assert len(results) == 2
        assert results[0]["status"] == "ok"
        assert results[1]["status"] == "error"

    @pytest.mark.asyncio
    async def test_progress_callback(self):
        progress_calls = []

        with patch("ingestion.batch_processor.scrape_url", new_callable=AsyncMock) as mock_scrape:
            mock_scrape.return_value = [{"id": "m1", "chunk_index": 0, "status": "ok"}]
            await process_batch(
                [
                    {"type": "url", "url": "https://a.com"},
                    {"type": "url", "url": "https://b.com"},
                ],
                on_progress=lambda completed, total: progress_calls.append((completed, total)),
            )

        assert progress_calls == [(1, 2), (2, 2)]

    @pytest.mark.asyncio
    async def test_empty_batch(self):
        results = await process_batch([])
        assert results == []
