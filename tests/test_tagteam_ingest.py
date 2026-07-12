"""Tests for tagteam export ingestion (Phase 11).

Fixtures under tests/fixtures/tagteam_repo_* are copies of this repo's
real rendered JSONL exports plus a stripped (non-approved) and a mangled
(malformed lines) variant.
"""

import shutil
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from core.models import Memory
from core.services import memory_service, tagteam_ingest
from core.services.tagteam_ingest import (
    ingest_repo,
    normalize_domain,
    parse_rounds,
    summarize_cycle,
)

FIXTURES = Path(__file__).parent / "fixtures"
FAKE_768 = [0.1] * 768


@pytest.fixture(autouse=True)
def mock_embed():
    with patch("core.services.memory_service.embed", new_callable=AsyncMock) as m:
        m.return_value = FAKE_768
        yield m


class TestParsing:
    def test_parse_real_export(self):
        path = FIXTURES / "tagteam_repo_a/docs/handoffs/revive-and-verify_plan_rounds.jsonl"
        rounds, malformed = parse_rounds(path)
        assert malformed == 0
        assert rounds[-1]["action"] == "APPROVE"

    def test_malformed_lines_tolerated_and_counted(self):
        path = FIXTURES / "tagteam_repo_a/docs/handoffs/mangled_impl_rounds.jsonl"
        rounds, malformed = parse_rounds(path)
        assert malformed == 3  # text line, JSON array, broken JSON
        assert rounds and rounds[-1]["action"] == "APPROVE"

    def test_non_approved_cycle_yields_no_summary(self):
        path = FIXTURES / "tagteam_repo_a/docs/handoffs/unfinished_plan_rounds.jsonl"
        rounds, _ = parse_rounds(path)
        assert summarize_cycle("unfinished", "plan", rounds) is None

    def test_normalize_domain(self):
        assert normalize_domain("My Repo!") == "my-repo"
        assert normalize_domain("###") is None


@pytest.mark.django_db(transaction=True)
class TestIngest:
    @pytest.mark.asyncio
    async def test_approved_only_created_then_skip(self):
        repo = FIXTURES / "tagteam_repo_a"
        r1 = await ingest_repo(repo, domain="fixture-a")
        # repo_a: revive plan (approved) + daily-driver impl (approved)
        # + mangled (approved after malformed lines) — unfinished excluded
        assert len(r1["created"]) == 3
        assert r1["not_approved"] == ["unfinished_plan_rounds.jsonl"]
        assert r1["malformed_lines"] == 3

        r2 = await ingest_repo(repo, domain="fixture-a")
        assert len(r2["skipped"]) == 3 and not r2["created"]

    @pytest.mark.asyncio
    async def test_same_filename_two_repos_distinct(self):
        r_a = await ingest_repo(FIXTURES / "tagteam_repo_a", domain="fixture-a")
        r_b = await ingest_repo(FIXTURES / "tagteam_repo_b", domain="fixture-b")
        assert r_a["created"] and r_b["created"]

        a_rows = await memory_service.list_recent(
            tags=["domain:fixture-a", "type:cycle-summary"], limit=100
        )
        b_rows = await memory_service.list_recent(
            tags=["domain:fixture-b", "type:cycle-summary"], limit=100
        )
        assert len(a_rows) == 3 and len(b_rows) == 1
        # re-ingesting one repo does not touch the other
        r_a2 = await ingest_repo(FIXTURES / "tagteam_repo_a", domain="fixture-a")
        assert len(r_a2["skipped"]) == 3

    @pytest.mark.asyncio
    async def test_content_change_same_round_count_updates(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "docs" / "handoffs").mkdir(parents=True)
        src = FIXTURES / "tagteam_repo_a/docs/handoffs/revive-and-verify_plan_rounds.jsonl"
        dst = repo / "docs/handoffs/revive-and-verify_plan_rounds.jsonl"
        shutil.copy(src, dst)

        r1 = await ingest_repo(repo, domain="changer")
        assert len(r1["created"]) == 1

        # Same number of rounds, corrected content in the approval line
        text = dst.read_text().replace("Approved", "Approved (corrected)")
        assert text != dst.read_text()
        dst.write_text(text)

        r2 = await ingest_repo(repo, domain="changer")
        assert len(r2["updated"]) == 1 and not r2["created"]
        rows = await memory_service.list_recent(
            tags=["domain:changer", "type:cycle-summary"]
        )
        assert len(rows) == 1 and "corrected" in rows[0].content

    @pytest.mark.asyncio
    async def test_same_key_different_system_untouched(self, tmp_path):
        repo = (tmp_path / "iso").resolve()
        (repo / "docs" / "handoffs").mkdir(parents=True)
        shutil.copy(
            FIXTURES / "tagteam_repo_a/docs/handoffs/revive-and-verify_plan_rounds.jsonl",
            repo / "docs/handoffs/revive-and-verify_plan_rounds.jsonl",
        )
        colliding_key = f"tagteam:{repo}:docs/handoffs/revive-and-verify_plan_rounds.jsonl"
        foreign = await memory_service.create_memory(
            "identity-sync row with a colliding key",
            metadata={"provenance": {
                "system": "identity_sync", "key": colliding_key, "sha256": "x",
            }},
        )
        r = await ingest_repo(repo, domain="iso")
        assert len(r["created"]) == 1  # fresh row despite the colliding key

        from asgiref.sync import sync_to_async
        still = await sync_to_async(Memory.objects.get)(pk=foreign.id)
        assert still.content == "identity-sync row with a colliding key"

    @pytest.mark.asyncio
    async def test_invalid_domain_raises(self, tmp_path):
        with pytest.raises(ValueError, match="invalid domain"):
            await ingest_repo(tmp_path, domain="Bad Domain!")

    @pytest.mark.asyncio
    async def test_empty_repo_reports_zero_files(self, tmp_path):
        report = await tagteam_ingest.ingest_repo(tmp_path, domain="empty")
        assert report["files"] == 0 and not report["created"]
