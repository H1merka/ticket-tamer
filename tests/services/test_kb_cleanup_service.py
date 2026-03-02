"""Tests for app/services/kb_cleanup_service.py — cleanup & extend lifetime."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.kb_cleanup_service import cleanup_expired_chunks, extend_chunk_lifetime


class TestCleanupExpiredChunks:
    @pytest.mark.asyncio
    async def test_dry_run_returns_count(self):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5

        db = AsyncMock()
        db.execute.return_value = mock_result

        count = await cleanup_expired_chunks(db, dry_run=True)
        assert count == 5
        db.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_actual_delete(self):
        mock_result = MagicMock()
        mock_result.rowcount = 3

        db = AsyncMock()
        db.execute.return_value = mock_result

        count = await cleanup_expired_chunks(db, dry_run=False)
        assert count == 3
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dry_run_zero(self):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0

        db = AsyncMock()
        db.execute.return_value = mock_result

        count = await cleanup_expired_chunks(db, dry_run=True)
        assert count == 0

    @pytest.mark.asyncio
    async def test_max_age_days_param(self):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 2

        db = AsyncMock()
        db.execute.return_value = mock_result

        count = await cleanup_expired_chunks(db, dry_run=True, max_age_days=30)
        assert count == 2


class TestExtendChunkLifetime:
    @pytest.mark.asyncio
    async def test_chunk_not_found(self):
        db = AsyncMock()
        db.get.return_value = None

        result = await extend_chunk_lifetime(db, chunk_id=999)
        assert result is None

    @pytest.mark.asyncio
    async def test_wrong_source_type(self):
        chunk = MagicMock()
        chunk.source_type = "official_docs"

        db = AsyncMock()
        db.get.return_value = chunk

        result = await extend_chunk_lifetime(db, chunk_id=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_extends_successfully(self):
        chunk = MagicMock()
        chunk.source_type = "support_history"
        chunk.id = 1
        chunk.expires_at = datetime.now(timezone.utc) + timedelta(days=10)

        db = AsyncMock()
        db.get.return_value = chunk

        result = await extend_chunk_lifetime(db, chunk_id=1, extend_days=60)
        assert result is not None
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()
