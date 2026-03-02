"""Tests for agent/response_generator.py — LLM response drafting."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.kb_lookup import KBMatch
from agent.response_generator import (
    _DISCLAIMER,
    _SIGNATURE,
    _build_user_prompt,
    _postprocess,
    generate_response,
)


# ---------------------------------------------------------------------------
# _postprocess
# ---------------------------------------------------------------------------


class TestPostprocess:
    def test_adds_disclaimer_on_low_kb_score(self):
        result = _postprocess("Здравствуйте!", max_kb_score=0.3)
        assert "автоматически" in result

    def test_no_disclaimer_on_high_kb_score(self):
        result = _postprocess("Здравствуйте!", max_kb_score=0.8)
        assert _DISCLAIMER not in result

    def test_ensures_signature(self):
        result = _postprocess("Здравствуйте! Ваш ответ.", max_kb_score=0.9)
        assert "С уважением" in result

    def test_does_not_duplicate_signature(self):
        text = "Ответ.\n\nС уважением,\nСлужба технической поддержки ЭРИС"
        result = _postprocess(text, max_kb_score=0.9)
        assert result.count("С уважением") == 1

    def test_does_not_duplicate_disclaimer(self):
        text = "Ответ сгенерирован автоматически."
        result = _postprocess(text, max_kb_score=0.2)
        assert result.count("автоматически") == 1

    def test_strips_whitespace(self):
        result = _postprocess("   text   ", max_kb_score=0.9)
        assert result.startswith("text")


# ---------------------------------------------------------------------------
# _build_user_prompt
# ---------------------------------------------------------------------------


class TestBuildUserPrompt:
    def test_includes_kb_context(self):
        match = KBMatch(article_id=1, content="KB content here", score=0.9)
        prompt = _build_user_prompt(
            [match],
            email_from="test@test.com",
            subject="Subject",
            body="Body",
            category="прочее",
            sentiment="нейтраль",
        )
        assert "KB content here" in prompt
        assert "0.90" in prompt

    def test_empty_kb_shows_placeholder(self):
        prompt = _build_user_prompt(
            [],
            email_from="test@test.com",
            subject="Subject",
            body="Body",
            category="прочее",
            sentiment="нейтраль",
        )
        assert "не содержит релевантной информации" in prompt

    def test_includes_ticket_metadata(self):
        prompt = _build_user_prompt(
            [],
            email_from="user@company.com",
            subject="Сломан ДГС",
            body="Прибор не работает",
            category="неисправность",
            sentiment="негатив",
            fio="Иванов Иван",
            organization="ООО Тест",
            device_type="ДГС ЭРИС-210",
            serial_numbers=["SN-001", "SN-002"],
        )
        assert "Иванов Иван" in prompt
        assert "ООО Тест" in prompt
        assert "ДГС ЭРИС-210" in prompt
        assert "SN-001, SN-002" in prompt
        assert "user@company.com" in prompt


# ---------------------------------------------------------------------------
# generate_response — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_response_success():
    """LLM returns a valid response → post-processed text returned."""
    mock_choice = MagicMock()
    mock_choice.message.content = "Здравствуйте! Мы решим вашу проблему."
    mock_result = MagicMock()
    mock_result.choices = [mock_choice]

    with patch("agent.response_generator.chat_completion", new_callable=AsyncMock, return_value=mock_result):
        response = await generate_response(
            email_from="test@test.com",
            subject="Проблема",
            category="неисправность",
            entities={"fio": "Иванов Иван", "device_type": "ДГС"},
            kb_matches=[KBMatch(article_id=1, content="решение", score=0.85)],
            body="Прибор не работает",
            sentiment="негатив",
        )

    assert "Здравствуйте" in response
    assert "С уважением" in response


@pytest.mark.asyncio
async def test_generate_response_low_score_adds_disclaimer():
    """Low KB score → disclaimer is appended."""
    mock_choice = MagicMock()
    mock_choice.message.content = "Возможное решение."
    mock_result = MagicMock()
    mock_result.choices = [mock_choice]

    with patch("agent.response_generator.chat_completion", new_callable=AsyncMock, return_value=mock_result):
        response = await generate_response(
            email_from="test@test.com",
            subject="Помощь",
            category="прочее",
            entities={},
            kb_matches=[KBMatch(article_id=1, content="text", score=0.25)],
            body="Вопрос",
        )

    assert "автоматически" in response


# ---------------------------------------------------------------------------
# generate_response — error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_response_llm_failure_returns_fallback():
    """If LLM fails, returns a fallback template."""
    with patch(
        "agent.response_generator.chat_completion",
        new_callable=AsyncMock,
        side_effect=RuntimeError("LLM error"),
    ):
        response = await generate_response(
            email_from="test@test.com",
            subject="Помощь",
            category="прочее",
            entities={},
        )

    assert "Здравствуйте" in response
    assert "support@eriskip.com" in response
    assert "С уважением" in response
    assert "автоматически" in response
