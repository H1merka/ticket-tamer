import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
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


@router.post("/index")
async def index_document(
    file: UploadFile = File(...),
    source_type: str = Form("official_docs"),
    category: str = Form("general"),
    db: AsyncSession = Depends(get_db),
):
    """Upload and index a document into the knowledge base.

    Accepts PDF, DOCX, TXT files. Chunks them, embeds via RouterAI,
    and stores in kb_chunks with HNSW-indexed vector embeddings.
    """
    from agent.indexer import index_document as _index_doc

    # Validate source_type
    if source_type not in ("official_docs", "support_history"):
        raise HTTPException(status_code=400, detail="source_type must be 'official_docs' or 'support_history'")

    # Save uploaded file to temp
    suffix = Path(file.filename or "doc.txt").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        article_id, chunks_created = await _index_doc(
            db, tmp_path, source_type=source_type, category=category,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if article_id == 0:
        raise HTTPException(status_code=400, detail="No text could be extracted from the file")

    return {
        "article_id": article_id,
        "chunks_created": chunks_created,
        "source_type": source_type,
    }


# ---------------------------------------------------------------------------
# KB Cleanup endpoints
# ---------------------------------------------------------------------------


@router.delete("/cleanup")
async def cleanup_kb(
    dry_run: bool = Query(True),
    max_age_days: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Delete expired support_history chunks.

    Use dry_run=true (default) to preview how many chunks would be removed.
    """
    from app.services.kb_cleanup_service import cleanup_expired_chunks

    deleted = await cleanup_expired_chunks(db, dry_run=dry_run, max_age_days=max_age_days)
    return {"deleted": deleted, "dry_run": dry_run}


@router.patch("/chunks/{chunk_id}/extend")
async def extend_chunk(
    chunk_id: int,
    extend_days: int = Query(90, ge=1),
    db: AsyncSession = Depends(get_db),
):
    """Extend the expires_at of a support_history chunk."""
    from app.services.kb_cleanup_service import extend_chunk_lifetime

    chunk = await extend_chunk_lifetime(db, chunk_id, extend_days=extend_days)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found or not support_history")
    return {
        "id": chunk.id,
        "article_id": chunk.article_id,
        "source_type": chunk.source_type,
        "expires_at": chunk.expires_at.isoformat() if chunk.expires_at else None,
    }
