"""Main agent pipeline — orchestrates the full email processing flow.

Flow:
  receive → parse attachments → classify → extract entities →
  RAG lookup → generate response → send reply → log everything
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from agent.attachment_parser import parse_attachments
from agent.classifier import ClassificationResult, classify_email
from agent.entity_extractor import extract_entities
from agent.kb_lookup import KBMatch, find_best_matches
from agent.response_generator import generate_response
from app.models.email_log import EmailLog
from app.models.ticket import Ticket
from app.services.email_service import Attachment, send_reply

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    classification: ClassificationResult
    entities: dict
    kb_matches: list[KBMatch] = field(default_factory=list)
    response_text: str = ""
    ticket_id: int | None = None
    email_sent: bool = False


async def process_email(
    db: AsyncSession,
    email_from: str,
    subject: str,
    body: str,
    message_id: str = "",
    attachments: list[Attachment] | None = None,
) -> PipelineResult:
    """Run the full agent pipeline on a single email.

    Each step is independent and can be replaced/upgraded separately.
    """
    logger.info("[PIPELINE] Processing email from=%s subject=%s", email_from, subject)

    # Step 0 — parse attachments (if any)
    full_body = body
    if attachments:
        attachment_text = await parse_attachments(attachments)
        if attachment_text:
            full_body = f"{body}\n\n--- Вложения ---\n{attachment_text}"
            logger.info("[PIPELINE] Parsed %d attachments, +%d chars", len(attachments), len(attachment_text))

    # Step 1 — classify
    classification = await classify_email(subject, full_body)
    logger.info(
        "[PIPELINE] classify: category=%s sentiment=%s confidence=%.2f priority=%s",
        classification.category, classification.sentiment,
        classification.confidence, classification.priority,
    )

    # Step 2 — extract entities
    entities = await extract_entities(full_body)
    logger.info("[PIPELINE] ner: entities=%s", entities)

    # Step 3 — RAG: find relevant KB chunks
    kb_matches = await find_best_matches(
        db,
        description=entities.get("description"),
        device_type=entities.get("device_type"),
        body=full_body,
    )
    max_score = max((m.score for m in kb_matches), default=0.0)
    logger.info("[PIPELINE] rag: chunks_found=%d max_score=%.2f", len(kb_matches), max_score)

    # Step 4 — generate response
    response_text = await generate_response(
        email_from=email_from,
        subject=subject,
        category=classification.category,
        entities=entities,
        kb_matches=kb_matches,
        body=full_body,
        sentiment=classification.sentiment,
    )
    logger.info("[PIPELINE] generate: %d chars", len(response_text))

    # Step 5 — create/update ticket
    status = "responded"
    if classification.confidence < 0.5 or max_score < 0.3:
        status = "needs_review"

    ticket = Ticket(
        email_from=email_from,
        subject=subject,
        body=full_body,
        category=classification.category,
        sentiment=classification.sentiment,
        confidence=classification.confidence,
        priority=classification.priority,
        response=response_text,
        status=status,
        fio=entities.get("fio"),
        organization=entities.get("organization"),
        phone=entities.get("phone"),
        serial_numbers=entities.get("serial_numbers"),
        device_type=entities.get("device_type"),
        description=entities.get("description"),
    )
    db.add(ticket)
    await db.flush()

    ticket_id = ticket.id
    logger.info("[PIPELINE] ticket_id=%d status=%s", ticket_id, status)

    # Log inbound email
    db.add(EmailLog(
        ticket_id=ticket_id,
        direction="inbound",
        message_id=message_id,
        raw_headers="",
    ))

    # Step 6 — send reply via SMTP (if status is responded)
    email_sent = False
    if status == "responded":
        email_sent = await send_reply(
            to=email_from,
            subject=subject,
            body=response_text,
            in_reply_to=message_id or None,
        )
        if not email_sent:
            ticket.status = "needs_review"
            logger.warning("[PIPELINE] SMTP failed; ticket %d → needs_review", ticket_id)

        # Log outbound email
        db.add(EmailLog(
            ticket_id=ticket_id,
            direction="outbound",
            message_id="",
        ))

    await db.commit()
    logger.info("[PIPELINE] ticket_id=%d complete, email_sent=%s", ticket_id, email_sent)

    # Step 7 — fire-and-forget: Telegram & Google Sheets notifications
    try:
        from app.services.telegram_service import send_ticket_notification
        await send_ticket_notification(ticket)
    except Exception:
        logger.exception("[PIPELINE] Telegram notification failed for ticket %d", ticket_id)

    try:
        from app.services.sheets_service import sync_ticket_to_sheet
        await sync_ticket_to_sheet(ticket)
    except Exception:
        logger.exception("[PIPELINE] Google Sheets sync failed for ticket %d", ticket_id)

    return PipelineResult(
        classification=classification,
        entities=entities,
        kb_matches=kb_matches,
        response_text=response_text,
        ticket_id=ticket_id,
        email_sent=email_sent,
    )
