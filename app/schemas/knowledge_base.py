from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KBArticleBase(BaseModel):
    category: str
    question: str
    answer: str


class KBArticleCreate(KBArticleBase):
    source_type: str = "official_docs"
    priority: int = 10
    file_path: str | None = None
    url: str | None = None


class KBArticleUpdate(BaseModel):
    category: str | None = None
    question: str | None = None
    answer: str | None = None
    is_active: bool | None = None
    source_type: str | None = None
    priority: int | None = None


class KBArticleRead(KBArticleBase):
    id: int
    is_active: bool
    source_type: str
    priority: int
    expires_at: datetime | None = None
    file_path: str | None = None
    url: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KBChunkRead(BaseModel):
    """Chunk returned from RAG search results."""
    id: int
    content: str
    source_type: str
    priority: int
    score: float = 0.0

    model_config = ConfigDict(from_attributes=True)
