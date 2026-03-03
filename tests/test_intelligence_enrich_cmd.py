from io import StringIO
from unittest.mock import AsyncMock, patch

import pytest
from django.core.management import call_command

FAKE_768 = [0.1] * 768


@pytest.mark.django_db(transaction=True)
class TestEnrichAllSelection:
    """Verify `manage.py enrich --all` processes only unenriched memories."""

    def _create_memory(self, content, tags=None, metadata=None):
        with patch("core.services.memory_service.embed", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = FAKE_768
            from asgiref.sync import async_to_sync

            from core.services import memory_service

            return async_to_sync(memory_service.create_memory)(
                content=content,
                tags=tags or [],
                metadata=metadata or {},
            )

    def test_skips_fully_enriched_memories(self):
        """Memories with tags AND metadata.entities should not be selected."""
        self._create_memory(
            "Fully enriched memory",
            tags=["python", "django"],
            metadata={"entities": {"people": ["Alice"], "projects": [], "organizations": [], "technologies": []}},
        )

        out = StringIO()
        with (
            patch(
                "intelligence.management.commands.enrich.enrich_tags",
                new_callable=AsyncMock,
            ) as mock_tags,
            patch(
                "intelligence.management.commands.enrich.enrich_entities",
                new_callable=AsyncMock,
            ) as mock_entities,
        ):
            call_command("enrich", "--all", stdout=out)

        assert "No memories to enrich" in out.getvalue()
        mock_tags.assert_not_called()
        mock_entities.assert_not_called()

    def test_selects_memory_with_empty_tags(self):
        """Memory with empty tags but present entities should be selected."""
        self._create_memory(
            "Has entities but no tags",
            tags=[],
            metadata={"entities": {"people": [], "projects": [], "organizations": [], "technologies": ["python"]}},
        )

        out = StringIO()
        with (
            patch(
                "intelligence.management.commands.enrich.enrich_tags",
                new_callable=AsyncMock,
            ) as mock_tags,
            patch(
                "intelligence.management.commands.enrich.enrich_entities",
                new_callable=AsyncMock,
            ) as mock_entities,
        ):
            call_command("enrich", "--all", stdout=out)

        assert "Enriched 1/1" in out.getvalue()
        mock_tags.assert_called_once()
        mock_entities.assert_called_once()

    def test_selects_memory_missing_entities(self):
        """Memory with tags but missing metadata.entities should be selected."""
        self._create_memory(
            "Has tags but no entities",
            tags=["python"],
            metadata={},
        )

        out = StringIO()
        with (
            patch(
                "intelligence.management.commands.enrich.enrich_tags",
                new_callable=AsyncMock,
            ) as mock_tags,
            patch(
                "intelligence.management.commands.enrich.enrich_entities",
                new_callable=AsyncMock,
            ) as mock_entities,
        ):
            call_command("enrich", "--all", stdout=out)

        assert "Enriched 1/1" in out.getvalue()
        mock_tags.assert_called_once()
        mock_entities.assert_called_once()

    def test_mixed_enriched_and_unenriched(self):
        """Only unenriched memories should be processed in a mixed set."""
        # Enriched — should be skipped
        self._create_memory(
            "Already enriched",
            tags=["done"],
            metadata={"entities": {"people": [], "projects": [], "organizations": [], "technologies": []}},
        )
        # Unenriched (no tags, no entities) — should be selected
        self._create_memory("Needs enrichment", tags=[], metadata={})
        # Unenriched (has tags, no entities) — should be selected
        self._create_memory("Has tags only", tags=["partial"], metadata={})

        out = StringIO()
        with (
            patch(
                "intelligence.management.commands.enrich.enrich_tags",
                new_callable=AsyncMock,
            ) as mock_tags,
            patch(
                "intelligence.management.commands.enrich.enrich_entities",
                new_callable=AsyncMock,
            ) as mock_entities,
        ):
            call_command("enrich", "--all", stdout=out)

        assert "Enriched 2/2" in out.getvalue()
        assert mock_tags.call_count == 2
        assert mock_entities.call_count == 2
