"""Tests for app/routers/export.py — CSV/XLSX export API."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.ticket import Ticket


def _make_ticket(**overrides):
    defaults = dict(
        id=1,
        email_from="client@example.com",
        email_to="support@eriskip.com",
        subject="Тема",
        body="Тело",
        fio="Иванов Иван",
        organization="ООО Тест",
        phone="+7 (342) 561-12-52",
        serial_numbers=["SN-001"],
        device_type="ДГС ЭРИС-210",
        description="Прибор не работает",
        category="неисправность",
        priority="high",
        sentiment="негатив",
        confidence=0.95,
        entities={},
        response="Ответ",
        kb_article_id=None,
        status="responded",
        is_auto=True,
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        responded_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    ticket = MagicMock(spec=Ticket)
    for k, v in defaults.items():
        setattr(ticket, k, v)
    return ticket


# ---------------------------------------------------------------------------
# GET /api/v1/export/csv
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_csv(client):
    ticket = _make_ticket()
    with patch("app.services.ticket_service.get_tickets", new_callable=AsyncMock, return_value=[ticket]):
        resp = await client.get("/api/v1/export/csv")

    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    content = resp.text
    assert "id" in content  # header row
    assert "client@example.com" in content


@pytest.mark.asyncio
async def test_export_csv_empty(client):
    with patch("app.services.ticket_service.get_tickets", new_callable=AsyncMock, return_value=[]):
        resp = await client.get("/api/v1/export/csv")

    assert resp.status_code == 200
    lines = resp.text.strip().split("\n")
    assert len(lines) == 1  # header only


# ---------------------------------------------------------------------------
# GET /api/v1/export/xlsx
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_xlsx(client):
    ticket = _make_ticket()
    with patch("app.services.ticket_service.get_tickets", new_callable=AsyncMock, return_value=[ticket]):
        resp = await client.get("/api/v1/export/xlsx")

    assert resp.status_code == 200
    ct = resp.headers["content-type"]
    assert "spreadsheet" in ct or "application" in ct
    # XLSX starts with PK magic bytes (ZIP)
    assert resp.content[:2] == b"PK"


@pytest.mark.asyncio
async def test_export_csv_with_filters(client):
    with patch("app.services.ticket_service.get_tickets", new_callable=AsyncMock, return_value=[]):
        resp = await client.get("/api/v1/export/csv?status=responded&category=неисправность")

    assert resp.status_code == 200
