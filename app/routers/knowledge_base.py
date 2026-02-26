from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.knowledge_base import KBArticleCreate, KBArticleRead, KBArticleUpdate
from app.services import kb_service

router = APIRouter(prefix="/api/v1/kb", tags=["knowledge_base"])


@router.get("/", response_model=list[KBArticleRead])
async def list_articles(
    category: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    return await kb_service.get_articles(db, category=category, skip=skip, limit=limit)


@router.get("/{article_id}", response_model=KBArticleRead)
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    article = await kb_service.get_article_by_id(db, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.post("/", response_model=KBArticleRead, status_code=201)
async def create_article(data: KBArticleCreate, db: AsyncSession = Depends(get_db)):
    return await kb_service.create_article(db, data)


@router.patch("/{article_id}", response_model=KBArticleRead)
async def update_article(
    article_id: int, data: KBArticleUpdate, db: AsyncSession = Depends(get_db)
):
    article = await kb_service.update_article(db, article_id, data)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article
