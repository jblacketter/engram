"""File parsing and ingestion for PDF, Markdown, DOCX, and plain text."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from django.conf import settings

from core.services import memory_service

from .chunker import chunk_text

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}

FORMAT_TAGS = {
    ".txt": "text",
    ".md": "markdown",
    ".pdf": "pdf",
    ".docx": "docx",
}


async def ingest_file(
    file_path: str | None = None,
    file_bytes: bytes | None = None,
    filename: str = "",
    source: str = "import",
    tags: list[str] | None = None,
    importance: float = 0.5,
) -> list[dict]:
    """Parse a file, chunk content, create memories.

    Provide either file_path (reads from disk) or file_bytes + filename.
    Returns list of {id, chunk_index, status}.
    """
    max_size = getattr(settings, "INGEST_MAX_FILE_SIZE", 10 * 1024 * 1024)

    if file_path:
        path = Path(file_path)
        filename = filename or path.name
        if path.stat().st_size > max_size:
            raise ValueError(f"File exceeds {max_size} byte limit")
        file_bytes = path.read_bytes()
    elif file_bytes is not None:
        if len(file_bytes) > max_size:
            raise ValueError(f"File exceeds {max_size} byte limit")
    else:
        raise ValueError("Provide either file_path or file_bytes")

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    text = _extract_text(file_bytes, ext)
    if not text.strip():
        raise ValueError("No text content extracted from file")

    chunks = chunk_text(text)
    total_chunks = len(chunks)
    tags = list(tags or [])
    format_tag = FORMAT_TAGS.get(ext, "text")

    results = []
    for i, chunk_content in enumerate(chunks):
        memory = await memory_service.create_memory(
            content=chunk_content,
            source=source,
            tags=tags + ["ingested", format_tag],
            metadata={
                "ingestion": {
                    "filename": filename,
                    "chunk_index": i,
                    "total_chunks": total_chunks,
                }
            },
            importance=importance,
        )
        results.append({"id": str(memory.id), "chunk_index": i, "status": "ok"})

    return results


def _extract_text(data: bytes, ext: str) -> str:
    """Extract text content from file bytes based on extension."""
    if ext in (".txt", ".md"):
        return data.decode("utf-8", errors="replace")
    elif ext == ".pdf":
        return _extract_pdf(data)
    elif ext == ".docx":
        return _extract_docx(data)
    else:
        raise ValueError(f"Unsupported extension: {ext}")


def _extract_pdf(data: bytes) -> str:
    """Extract text from PDF using pdfminer.six."""
    import io

    from pdfminer.high_level import extract_text

    return extract_text(io.BytesIO(data))


def _extract_docx(data: bytes) -> str:
    """Extract text from DOCX by parsing word/document.xml inside the zip."""
    import io

    docx_zip = zipfile.ZipFile(io.BytesIO(data))
    try:
        xml_content = docx_zip.read("word/document.xml")
    except KeyError:
        raise ValueError("Invalid DOCX file: missing word/document.xml")

    tree = ET.fromstring(xml_content)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    paragraphs = []
    for para in tree.iter(f"{{{ns['w']}}}p"):
        texts = []
        for run in para.iter(f"{{{ns['w']}}}t"):
            if run.text:
                texts.append(run.text)
        if texts:
            paragraphs.append("".join(texts))

    return "\n\n".join(paragraphs)
