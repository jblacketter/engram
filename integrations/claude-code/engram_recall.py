#!/usr/bin/env python3
"""Engram SessionStart hook for Claude Code.

Reads the hook payload from stdin, resolves the project domain from the
payload's cwd, fetches the latest project-status snapshot and recent
memories from the engram REST API, and prints a compact context block to
stdout (which Claude Code injects into the session).

Fail-soft by design: on ANY problem — malformed stdin, missing cwd,
unreachable API, auth errors, bad JSON, timeouts — print nothing and exit 0
so the session starts normally.

Config (env):
  ENGRAM_API_URL       default http://localhost:8000/api
  ENGRAM_REST_API_KEY  optional bearer token
  ENGRAM_DOMAIN        overrides domain resolution entirely
  ENGRAM_HOOK_TIMEOUT  per-request timeout seconds (default 1.5; total
                       budget is twice this — one status + one recents call)

Domain resolution precedence:
  ENGRAM_DOMAIN env var
  > `.engram` marker file (one line: `domain=<slug>`), found by a bounded
    upward walk from cwd (<=20 levels, stops at filesystem root)
  > nearest ancestor directory containing `.git` (its directory name)
  > cwd basename
Slugs normalize to [a-z0-9-]; empty/invalid resolution falls through.

Stdlib only — runs under any Python 3.9+, no project venv required.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

MAX_WALK = 20
MAX_OUTPUT_BYTES = 4096
MEMORY_SNIPPET_CHARS = 200


def normalize_slug(name):
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    return slug or None


def read_marker(path):
    """Parse a .engram marker file. Returns a slug or None."""
    try:
        with open(path, encoding="utf-8") as fh:
            line = fh.readline().strip()
    except OSError:
        return None
    if line.startswith("domain="):
        return normalize_slug(line[len("domain="):])
    return None


def resolve_domain(cwd, env):
    env_domain = env.get("ENGRAM_DOMAIN", "")
    if env_domain:
        slug = normalize_slug(env_domain)
        if slug:
            return slug

    # Bounded upward walk for a .engram marker
    directory = os.path.abspath(cwd)
    git_root_name = None
    for _ in range(MAX_WALK):
        marker = os.path.join(directory, ".engram")
        if os.path.isfile(marker):
            slug = read_marker(marker)
            if slug:
                return slug
        if git_root_name is None and os.path.isdir(os.path.join(directory, ".git")):
            git_root_name = os.path.basename(directory)
        parent = os.path.dirname(directory)
        if parent == directory:  # filesystem root
            break
        directory = parent

    if git_root_name:
        slug = normalize_slug(git_root_name)
        if slug:
            return slug

    return normalize_slug(os.path.basename(os.path.abspath(cwd)))


def fetch_memories(api_url, api_key, params, timeout):
    """GET /memories/ with query params. Returns a list or raises."""
    url = api_url.rstrip("/") + "/memories/?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url)
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("unexpected response shape")
    return payload


def build_context(domain, status_memories, recent_memories):
    lines = [f"<engram-context domain=\"{domain}\">"]
    if status_memories:
        lines.append("## Project status (latest snapshot)")
        lines.append(status_memories[0].get("content", "").strip())
    if recent_memories:
        lines.append("## Recent memories")
        for memory in recent_memories:
            content = " ".join(memory.get("content", "").split())
            if len(content) > MEMORY_SNIPPET_CHARS:
                content = content[:MEMORY_SNIPPET_CHARS] + "…"
            created = memory.get("created_at", "")[:10]
            lines.append(f"- [{created}] {content}")
    lines.append(
        "Use /engram search|store|status|checkpoint or the engram MCP tools "
        f"(tag writes with domain:{domain})."
    )
    lines.append("</engram-context>")
    block = "\n".join(lines)
    if len(block.encode("utf-8")) > MAX_OUTPUT_BYTES:
        block = block.encode("utf-8")[:MAX_OUTPUT_BYTES].decode("utf-8", "ignore")
    return block


def main():
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            return 0
        # Skip when context is already present: resume keeps the transcript,
        # compact preserves a summary. Inject on startup and clear only.
        source = payload.get("source", "startup")
        if source not in ("startup", "clear"):
            return 0
        cwd = payload.get("cwd")
        if not cwd or not isinstance(cwd, str):
            return 0

        domain = resolve_domain(cwd, os.environ)
        if not domain:
            return 0

        api_url = os.environ.get("ENGRAM_API_URL", "http://localhost:8000/api")
        api_key = os.environ.get("ENGRAM_REST_API_KEY", "")
        timeout = float(os.environ.get("ENGRAM_HOOK_TIMEOUT", "1.5"))

        status = fetch_memories(
            api_url, api_key,
            {"tags": f"domain:{domain},type:project-status", "limit": 1},
            timeout,
        )
        recents = fetch_memories(
            api_url, api_key,
            {"tags": f"domain:{domain}",
             "exclude_tags": "type:project-status", "limit": 5},
            timeout,
        )
        if not status and not recents:
            return 0
        print(build_context(domain, status, recents))
        return 0
    except Exception:
        return 0  # fail-soft: never block or noise a session start


if __name__ == "__main__":
    sys.exit(main())
