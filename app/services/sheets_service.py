"""Google Sheets synchronisation — append ticket rows to a shared spreadsheet.

Uses gspread with a Service Account JSON key.
"""

from __future__ import annotations

import logging

import gspread

from app.config import settings

logger = logging.getLogger(__name__)


def _get_client() -> gspread.Client | None:
    """Get an authenticated gspread client, or None if not configured."""
    if not settings.google_sheets_credentials_file or not settings.google_sheets_spreadsheet_id:
        logger.debug("Google Sheets not configured — skipping")
        return None
    try:
        return gspread.service_account(filename=settings.google_sheets_credentials_file)
    except Exception:
        logger.exception("Failed to authenticate with Google Sheets")
        return None


async def sync_ticket_to_sheet(ticket) -> bool:
    """Append a single ticket row to Sheet1 of the configured spreadsheet.

    Note: gspread is synchronous; we run it inline because the payload is tiny.
    In high-throughput scenarios consider running in a threadpool.

    Returns True on success.
    """
    gc = _get_client()
    if gc is None:
        return False

    try:
        sh = gc.open_by_key(settings.google_sheets_spreadsheet_id)
        ws = sh.sheet1
        ws.append_row(
            [
                ticket.created_at.strftime("%d.%m.%Y %H:%M") if ticket.created_at else "",
                ticket.fio or "",
                ticket.organization or "",
                ticket.phone or "",
                ticket.email_from or "",
                ", ".join(ticket.serial_numbers or []),
                ticket.device_type or "",
                ticket.sentiment or "",
                ticket.description or ticket.subject or "",
                ticket.category or "",
                ticket.status or "",
                ticket.priority or "",
            ],
            value_input_option="RAW",
        )
        logger.info("Synced ticket #%s to Google Sheets", ticket.id)
        return True
    except Exception:
        logger.exception("Failed to sync ticket #%s to Google Sheets", ticket.id)
        return False
