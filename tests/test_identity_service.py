"""Tests for the identity scaffold + sync contracts (Phase 11)."""

import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from core.models import Memory
from core.services import identity_service, memory_service
from core.services.identity_service import (
    MAX_FILE_BYTES,
    PROVENANCE_SYSTEM,
    IdentityFileError,
    provenance_key,
    read_file_checked,
    scaffold,
    scan_files,
    tags_for,
)

FAKE_768 = [0.1] * 768


@pytest.fixture(autouse=True)
def mock_embed():
    with patch("core.services.memory_service.embed", new_callable=AsyncMock) as m:
        m.return_value = FAKE_768
        yield m


# ---------------------------------------------------------------------------
# Scaffold
# ---------------------------------------------------------------------------

class TestScaffold:
    def test_creates_structure(self, tmp_path):
        created = scaffold(tmp_path)
        assert set(created) == {
            "identity.md", "context/example.md", "projects/example.md"
        }
        assert (tmp_path / "identity.md").is_file()

    def test_idempotent_never_overwrites(self, tmp_path):
        scaffold(tmp_path)
        (tmp_path / "identity.md").write_text("MY REAL IDENTITY")
        created = scaffold(tmp_path)
        assert created == []
        assert (tmp_path / "identity.md").read_text() == "MY REAL IDENTITY"


# ---------------------------------------------------------------------------
# Size / encoding contract
# ---------------------------------------------------------------------------

class TestReadFileChecked:
    def test_exactly_max_bytes_accepted(self, tmp_path):
        f = tmp_path / "ok.md"
        f.write_bytes(b"a" * MAX_FILE_BYTES)
        assert len(read_file_checked(f)) == MAX_FILE_BYTES

    def test_one_byte_over_rejected(self, tmp_path):
        f = tmp_path / "big.md"
        f.write_bytes(b"a" * (MAX_FILE_BYTES + 1))
        with pytest.raises(IdentityFileError, match="exceeds"):
            read_file_checked(f)

    def test_invalid_utf8_rejected(self, tmp_path):
        f = tmp_path / "bad.md"
        f.write_bytes(b"\xff\xfe broken")
        with pytest.raises(IdentityFileError, match="UTF-8"):
            read_file_checked(f)


# ---------------------------------------------------------------------------
# Scan + slugs + containment
# ---------------------------------------------------------------------------

class TestScanFiles:
    def test_valid_layout(self, tmp_path):
        (tmp_path / "identity.md").write_text("me")
        (tmp_path / "context").mkdir()
        (tmp_path / "context" / "infra_notes.md").write_text("c")
        (tmp_path / "projects").mkdir()
        (tmp_path / "projects" / "my-proj.md").write_text("p")
        files, rejected = scan_files(tmp_path)
        assert [f[0] for f in files] == [
            "identity.md", "context/infra_notes.md", "projects/my-proj.md"
        ]
        assert rejected == []

    def test_invalid_slugs_rejected_not_normalized(self, tmp_path):
        (tmp_path / "projects").mkdir()
        (tmp_path / "projects" / "Bad Name.md").write_text("x")
        (tmp_path / "projects" / "under_score.md").write_text("x")  # _ invalid for domains
        (tmp_path / "context").mkdir()
        (tmp_path / "context" / "café.md").write_text("x")
        files, rejected = scan_files(tmp_path)
        assert files == []
        assert len(rejected) == 3

    def test_symlink_escape_rejected(self, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        secret = outside / "secret.md"
        secret.write_text("private")
        root = tmp_path / "identity"
        (root / "projects").mkdir(parents=True)
        os.symlink(secret, root / "projects" / "sneaky.md")
        files, rejected = scan_files(root)
        assert files == []
        assert any("escapes" in r for r in rejected)

    def test_same_basename_different_folders_distinct_keys(self, tmp_path):
        (tmp_path / "context").mkdir()
        (tmp_path / "projects").mkdir()
        (tmp_path / "context" / "alpha.md").write_text("c")
        (tmp_path / "projects" / "alpha.md").write_text("p")
        files, _ = scan_files(tmp_path)
        keys = {provenance_key(rel) for rel, _ in files}
        assert keys == {"identity:context/alpha.md", "identity:projects/alpha.md"}
        assert tags_for("context/alpha.md") == ["type:context", "context:alpha"]
        assert tags_for("projects/alpha.md") == ["domain:alpha", "type:project-context"]


# ---------------------------------------------------------------------------
# Local-only embedding
# ---------------------------------------------------------------------------

class TestLocalOnlyEmbedding:
    @pytest.mark.asyncio
    async def test_fallback_never_called_when_disallowed(self):
        from embeddings import registry
        with (
            patch.object(registry, "get_provider") as mock_primary,
            patch.object(registry, "get_fallback_provider") as mock_fallback,
        ):
            mock_primary.return_value.embed = AsyncMock(
                side_effect=httpx.ConnectError("down")
            )
            with pytest.raises(httpx.ConnectError):
                await registry.embed("private text", allow_cloud_fallback=False)
            mock_fallback.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_still_works_by_default(self):
        from embeddings import registry
        with (
            patch.object(registry, "get_provider") as mock_primary,
            patch.object(registry, "get_fallback_provider") as mock_fallback,
        ):
            mock_primary.return_value.embed = AsyncMock(
                side_effect=httpx.ConnectError("down")
            )
            mock_fallback.return_value.embed = AsyncMock(return_value=FAKE_768)
            vector = await registry.embed("public text")
            assert vector == FAKE_768


# ---------------------------------------------------------------------------
# Sync (database)
# ---------------------------------------------------------------------------

def _identity_dir(tmp_path, files: dict) -> "os.PathLike":
    for rel, content in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    return tmp_path


@pytest.mark.django_db(transaction=True)
class TestSync:
    @pytest.mark.asyncio
    async def test_create_skip_update_cycle(self, tmp_path):
        root = _identity_dir(tmp_path, {"identity.md": "v1"})
        r1 = await identity_service.sync(root)
        assert len(r1["created"]) == 1

        r2 = await identity_service.sync(root)
        assert r2["skipped"] == ["identity.md"] and not r2["created"]

        (root / "identity.md").write_text("v2")
        r3 = await identity_service.sync(root)
        assert len(r3["updated"]) == 1
        rows = await memory_service.list_recent(tags=["type:identity"])
        assert len(rows) == 1 and rows[0].content == "v2"

    @pytest.mark.asyncio
    async def test_more_than_twenty_files_no_recency_limit(self, tmp_path):
        files = {f"context/topic{i:02d}.md": f"content {i}" for i in range(25)}
        root = _identity_dir(tmp_path, files)
        r1 = await identity_service.sync(root)
        assert len(r1["created"]) == 25
        r2 = await identity_service.sync(root)
        assert len(r2["skipped"]) == 25 and not r2["created"] and not r2["updated"]

    @pytest.mark.asyncio
    async def test_orphan_report_then_prune(self, tmp_path):
        root = _identity_dir(tmp_path, {"context/gone.md": "bye"})
        await identity_service.sync(root)
        (root / "context" / "gone.md").unlink()

        report = await identity_service.sync(root)
        assert len(report["orphaned"]) == 1 and not report["pruned"]
        assert await memory_service.list_recent(tags=["type:context"])

        report = await identity_service.sync(root, prune=True)
        assert len(report["pruned"]) == 1
        assert not await memory_service.list_recent(tags=["type:context"])

    @pytest.mark.asyncio
    async def test_same_key_different_system_untouched(self, tmp_path):
        foreign = await memory_service.create_memory(
            "foreign importer row",
            metadata={"provenance": {
                "system": "other_importer",
                "key": "identity:identity.md",
                "sha256": "x",
            }},
        )
        root = _identity_dir(tmp_path, {"identity.md": "mine"})

        r = await identity_service.sync(root)
        assert len(r["created"]) == 1  # created fresh despite same key string

        (root / "identity.md").unlink()
        r = await identity_service.sync(root, prune=True)
        assert len(r["pruned"]) == 1

        from asgiref.sync import sync_to_async
        still = await sync_to_async(Memory.objects.get)(pk=foreign.id)
        assert still.content == "foreign importer row"

    @pytest.mark.asyncio
    async def test_duplicates_skip_then_repair_then_update(self, tmp_path):
        root = _identity_dir(tmp_path, {"identity.md": "v1"})
        await identity_service.sync(root)
        # Manufacture a pre-existing duplicate
        dup = await memory_service.create_memory(
            "old duplicate",
            metadata={"provenance": {
                "system": PROVENANCE_SYSTEM,
                "key": "identity:identity.md",
                "sha256": "stale",
            }},
        )
        (root / "identity.md").write_text("v2")

        # 1) ordinary sync: reports, mutates NOTHING for that file
        r = await identity_service.sync(root)
        assert len(r["duplicates"]) == 1
        assert not r["updated"] and not r["created"]
        from asgiref.sync import sync_to_async
        assert (await sync_to_async(Memory.objects.get)(pk=dup.id)).content == "old duplicate"

        # 2) repair: canonical kept (dup is newest by updated_at), extra deleted
        r = await identity_service.sync(root, repair_duplicates=True)
        assert len(r["repaired"]) == 1
        remaining = await sync_to_async(list)(
            Memory.objects.filter(
                metadata__provenance__system=PROVENANCE_SYSTEM,
                metadata__provenance__key="identity:identity.md",
            )
        )
        assert len(remaining) == 1 and remaining[0].id == dup.id

        # 3) subsequent ordinary sync updates the canonical row
        r = await identity_service.sync(root)
        assert len(r["updated"]) == 1
        assert (await sync_to_async(Memory.objects.get)(pk=dup.id)).content == "v2"

    @pytest.mark.asyncio
    async def test_failed_embed_leaves_existing_unchanged(self, tmp_path, mock_embed):
        root = _identity_dir(tmp_path, {"identity.md": "v1"})
        await identity_service.sync(root)
        (root / "identity.md").write_text("v2")
        mock_embed.side_effect = httpx.ConnectError("ollama down")

        report = await identity_service.sync(root)
        assert len(report["errors"]) == 1 and not report["updated"]
        rows = await memory_service.list_recent(tags=["type:identity"])
        assert rows[0].content == "v1"

    @pytest.mark.asyncio
    async def test_oversized_file_rejected_existing_preserved(self, tmp_path):
        root = _identity_dir(tmp_path, {"identity.md": "v1"})
        await identity_service.sync(root)
        (root / "identity.md").write_bytes(b"a" * (MAX_FILE_BYTES + 1))

        report = await identity_service.sync(root)
        assert any("exceeds" in r for r in report["rejected"])
        assert not report["updated"] and not report["orphaned"]
        rows = await memory_service.list_recent(tags=["type:identity"])
        assert rows[0].content == "v1"


# ---------------------------------------------------------------------------
# Hardening: safe_read, bounded I/O, scaffold containment
# ---------------------------------------------------------------------------

class TestSafeRead:
    def test_reads_contained_file(self, tmp_path):
        (tmp_path / "identity.md").write_text("me")
        assert identity_service.safe_read(tmp_path, "identity.md") == "me"

    def test_symlinked_identity_file_rejected(self, tmp_path):
        secret = tmp_path / "outside-secret.md"
        secret.write_text("TOP SECRET")
        root = tmp_path / "identity"
        root.mkdir()
        os.symlink(secret, root / "identity.md")
        with pytest.raises(identity_service.IdentityFileMissing, match="escapes"):
            identity_service.safe_read(root, "identity.md")

    def test_missing_file_raises_missing(self, tmp_path):
        with pytest.raises(identity_service.IdentityFileMissing, match="not found"):
            identity_service.safe_read(tmp_path, "identity.md")


class TestBoundedRead:
    def test_stat_checked_before_read(self, tmp_path):
        """Oversized files are rejected via stat, without a full read."""
        f = tmp_path / "big.md"
        f.write_bytes(b"a" * (MAX_FILE_BYTES + 100))
        with patch("builtins.open", side_effect=AssertionError("must not read")):
            with pytest.raises(IdentityFileError, match="exceeds"):
                read_file_checked(f)

    def test_post_read_recheck_catches_growth_race(self, tmp_path):
        """If the file grows between stat and read, the bounded read's
        re-check still rejects it."""
        from types import SimpleNamespace
        f = tmp_path / "race.md"
        f.write_bytes(b"a" * (MAX_FILE_BYTES + 1))
        with patch.object(
            type(f), "stat", return_value=SimpleNamespace(st_size=10)
        ):
            with pytest.raises(IdentityFileError, match="exceeds"):
                read_file_checked(f)

    def test_unreadable_file_friendly_error(self, tmp_path):
        f = tmp_path / "locked.md"
        f.write_text("secret")
        f.chmod(0)
        try:
            with pytest.raises(IdentityFileError, match="unreadable"):
                read_file_checked(f)
        finally:
            f.chmod(0o644)


class TestScaffoldContainment:
    def test_symlinked_projects_dir_fails_safely(self, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        root = tmp_path / "identity"
        root.mkdir()
        os.symlink(outside, root / "projects")
        with pytest.raises(IdentityFileError, match="not a real directory"):
            scaffold(root)
        assert list(outside.iterdir()) == []  # nothing written outside

    def test_symlinked_context_dir_fails_safely(self, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir()
        root = tmp_path / "identity"
        root.mkdir()
        os.symlink(outside, root / "context")
        with pytest.raises(IdentityFileError, match="not a real directory"):
            scaffold(root)
        assert list(outside.iterdir()) == []

    def test_symlinked_identity_md_refused(self, tmp_path):
        target = tmp_path / "elsewhere.md"
        target.write_text("original")
        root = tmp_path / "identity"
        root.mkdir()
        os.symlink(target, root / "identity.md")
        with pytest.raises(IdentityFileError, match="symlink"):
            scaffold(root)
        assert target.read_text() == "original"
