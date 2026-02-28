"""Pydantic schemas for analytics responses."""

from __future__ import annotations

from pydantic import BaseModel


class DeviceCount(BaseModel):
    device: str
    count: int


class AnalyticsSummary(BaseModel):
    total_tickets: int
    by_category: dict[str, int]
    by_sentiment: dict[str, int]
    by_status: dict[str, int]
    avg_response_time_minutes: float | None
    auto_response_rate: float
    top_devices: list[DeviceCount]


class TimelinePoint(BaseModel):
    date: str
    count: int
    auto: int
    manual: int
