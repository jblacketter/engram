"""MCP agent-scoping enforcement tests (Phase 12).

The MCP tools import `current_agent` into their module namespace, so each
test patches it in the module under test. Verifier tests exercise
EngramTokenVerifier directly.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from core.models import AgentKey
from core.services import memory_service, scoping
from mcp_server.auth import EngramTokenVerifier, build_auth, current_agent

FAKE_768 = [0.1] * 768


@pytest.fixture(autouse=True)
def mock_embed():
    with patch("core.services.memory_service.embed", new_callable=AsyncMock) as m:
        m.return_value = FAKE_768
        yield m


@pytest.fixture
def agent_a(db):
    plain, key_hash = scoping.generate_key()
    agent = AgentKey.objects.create(
        name="agent-a", key_hash=key_hash,
        default_domain="domain-a", allowed_domains=["domain-a"],
    )
    agent.plaintext = plain
    return agent


def _as_agent(module: str, agent):
    return patch(
        f"mcp_server.tools.{module}.current_agent",
        AsyncMock(return_value=agent),
    )


async def _seed():
    a = await memory_service.create_memory("A secret", tags=["domain:domain-a"])
    b = await memory_service.create_memory("B secret", tags=["domain:domain-b"])
    untagged = await memory_service.create_memory("Untagged")
    return a, b, untagged


@pytest.mark.django_db(transaction=True)
class TestVerifier:
    @pytest.mark.asyncio
    async def test_global_key_owner_claims(self, settings):
        settings.MCP_API_KEY = "global-secret"
        token = await EngramTokenVerifier().verify_token("global-secret")
        assert token is not None and token.claims["principal"] == "owner"

    @pytest.mark.asyncio
    async def test_agent_key_claims_and_last_used(self, agent_a, settings):
        settings.MCP_API_KEY = "global-secret"
        token = await EngramTokenVerifier().verify_token(agent_a.plaintext)
        assert token.claims == {"principal": "agent", "agent_id": str(agent_a.pk)}
        from asgiref.sync import sync_to_async
        await sync_to_async(agent_a.refresh_from_db)()
        assert agent_a.last_used_at is not None

    @pytest.mark.asyncio
    async def test_revoked_and_garbage_rejected(self, agent_a):
        from asgiref.sync import sync_to_async
        await sync_to_async(
            AgentKey.objects.filter(pk=agent_a.pk).update
        )(is_active=False)
        verifier = EngramTokenVerifier()
        assert await verifier.verify_token(agent_a.plaintext) is None
        assert await verifier.verify_token("egk_" + "x" * 43) is None
        assert await verifier.verify_token("") is None

    def test_build_auth_matrix(self, settings, db):
        settings.MCP_API_KEY = ""
        assert build_auth() is None  # no global key, no agent keys: open
        _, key_hash = scoping.generate_key()
        AgentKey.objects.create(
            name="x", key_hash=key_hash, default_domain="d", allowed_domains=["d"]
        )
        assert isinstance(build_auth(), EngramTokenVerifier)  # keys exist
        settings.MCP_API_KEY = "k"
        assert isinstance(build_auth(), EngramTokenVerifier)

    @pytest.mark.asyncio
    async def test_current_agent_revoked_raises(self, agent_a):
        from asgiref.sync import sync_to_async
        await sync_to_async(
            AgentKey.objects.filter(pk=agent_a.pk).update
        )(is_active=False)
        fake_access = type("T", (), {"claims": {
            "principal": "agent", "agent_id": str(agent_a.pk)
        }})()
        with patch(
            "fastmcp.server.dependencies.get_access_token",
            return_value=fake_access,
        ):
            with pytest.raises(scoping.ScopeError, match="revoked"):
                await current_agent()

    @pytest.mark.asyncio
    async def test_current_agent_none_without_context(self):
        assert await current_agent() is None


@pytest.mark.django_db(transaction=True)
class TestToolEnforcement:
    @pytest.mark.asyncio
    async def test_store_injects_default_domain(self, agent_a):
        from mcp_server.tools.memory import store_memory
        with _as_agent("memory", agent_a):
            result = await store_memory.fn("scoped content")
        data = json.loads(result)
        mem = await memory_service.get_memory(data["id"])
        assert "domain:domain-a" in mem.tags

    @pytest.mark.asyncio
    async def test_store_outside_domain_rejected(self, agent_a):
        from mcp_server.tools.memory import store_memory
        with _as_agent("memory", agent_a):
            result = await store_memory.fn("sneaky", tags=["domain:domain-b"])
        assert "Scope error" in result

    @pytest.mark.asyncio
    async def test_get_update_delete_blocked_as_not_found(self, agent_a):
        from mcp_server.tools.memory import delete_memory, get_memory, update_memory
        _, mem_b, untagged = await _seed()
        with _as_agent("memory", agent_a):
            assert "not found" in await get_memory.fn(str(mem_b.id))
            assert "not found" in await get_memory.fn(str(untagged.id))
            assert "not found" in await update_memory.fn(
                str(mem_b.id), importance=0.9
            )
            assert "not found" in await delete_memory.fn(str(mem_b.id))
        # untouched
        assert (await memory_service.get_memory(mem_b.id)).importance == 0.5

    @pytest.mark.asyncio
    async def test_get_own_domain_allowed(self, agent_a):
        from mcp_server.tools.memory import get_memory
        mem_a, _, _ = await _seed()
        with _as_agent("memory", agent_a):
            result = await get_memory.fn(str(mem_a.id))
        assert json.loads(result)["content"] == "A secret"

    @pytest.mark.asyncio
    async def test_search_brain_constrained(self, agent_a):
        from mcp_server.tools.search import search_brain
        with (
            _as_agent("search", agent_a),
            patch("mcp_server.tools.search.search_service") as svc,
        ):
            svc.search = AsyncMock(return_value=[])
            await search_brain.fn("query")
            assert svc.search.call_args.kwargs["tags"] == ["domain:domain-a"]

            result = await search_brain.fn("query", tags=["domain:domain-b"])
            assert "Scope error" in result

    @pytest.mark.asyncio
    async def test_find_related_seed_blocked(self, agent_a):
        from mcp_server.tools.search import find_related
        _, mem_b, _ = await _seed()
        with _as_agent("search", agent_a):
            result = await find_related.fn(str(mem_b.id))
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_list_recent_constrained(self, agent_a):
        from mcp_server.tools.search import list_recent_memories
        await _seed()
        with _as_agent("search", agent_a):
            result = await list_recent_memories.fn()
        data = json.loads(result)
        assert {m["content"] for m in data} == {"A secret"}

    @pytest.mark.asyncio
    async def test_get_stats_restricted(self, agent_a):
        from mcp_server.tools.stats import get_stats
        await _seed()
        with _as_agent("stats", agent_a):
            result = await get_stats.fn()
        data = json.loads(result)
        assert data["total"] == 1
        assert "domain:domain-b" not in {t["tag"] for t in data["top_tags"]}

    @pytest.mark.asyncio
    async def test_list_domains_restricted(self, agent_a):
        from mcp_server.tools.domains import list_domains
        await _seed()
        with _as_agent("domains", agent_a):
            result = await list_domains.fn()
        data = json.loads(result)
        assert [d["domain"] for d in data] == ["domain-a"]

    @pytest.mark.asyncio
    async def test_ingest_rejected_outside_domain(self, agent_a):
        import base64
        from mcp_server.tools.ingest import ingest_file, store_from_url
        with _as_agent("ingest", agent_a):
            result = await store_from_url.fn(
                "https://example.com", tags=["domain:domain-b"]
            )
            assert "Scope error" in result
            result = await ingest_file.fn(
                content_base64=base64.b64encode(b"x").decode(),
                filename="x.txt",
                tags=["domain:domain-b"],
            )
            assert "Scope error" in result

    @pytest.mark.asyncio
    async def test_owner_unrestricted(self):
        from mcp_server.tools.stats import get_stats
        await _seed()
        # no patching: current_agent resolves to None (no request context)
        result = await get_stats.fn()
        assert json.loads(result)["total"] == 3
