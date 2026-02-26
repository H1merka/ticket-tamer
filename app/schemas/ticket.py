from datetime import datetime

from pydantic import BaseModel, ConfigDict


# --- Ticket ---


class TicketBase(BaseModel):
    email_from: str
    email_to: str | None = None
    subject: str
    body: str


class TicketCreate(TicketBase):
    """Payload for creating a ticket manually (or from email ingestion)."""
    pass


class TicketUpdate(BaseModel):
    """Payload for updating a ticket (operator edits)."""
    status: str | None = None
    response: str | None = None
    category: str | None = None
    priority: str | None = None


class TicketRead(TicketBase):
    id: int
    category: str | None = None
    priority: str
    sentiment: str | None = None
    confidence: float | None = None
    entities: dict | None = None
    response: str | None = None
    kb_article_id: int | None = None
    status: str
    is_auto: bool
    created_at: datetime
    updated_at: datetime
    responded_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
