"""Knowledge-base lookup — find the most relevant KB article for a ticket."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.knowledge_base import KnowledgeBaseArticle


@dataclass
class KBMatch:
    article_id: int
    question: str
    answer: str
    score: float


async def find_best_match(
    db: AsyncSession,
    category: str,
    body: str,
) -> KBMatch | None:
    """Find the most relevant KB article for the given category and body text.

    Current implementation: simple category-based lookup (first active match).
    Will be upgraded to semantic search (embedding cosine similarity) on hackathon.
    """
    # TODO: semantic search via pgvector / sentence-transformers embeddings
    query = (
        select(KnowledgeBaseArticle)
        .where(
            KnowledgeBaseArticle.category == category,
            KnowledgeBaseArticle.is_active.is_(True),
        )
        .limit(1)
    )
    result = await db.execute(query)
    article = result.scalar_one_or_none()

    if article is None:
        return None

    return KBMatch(
        article_id=article.id,
        question=article.question,
        answer=article.answer,
        score=1.0,  # placeholder
    )
