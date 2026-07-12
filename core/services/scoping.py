"""Agent-scoping enforcement (Phase 12).

One shared module used by BOTH the REST views and the MCP tools, so the
two surfaces cannot drift. Principals:

- Owner (global key / dashboard session) and Anonymous (auth disabled):
  ``principal is None`` here — unrestricted, behavior unchanged.
- Agent (a valid, active AgentKey): the enforcement below.

Semantics (docs/phases/agent-scoping.md):
- Writes: no domain tag -> inject domain:<default>; a domain tag outside
  allowed_domains -> explicit rejection (never silent rewrite).
- Scoped reads: requested domain outside allowed -> rejection; no domain
  filter -> constrained to domain:<default> (reading another allowed
  domain requires naming it).
- Visibility: a memory is visible to an agent iff it carries at least one
  allowed domain tag. Invisible memories yield 404/"not found" — never a
  403 existence oracle. Untagged memories are invisible to agents.
"""

import hashlib
import secrets

from django.db.models import Q

from core.models import AgentKey, Memory

KEY_PREFIX = "egk_"

DOMAIN_TAG_PREFIX = "domain:"


class ScopeError(Exception):
    """A request tried to leave its allowed domains. Message is safe to
    show to the caller."""


def generate_key() -> tuple[str, str]:
    """Return (plaintext, sha256_hash). Plaintext is shown once."""
    plaintext = KEY_PREFIX + secrets.token_urlsafe(32)
    return plaintext, hash_key(plaintext)


def hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def resolve_agent_key(token: str) -> AgentKey | None:
    """Look up an active AgentKey by token. None if unknown/inactive."""
    if not token.startswith(KEY_PREFIX):
        return None
    try:
        return AgentKey.objects.get(key_hash=hash_key(token), is_active=True)
    except AgentKey.DoesNotExist:
        return None


def _domain_tags(tags: list[str] | None) -> list[str]:
    return [t for t in (tags or []) if t.startswith(DOMAIN_TAG_PREFIX)]


def _domains(tags: list[str] | None) -> set[str]:
    return {t[len(DOMAIN_TAG_PREFIX):] for t in _domain_tags(tags)}


def check_write_tags(agent: AgentKey | None, tags: list[str] | None):
    """Return the tags a write must carry. Raises ScopeError.

    Owner/anonymous: tags pass through UNCHANGED (None stays None) — the
    pre-scoping behavior is bit-for-bit preserved.
    """
    if agent is None:
        return tags
    tags = list(tags or [])
    requested = _domains(tags)
    if not requested:
        return tags + [f"{DOMAIN_TAG_PREFIX}{agent.default_domain}"]
    outside = requested - set(agent.allowed_domains)
    if outside:
        raise ScopeError(
            f"domain(s) not allowed for this key: {', '.join(sorted(outside))}"
        )
    return tags


def constrain_read_tags(agent: AgentKey | None, tags: list[str] | None):
    """Return the tag filter a scoped read must use. Raises ScopeError.

    Owner/anonymous: tags pass through UNCHANGED (None stays None).
    """
    if agent is None:
        return tags
    tags = list(tags or [])
    requested = _domains(tags)
    if not requested:
        return tags + [f"{DOMAIN_TAG_PREFIX}{agent.default_domain}"]
    outside = requested - set(agent.allowed_domains)
    if outside:
        raise ScopeError(
            f"domain(s) not allowed for this key: {', '.join(sorted(outside))}"
        )
    return tags


def visible(agent: AgentKey | None, memory: Memory) -> bool:
    """Is this memory visible to the principal?"""
    if agent is None:
        return True
    return bool(_domains(memory.tags) & set(agent.allowed_domains))


def allowed_domains(agent: AgentKey | None) -> list[str] | None:
    """None = unrestricted (owner/anonymous)."""
    if agent is None:
        return None
    return list(agent.allowed_domains)


def allowed_queryset(agent: AgentKey | None, qs=None):
    """Filter a Memory queryset to the agent's allowed domains (OR-union).

    Owner/anonymous get the queryset unchanged.
    """
    if qs is None:
        qs = Memory.objects.all()
    if agent is None:
        return qs
    condition = Q(pk__in=[])  # empty
    for domain in agent.allowed_domains:
        condition |= Q(tags__contains=[f"{DOMAIN_TAG_PREFIX}{domain}"])
    return qs.filter(condition)
