"""Email service — IMAP polling and SMTP sending.

This module handles all email I/O, isolated from agent logic.
"""

from __future__ import annotations

import email
import email.policy
import logging
from dataclasses import dataclass, field
from email.message import EmailMessage

import aioimaplib
import aiosmtplib

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Attachment:
    """Represents an email attachment."""
    filename: str
    content_type: str
    data: bytes


@dataclass
class IncomingEmail:
    """Parsed representation of an incoming support email."""
    message_id: str
    sender: str
    recipient: str
    subject: str
    body: str
    raw_headers: str
    uid: str = ""
    attachments: list[Attachment] = field(default_factory=list)


# ---------------------------------------------------------------------------
# IMAP — Fetch new (UNSEEN) emails
# ---------------------------------------------------------------------------

async def fetch_new_emails() -> list[IncomingEmail]:
    """Connect to IMAP and fetch unread emails.

    Marks fetched emails as Seen.
    Returns list of parsed IncomingEmail.
    """
    if not settings.imap_user or not settings.imap_password:
        logger.debug("IMAP credentials not configured; skipping poll")
        return []

    emails: list[IncomingEmail] = []

    try:
        imap = aioimaplib.IMAP4_SSL(
            host=settings.imap_host,
            port=settings.imap_port,
            timeout=30,
        )
        await imap.wait_hello_from_server()
        await imap.login(settings.imap_user, settings.imap_password)
        await imap.select("INBOX")

        # Search for unseen messages
        _status, data = await imap.search("UNSEEN")
        if not data or not data[0]:
            await imap.logout()
            return emails

        uids = data[0].split()
        logger.info("Found %d unseen emails", len(uids))

        for uid_bytes in uids:
            uid = uid_bytes.decode() if isinstance(uid_bytes, bytes) else str(uid_bytes)
            try:
                _status, msg_data = await imap.fetch(uid, "(RFC822)")
                if not msg_data:
                    continue

                # msg_data is a list; the raw bytes are typically at index 1
                raw_bytes: bytes | None = None
                for item in msg_data:
                    if isinstance(item, bytes):
                        raw_bytes = item
                        break
                    if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], bytes):
                        raw_bytes = item[1]
                        break

                if raw_bytes is None:
                    continue

                parsed = parse_email_message(raw_bytes)
                parsed.uid = uid
                emails.append(parsed)

                # Mark as seen
                await imap.store(uid, "+FLAGS", "(\\Seen)")
            except Exception:
                logger.exception("Error fetching UID %s — skipping", uid)
                continue

        await imap.logout()
    except Exception:
        logger.exception("IMAP connection failed")

    return emails


# ---------------------------------------------------------------------------
# SMTP — Send reply
# ---------------------------------------------------------------------------

async def send_reply(
    to: str,
    subject: str,
    body: str,
    in_reply_to: str | None = None,
) -> bool:
    """Send a reply via SMTP with TLS.

    Returns True if the message was sent successfully.
    """
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("SMTP credentials not configured; cannot send reply")
        return False

    msg = EmailMessage()
    msg["From"] = settings.smtp_user
    msg["To"] = to
    msg["Subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg.set_content(body)

    retries = 3
    for attempt in range(1, retries + 1):
        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user,
                password=settings.smtp_password,
                use_tls=True if settings.smtp_port == 465 else False,
                start_tls=True if settings.smtp_port == 587 else False,
            )
            logger.info("Sent reply to %s (attempt %d)", to, attempt)
            return True
        except Exception:
            logger.exception("SMTP send attempt %d/%d failed", attempt, retries)
            if attempt == retries:
                return False

    return False


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_email_message(raw: bytes) -> IncomingEmail:
    """Parse a raw email message into an IncomingEmail dataclass."""
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    body = ""
    attachments: list[Attachment] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))

            if "attachment" in disposition or (
                content_type not in ("text/plain", "text/html", "multipart/mixed", "multipart/alternative")
            ):
                filename = part.get_filename() or "attachment"
                data = part.get_payload(decode=True)
                if data:
                    attachments.append(Attachment(
                        filename=filename,
                        content_type=content_type,
                        data=data,
                    ))
            elif content_type == "text/plain" and not body:
                body = part.get_content()
    else:
        body = msg.get_content()

    return IncomingEmail(
        message_id=msg.get("Message-ID", ""),
        sender=msg.get("From", ""),
        recipient=msg.get("To", ""),
        subject=msg.get("Subject", ""),
        body=body,
        raw_headers=str(msg),
        attachments=attachments,
    )

