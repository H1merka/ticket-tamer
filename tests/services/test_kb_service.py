"""Tests for app/services/kb_service.py — CRUD with mocked async DB session."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.knowledge_base import KBArticleCreate, KBArticleUpdate
from app.services.kb_service import (
    create_article,
    get_article_by_id,
    get_articles,
    update_article,
)


def _mock_article(**overrides):
    defaults = dict(
        id=1,
        category="general",
        question="Q",
        answer="A",
        source_type="official_docs",
        is_active=True,
    )
    defaults.update(overrides)
    return MagicMock(**defaults)


class TestGetArticles:
    @pytest.mark.asyncio
    async def test_returns_list(self):
        articles = [_mock_article(id=1), _mock_article(id=2)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = articles

        db = AsyncMock()
        db.execute.return_value = mock_result

        result = await get_articles(db)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_filter_by_category(self):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        db = AsyncMock()
        db.execute.return_value = mock_result

        await get_articles(db, category="product_info")
        db.execute.assert_awaited_once()


class TestGetArticleById:
    @pytest.mark.asyncio
    async def test_found(self):
        db = AsyncMock()
        db.get.return_value = _mock_article(id=7)
        result = await get_article_by_id(db, 7)
        assert result.id == 7

    @pytest.mark.asyncio
    async def test_not_found(self):
        db = AsyncMock()
        db.get.return_value = None
        result = await get_article_by_id(db, 999)
        assert result is None


class TestCreateArticle:
    @pytest.mark.asyncio
    async def test_creates_and_flushes(self):
        db = AsyncMock()
        db.add = MagicMock()
        data = KBArticleCreate(category="test", question="Q", answer="A")

        await create_article(db, data)
        db.add.assert_called_once()
        db.flush.assert_awaited_once()
        db.refresh.assert_awaited_once()


class TestUpdateArticle:
    @pytest.mark.asyncio
    async def test_updates_fields(self):
        article = _mock_article(id=1)
        db = AsyncMock()
        db.get.return_value = article

        data = KBArticleUpdate(is_active=False)
        await update_article(db, 1, data)
        db.flush.assert_awaited_once()
        db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_not_found(self):
        db = AsyncMock()
        db.get.return_value = None

        data = KBArticleUpdate(answer="Updated")
        result = await update_article(db, 999, data)
        assert result is None
