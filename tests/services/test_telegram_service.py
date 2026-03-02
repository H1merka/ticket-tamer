"""Tests for app/services/telegram_service.py — Telegram notifications."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.telegram_service import send_ticket_notification, SENTIMENT_EMOJI


def _make_ticket(**overrides):
    defaults = dict(
        id=1,
        fio="Иванов Иван",
        organization="ООО Тест",
        email_from="client@example.com",
        phone="+7 (342) 561-12-52",
        device_type="ДГС ЭРИС-210",
        category="неисправность",
        sentiment="негатив",
        subject="Прибор не работает",
        description="Описание проблемы",
        status="responded",
    )
    defaults.update(overrides)
    ticket = MagicMock()
    for k, v in defaults.items():
        setattr(ticket, k, v)
    return ticket


# ---------------------------------------------------------------------------
# send_ticket_notification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_notification_not_configured():
    """Returns False when Telegram is not configured."""
    with patch("app.services.telegram_service._get_bot", return_value=None):
        result = await send_ticket_notification(_make_ticket())
    assert result is False


@pytest.mark.asyncio
async def test_send_notification_success():
    """Sends message successfully → True."""
    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock()
    with (
        patch("app.services.telegram_service._get_bot", return_value=mock_bot),
        patch("app.services.telegram_service.settings", MagicMock(telegram_chat_id="12345")),
    ):
        result = await send_ticket_notification(_make_ticket())

    assert result is True
    mock_bot.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_notification_failure():
    """Bot raises exception → returns False."""
    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock(side_effect=RuntimeError("Network error"))
    with (
        patch("app.services.telegram_service._get_bot", return_value=mock_bot),
        patch("app.services.telegram_service.settings", MagicMock(telegram_chat_id="12345")),
    ):
        result = await send_ticket_notification(_make_ticket())

    assert result is False


@pytest.mark.asyncio
async def test_send_notification_needs_review_flag():
    """Ticket with needs_review → message includes warning."""
    mock_bot = AsyncMock()
    captured_text = None

    async def _capture_send(**kwargs):
        nonlocal captured_text
        captured_text = kwargs.get("text", "")

    mock_bot.send_message = _capture_send

    with (
        patch("app.services.telegram_service._get_bot", return_value=mock_bot),
        patch("app.services.telegram_service.settings", MagicMock(telegram_chat_id="12345")),
    ):
        await send_ticket_notification(_make_ticket(status="needs_review"))

    assert captured_text is not None
    assert "ТРЕБУЕТ РУЧНОЙ ПРОВЕРКИ" in captured_text


# ---------------------------------------------------------------------------
# SENTIMENT_EMOJI mapping
# ---------------------------------------------------------------------------


def test_sentiment_emoji_keys():
    assert "позитив" in SENTIMENT_EMOJI
    assert "нейтраль" in SENTIMENT_EMOJI
    assert "негатив" in SENTIMENT_EMOJI
