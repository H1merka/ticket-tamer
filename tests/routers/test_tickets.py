"""Tests for app/routers/tickets.py — Ticket CRUD API."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.models.ticket import Ticket


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ticket(**overrides) -> Ticket:
    defaults = dict(
        id=1,
        email_from="client@example.com",
        email_to="support@eriskip.com",
        subject="Тестовая тема",
        body="Тестовое тело письма",
        fio="Иванов Иван",
        organization="ООО Тест",
        phone="+7 (342) 561-12-52",
        serial_numbers=["SN-001"],
        device_type="ДГС ЭРИС-210",
        description="Прибор не включается",
        category="неисправность",
        priority="high",
        sentiment="негатив",
        confidence=0.95,
        entities={"fio": "Иванов Иван"},
        response="Мы решим вашу проблему.",
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
# GET /api/v1/tickets/
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tickets(client):
    ticket = _make_ticket()
    with patch("app.services.ticket_service.get_tickets", new_callable=AsyncMock, return_value=[ticket]):
        resp = await client.get("/api/v1/tickets/")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["email_from"] == "client@example.com"


@pytest.mark.asyncio
async def test_list_tickets_with_filters(client):
    with patch("app.services.ticket_service.get_tickets", new_callable=AsyncMock, return_value=[]):
        resp = await client.get("/api/v1/tickets/?status=responded&category=неисправность&skip=0&limit=10")

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_tickets_empty(client):
    with patch("app.services.ticket_service.get_tickets", new_callable=AsyncMock, return_value=[]):
        resp = await client.get("/api/v1/tickets/")

    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/v1/tickets/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ticket_found(client):
    ticket = _make_ticket(id=42)
    with patch("app.services.ticket_service.get_ticket_by_id", new_callable=AsyncMock, return_value=ticket):
        resp = await client.get("/api/v1/tickets/42")

    assert resp.status_code == 200
    assert resp.json()["id"] == 42


@pytest.mark.asyncio
async def test_get_ticket_not_found(client):
    with patch("app.services.ticket_service.get_ticket_by_id", new_callable=AsyncMock, return_value=None):
        resp = await client.get("/api/v1/tickets/999")

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# POST /api/v1/tickets/
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_ticket(client):
    ticket = _make_ticket()
    with patch("app.services.ticket_service.create_ticket", new_callable=AsyncMock, return_value=ticket):
        resp = await client.post(
            "/api/v1/tickets/",
            json={
                "email_from": "client@example.com",
                "subject": "Тестовая тема",
                "body": "Тестовое тело письма",
            },
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["email_from"] == "client@example.com"


@pytest.mark.asyncio
async def test_create_ticket_validation_error(client):
    """Missing required fields → 422."""
    resp = await client.post("/api/v1/tickets/", json={"email_from": "test@test.com"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /api/v1/tickets/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_ticket(client):
    updated = _make_ticket(status="closed")
    with patch("app.services.ticket_service.update_ticket", new_callable=AsyncMock, return_value=updated):
        resp = await client.patch(
            "/api/v1/tickets/1",
            json={"status": "closed"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "closed"


@pytest.mark.asyncio
async def test_update_ticket_not_found(client):
    with patch("app.services.ticket_service.update_ticket", new_callable=AsyncMock, return_value=None):
        resp = await client.patch(
            "/api/v1/tickets/999",
            json={"status": "closed"},
        )

    assert resp.status_code == 404
