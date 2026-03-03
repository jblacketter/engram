from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from intelligence.memory_decay import compute_decay_factor, run_decay

FAKE_768 = [0.1] * 768


class TestComputeDecayFactor:
    def test_new_high_importance_memory(self):
        now = datetime(2026, 3, 3, tzinfo=timezone.utc)
        score = compute_decay_factor(
            importance=1.0,
            created_at=now,
            last_accessed=now,
            access_count=0,
            now=now,
        )
        assert score == pytest.approx(0.5, abs=0.01)

    def test_old_unaccessed_memory_decays(self):
        now = datetime(2026, 3, 3, tzinfo=timezone.utc)
        created = now - timedelta(days=365)
        score = compute_decay_factor(
            importance=0.5,
            created_at=created,
            last_accessed=None,
            access_count=0,
            now=now,
        )
        assert score < 0.15

    def test_recently_accessed_decays_slower(self):
        now = datetime(2026, 3, 3, tzinfo=timezone.utc)
        created = now - timedelta(days=90)

        score_old_access = compute_decay_factor(
            importance=0.5,
            created_at=created,
            last_accessed=created,
            access_count=0,
            now=now,
        )
        score_recent_access = compute_decay_factor(
            importance=0.5,
            created_at=created,
            last_accessed=now - timedelta(days=1),
            access_count=0,
            now=now,
        )
        assert score_recent_access > score_old_access

    def test_high_access_count_boosts(self):
        now = datetime(2026, 3, 3, tzinfo=timezone.utc)
        created = now - timedelta(days=30)

        score_low = compute_decay_factor(
            importance=0.5, created_at=created, last_accessed=created,
            access_count=0, now=now,
        )
        score_high = compute_decay_factor(
            importance=0.5, created_at=created, last_accessed=created,
            access_count=20, now=now,
        )
        assert score_high > score_low

    def test_clamped_to_unit_range(self):
        now = datetime(2026, 3, 3, tzinfo=timezone.utc)
        score = compute_decay_factor(
            importance=1.0, created_at=now, last_accessed=now,
            access_count=100, now=now,
        )
        assert 0.0 <= score <= 1.0

    def test_zero_importance_gives_zero(self):
        now = datetime(2026, 3, 3, tzinfo=timezone.utc)
        score = compute_decay_factor(
            importance=0.0, created_at=now, last_accessed=now,
            access_count=10, now=now,
        )
        assert score == 0.0


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class TestRunDecay:
    async def test_updates_decay_factors(self):
        with patch("core.services.memory_service.embed", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = FAKE_768
            from core.services import memory_service

            memory = await memory_service.create_memory(
                content="Test memory for decay",
                importance=0.8,
            )

        changes = await run_decay(dry_run=False)
        assert len(changes) >= 1

        from asgiref.sync import sync_to_async
        from core.models import Memory

        refreshed = await sync_to_async(Memory.objects.get)(pk=memory.id)
        assert refreshed.decay_factor != 1.0

    async def test_dry_run_no_save(self):
        with patch("core.services.memory_service.embed", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = FAKE_768
            from core.services import memory_service

            memory = await memory_service.create_memory(
                content="Test memory for dry run",
                importance=0.5,
            )

        changes = await run_decay(dry_run=True)
        assert len(changes) >= 1

        from asgiref.sync import sync_to_async
        from core.models import Memory

        refreshed = await sync_to_async(Memory.objects.get)(pk=memory.id)
        assert refreshed.decay_factor == 1.0
