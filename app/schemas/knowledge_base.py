from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KBArticleBase(BaseModel):
    category: str
    question: str
    answer: str


class KBArticleCreate(KBArticleBase):
    pass


class KBArticleUpdate(BaseModel):
    category: str | None = None
    question: str | None = None
    answer: str | None = None
    is_active: bool | None = None


class KBArticleRead(KBArticleBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
