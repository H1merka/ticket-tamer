"""Tests for app/routers/knowledge_base.py — KB CRUD API."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.knowledge_base import KnowledgeBaseArticle


def _make_article(**overrides) -> KnowledgeBaseArticle:
    defaults = dict(
        id=1,
        category="product_info",
        question="ДГС ЭРИС-210",
        answer="Описание прибора ДГС.",
        is_active=True,
        source_type="official_docs",
        priority=10,
        expires_at=None,
        file_path=None,
        url=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    article = MagicMock(spec=KnowledgeBaseArticle)
    for k, v in defaults.items():
        setattr(article, k, v)
    return article


# ---------------------------------------------------------------------------
# GET /api/v1/kb/
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_articles(client):
    article = _make_article()
    with patch("app.services.kb_service.get_articles", new_callable=AsyncMock, return_value=[article]):
        resp = await client.get("/api/v1/kb/")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["category"] == "product_info"


@pytest.mark.asyncio
async def test_list_articles_with_filter(client):
    with patch("app.services.kb_service.get_articles", new_callable=AsyncMock, return_value=[]):
        resp = await client.get("/api/v1/kb/?category=manual")

    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# GET /api/v1/kb/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_article_found(client):
    article = _make_article(id=5)
    with patch("app.services.kb_service.get_article_by_id", new_callable=AsyncMock, return_value=article):
        resp = await client.get("/api/v1/kb/5")

    assert resp.status_code == 200
    assert resp.json()["id"] == 5


@pytest.mark.asyncio
async def test_get_article_not_found(client):
    with patch("app.services.kb_service.get_article_by_id", new_callable=AsyncMock, return_value=None):
        resp = await client.get("/api/v1/kb/999")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/kb/
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_article(client):
    article = _make_article()
    with patch("app.services.kb_service.create_article", new_callable=AsyncMock, return_value=article):
        resp = await client.post(
            "/api/v1/kb/",
            json={
                "category": "product_info",
                "question": "ДГС ЭРИС-210",
                "answer": "Описание прибора.",
            },
        )

    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# PATCH /api/v1/kb/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_article(client):
    updated = _make_article(is_active=False)
    with patch("app.services.kb_service.update_article", new_callable=AsyncMock, return_value=updated):
        resp = await client.patch(
            "/api/v1/kb/1",
            json={"is_active": False},
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_article_not_found(client):
    with patch("app.services.kb_service.update_article", new_callable=AsyncMock, return_value=None):
        resp = await client.patch("/api/v1/kb/999", json={"category": "test"})

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/kb/cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_kb_dry_run(client):
    with patch(
        "app.services.kb_cleanup_service.cleanup_expired_chunks",
        new_callable=AsyncMock,
        return_value=5,
    ):
        resp = await client.delete("/api/v1/kb/cleanup?dry_run=true")

    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] == 5
    assert data["dry_run"] is True
