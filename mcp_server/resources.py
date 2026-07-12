"""Read-only MCP resources for identity/project context (Phase 11).

Files are read from ENGRAM_IDENTITY_DIR at request time (no caching).
Slug validation rejects (never normalizes) bad input; containment uses
resolved paths; the identity-sync size/encoding contract applies (an
oversized or non-UTF-8 file yields a clear error message, never partial
content or an exception).
"""

from pathlib import Path

from core.services.identity_service import (
    DOMAIN_SLUG_RE,
    TOPIC_SLUG_RE,
    IdentityFileError,
    identity_root,
    read_file_checked,
)
from mcp_server.server import mcp


def _read_contained(root: Path, relpath: str) -> str:
    """Read a file if it resolves inside root; friendly errors otherwise."""
    target = root / relpath
    try:
        resolved_root = root.resolve()
        if not target.resolve().is_relative_to(resolved_root):
            return f"Not found: {relpath} (escapes the identity directory)"
    except OSError:
        return f"Not found: {relpath}"
    if not target.is_file():
        return (
            f"Not found: {relpath}. Run `python manage.py init_identity` and "
            "populate the identity directory."
        )
    try:
        return read_file_checked(target)
    except IdentityFileError as exc:
        return f"Unreadable: {exc}"


def _list_slugs(subdir: str) -> list[str]:
    directory = identity_root() / subdir
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.md") if p.is_file())


@mcp.resource("engram://identity")
def identity() -> str:
    """The user's identity file: who they are, preferences, house rules."""
    return _read_contained(identity_root(), "identity.md")


@mcp.resource("engram://context")
def context_index() -> str:
    """List available context topics."""
    topics = _list_slugs("context")
    if not topics:
        return "No context files. Add markdown files under context/ in the identity directory."
    return "\n".join(f"- engram://context/{t}" for t in topics)


@mcp.resource("engram://context/{topic}")
def context_topic(topic: str) -> str:
    """One standing-knowledge context file."""
    if not TOPIC_SLUG_RE.match(topic):
        return f"Invalid topic slug: {topic!r} (allowed: [a-z0-9_-]+)"
    return _read_contained(identity_root(), f"context/{topic}.md")


@mcp.resource("engram://projects")
def projects_index() -> str:
    """List domains that have a canonical project-context file."""
    domains = _list_slugs("projects")
    if not domains:
        return "No project files. Add markdown files under projects/ in the identity directory."
    return "\n".join(f"- engram://projects/{d}" for d in domains)


@mcp.resource("engram://projects/{domain}")
def project_context(domain: str) -> str:
    """Canonical long-form context for one project domain."""
    if not DOMAIN_SLUG_RE.match(domain):
        return f"Invalid domain slug: {domain!r} (allowed: [a-z0-9-]+)"
    return _read_contained(identity_root(), f"projects/{domain}.md")
