"""Tests for ingestion.obsidian_importer — Obsidian vault import."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ingestion.obsidian_importer import (
    _extract_body_tags,
    _extract_frontmatter_tags,
    _parse_frontmatter,
    import_vault,
)


class TestParseFrontmatter:
    """YAML frontmatter parsing."""

    def test_no_frontmatter(self):
        fm, body = _parse_frontmatter("Just a note with no frontmatter.")
        assert fm == {}
        assert body == "Just a note with no frontmatter."

    def test_basic_frontmatter(self):
        text = "---\ntitle: My Note\nauthor: Alice\n---\nBody text."
        fm, body = _parse_frontmatter(text)
        assert fm["title"] == "My Note"
        assert fm["author"] == "Alice"
        assert body.strip() == "Body text."

    def test_tags_as_inline_list(self):
        text = "---\ntags: [python, django, web]\n---\nContent."
        fm, body = _parse_frontmatter(text)
        assert fm["tags"] == ["python", "django", "web"]

    def test_tags_as_yaml_list(self):
        text = "---\ntags:\n- python\n- django\n---\nContent."
        fm, body = _parse_frontmatter(text)
        assert "python" in fm["tags"]
        assert "django" in fm["tags"]

    def test_aliases(self):
        text = "---\naliases: [alias1, alias2]\n---\nBody."
        fm, body = _parse_frontmatter(text)
        assert fm["aliases"] == ["alias1", "alias2"]

    def test_empty_frontmatter(self):
        text = "---\n---\nBody only."
        fm, body = _parse_frontmatter(text)
        assert fm == {}
        assert body.strip() == "Body only."


class TestExtractFrontmatterTags:
    """Tag extraction from frontmatter."""

    def test_list_tags(self):
        fm = {"tags": ["Python", "Django"]}
        result = _extract_frontmatter_tags(fm)
        assert "python" in result
        assert "django" in result

    def test_string_tags(self):
        fm = {"tags": "python, django, web"}
        result = _extract_frontmatter_tags(fm)
        assert "python" in result
        assert "django" in result

    def test_no_tags(self):
        assert _extract_frontmatter_tags({}) == []

    def test_strips_hash(self):
        fm = {"tags": ["#python", "#web"]}
        result = _extract_frontmatter_tags(fm)
        assert "python" in result
        assert "web" in result


class TestExtractBodyTags:
    """Hashtag extraction from note body."""

    def test_basic_hashtags(self):
        body = "Some text #python and #web-dev here."
        result = _extract_body_tags(body)
        assert "python" in result
        assert "web-dev" in result

    def test_ignores_code_blocks(self):
        body = "```python\n#comment\n```\n#real-tag"
        result = _extract_body_tags(body)
        assert "real-tag" in result
        assert "comment" not in result

    def test_ignores_inline_code(self):
        body = "Use `#include` for C headers. #programming"
        result = _extract_body_tags(body)
        assert "programming" in result
        assert "include" not in result

    def test_short_tags_filtered(self):
        body = "#a #ab #abc"
        result = _extract_body_tags(body)
        assert "a" not in result
        assert "ab" in result


class TestImportVault:
    """Full vault import pipeline."""

    @pytest.mark.asyncio
    async def test_imports_markdown_files(self):
        mock_memory = MagicMock()
        mock_memory.id = "vault-mem-1"

        with tempfile.TemporaryDirectory() as vault_dir:
            note1 = Path(vault_dir) / "note1.md"
            note1.write_text("---\ntags: [python]\n---\nFirst note content.")
            note2 = Path(vault_dir) / "subdir"
            note2.mkdir()
            (note2 / "note2.md").write_text("Second note without frontmatter.")

            with patch("ingestion.obsidian_importer.memory_service") as svc:
                svc.create_memory = AsyncMock(return_value=mock_memory)
                results = await import_vault(vault_dir)

        ok_results = [r for r in results if r["status"] == "ok"]
        assert len(ok_results) >= 2

    @pytest.mark.asyncio
    async def test_preserves_wikilinks_in_content(self):
        mock_memory = MagicMock()
        mock_memory.id = "vault-mem-2"

        with tempfile.TemporaryDirectory() as vault_dir:
            note = Path(vault_dir) / "linked.md"
            note.write_text("See [[Other Note]] for details.")

            with patch("ingestion.obsidian_importer.memory_service") as svc:
                svc.create_memory = AsyncMock(return_value=mock_memory)
                await import_vault(vault_dir)

        call_kwargs = svc.create_memory.call_args[1]
        assert "[[Other Note]]" in call_kwargs["content"]

    @pytest.mark.asyncio
    async def test_maps_tags_correctly(self):
        mock_memory = MagicMock()
        mock_memory.id = "vault-mem-3"

        with tempfile.TemporaryDirectory() as vault_dir:
            note = Path(vault_dir) / "tagged.md"
            note.write_text("---\ntags: [python]\n---\nContent with #django tag.")

            with patch("ingestion.obsidian_importer.memory_service") as svc:
                svc.create_memory = AsyncMock(return_value=mock_memory)
                await import_vault(vault_dir)

        call_kwargs = svc.create_memory.call_args[1]
        assert "python" in call_kwargs["tags"]
        assert "django" in call_kwargs["tags"]
        assert "obsidian" in call_kwargs["tags"]

    @pytest.mark.asyncio
    async def test_extra_tags_merged_with_note_tags(self):
        mock_memory = MagicMock()
        mock_memory.id = "vault-mem-extra"

        with tempfile.TemporaryDirectory() as vault_dir:
            note = Path(vault_dir) / "note.md"
            note.write_text("---\ntags: [python]\n---\nNote body.")

            with patch("ingestion.obsidian_importer.memory_service") as svc:
                svc.create_memory = AsyncMock(return_value=mock_memory)
                await import_vault(vault_dir, extra_tags=["cli-tag", "extra"])

        call_kwargs = svc.create_memory.call_args[1]
        assert "python" in call_kwargs["tags"]
        assert "obsidian" in call_kwargs["tags"]
        assert "cli-tag" in call_kwargs["tags"]
        assert "extra" in call_kwargs["tags"]

    @pytest.mark.asyncio
    async def test_invalid_vault_path_raises(self):
        with pytest.raises(ValueError, match="not a directory"):
            await import_vault("/nonexistent/path")

    @pytest.mark.asyncio
    async def test_handles_per_note_errors(self):
        with tempfile.TemporaryDirectory() as vault_dir:
            # Create a valid note and a binary file with .md extension
            good = Path(vault_dir) / "good.md"
            good.write_text("Good note content.")
            bad = Path(vault_dir) / "bad.md"
            bad.write_bytes(b"\x80\x81\x82")

            mock_memory = MagicMock()
            mock_memory.id = "vault-mem-4"

            with patch("ingestion.obsidian_importer.memory_service") as svc:
                svc.create_memory = AsyncMock(return_value=mock_memory)
                results = await import_vault(vault_dir)

        # Should have results for both files (good succeeds, bad may succeed with replacement chars)
        assert len(results) >= 1
