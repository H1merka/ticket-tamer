"""Shared fixtures for ticket-tamer test suite.

Provides:
  - Async SQLite in-memory database (no PostgreSQL required)
  - Overridden FastAPI dependency injection (DB session, auth)
  - Authenticated ``AsyncClient`` for API integration tests
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import JSON, String, Text, event
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.dependencies import get_current_user
from app.models.user import User


# ---------------------------------------------------------------------------
# Patch PostgreSQL-specific column types so SQLite can compile them
# ---------------------------------------------------------------------------

def _patch_pg_columns_for_sqlite():
    """Replace JSONB / Vector column types with SQLite-compatible equivalents.

    Must be called before ``Base.metadata.create_all``.
    """
    for table in Base.metadata.tables.values():
        for col in table.columns:
            type_name = type(col.type).__name__
            if type_name in ("JSONB", "JSON"):
                col.type = JSON()
            elif type_name == "Vector":
                # pgvector Vector(1024) → nullable TEXT (not used in SQLite tests)
                col.type = Text()


# ---------------------------------------------------------------------------
# Event loop — use a single loop for the entire session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# In-memory SQLite async engine (no pgvector, no PostgreSQL needed)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def async_engine():
    _patch_pg_columns_for_sqlite()
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Fake authenticated user
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_user() -> User:
    """Return a fake User object for dependency override."""
    user = MagicMock(spec=User)
    user.id = 1
    user.username = "testuser"
    user.full_name = "Test User"
    user.role = "specialist"
    user.is_active = True
    user.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return user


# ---------------------------------------------------------------------------
# FastAPI test client with dependency overrides
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture()
async def client(db_session: AsyncSession, fake_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Provide an httpx.AsyncClient bound to the FastAPI app with
    overridden DB session and auth dependencies.
    """
    # Import app lazily to avoid import-time side effects (scheduler, etc.)
    from app.main import app
    from app.routers.export import _get_export_user

    async def _override_get_db():
        yield db_session

    async def _override_get_current_user():
        return fake_user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[_get_export_user] = _override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
