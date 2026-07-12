"""Identity directory scaffold + sync (Phase 11: identity-and-onboarding).

Contracts (see docs/phases/identity-and-onboarding.md):
- Scaffold writes commented placeholder templates only, never overwrites.
- Sync provenance: metadata.provenance = {system: "identity_sync",
  key: "identity:<relpath>", sha256}. Every lookup/update/orphan/prune
  query filters on BOTH system and key — the key namespace is a
  convention, not an integrity boundary.
- Ordinary sync prevents new duplicates, reports pre-existing duplicate
  sets and skips ALL mutation for those files; --repair-duplicates keeps
  the canonical row (latest updated_at, then created_at, then id) and
  deletes only extra identity_sync rows. Ordinary sync never deletes.
- Files are rejected before decode/embed if over MAX_FILE_BYTES
  (262,144 bytes exactly allowed) or not valid UTF-8; a rejected or
  failed file never modifies its existing memory.
- Identity content is embedded locally only unless
  ENGRAM_IDENTITY_CLOUD_EMBED is set.
"""

import hashlib
import re
from pathlib import Path

from asgiref.sync import sync_to_async
from django.conf import settings

from core.models import Memory
from core.services import memory_service

PROVENANCE_SYSTEM = "identity_sync"
MAX_FILE_BYTES = 262144  # 256 KiB, exact: this many bytes allowed, more rejected

DOMAIN_SLUG_RE = re.compile(r"^[a-z0-9-]+$")
TOPIC_SLUG_RE = re.compile(r"^[a-z0-9_-]+$")

IDENTITY_TEMPLATE = """\
# Identity

<!-- Who you are: name, role, what you work on, working preferences,
     house rules for agents. This file is returned verbatim by
     onboard_agent as YOUR trusted instructions — write it yourself;
     tooling never invents content here. -->
"""

CONTEXT_TEMPLATE = """\
# Context: example

<!-- Standing knowledge agents should have (infrastructure, conventions,
     accounts layout, ...). One topic per file; filename = topic slug
     ([a-z0-9_-]). Delete this example when you add real topics. -->
"""

PROJECT_TEMPLATE = """\
# Project: example

<!-- Canonical long-form context for one project; filename = domain slug
     ([a-z0-9-]). Complements the fast-changing type:project-status
     snapshots. Delete this example when you add real projects. -->
"""


class IdentityFileError(Exception):
    """A file failed the size/encoding contract."""


def identity_root() -> Path:
    return Path(settings.ENGRAM_IDENTITY_DIR).expanduser()


def scaffold(root: Path) -> list[str]:
    """Create the directory structure + placeholder templates.

    Never overwrites an existing file. Returns relative paths created.
    """
    created = []
    root.mkdir(parents=True, exist_ok=True)
    (root / "context").mkdir(exist_ok=True)
    (root / "projects").mkdir(exist_ok=True)
    for relpath, template in (
        ("identity.md", IDENTITY_TEMPLATE),
        ("context/example.md", CONTEXT_TEMPLATE),
        ("projects/example.md", PROJECT_TEMPLATE),
    ):
        target = root / relpath
        if not target.exists():
            target.write_text(template, encoding="utf-8")
            created.append(relpath)
    return created


def read_file_checked(path: Path) -> str:
    """Read a file enforcing the size/encoding contract.

    Size is checked on raw bytes BEFORE decoding: exactly MAX_FILE_BYTES
    is allowed, one more byte is rejected.
    """
    raw = path.read_bytes()
    if len(raw) > MAX_FILE_BYTES:
        raise IdentityFileError(
            f"{path.name}: {len(raw)} bytes exceeds the {MAX_FILE_BYTES}-byte limit"
        )
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IdentityFileError(f"{path.name}: not valid UTF-8 ({exc})") from exc


def scan_files(root: Path) -> tuple[list[tuple[str, Path]], list[str]]:
    """Enumerate syncable identity files.

    Returns (files, rejected) where files is [(relpath, abspath)] and
    rejected lists files whose name is not a valid slug. Containment is
    enforced with resolved paths (symlinks that escape the root are
    rejected).
    """
    files: list[tuple[str, Path]] = []
    rejected: list[str] = []
    resolved_root = root.resolve()

    def contained(p: Path) -> bool:
        try:
            return p.resolve().is_relative_to(resolved_root)
        except OSError:
            return False

    identity_md = root / "identity.md"
    if identity_md.is_file() and contained(identity_md):
        files.append(("identity.md", identity_md))

    for subdir, slug_re in (("context", TOPIC_SLUG_RE), ("projects", DOMAIN_SLUG_RE)):
        directory = root / subdir
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            relpath = f"{subdir}/{path.name}"
            if not slug_re.match(path.stem):
                rejected.append(f"{relpath}: invalid slug {path.stem!r}")
                continue
            if not path.is_file() or not contained(path):
                rejected.append(f"{relpath}: escapes the identity directory")
                continue
            files.append((relpath, path))
    return files, rejected


def tags_for(relpath: str) -> list[str]:
    if relpath == "identity.md":
        return ["type:identity"]
    if relpath.startswith("context/"):
        return ["type:context", f"context:{Path(relpath).stem}"]
    if relpath.startswith("projects/"):
        return [f"domain:{Path(relpath).stem}", "type:project-context"]
    raise ValueError(f"unexpected identity path: {relpath}")


def provenance_key(relpath: str) -> str:
    return f"identity:{relpath}"


def _matches(system: str, key: str):
    """The (system, key)-scoped provenance query — no recency limit."""
    return list(
        Memory.objects.filter(
            metadata__provenance__system=system,
            metadata__provenance__key=key,
        ).order_by("-updated_at", "-created_at", "-id")
    )


def _orphan_rows(current_keys: set[str]):
    rows = Memory.objects.filter(metadata__provenance__system=PROVENANCE_SYSTEM)
    return [
        m for m in rows
        if (m.metadata or {}).get("provenance", {}).get("key") not in current_keys
    ]


async def sync(
    root: Path,
    prune: bool = False,
    repair_duplicates: bool = False,
) -> dict:
    """Sync identity files into engram per the phase contract.

    Returns a report dict with lists per outcome. Ordinary sync (both
    flags False) never deletes anything.
    """
    report = {
        "created": [], "updated": [], "skipped": [], "orphaned": [],
        "duplicates": [], "rejected": [], "errors": [],
        "pruned": [], "repaired": [],
    }
    allow_cloud = bool(getattr(settings, "ENGRAM_IDENTITY_CLOUD_EMBED", False))

    files, rejected = scan_files(root)
    report["rejected"].extend(rejected)

    current_keys = set()
    for relpath, path in files:
        key = provenance_key(relpath)
        current_keys.add(key)
        try:
            content = read_file_checked(path)
        except IdentityFileError as exc:
            report["rejected"].append(str(exc))
            continue

        sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        matches = await sync_to_async(_matches)(PROVENANCE_SYSTEM, key)

        if len(matches) > 1:
            if repair_duplicates:
                extras = matches[1:]
                for extra in extras:
                    await sync_to_async(extra.delete)()
                report["repaired"].append(
                    f"{relpath}: kept {matches[0].id}, deleted {len(extras)}"
                )
                # Contract: repair only deletes extras; the content update
                # happens on the next ordinary sync of the canonical row.
                continue
            # Skip ALL mutation for this file until explicit repair
            report["duplicates"].append(
                f"{relpath}: {len(matches)} rows share this provenance"
            )
            continue

        metadata = {"provenance": {
            "system": PROVENANCE_SYSTEM, "key": key, "sha256": sha,
        }}
        try:
            if not matches:
                memory = await memory_service.create_memory(
                    content=content,
                    source="identity-sync",
                    tags=tags_for(relpath),
                    metadata=metadata,
                    allow_cloud_fallback=allow_cloud,
                )
                report["created"].append(f"{relpath} -> {memory.id}")
            else:
                existing = matches[0]
                stored_sha = (existing.metadata or {}).get("provenance", {}).get("sha256")
                if stored_sha == sha:
                    report["skipped"].append(relpath)
                else:
                    await memory_service.update_memory(
                        existing.id,
                        allow_cloud_fallback=allow_cloud,
                        content=content,
                        tags=tags_for(relpath),
                        metadata=metadata,
                    )
                    report["updated"].append(f"{relpath} -> {existing.id}")
        except Exception as exc:  # embed failure etc. — existing row untouched
            report["errors"].append(f"{relpath}: {type(exc).__name__}: {exc}")

    orphans = await sync_to_async(_orphan_rows)(current_keys)
    for orphan in orphans:
        key = (orphan.metadata or {}).get("provenance", {}).get("key", "?")
        orphan_id = orphan.id  # delete() clears the pk
        if prune:
            await sync_to_async(orphan.delete)()
            report["pruned"].append(f"{key} ({orphan_id})")
        else:
            report["orphaned"].append(f"{key} ({orphan_id})")

    return report
