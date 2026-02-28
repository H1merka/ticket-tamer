from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Ticket(Base):
    """Support ticket created from an incoming email."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email_from: Mapped[str] = mapped_column(String(255), nullable=False)
    email_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # ERIS-specific extracted fields
    fio: Mapped[str | None] = mapped_column(String(255), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    serial_numbers: Mapped[list | None] = mapped_column(JSONB, default=list)
    device_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI processing results
    # category: неисправность | калибровка | запрос_документации | запрос_доступа | прочее
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    # sentiment: позитив | нейтраль | негатив
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    entities: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    # Response
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    kb_article_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("knowledge_base.id"), nullable=True
    )

    # Status: new | processing | responded | needs_review | closed
    status: Mapped[str] = mapped_column(String(30), default="new")
    is_auto: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    kb_article = relationship("KnowledgeBaseArticle", back_populates="tickets")
    email_logs = relationship("EmailLog", back_populates="ticket")
