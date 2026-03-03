"""Progress-tracked batch ingestion pipeline."""

from __future__ import annotations

from collections.abc import Callable

from .file_ingestor import ingest_file
from .url_scraper import scrape_url


async def process_batch(
    items: list[dict],
    on_progress: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """Process a batch of ingestion items sequentially.

    Each item is a dict with 'type' ('file' or 'url') and relevant parameters.
    Returns per-item results with index, type, status, and memories_created or error.
    """
    total = len(items)
    results = []

    for i, item in enumerate(items):
        item_type = item.get("type", "")
        try:
            if item_type == "file":
                item_results = await ingest_file(
                    file_path=item.get("file_path"),
                    file_bytes=item.get("file_bytes"),
                    filename=item.get("filename", ""),
                    source=item.get("source", "import"),
                    tags=item.get("tags"),
                    importance=item.get("importance", 0.5),
                )
                results.append({
                    "index": i,
                    "type": "file",
                    "status": "ok",
                    "memories_created": len(item_results),
                })
            elif item_type == "url":
                item_results = await scrape_url(
                    url=item["url"],
                    source=item.get("source", "url"),
                    tags=item.get("tags"),
                    importance=item.get("importance", 0.5),
                )
                results.append({
                    "index": i,
                    "type": "url",
                    "status": "ok",
                    "memories_created": len(item_results),
                })
            else:
                results.append({
                    "index": i,
                    "type": item_type,
                    "status": "error",
                    "error": f"Unknown item type: {item_type}",
                })
        except Exception as exc:
            results.append({
                "index": i,
                "type": item_type,
                "status": "error",
                "error": str(exc),
            })

        if on_progress:
            on_progress(i + 1, total)

    return results
