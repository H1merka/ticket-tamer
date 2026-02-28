"""KB Chunk model — stores document fragments with vector embeddings for RAG."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class KBChunk(Base):
    """A single chunk of a knowledge-base article with a 1024-dim embedding."""

    __tablename__ = "kb_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, default=dict
    )
    embedding = mapped_column(Vector(1024), nullable=True)

    # Source classification
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="official_docs"
    )
    priority: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    article = relationship("KnowledgeBaseArticle", back_populates="chunks")
