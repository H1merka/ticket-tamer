"""Pydantic schemas for authentication endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserLogin(BaseModel):
    """Login request body."""
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=4, max_length=128)


class UserCreate(BaseModel):
    """Registration request body."""
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=4, max_length=128)
    full_name: str = Field("", max_length=255)


class UserRead(BaseModel):
    """Public user representation (no password)."""
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Decoded token payload."""
    username: str | None = None
