"""Tests for app/routers/analytics.py — analytics API."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.analytics import AnalyticsSummary, DeviceCount, TimelinePoint


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_summary(client):
    summary = AnalyticsSummary(
        total_tickets=100,
        by_category={"неисправность": 40, "калибровка": 30, "прочее": 30},
        by_sentiment={"позитив": 10, "нейтраль": 60, "негатив": 30},
        by_status={"responded": 70, "needs_review": 20, "new": 10},
        avg_response_time_minutes=5.2,
        auto_response_rate=0.65,
        top_devices=[DeviceCount(device="ДГС ЭРИС-210", count=25)],
    )
    with patch("app.services.analytics_service.get_summary", new_callable=AsyncMock, return_value=summary):
        resp = await client.get("/api/v1/analytics/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_tickets"] == 100
    assert data["by_category"]["неисправность"] == 40
    assert data["auto_response_rate"] == 0.65
    assert len(data["top_devices"]) == 1


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/timeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_timeline(client):
    timeline = [
        TimelinePoint(date="2026-03-01", count=10, auto=7, manual=3),
        TimelinePoint(date="2026-03-02", count=15, auto=10, manual=5),
    ]
    with patch("app.services.analytics_service.get_timeline", new_callable=AsyncMock, return_value=timeline):
        resp = await client.get("/api/v1/analytics/timeline?days=7")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["date"] == "2026-03-01"
    assert data[0]["auto"] == 7
    assert data[1]["count"] == 15


@pytest.mark.asyncio
async def test_get_timeline_default_days(client):
    with patch("app.services.analytics_service.get_timeline", new_callable=AsyncMock, return_value=[]):
        resp = await client.get("/api/v1/analytics/timeline")

    assert resp.status_code == 200
    assert resp.json() == []
