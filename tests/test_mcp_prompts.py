"""Tests for the daily-driver MCP prompts.

Each prompt template must reference only tools that actually exist on the
server, and must carry the suggestion-first / full-snapshot contracts.
"""

import re

import pytest

from mcp_server import prompts
from mcp_server.server import mcp

PROMPTS = {
    "start_day": prompts.start_day,
    "switch_project": prompts.switch_project,
    "end_session": prompts.end_session,
    "weekly_review": prompts.weekly_review,
}


def _render(name, **kwargs):
    return PROMPTS[name].fn(**kwargs)


def _referenced_tools(text):
    """Tool names referenced as `tool_name(` in backticks."""
    return set(re.findall(r"`(\w+)\(", text))


@pytest.mark.asyncio
async def test_all_prompts_registered_on_server():
    registered = set((await mcp.get_prompts()).keys())
    assert set(PROMPTS) <= registered


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,kwargs",
    [
        ("start_day", {}),
        ("start_day", {"domains": ["engram", "qa"]}),
        ("switch_project", {"domain": "engram"}),
        ("end_session", {"domain": "engram"}),
        ("weekly_review", {}),
        ("weekly_review", {"domains": ["engram"], "days": 14}),
    ],
)
async def test_prompts_reference_only_existing_tools(name, kwargs):
    tools = set((await mcp.get_tools()).keys())
    text = _render(name, **kwargs)
    referenced = _referenced_tools(text)
    assert referenced, f"{name} references no tools"
    assert referenced <= tools, f"{name} references unknown tools: {referenced - tools}"


def test_start_day_discovers_domains_when_none_given():
    assert "list_domains" in _render("start_day")


def test_start_day_uses_explicit_domains():
    text = _render("start_day", domains=["engram", "qa"])
    assert "engram, qa" in text
    assert "list_domains" not in text


def test_switch_project_scopes_to_domain():
    text = _render("switch_project", domain="engram")
    assert 'tags=["domain:engram", "type:project-status"], limit=1' in text


def test_end_session_is_suggestion_first_full_snapshot():
    text = _render("end_session", domain="engram")
    assert "do not store yet" in text.lower()
    assert "confirmation" in text.lower()
    assert "FULL SNAPSHOT" in text
    assert "type:checkpoint" in text
    assert "type:project-status" in text


def test_weekly_review_computes_cutoff_and_uses_after():
    text = _render("weekly_review", days=14)
    assert "14 days" in text
    assert "after=<cutoff>" in text
    assert "list_domains" in text


def test_read_only_prompts_do_not_store():
    for name, kwargs in (("start_day", {}), ("switch_project", {"domain": "x"})):
        text = " ".join(_render(name, **kwargs).split())
        assert "Do not store anything." in text
