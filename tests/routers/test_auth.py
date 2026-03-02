"""Tests for app/routers/auth.py — authentication API."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.user import User


def _make_user(**overrides) -> User:
    defaults = dict(
        id=1,
        username="testuser",
        full_name="Test User",
        hashed_password="$2b$12$fakehash",
        role="specialist",
        is_active=True,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    user = MagicMock(spec=User)
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_success(client):
    user = _make_user()
    with (
        patch("app.routers.auth.authenticate_user", new_callable=AsyncMock, return_value=user),
        patch("app.routers.auth.create_access_token", return_value="jwt.token.here"),
    ):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "pass1234"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["access_token"] == "jwt.token.here"
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_credentials(client):
    with patch("app.routers.auth.authenticate_user", new_callable=AsyncMock, return_value=None):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "wrong", "password": "wrong"},
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_validation_error(client):
    """Password too short → 422."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "user", "password": "ab"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_success(client):
    new_user = _make_user(id=2, username="newuser")
    with (
        patch("app.routers.auth.get_user_by_username", new_callable=AsyncMock, return_value=None),
        patch("app.routers.auth.create_user", new_callable=AsyncMock, return_value=new_user),
    ):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"username": "newuser", "password": "pass1234", "full_name": "New User"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"


@pytest.mark.asyncio
async def test_register_duplicate_username(client):
    existing = _make_user()
    with patch("app.routers.auth.get_user_by_username", new_callable=AsyncMock, return_value=existing):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"username": "testuser", "password": "pass1234"},
        )

    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_me_returns_current_user(client, fake_user):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == fake_user.username
