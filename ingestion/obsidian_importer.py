"""Obsidian vault import — parse notes with frontmatter and wikilinks."""

from __future__ import annotations

import re
from pathlib import Path

from core.services import memory_service

from .chunker import chunk_text


async def import_vault(
    vault_path: str,
    source: str = "obsidian",
    importance: float = 0.5,
    extra_tags: list[str] | None = None,
) -> list[dict]:
    """Walk an Obsidian vault, import all .md files.

    Args:
        extra_tags: Additional tags to merge with each note's tags.

    Returns list of {file, id, status} or {file, status, error}.
    """
    vault = Path(vault_path)
    if not vault.is_dir():
        raise ValueError(f"Vault path is not a directory: {vault_path}")

    results = []
    md_files = sorted(vault.rglob("*.md"))

    for md_file in md_files:
        try:
            note_results = await _import_note(
                md_file, vault, source, importance, extra_tags or [],
            )
            results.extend(note_results)
        except Exception as exc:
            results.append({
                "file": str(md_file.relative_to(vault)),
                "status": "error",
                "error": str(exc),
            })

    return results


async def _import_note(
    note_path: Path,
    vault_root: Path,
    source: str,
    importance: float,
    extra_tags: list[str],
) -> list[dict]:
    """Import a single Obsidian note."""
    raw = note_path.read_text(encoding="utf-8", errors="replace")
    relative = str(note_path.relative_to(vault_root))

    frontmatter, body = _parse_frontmatter(raw)
    fm_tags = _extract_frontmatter_tags(frontmatter)
    body_tags = _extract_body_tags(body)
    aliases = _extract_frontmatter_list(frontmatter, "aliases")

    all_tags = list(set(fm_tags + body_tags + extra_tags + ["obsidian"]))

    chunks = chunk_text(body)
    total_chunks = len(chunks)

    results = []
    for i, chunk_content in enumerate(chunks):
        metadata: dict = {
            "ingestion": {
                "filename": relative,
                "vault_path": str(vault_root),
            },
            "obsidian": {
                "aliases": aliases,
                "frontmatter": frontmatter,
            },
        }
        if total_chunks > 1:
            metadata["ingestion"]["chunk_index"] = i
            metadata["ingestion"]["total_chunks"] = total_chunks

        memory = await memory_service.create_memory(
            content=chunk_content,
            source=source,
            tags=all_tags,
            metadata=metadata,
            importance=importance,
        )
        results.append({
            "file": relative,
            "id": str(memory.id),
            "status": "ok",
        })

    return results


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter between --- delimiters.

    Returns (frontmatter_dict, body_text). Simple regex-based parser
    for flat key-value pairs — no PyYAML dependency.
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not match:
        return {}, text

    fm_text = match.group(1)
    body = text[match.end():]

    frontmatter: dict = {}
    for line in fm_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Handle key: value
        kv_match = re.match(r"^(\w+)\s*:\s*(.*)", line)
        if kv_match:
            key = kv_match.group(1).lower()
            value = kv_match.group(2).strip()

            # Handle YAML list values: [item1, item2]
            if value.startswith("[") and value.endswith("]"):
                items = [v.strip().strip("\"'") for v in value[1:-1].split(",")]
                frontmatter[key] = [i for i in items if i]
            # Handle bare value
            elif value:
                frontmatter[key] = value.strip("\"'")

        # Handle YAML list items: - item
        elif line.startswith("- ") and frontmatter:
            last_key = list(frontmatter.keys())[-1]
            current = frontmatter[last_key]
            item = line[2:].strip().strip("\"'")
            if isinstance(current, list):
                current.append(item)
            else:
                frontmatter[last_key] = [current, item] if current else [item]

    return frontmatter, body


def _extract_frontmatter_tags(frontmatter: dict) -> list[str]:
    """Extract tags from frontmatter 'tags' key."""
    raw_tags = frontmatter.get("tags", [])
    if isinstance(raw_tags, str):
        # Comma-separated or space-separated
        raw_tags = re.split(r"[,\s]+", raw_tags)
    return [t.strip().lower().lstrip("#") for t in raw_tags if t.strip()]


def _extract_frontmatter_list(frontmatter: dict, key: str) -> list[str]:
    """Extract a list value from frontmatter."""
    val = frontmatter.get(key, [])
    if isinstance(val, str):
        return [val] if val else []
    if isinstance(val, list):
        return [str(v) for v in val if v]
    return []


def _extract_body_tags(body: str) -> list[str]:
    """Extract #tags from note body (not inside wikilinks or code blocks)."""
    # Remove code blocks
    cleaned = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    cleaned = re.sub(r"`[^`]+`", "", cleaned)

    # Find #tags (word chars after #, not part of a heading)
    tags = re.findall(r"(?<!\w)#(\w[\w/-]*)", cleaned)
    return [t.lower() for t in tags if len(t) >= 2]
