"""Tests for AgentKey lifecycle and the scoping primitives (Phase 12)."""

from io import StringIO
from unittest.mock import MagicMock

import pytest
from django.core.management import CommandError, call_command

from core.models import AgentKey
from core.services import scoping


def _agent(name="agent-a", default="domain-a", allowed=None):
    key = MagicMock(spec=AgentKey)
    key.name = name
    key.default_domain = default
    key.allowed_domains = allowed if allowed is not None else [default]
    return key


class TestKeyGeneration:
    def test_format_and_hash(self):
        plaintext, key_hash = scoping.generate_key()
        assert plaintext.startswith("egk_")
        assert len(key_hash) == 64
        assert scoping.hash_key(plaintext) == key_hash

    def test_keys_unique(self):
        assert scoping.generate_key()[0] != scoping.generate_key()[0]


class TestScopingPrimitives:
    def test_owner_passthrough_unchanged(self):
        assert scoping.check_write_tags(None, None) is None
        assert scoping.check_write_tags(None, ["x"]) == ["x"]
        assert scoping.constrain_read_tags(None, None) is None

    def test_write_injects_default_domain(self):
        agent = _agent()
        assert scoping.check_write_tags(agent, None) == ["domain:domain-a"]
        assert scoping.check_write_tags(agent, ["type:note"]) == [
            "type:note", "domain:domain-a",
        ]

    def test_write_allows_named_allowed_domain(self):
        agent = _agent(allowed=["domain-a", "domain-x"])
        tags = ["domain:domain-x", "type:note"]
        assert scoping.check_write_tags(agent, tags) == tags  # unchanged

    def test_write_rejects_outside_domain(self):
        agent = _agent()
        with pytest.raises(scoping.ScopeError, match="domain-b"):
            scoping.check_write_tags(agent, ["domain:domain-b"])

    def test_read_defaults_to_default_domain(self):
        agent = _agent(allowed=["domain-a", "domain-x"])
        assert scoping.constrain_read_tags(agent, None) == ["domain:domain-a"]
        assert scoping.constrain_read_tags(agent, ["domain:domain-x"]) == [
            "domain:domain-x"
        ]

    def test_read_rejects_outside_domain(self):
        agent = _agent()
        with pytest.raises(scoping.ScopeError):
            scoping.constrain_read_tags(agent, ["domain:domain-b"])

    def test_visibility(self):
        agent = _agent()
        mem = MagicMock(tags=["domain:domain-a", "type:note"])
        assert scoping.visible(agent, mem)
        assert not scoping.visible(agent, MagicMock(tags=["domain:domain-b"]))
        assert not scoping.visible(agent, MagicMock(tags=["type:note"]))  # untagged
        assert scoping.visible(None, MagicMock(tags=[]))  # owner sees all

    def test_allowed_domains(self):
        assert scoping.allowed_domains(None) is None
        assert scoping.allowed_domains(_agent(allowed=["a", "b"])) == ["a", "b"]


@pytest.mark.django_db(transaction=True)
class TestKeyResolution:
    def test_resolve_valid_key(self):
        plaintext, key_hash = scoping.generate_key()
        AgentKey.objects.create(
            name="tool-a", key_hash=key_hash,
            default_domain="domain-a", allowed_domains=["domain-a"],
        )
        agent = scoping.resolve_agent_key(plaintext)
        assert agent is not None and agent.name == "tool-a"

    def test_resolve_revoked_key_none(self):
        plaintext, key_hash = scoping.generate_key()
        AgentKey.objects.create(
            name="tool-r", key_hash=key_hash, default_domain="d",
            allowed_domains=["d"], is_active=False,
        )
        assert scoping.resolve_agent_key(plaintext) is None

    def test_resolve_unknown_and_non_prefixed(self):
        assert scoping.resolve_agent_key("egk_" + "x" * 43) is None
        assert scoping.resolve_agent_key("not-an-agent-key") is None


@pytest.mark.django_db(transaction=True)
class TestManagementCommand:
    def _create(self, *args):
        out = StringIO()
        call_command("agent_keys", *args, stdout=out)
        return out.getvalue()

    def test_create_prints_plaintext_once_stores_hash_only(self):
        out = self._create("create", "claude-code", "--default-domain", "engram")
        plaintext = [
            word for line in out.splitlines() for word in line.split()
            if word.startswith("egk_")
        ][0]
        key = AgentKey.objects.get(name="claude-code")
        assert key.key_hash == scoping.hash_key(plaintext)
        assert plaintext not in key.key_hash
        assert key.allowed_domains == ["engram"]

    def test_create_with_extra_allowed_domains(self):
        self._create(
            "create", "aegis", "--default-domain", "qa", "--allow", "engram"
        )
        key = AgentKey.objects.get(name="aegis")
        assert key.allowed_domains == ["qa", "engram"]

    def test_create_duplicate_name_rejected(self):
        self._create("create", "dup", "--default-domain", "d")
        with pytest.raises(CommandError, match="already exists"):
            self._create("create", "dup", "--default-domain", "d")

    def test_create_invalid_slugs_rejected(self):
        with pytest.raises(CommandError, match="invalid"):
            self._create("create", "Bad Name", "--default-domain", "d")
        with pytest.raises(CommandError, match="invalid"):
            self._create("create", "ok-name", "--default-domain", "Bad Domain")

    def test_revoke_and_list_no_secrets(self):
        out = self._create("create", "temp", "--default-domain", "d")
        plaintext = [w for w in out.split() if w.startswith("egk_")][0]

        self._create("revoke", "temp")
        assert not AgentKey.objects.get(name="temp").is_active

        listing = self._create("list")
        assert "temp: revoked" in listing
        assert plaintext not in listing
        assert AgentKey.objects.get(name="temp").key_hash not in listing

    def test_revoke_unknown_errors(self):
        with pytest.raises(CommandError, match="no key named"):
            self._create("revoke", "ghost")
