from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBaseArticle
from app.schemas.knowledge_base import KBArticleCreate, KBArticleUpdate


async def get_articles(
    db: AsyncSession,
    *,
    category: str | None = None,
    only_active: bool = True,
    skip: int = 0,
    limit: int = 50,
) -> list[KnowledgeBaseArticle]:
    query = select(KnowledgeBaseArticle).order_by(
        KnowledgeBaseArticle.created_at.desc()
    )
    if only_active:
        query = query.where(KnowledgeBaseArticle.is_active.is_(True))
    if category:
        query = query.where(KnowledgeBaseArticle.category == category)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_article_by_id(
    db: AsyncSession, article_id: int
) -> KnowledgeBaseArticle | None:
    return await db.get(KnowledgeBaseArticle, article_id)


async def create_article(
    db: AsyncSession, data: KBArticleCreate
) -> KnowledgeBaseArticle:
    article = KnowledgeBaseArticle(**data.model_dump())
    db.add(article)
    await db.flush()
    await db.refresh(article)
    return article


async def update_article(
    db: AsyncSession, article_id: int, data: KBArticleUpdate
) -> KnowledgeBaseArticle | None:
    article = await db.get(KnowledgeBaseArticle, article_id)
    if article is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(article, field, value)
    await db.flush()
    await db.refresh(article)
    return article
