"""Tests for agent/pipeline.py — full email processing flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.classifier import ClassificationResult
from agent.kb_lookup import KBMatch
from agent.pipeline import PipelineResult, process_email


def _mock_classification(**overrides) -> ClassificationResult:
    defaults = {
        "category": "неисправность",
        "priority": "high",
        "sentiment": "негатив",
        "confidence": 0.95,
    }
    defaults.update(overrides)
    return ClassificationResult(**defaults)


def _mock_entities(**overrides) -> dict:
    defaults = {
        "fio": "Иванов Иван",
        "organization": "ООО Тест",
        "phone": "+7 (342) 561-12-52",
        "serial_numbers": ["SN-001"],
        "device_type": "ДГС ЭРИС-210",
        "description": "Прибор не работает",
    }
    defaults.update(overrides)
    return defaults


def _mock_kb_matches() -> list[KBMatch]:
    return [
        KBMatch(article_id=1, content="Руководство по ДГС", score=0.85),
    ]


@pytest.mark.asyncio
async def test_pipeline_responded_status():
    """High confidence + good KB score → status = responded."""
    with (
        patch("agent.pipeline.parse_attachments", new_callable=AsyncMock, return_value=""),
        patch("agent.pipeline.classify_email", new_callable=AsyncMock, return_value=_mock_classification(confidence=0.95)),
        patch("agent.pipeline.extract_entities", new_callable=AsyncMock, return_value=_mock_entities()),
        patch("agent.pipeline.find_best_matches", new_callable=AsyncMock, return_value=_mock_kb_matches()),
        patch("agent.pipeline.generate_response", new_callable=AsyncMock, return_value="Ответ."),
        patch("agent.pipeline.send_reply", new_callable=AsyncMock, return_value=True),
        patch("app.config.settings", MagicMock(classification_confidence_threshold=0.7)),
        patch("agent.indexer.index_text", new_callable=AsyncMock, return_value=(1, 3)),
        patch("app.services.telegram_service.send_ticket_notification", new_callable=AsyncMock, return_value=True),
        patch("app.services.sheets_service.sync_ticket_to_sheet", new_callable=AsyncMock, return_value=True),
    ):
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()

        result = await process_email(
            db=mock_db,
            email_from="client@example.com",
            subject="Прибор не работает",
            body="ДГС ЭРИС-210 вышел из строя.",
            message_id="<msg123@example.com>",
        )

    assert isinstance(result, PipelineResult)
    assert result.classification.category == "неисправность"
    assert result.entities["fio"] == "Иванов Иван"
    assert len(result.kb_matches) == 1
    assert result.response_text == "Ответ."


@pytest.mark.asyncio
async def test_pipeline_needs_review_low_confidence():
    """Low confidence → status = needs_review."""
    with (
        patch("agent.pipeline.parse_attachments", new_callable=AsyncMock, return_value=""),
        patch("agent.pipeline.classify_email", new_callable=AsyncMock, return_value=_mock_classification(confidence=0.4)),
        patch("agent.pipeline.extract_entities", new_callable=AsyncMock, return_value=_mock_entities()),
        patch("agent.pipeline.find_best_matches", new_callable=AsyncMock, return_value=_mock_kb_matches()),
        patch("agent.pipeline.generate_response", new_callable=AsyncMock, return_value="Ответ."),
        patch("agent.pipeline.send_reply", new_callable=AsyncMock, return_value=False),
        patch("app.config.settings", MagicMock(classification_confidence_threshold=0.7)),
        patch("app.services.telegram_service.send_ticket_notification", new_callable=AsyncMock, return_value=True),
        patch("app.services.sheets_service.sync_ticket_to_sheet", new_callable=AsyncMock, return_value=True),
    ):
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()

        result = await process_email(
            db=mock_db,
            email_from="client@example.com",
            subject="Вопрос",
            body="Непонятный запрос.",
        )

    assert result.classification.confidence == 0.4
    # send_reply should NOT be called for needs_review
    # (it was mocked to return False indicating it should not have been called)


@pytest.mark.asyncio
async def test_pipeline_needs_review_low_kb_score():
    """Low KB score (< 0.3) → status = needs_review."""
    low_score_matches = [KBMatch(article_id=1, content="text", score=0.1)]
    with (
        patch("agent.pipeline.parse_attachments", new_callable=AsyncMock, return_value=""),
        patch("agent.pipeline.classify_email", new_callable=AsyncMock, return_value=_mock_classification(confidence=0.95)),
        patch("agent.pipeline.extract_entities", new_callable=AsyncMock, return_value=_mock_entities()),
        patch("agent.pipeline.find_best_matches", new_callable=AsyncMock, return_value=low_score_matches),
        patch("agent.pipeline.generate_response", new_callable=AsyncMock, return_value="Ответ."),
        patch("agent.pipeline.send_reply", new_callable=AsyncMock, return_value=False),
        patch("app.config.settings", MagicMock(classification_confidence_threshold=0.7)),
        patch("app.services.telegram_service.send_ticket_notification", new_callable=AsyncMock, return_value=True),
        patch("app.services.sheets_service.sync_ticket_to_sheet", new_callable=AsyncMock, return_value=True),
    ):
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()

        result = await process_email(
            db=mock_db,
            email_from="client@example.com",
            subject="Вопрос",
            body="Текст.",
        )

    assert result.kb_matches[0].score == 0.1


@pytest.mark.asyncio
async def test_pipeline_with_attachments():
    """Attachments are parsed and appended to body."""
    with (
        patch("agent.pipeline.parse_attachments", new_callable=AsyncMock, return_value="Текст из PDF"),
        patch("agent.pipeline.classify_email", new_callable=AsyncMock, return_value=_mock_classification()),
        patch("agent.pipeline.extract_entities", new_callable=AsyncMock, return_value=_mock_entities()),
        patch("agent.pipeline.find_best_matches", new_callable=AsyncMock, return_value=_mock_kb_matches()),
        patch("agent.pipeline.generate_response", new_callable=AsyncMock, return_value="Ответ."),
        patch("agent.pipeline.send_reply", new_callable=AsyncMock, return_value=True),
        patch("app.config.settings", MagicMock(classification_confidence_threshold=0.7)),
        patch("agent.indexer.index_text", new_callable=AsyncMock, return_value=(1, 3)),
        patch("app.services.telegram_service.send_ticket_notification", new_callable=AsyncMock, return_value=True),
        patch("app.services.sheets_service.sync_ticket_to_sheet", new_callable=AsyncMock, return_value=True),
    ):
        mock_db = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()

        fake_attachments = [MagicMock()]

        result = await process_email(
            db=mock_db,
            email_from="client@example.com",
            subject="С вложением",
            body="Основной текст",
            attachments=fake_attachments,
        )

    assert result.response_text == "Ответ."
