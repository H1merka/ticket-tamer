"""Tests for app/services/auth_service.py — password hashing, JWT, and DB auth."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_user,
    decode_access_token,
    get_user_by_username,
    hash_password,
    verify_password,
)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_and_verify(self):
        hashed = hash_password("secret123")
        assert verify_password("secret123", hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("secret123")
        assert verify_password("wrong", hashed) is False

    def test_hash_is_not_plaintext(self):
        hashed = hash_password("secret123")
        assert hashed != "secret123"
        assert "$2b$" in hashed  # bcrypt prefix


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------


class TestJWT:
    def test_create_and_decode_token(self):
        token = create_access_token(data={"sub": "testuser"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "testuser"

    def test_expired_token_returns_none(self):
        token = create_access_token(
            data={"sub": "testuser"},
            expires_delta=timedelta(seconds=-1),
        )
        payload = decode_access_token(token)
        assert payload is None

    def test_invalid_token_returns_none(self):
        payload = decode_access_token("totally.invalid.token")
        assert payload is None

    def test_empty_token_returns_none(self):
        payload = decode_access_token("")
        assert payload is None

    def test_token_contains_exp(self):
        token = create_access_token(data={"sub": "user"})
        payload = decode_access_token(token)
        assert "exp" in payload

    def test_custom_expiry(self):
        token = create_access_token(
            data={"sub": "user"},
            expires_delta=timedelta(hours=1),
        )
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user"


# ---------------------------------------------------------------------------
# DB-touching auth functions
# ---------------------------------------------------------------------------


class TestGetUserByUsername:
    @pytest.mark.asyncio
    async def test_found(self):
        user = MagicMock(username="admin")
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = user

        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await get_user_by_username(db, "admin")
        assert result.username == "admin"

    @pytest.mark.asyncio
    async def test_not_found(self):
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None

        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await get_user_by_username(db, "ghost")
        assert result is None


class TestAuthenticateUser:
    @pytest.mark.asyncio
    async def test_valid_credentials(self):
        hashed = hash_password("secret123")
        user = MagicMock(username="admin", hashed_password=hashed)

        with patch(
            "app.services.auth_service.get_user_by_username",
            new_callable=AsyncMock,
            return_value=user,
        ):
            result = await authenticate_user(AsyncMock(), "admin", "secret123")
        assert result is not None
        assert result.username == "admin"

    @pytest.mark.asyncio
    async def test_wrong_password(self):
        hashed = hash_password("secret123")
        user = MagicMock(username="admin", hashed_password=hashed)

        with patch(
            "app.services.auth_service.get_user_by_username",
            new_callable=AsyncMock,
            return_value=user,
        ):
            result = await authenticate_user(AsyncMock(), "admin", "wrong")
        assert result is None

    @pytest.mark.asyncio
    async def test_user_not_found(self):
        with patch(
            "app.services.auth_service.get_user_by_username",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await authenticate_user(AsyncMock(), "ghost", "pass")
        assert result is None


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_creates_user(self):
        db = AsyncMock()
        db.add = MagicMock()
        result = await create_user(db, "newuser", "pass1234", full_name="Test User")
        db.add.assert_called_once()
        db.flush.assert_awaited_once()
        db.refresh.assert_awaited_once()
