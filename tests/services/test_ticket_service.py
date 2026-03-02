"""Tests for app/services/ticket_service.py — CRUD with mocked async DB session."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.ticket import TicketCreate, TicketUpdate
from app.services.ticket_service import (
    create_ticket,
    get_ticket_by_id,
    get_tickets,
    update_ticket,
)


def _mock_ticket(**overrides):
    """Build a fake Ticket ORM object."""
    defaults = dict(
        id=1,
        email_from="client@example.com",
        email_to="support@eriskip.com",
        subject="Тема",
        body="Текст",
        status="new",
        category="прочее",
    )
    defaults.update(overrides)
    t = MagicMock(**defaults)
    return t


# ---------------------------------------------------------------------------
# get_tickets
# ---------------------------------------------------------------------------


class TestGetTickets:
    @pytest.mark.asyncio
    async def test_returns_list(self):
        tickets = [_mock_ticket(id=1), _mock_ticket(id=2)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = tickets

        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await get_tickets(db)
        assert len(result) == 2
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_filter_by_status(self):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        db = AsyncMock()
        db.execute.return_value = mock_result

        await get_tickets(db, status="responded")
        # Verify execute was called (filter is baked into the query)
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_filter_by_category(self):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        db = AsyncMock()
        db.execute.return_value = mock_result

        await get_tickets(db, category="неисправность")
        db.execute.assert_awaited_once()


# ---------------------------------------------------------------------------
# get_ticket_by_id
# ---------------------------------------------------------------------------


class TestGetTicketById:
    @pytest.mark.asyncio
    async def test_found(self):
        db = AsyncMock()
        db.get.return_value = _mock_ticket(id=42)

        result = await get_ticket_by_id(db, 42)
        assert result.id == 42
        db.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_not_found(self):
        db = AsyncMock()
        db.get.return_value = None

        result = await get_ticket_by_id(db, 999)
        assert result is None


# ---------------------------------------------------------------------------
# create_ticket
# ---------------------------------------------------------------------------


class TestCreateTicket:
    @pytest.mark.asyncio
    async def test_creates_and_flushes(self):
        db = AsyncMock()
        data = TicketCreate(
            email_from="x@y.com", subject="S", body="B",
        )

        result = await create_ticket(db, data)
        db.add.assert_called_once()
        db.flush.assert_awaited_once()
        db.refresh.assert_awaited_once()


# ---------------------------------------------------------------------------
# update_ticket
# ---------------------------------------------------------------------------


class TestUpdateTicket:
    @pytest.mark.asyncio
    async def test_updates_fields(self):
        ticket = _mock_ticket(id=1, status="new")
        db = AsyncMock()
        db.get.return_value = ticket

        data = TicketUpdate(status="responded")
        result = await update_ticket(db, 1, data)

        db.flush.assert_awaited_once()
        db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_not_found(self):
        db = AsyncMock()
        db.get.return_value = None

        data = TicketUpdate(status="closed")
        result = await update_ticket(db, 999, data)
        assert result is None
