"""Tests for ingestion.file_ingestor — file parsing and memory creation."""

import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ingestion.file_ingestor import ALLOWED_EXTENSIONS, _extract_docx, _extract_text, ingest_file


class TestExtractText:
    """Text extraction from different file formats."""

    def test_extract_txt(self):
        data = b"Hello, this is plain text."
        result = _extract_text(data, ".txt")
        assert result == "Hello, this is plain text."

    def test_extract_md(self):
        data = b"# Heading\n\nSome *markdown* content."
        result = _extract_text(data, ".md")
        assert "# Heading" in result
        assert "markdown" in result

    def test_extract_txt_with_utf8(self):
        data = "Unicode: \u00e9\u00e8\u00ea \u00fc\u00f6\u00e4".encode("utf-8")
        result = _extract_text(data, ".txt")
        assert "\u00e9\u00e8\u00ea" in result

    def test_unsupported_extension_raises(self):
        with pytest.raises(ValueError, match="Unsupported extension"):
            _extract_text(b"data", ".xyz")


class TestExtractDocx:
    """DOCX text extraction."""

    def test_extract_docx_valid(self):
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body>"
                "<w:p><w:r><w:t>Hello World</w:t></w:r></w:p>"
                "<w:p><w:r><w:t>Second paragraph</w:t></w:r></w:p>"
                "</w:body>"
                "</w:document>"
            )
            zf.writestr("word/document.xml", xml)
        result = _extract_docx(buf.getvalue())
        assert "Hello World" in result
        assert "Second paragraph" in result

    def test_extract_docx_missing_document_xml_raises(self):
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("other.xml", "<data/>")
        with pytest.raises(ValueError, match="missing word/document.xml"):
            _extract_docx(buf.getvalue())


class TestIngestFile:
    """Full file ingestion pipeline."""

    @pytest.mark.asyncio
    async def test_ingest_txt_file_creates_memories(self):
        content = "This is test content for ingestion."
        mock_memory = MagicMock()
        mock_memory.id = "test-uuid-1"

        with patch("ingestion.file_ingestor.memory_service") as svc:
            svc.create_memory = AsyncMock(return_value=mock_memory)
            results = await ingest_file(
                file_bytes=content.encode("utf-8"),
                filename="test.txt",
                source="test",
                tags=["unit-test"],
            )

        assert len(results) >= 1
        assert results[0]["status"] == "ok"
        assert results[0]["id"] == "test-uuid-1"
        svc.create_memory.assert_called()
        call_kwargs = svc.create_memory.call_args[1]
        assert "ingested" in call_kwargs["tags"]
        assert "text" in call_kwargs["tags"]
        assert call_kwargs["metadata"]["ingestion"]["filename"] == "test.txt"

    @pytest.mark.asyncio
    async def test_ingest_file_from_path(self):
        content = "File on disk content."
        mock_memory = MagicMock()
        mock_memory.id = "test-uuid-2"

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(content.encode("utf-8"))
            f.flush()
            temp_path = f.name

        try:
            with patch("ingestion.file_ingestor.memory_service") as svc:
                svc.create_memory = AsyncMock(return_value=mock_memory)
                results = await ingest_file(file_path=temp_path, source="disk")

            assert len(results) >= 1
            assert results[0]["status"] == "ok"
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_rejects_unsupported_extension(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            await ingest_file(file_bytes=b"data", filename="file.exe")

    @pytest.mark.asyncio
    async def test_rejects_oversized_file(self):
        with patch("ingestion.file_ingestor.settings") as mock_settings:
            mock_settings.INGEST_MAX_FILE_SIZE = 100
            with pytest.raises(ValueError, match="exceeds"):
                await ingest_file(file_bytes=b"x" * 200, filename="big.txt")

    @pytest.mark.asyncio
    async def test_rejects_empty_content(self):
        with pytest.raises(ValueError, match="No text content"):
            await ingest_file(file_bytes=b"", filename="empty.txt")

    @pytest.mark.asyncio
    async def test_requires_file_path_or_bytes(self):
        with pytest.raises(ValueError, match="Provide either"):
            await ingest_file()

    def test_allowed_extensions(self):
        assert ".txt" in ALLOWED_EXTENSIONS
        assert ".md" in ALLOWED_EXTENSIONS
        assert ".pdf" in ALLOWED_EXTENSIONS
        assert ".docx" in ALLOWED_EXTENSIONS
        assert ".exe" not in ALLOWED_EXTENSIONS
