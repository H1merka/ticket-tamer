"""Tests for app/services/sheets_service.py — Google Sheets sync."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.sheets_service import sync_ticket_to_sheet


def _make_ticket(**overrides):
    from datetime import datetime, timezone
    defaults = dict(
        id=1,
        fio="Иванов Иван",
        organization="ООО Тест",
        phone="+7 (342) 561-12-52",
        email_from="client@example.com",
        serial_numbers=["SN-001"],
        device_type="ДГС ЭРИС-210",
        sentiment="негатив",
        description="Прибор не работает",
        subject="Тема",
        category="неисправность",
        status="responded",
        priority="high",
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    ticket = MagicMock()
    for k, v in defaults.items():
        setattr(ticket, k, v)
    return ticket


@pytest.mark.asyncio
async def test_sync_not_configured():
    """Returns False when Google Sheets is not configured."""
    with patch("app.services.sheets_service._get_client", return_value=None):
        result = await sync_ticket_to_sheet(_make_ticket())
    assert result is False


@pytest.mark.asyncio
async def test_sync_success():
    """Appends row successfully → True."""
    mock_ws = MagicMock()
    mock_ws.append_row = MagicMock()
    mock_sh = MagicMock()
    mock_sh.sheet1 = mock_ws
    mock_client = MagicMock()
    mock_client.open_by_key = MagicMock(return_value=mock_sh)

    with (
        patch("app.services.sheets_service._get_client", return_value=mock_client),
        patch("app.services.sheets_service.settings", MagicMock(google_sheets_spreadsheet_id="sheet123")),
    ):
        result = await sync_ticket_to_sheet(_make_ticket())

    assert result is True
    mock_ws.append_row.assert_called_once()


@pytest.mark.asyncio
async def test_sync_failure():
    """gspread raises → returns False."""
    mock_client = MagicMock()
    mock_client.open_by_key = MagicMock(side_effect=RuntimeError("API error"))

    with (
        patch("app.services.sheets_service._get_client", return_value=mock_client),
        patch("app.services.sheets_service.settings", MagicMock(google_sheets_spreadsheet_id="sheet123")),
    ):
        result = await sync_ticket_to_sheet(_make_ticket())

    assert result is False
