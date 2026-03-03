"""Text chunking with overlap for ingestion pipeline."""

from __future__ import annotations

import re

from django.conf import settings


def chunk_text(
    text: str,
    max_chars: int | None = None,
    overlap: int | None = None,
) -> list[str]:
    """Split text into chunks with overlap. Breaks at paragraph/sentence boundaries.

    Returns at least one chunk even for short/empty text.
    """
    if max_chars is None:
        max_chars = getattr(settings, "INGEST_CHUNK_SIZE", 2000)
    if overlap is None:
        overlap = getattr(settings, "INGEST_CHUNK_OVERLAP", 200)

    text = text.strip()
    if not text:
        return [text]

    if len(text) <= max_chars:
        return [text]

    # Split on double-newlines (paragraphs)
    paragraphs = re.split(r"\n\n+", text)

    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # If adding this paragraph would exceed max_chars, flush current chunk
        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current.strip())
            # Start next chunk with overlap from end of previous
            if overlap > 0 and len(current) > overlap:
                current = current[-overlap:] + "\n\n" + para
            else:
                current = para
        elif len(para) > max_chars:
            # Paragraph itself exceeds max_chars — split on sentence boundaries
            if current:
                chunks.append(current.strip())
                overlap_prefix = current[-overlap:] if overlap > 0 and len(current) > overlap else ""
                current = overlap_prefix
            else:
                current = ""

            sentences = _split_sentences(para)
            for sentence in sentences:
                if current and len(current) + len(sentence) + 1 > max_chars:
                    chunks.append(current.strip())
                    if overlap > 0 and len(current) > overlap:
                        current = current[-overlap:] + " " + sentence
                    else:
                        current = sentence
                elif not current:
                    current = sentence
                else:
                    current = current + " " + sentence
        else:
            if current:
                current = current + "\n\n" + para
            else:
                current = para

    if current.strip():
        chunks.append(current.strip())

    return chunks if chunks else [text]


def _split_sentences(text: str) -> list[str]:
    """Split text on sentence boundaries (. ? !)."""
    parts = re.split(r"(?<=[.?!])\s+", text)
    return [p for p in parts if p.strip()]
