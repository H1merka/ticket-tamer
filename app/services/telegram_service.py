"""Telegram notification service — notify operators about new tickets.

Uses python-telegram-bot's Bot class for async message sending.
"""

from __future__ import annotations

import logging

from telegram import Bot

from app.config import settings

logger = logging.getLogger(__name__)

SENTIMENT_EMOJI = {
    "позитив": "\U0001f60a",   # 😊
    "нейтраль": "\U0001f610",  # 😐
    "негатив": "\U0001f624",   # 😤
}


def _get_bot() -> Bot | None:
    """Create a Bot instance if credentials are configured."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.debug("Telegram not configured — skipping")
        return None
    return Bot(token=settings.telegram_bot_token)


async def send_ticket_notification(ticket) -> bool:
    """Send a formatted notification about a ticket to the Telegram chat.

    Returns True on success, False on error or if not configured.
    """
    bot = _get_bot()
    if bot is None:
        return False

    emoji = SENTIMENT_EMOJI.get(ticket.sentiment, "\u2753")  # ❓

    text = (
        f"\U0001f514 Новый тикет #{ticket.id}\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f464 ФИО: {ticket.fio or 'Не указано'}\n"
        f"\U0001f3e2 Организация: {ticket.organization or 'Не указано'}\n"
        f"\U0001f4e7 Email: {ticket.email_from}\n"
        f"\U0001f4f1 Телефон: {ticket.phone or 'Не указано'}\n"
        f"\U0001f527 Прибор: {ticket.device_type or 'Не указано'}\n"
        f"\U0001f4cb Категория: {ticket.category}\n"
        f"{emoji} Тональность: {ticket.sentiment}\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"\U0001f4dd {ticket.description or ticket.subject}\n"
    )

    if ticket.status == "needs_review":
        text += "\n\u26a0\ufe0f ТРЕБУЕТ РУЧНОЙ ПРОВЕРКИ"

    try:
        await bot.send_message(
            chat_id=settings.telegram_chat_id,
            text=text,
        )
        logger.info("Sent Telegram notification for ticket #%s", ticket.id)
        return True
    except Exception:
        logger.exception("Failed to send Telegram notification for ticket #%s", ticket.id)
        return False
