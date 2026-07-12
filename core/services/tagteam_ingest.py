"""Tagteam → engram integration boundary (Phase 11).

Consumes tagteam's *rendered JSONL exports* (docs/handoffs/*_rounds.jsonl)
— export artifacts, NOT tagteam's source of truth (.tagteam/tagteam.db is,
and is never parsed; SQLite internals are not a public API). Documented
prerequisite: refresh exports with
`tagteam cycle render --phase <phase> --type <plan|impl>` before ingesting.

For each cycle whose final round is APPROVE, exactly one memory is stored
(tags: domain:<slug>, type:cycle-summary) with collision-safe provenance:
key = "tagteam:<resolved repo path>:<relative source file>", updated when
the source file's content hash changes. Engram never writes tagteam state.
"""

import hashlib
import json
import re
from pathlib import Path

from asgiref.sync import sync_to_async

from core.models import Memory
from core.services import memory_service

PROVENANCE_SYSTEM = "tagteam"
DOMAIN_SLUG_RE = re.compile(r"^[a-z0-9-]+$")

EXPORT_GLOB = "docs/handoffs/*_rounds.jsonl"
FILENAME_RE = re.compile(r"^(?P<phase>.+)_(?P<ctype>plan|impl)_rounds\.jsonl$")


def normalize_domain(name: str) -> str | None:
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    return slug if slug and DOMAIN_SLUG_RE.match(slug) else None


def parse_rounds(path: Path) -> tuple[list[dict], int]:
    """Parse a rounds JSONL export defensively.

    Returns (rounds, malformed_line_count). Unknown keys are tolerated;
    malformed lines are skipped and counted.
    """
    rounds: list[dict] = []
    malformed = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if isinstance(record, dict):
            rounds.append(record)
        else:
            malformed += 1
    return rounds, malformed


def summarize_cycle(phase: str, ctype: str, rounds: list[dict]) -> str | None:
    """Build the summary content for an APPROVED cycle, else None."""
    if not rounds:
        return None
    final = rounds[-1]
    if final.get("action") != "APPROVE":
        return None
    lead_rounds = [r for r in rounds if r.get("role") == "lead" and r.get("content")]
    lead_final = lead_rounds[-1]["content"] if lead_rounds else "(no lead submission recorded)"
    approval = final.get("content", "Approved.")
    return (
        f"Approved tagteam cycle: {phase} ({ctype}), {len(rounds)} rounds.\n\n"
        f"## Final lead submission\n{lead_final}\n\n"
        f"## Approval\n{approval}"
    )


def _matches(key: str):
    return list(
        Memory.objects.filter(
            metadata__provenance__system=PROVENANCE_SYSTEM,
            metadata__provenance__key=key,
        ).order_by("-updated_at", "-created_at", "-id")
    )


async def ingest_repo(repo: Path, domain: str | None = None) -> dict:
    """Ingest approved cycles from one repo's rendered exports."""
    report = {
        "created": [], "updated": [], "skipped": [],
        "not_approved": [], "malformed_lines": 0, "errors": [], "files": 0,
    }
    repo = repo.resolve()
    slug = domain or normalize_domain(repo.name)
    if not slug or not DOMAIN_SLUG_RE.match(slug):
        raise ValueError(f"invalid domain slug: {domain or repo.name!r}")

    export_files = sorted(repo.glob(EXPORT_GLOB))
    report["files"] = len(export_files)

    for path in export_files:
        name_match = FILENAME_RE.match(path.name)
        if not name_match:
            continue
        phase = name_match.group("phase")
        ctype = name_match.group("ctype")
        relpath = str(path.relative_to(repo))

        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        rounds, malformed = parse_rounds(path)
        report["malformed_lines"] += malformed

        content = summarize_cycle(phase, ctype, rounds)
        if content is None:
            report["not_approved"].append(path.name)
            continue

        key = f"tagteam:{repo}:{relpath}"
        metadata = {
            "provenance": {"system": PROVENANCE_SYSTEM, "key": key, "sha256": sha},
            "tagteam": {
                "phase": phase, "cycle_type": ctype,
                "rounds": len(rounds), "source_file": relpath,
            },
        }
        tags = [f"domain:{slug}", "type:cycle-summary"]

        try:
            matches = await sync_to_async(_matches)(key)
            if not matches:
                memory = await memory_service.create_memory(
                    content=content, source="tagteam",
                    tags=tags, metadata=metadata,
                )
                report["created"].append(f"{path.name} -> {memory.id}")
            else:
                existing = matches[0]
                stored_sha = (existing.metadata or {}).get("provenance", {}).get("sha256")
                if stored_sha == sha:
                    report["skipped"].append(path.name)
                else:
                    await memory_service.update_memory(
                        existing.id, content=content, tags=tags, metadata=metadata,
                    )
                    report["updated"].append(f"{path.name} -> {existing.id}")
        except Exception as exc:
            report["errors"].append(f"{path.name}: {type(exc).__name__}: {exc}")

    return report
