"""Main agent pipeline — orchestrates the full email processing flow.

Flow: receive → classify → extract entities → lookup KB → draft response
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from agent.classifier import ClassificationResult, classify_email
from agent.entity_extractor import extract_entities
from agent.kb_lookup import KBMatch, find_best_match
from agent.response_generator import generate_response


@dataclass
class PipelineResult:
    classification: ClassificationResult
    entities: dict
    kb_match: KBMatch | None
    response_text: str


async def process_email(
    db: AsyncSession,
    email_from: str,
    subject: str,
    body: str,
) -> PipelineResult:
    """Run the full agent pipeline on a single email.

    Each step is independent and can be replaced/upgraded separately.
    """
    # Step 1 — classify
    classification = await classify_email(subject, body)

    # Step 2 — extract entities
    entities = await extract_entities(body)

    # Step 3 — find relevant KB article
    kb_match = await find_best_match(db, classification.category, body)

    # Step 4 — generate response
    response_text = await generate_response(
        email_from=email_from,
        subject=subject,
        category=classification.category,
        entities=entities,
        kb_match=kb_match,
    )

    return PipelineResult(
        classification=classification,
        entities=entities,
        kb_match=kb_match,
        response_text=response_text,
    )
