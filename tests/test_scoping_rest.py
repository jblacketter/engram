"""REST agent-scoping enforcement tests (Phase 12).

Two agents bound to different domains must not see each other's memories
on any surface; owner and anonymous behavior stays unchanged.
"""

from unittest.mock import AsyncMock, patch

import pytest
from rest_framework.test import APIClient

from core.models import AgentKey
from core.services import memory_service, scoping

FAKE_768 = [0.1] * 768


@pytest.fixture(autouse=True)
def mock_embed():
    with patch("core.services.memory_service.embed", new_callable=AsyncMock) as m:
        m.return_value = FAKE_768
        yield m


@pytest.fixture
def agents(db):
    plain_a, hash_a = scoping.generate_key()
    plain_b, hash_b = scoping.generate_key()
    AgentKey.objects.create(
        name="agent-a", key_hash=hash_a,
        default_domain="domain-a", allowed_domains=["domain-a"],
    )
    AgentKey.objects.create(
        name="agent-b", key_hash=hash_b,
        default_domain="domain-b", allowed_domains=["domain-b"],
    )
    return plain_a, plain_b


def _client(token=None):
    client = APIClient()
    if token:
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


async def _seed():
    a = await memory_service.create_memory("A secret", tags=["domain:domain-a"])
    b = await memory_service.create_memory("B secret", tags=["domain:domain-b"])
    untagged = await memory_service.create_memory("Untagged note")
    return a, b, untagged


@pytest.mark.django_db(transaction=True)
class TestAuth:
    def test_valid_agent_key_authenticates(self, agents):
        plain_a, _ = agents
        response = _client(plain_a).get("/api/memories/")
        assert response.status_code == 200

    def test_revoked_agent_key_rejected(self, agents):
        plain_a, _ = agents
        AgentKey.objects.filter(name="agent-a").update(is_active=False)
        response = _client(plain_a).get("/api/memories/")
        assert response.status_code in (401, 403)

    def test_unknown_agent_key_rejected(self, agents):
        response = _client("egk_" + "z" * 43).get("/api/memories/")
        assert response.status_code in (401, 403)

    def test_last_used_updated(self, agents):
        plain_a, _ = agents
        assert AgentKey.objects.get(name="agent-a").last_used_at is None
        _client(plain_a).get("/api/memories/")
        assert AgentKey.objects.get(name="agent-a").last_used_at is not None

    def test_no_key_open_dev_mode_unchanged(self, db):
        # zero AgentKey rows, no header: open as today
        assert _client().get("/api/memories/").status_code == 200


@pytest.mark.django_db(transaction=True)
class TestWriteScoping:
    def test_agent_write_injects_default_domain(self, agents):
        plain_a, _ = agents
        response = _client(plain_a).post(
            "/api/memories/", {"content": "from A"}, format="json"
        )
        assert response.status_code == 201
        assert "domain:domain-a" in response.data["tags"]

    def test_agent_write_outside_domain_403(self, agents):
        plain_a, _ = agents
        response = _client(plain_a).post(
            "/api/memories/",
            {"content": "sneaky", "tags": ["domain:domain-b"]},
            format="json",
        )
        assert response.status_code == 403

    def test_anonymous_write_unchanged(self, db):
        response = _client().post(
            "/api/memories/", {"content": "no tags"}, format="json"
        )
        assert response.status_code == 201
        assert response.data["tags"] == []

    def test_ingest_url_outside_domain_403(self, agents):
        plain_a, _ = agents
        response = _client(plain_a).post(
            "/api/ingest/url/",
            {"url": "https://example.com", "tags": ["domain:domain-b"]},
            format="json",
        )
        assert response.status_code == 403


@pytest.mark.django_db(transaction=True)
class TestReadScoping:
    def test_cross_domain_invisibility_all_surfaces(self, agents):
        from asgiref.sync import async_to_sync
        plain_a, plain_b = agents
        mem_a, mem_b, untagged = async_to_sync(_seed)()
        client_b = _client(plain_b)

        # list: only domain-b
        listing = client_b.get("/api/memories/")
        contents = {m["content"] for m in listing.data}
        assert contents == {"B secret"}

        # explicit request for domain-a -> 403
        assert client_b.get("/api/memories/?tags=domain:domain-a").status_code == 403

        # detail: A's memory and the untagged one -> 404 (no oracle)
        assert client_b.get(f"/api/memories/{mem_a.id}/").status_code == 404
        assert client_b.get(f"/api/memories/{untagged.id}/").status_code == 404
        assert client_b.get(f"/api/memories/{mem_b.id}/").status_code == 200

        # update/delete out of scope -> 404
        assert client_b.patch(
            f"/api/memories/{mem_a.id}/", {"importance": 0.9}, format="json"
        ).status_code == 404
        assert client_b.delete(f"/api/memories/{mem_a.id}/").status_code == 404

        # stats: only domain-b counted
        stats = client_b.get("/api/stats/")
        assert stats.data["total"] == 1

        # tags: only domain-b's tags enumerated
        tags = client_b.get("/api/tags/")
        tag_names = {t["tag"] for t in tags.data}
        assert "domain:domain-a" not in tag_names
        assert "domain:domain-b" in tag_names

    def test_owner_sees_everything(self, agents):
        from asgiref.sync import async_to_sync
        async_to_sync(_seed)()
        listing = _client().get("/api/memories/")  # anonymous/owner surface
        assert len(listing.data) == 3
        stats = _client().get("/api/stats/")
        assert stats.data["total"] == 3

    def test_search_constrained_and_rejected(self, agents):
        plain_a, _ = agents
        with patch("api.views.search_service") as svc:
            svc.search = AsyncMock(return_value=[])
            response = _client(plain_a).post(
                "/api/search/", {"query": "x"}, format="json"
            )
            assert response.status_code == 200
            assert svc.search.call_args.kwargs["tags"] == ["domain:domain-a"]

            response = _client(plain_a).post(
                "/api/search/",
                {"query": "x", "tags": ["domain:domain-b"]},
                format="json",
            )
            assert response.status_code == 403
