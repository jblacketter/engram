from unittest.mock import AsyncMock, patch

import pytest

from intelligence.report_generator import generate_report

FAKE_768 = [0.1] * 768


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestGenerateReport:
    async def test_empty_report(self):
        report = await generate_report(days=7)
        assert "# Engram Weekly Digest" in report
        assert "Total memories:** 0" in report

    async def test_report_with_memories(self):
        with patch("core.services.memory_service.embed", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = FAKE_768
            from core.services import memory_service

            await memory_service.create_memory(
                content="Meeting with Sarah about Django migration",
                source="mcp",
                tags=["django", "meeting"],
                metadata={"entities": {"people": ["Sarah"], "technologies": ["Django"]}},
            )
            await memory_service.create_memory(
                content="Python testing best practices",
                source="api",
                tags=["python", "testing"],
            )

        report = await generate_report(days=7)
        assert "Total memories:** 2" in report
        assert "New in period:** 2" in report

    async def test_report_includes_tags(self):
        with patch("core.services.memory_service.embed", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = FAKE_768
            from core.services import memory_service

            await memory_service.create_memory(
                content="Python web development",
                tags=["python", "web"],
            )

        report = await generate_report(days=7)
        assert "Top Tags" in report
        assert "`python`" in report

    async def test_report_includes_entities(self):
        with patch("core.services.memory_service.embed", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = FAKE_768
            from core.services import memory_service

            await memory_service.create_memory(
                content="Sarah works on Engram",
                metadata={"entities": {
                    "people": ["Sarah"],
                    "projects": ["Engram"],
                    "organizations": [],
                    "technologies": [],
                }},
            )

        report = await generate_report(days=7)
        assert "Top Entities" in report
        assert "Sarah" in report
