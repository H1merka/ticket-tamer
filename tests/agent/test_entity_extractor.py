"""Tests for agent/entity_extractor.py — NER via LLM JSON-mode."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agent.entity_extractor import (
    _dedupe_serials,
    _validate_fio,
    _validate_phone,
    extract_entities,
)


# ---------------------------------------------------------------------------
# _validate_phone
# ---------------------------------------------------------------------------


class TestValidatePhone:
    def test_canonical_format_accepted(self):
        assert _validate_phone("+7 (342) 561-12-52") == "+7 (342) 561-12-52"

    def test_none_returns_none(self):
        assert _validate_phone(None) is None

    def test_empty_string_returns_none(self):
        assert _validate_phone("") is None

    def test_normalizes_11_digit_starting_with_8(self):
        result = _validate_phone("83425611252")
        assert result == "+7 (342) 561-12-52"

    def test_normalizes_11_digit_starting_with_7(self):
        result = _validate_phone("73425611252")
        assert result == "+7 (342) 561-12-52"

    def test_strips_non_digit_and_normalizes(self):
        result = _validate_phone("+7-342-561-12-52")
        assert result == "+7 (342) 561-12-52"

    def test_short_number_returned_as_is(self):
        result = _validate_phone("12345")
        assert result == "12345"


# ---------------------------------------------------------------------------
# _validate_fio
# ---------------------------------------------------------------------------


class TestValidateFio:
    def test_full_name_accepted(self):
        assert _validate_fio("Иванов Иван Иванович") == "Иванов Иван Иванович"

    def test_two_words_accepted(self):
        assert _validate_fio("Иванов Иван") == "Иванов Иван"

    def test_single_word_rejected(self):
        assert _validate_fio("Иванов") is None

    def test_none_returns_none(self):
        assert _validate_fio(None) is None

    def test_empty_string_returns_none(self):
        assert _validate_fio("") is None

    def test_strips_whitespace(self):
        assert _validate_fio("  Иванов Иван  ") == "Иванов Иван"


# ---------------------------------------------------------------------------
# _dedupe_serials
# ---------------------------------------------------------------------------


class TestDedupeSerials:
    def test_removes_duplicates(self):
        result = _dedupe_serials(["abc", "ABC", "def"])
        assert result == ["ABC", "DEF"]

    def test_uppercases_serials(self):
        result = _dedupe_serials(["sn-001"])
        assert result == ["SN-001"]

    def test_none_returns_empty(self):
        assert _dedupe_serials(None) == []

    def test_empty_list_returns_empty(self):
        assert _dedupe_serials([]) == []

    def test_strips_whitespace(self):
        result = _dedupe_serials(["  aaa  ", "bbb"])
        assert result == ["AAA", "BBB"]

    def test_empty_strings_filtered(self):
        result = _dedupe_serials(["", "  ", "abc"])
        assert result == ["ABC"]


# ---------------------------------------------------------------------------
# extract_entities — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_entities_happy_path():
    """LLM returns well-formed JSON → entities are extracted and validated."""
    llm_response = {
        "fio": "Иванов Иван Иванович",
        "organization": "ООО Тест",
        "phone": "83425611252",
        "serial_numbers": ["SN-001", "sn-001", "SN-002"],
        "device_type": "ДГС ЭРИС-210",
        "description": "Прибор показывает ошибку E05",
    }
    with patch("agent.entity_extractor.chat_completion_json", new_callable=AsyncMock, return_value=llm_response):
        result = await extract_entities("Прибор ДГС ЭРИС-210 показывает ошибку E05")

    assert result["fio"] == "Иванов Иван Иванович"
    assert result["organization"] == "ООО Тест"
    assert result["phone"] == "+7 (342) 561-12-52"
    assert result["serial_numbers"] == ["SN-001", "SN-002"]  # deduplicated
    assert result["device_type"] == "ДГС ЭРИС-210"
    assert result["description"] == "Прибор показывает ошибку E05"


@pytest.mark.asyncio
async def test_extract_entities_null_fields():
    """LLM returns null for missing fields → None / empty list."""
    llm_response = {
        "fio": None,
        "organization": None,
        "phone": None,
        "serial_numbers": None,
        "device_type": None,
        "description": None,
    }
    with patch("agent.entity_extractor.chat_completion_json", new_callable=AsyncMock, return_value=llm_response):
        result = await extract_entities("Привет, помогите пожалуйста.")

    assert result["fio"] is None
    assert result["organization"] is None
    assert result["phone"] is None
    assert result["serial_numbers"] == []
    assert result["device_type"] is None
    assert result["description"] is None


# ---------------------------------------------------------------------------
# extract_entities — error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_entities_llm_failure_returns_empty():
    """If LLM call raises, return safe empty dict."""
    with patch(
        "agent.entity_extractor.chat_completion_json",
        new_callable=AsyncMock,
        side_effect=RuntimeError("API error"),
    ):
        result = await extract_entities("Some text")

    assert result["fio"] is None
    assert result["serial_numbers"] == []
    assert result["description"] is None
