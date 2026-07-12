"""Read-only MCP resources for identity/project context (Phase 11).

Files are read from ENGRAM_IDENTITY_DIR at request time (no caching)
through identity_service.safe_read — the single containment-checked,
bounded-read primitive. Slug validation rejects (never normalizes) bad
input; index listings apply the same slug + containment rules as the
per-item endpoints, so the index never advertises something the endpoint
would refuse to serve.
"""

from core.services.identity_service import (
    DOMAIN_SLUG_RE,
    TOPIC_SLUG_RE,
    IdentityFileError,
    IdentityFileMissing,
    identity_root,
    safe_read,
)
from mcp_server.server import mcp


def _read(relpath: str) -> str:
    try:
        return safe_read(identity_root(), relpath)
    except IdentityFileMissing:
        return (
            f"Not found: {relpath}. Run `python manage.py init_identity` and "
            "populate the identity directory."
        )
    except IdentityFileError as exc:
        return f"Unreadable: {exc}"


def _list_slugs(subdir: str, slug_re) -> list[str]:
    """List servable slugs: valid name, real file, contained in the root."""
    root = identity_root()
    directory = root / subdir
    if not directory.is_dir():
        return []
    resolved_root = root.resolve()
    slugs = []
    for path in sorted(directory.glob("*.md")):
        if not slug_re.match(path.stem):
            continue
        try:
            if not path.is_file() or not path.resolve().is_relative_to(resolved_root):
                continue
        except OSError:
            continue
        slugs.append(path.stem)
    return slugs


@mcp.resource("engram://identity")
def identity() -> str:
    """The user's identity file: who they are, preferences, house rules."""
    return _read("identity.md")


@mcp.resource("engram://context")
def context_index() -> str:
    """List available context topics."""
    topics = _list_slugs("context", TOPIC_SLUG_RE)
    if not topics:
        return "No context files. Add markdown files under context/ in the identity directory."
    return "\n".join(f"- engram://context/{t}" for t in topics)


@mcp.resource("engram://context/{topic}")
def context_topic(topic: str) -> str:
    """One standing-knowledge context file."""
    if not TOPIC_SLUG_RE.match(topic):
        return f"Invalid topic slug: {topic!r} (allowed: [a-z0-9_-]+)"
    return _read(f"context/{topic}.md")


@mcp.resource("engram://projects")
def projects_index() -> str:
    """List domains that have a canonical project-context file."""
    domains = _list_slugs("projects", DOMAIN_SLUG_RE)
    if not domains:
        return "No project files. Add markdown files under projects/ in the identity directory."
    return "\n".join(f"- engram://projects/{d}" for d in domains)


@mcp.resource("engram://projects/{domain}")
def project_context(domain: str) -> str:
    """Canonical long-form context for one project domain."""
    if not DOMAIN_SLUG_RE.match(domain):
        return f"Invalid domain slug: {domain!r} (allowed: [a-z0-9-]+)"
    return _read(f"projects/{domain}.md")
