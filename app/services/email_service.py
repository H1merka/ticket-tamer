"""Email service — IMAP polling and SMTP sending.

This module handles all email I/O, isolated from agent logic.
"""

from __future__ import annotations

import email
import email.policy
from dataclasses import dataclass
from email.message import EmailMessage

from app.config import settings


@dataclass
class IncomingEmail:
    """Parsed representation of an incoming support email."""
    message_id: str
    sender: str
    recipient: str
    subject: str
    body: str
    raw_headers: str


async def fetch_new_emails() -> list[IncomingEmail]:
    """Connect to IMAP and fetch unread emails.

    Placeholder — will be implemented with aioimaplib on hackathon.
    """
    # TODO: implement IMAP connection
    # async with aioimaplib.IMAP4_SSL(settings.imap_host, settings.imap_port) as imap:
    #     await imap.login(settings.imap_user, settings.imap_password)
    #     await imap.select("INBOX")
    #     ...
    return []


async def send_reply(to: str, subject: str, body: str, in_reply_to: str | None = None) -> bool:
    """Send a reply via SMTP.

    Placeholder — will be implemented with aiosmtplib on hackathon.
    """
    # TODO: implement SMTP sending
    # async with aiosmtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
    #     await smtp.login(settings.smtp_user, settings.smtp_password)
    #     msg = EmailMessage()
    #     msg["From"] = settings.smtp_user
    #     msg["To"] = to
    #     msg["Subject"] = f"Re: {subject}"
    #     if in_reply_to:
    #         msg["In-Reply-To"] = in_reply_to
    #     msg.set_content(body)
    #     await smtp.send_message(msg)
    return False


def parse_email_message(raw: bytes) -> IncomingEmail:
    """Parse a raw email message into an IncomingEmail dataclass."""
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_content()
                break
    else:
        body = msg.get_content()

    return IncomingEmail(
        message_id=msg.get("Message-ID", ""),
        sender=msg.get("From", ""),
        recipient=msg.get("To", ""),
        subject=msg.get("Subject", ""),
        body=body,
        raw_headers=str(msg),
    )
