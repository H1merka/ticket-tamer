"""Tests for agent/classifier.py — email classification via LLM."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agent.classifier import (
    PRIORITY_MAP,
    VALID_CATEGORIES,
    VALID_SENTIMENTS,
    ClassificationResult,
    classify_email,
)


# ---------------------------------------------------------------------------
# classify_email — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_email_returns_valid_result():
    """LLM returns a well-formed JSON → correct ClassificationResult."""
    mock_response = {
        "category": "неисправность",
        "sentiment": "негатив",
        "confidence": 0.92,
    }
    with patch("agent.classifier.chat_completion_json", new_callable=AsyncMock, return_value=mock_response):
        result = await classify_email("Прибор не работает", "Датчик ДГС вышел из строя.")

    assert isinstance(result, ClassificationResult)
    assert result.category == "неисправность"
    assert result.sentiment == "негатив"
    assert result.confidence == 0.92
    assert result.priority == "high"  # неисправность → high


@pytest.mark.asyncio
async def test_classify_email_derives_priority_from_category():
    """Priority is derived from PRIORITY_MAP based on category."""
    for category, expected_priority in PRIORITY_MAP.items():
        mock_resp = {"category": category, "sentiment": "нейтраль", "confidence": 0.5}
        with patch("agent.classifier.chat_completion_json", new_callable=AsyncMock, return_value=mock_resp):
            result = await classify_email("Test", "Test body")
        assert result.priority == expected_priority, f"Mismatch for {category}"


@pytest.mark.asyncio
async def test_classify_email_escalates_on_strong_negative():
    """Negative sentiment + high confidence → priority escalated to 'high'."""
    mock_resp = {"category": "калибровка", "sentiment": "негатив", "confidence": 0.90}
    with patch("agent.classifier.chat_completion_json", new_callable=AsyncMock, return_value=mock_resp):
        result = await classify_email("Калибровка", "Ужасный сервис!")

    assert result.priority == "high"
    assert result.sentiment == "негатив"


@pytest.mark.asyncio
async def test_classify_email_no_escalation_on_weak_negative():
    """Negative sentiment + low confidence → no escalation."""
    mock_resp = {"category": "калибровка", "sentiment": "негатив", "confidence": 0.60}
    with patch("agent.classifier.chat_completion_json", new_callable=AsyncMock, return_value=mock_resp):
        result = await classify_email("Калибровка", "Не очень доволен.")

    assert result.priority == "medium"  # калибровка default, not escalated


# ---------------------------------------------------------------------------
# classify_email — validation and fallbacks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_email_unknown_category_defaults_to_other():
    """Unknown category from LLM is normalized to 'прочее'."""
    mock_resp = {"category": "billing", "sentiment": "нейтраль", "confidence": 0.8}
    with patch("agent.classifier.chat_completion_json", new_callable=AsyncMock, return_value=mock_resp):
        result = await classify_email("Billing", "Pay the bill")

    assert result.category == "прочее"


@pytest.mark.asyncio
async def test_classify_email_unknown_sentiment_defaults_to_neutral():
    """Unknown sentiment from LLM is normalized to 'нейтраль'."""
    mock_resp = {"category": "прочее", "sentiment": "angry", "confidence": 0.8}
    with patch("agent.classifier.chat_completion_json", new_callable=AsyncMock, return_value=mock_resp):
        result = await classify_email("Subject", "Body text")

    assert result.sentiment == "нейтраль"


@pytest.mark.asyncio
async def test_classify_email_clamps_confidence():
    """Confidence outside [0, 1] is clamped."""
    mock_resp = {"category": "прочее", "sentiment": "нейтраль", "confidence": 1.5}
    with patch("agent.classifier.chat_completion_json", new_callable=AsyncMock, return_value=mock_resp):
        result = await classify_email("Subject", "Body")

    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_classify_email_negative_confidence_clamped():
    mock_resp = {"category": "прочее", "sentiment": "нейтраль", "confidence": -0.3}
    with patch("agent.classifier.chat_completion_json", new_callable=AsyncMock, return_value=mock_resp):
        result = await classify_email("Subject", "Body")

    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_classify_email_missing_fields_use_defaults():
    """LLM returns empty dict → all fields get safe defaults."""
    with patch("agent.classifier.chat_completion_json", new_callable=AsyncMock, return_value={}):
        result = await classify_email("Subject", "Body")

    assert result.category == "прочее"
    assert result.sentiment == "нейтраль"
    assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# classify_email — error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_email_llm_exception_returns_fallback():
    """If LLM call fails, returns safe default result."""
    with patch(
        "agent.classifier.chat_completion_json",
        new_callable=AsyncMock,
        side_effect=RuntimeError("API timeout"),
    ):
        result = await classify_email("Subject", "Body")

    assert result.category == "прочее"
    assert result.priority == "medium"
    assert result.sentiment == "нейтраль"
    assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------


def test_valid_categories_not_empty():
    assert len(VALID_CATEGORIES) == 5


def test_valid_sentiments_not_empty():
    assert len(VALID_SENTIMENTS) == 3


def test_priority_map_covers_all_categories():
    assert set(PRIORITY_MAP.keys()) == VALID_CATEGORIES
