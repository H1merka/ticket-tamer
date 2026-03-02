"""Tests for app/services/analytics_service.py — summary & timeline with mocked DB."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from datetime import date

import pytest

from app.services.analytics_service import get_summary, get_timeline


class TestGetSummary:
    @pytest.mark.asyncio
    async def test_returns_summary(self):
        """Simulate a sequence of db.execute calls matching get_summary's queries."""
        db = AsyncMock()

        # Build a side_effect list for each sequential db.execute call:
        # 1. total count
        total_result = MagicMock()
        total_result.scalar.return_value = 10

        # 2. by category
        cat_result = MagicMock()
        cat_result.all.return_value = [("неисправность", 5), ("прочее", 5)]

        # 3. by sentiment
        sent_result = MagicMock()
        sent_result.all.return_value = [("негатив", 3), ("нейтраль", 7)]

        # 4. by status
        stat_result = MagicMock()
        stat_result.all.return_value = [("new", 4), ("responded", 6)]

        # 5. avg response time
        avg_result = MagicMock()
        avg_result.scalar.return_value = 300.0  # 300 seconds → 5.0 min

        # 6. auto count
        auto_result = MagicMock()
        auto_result.scalar.return_value = 4

        # 7. top devices
        dev_result = MagicMock()
        dev_result.all.return_value = [("ДГС ЭРИС-210", 3), ("СЕНСОН", 2)]

        db.execute.side_effect = [
            total_result, cat_result, sent_result,
            stat_result, avg_result, auto_result, dev_result,
        ]

        summary = await get_summary(db)
        assert summary.total_tickets == 10
        assert summary.by_category["неисправность"] == 5
        assert summary.by_sentiment["негатив"] == 3
        assert summary.by_status["responded"] == 6
        assert summary.avg_response_time_minutes == 5.0
        assert summary.auto_response_rate == 0.4
        assert len(summary.top_devices) == 2

    @pytest.mark.asyncio
    async def test_empty_database(self):
        db = AsyncMock()

        total_result = MagicMock()
        total_result.scalar.return_value = 0

        empty = MagicMock()
        empty.all.return_value = []

        avg_result = MagicMock()
        avg_result.scalar.return_value = None

        auto_result = MagicMock()
        auto_result.scalar.return_value = 0

        dev_result = MagicMock()
        dev_result.all.return_value = []

        db.execute.side_effect = [
            total_result, empty, empty, empty, avg_result, auto_result, dev_result,
        ]

        summary = await get_summary(db)
        assert summary.total_tickets == 0
        assert summary.auto_response_rate == 0.0
        assert summary.top_devices == []


class TestGetTimeline:
    @pytest.mark.asyncio
    async def test_returns_timeline_points(self):
        row = MagicMock()
        row.day = date(2026, 3, 1)
        row.total = 5
        row.auto = 3
        row.manual = 2

        mock_result = MagicMock()
        mock_result.all.return_value = [row]

        db = AsyncMock()
        db.execute.return_value = mock_result

        points = await get_timeline(db, days=7)
        assert len(points) == 1
        assert points[0].date == "2026-03-01"
        assert points[0].count == 5
        assert points[0].auto == 3

    @pytest.mark.asyncio
    async def test_empty_timeline(self):
        mock_result = MagicMock()
        mock_result.all.return_value = []

        db = AsyncMock()
        db.execute.return_value = mock_result

        points = await get_timeline(db, days=30)
        assert points == []
