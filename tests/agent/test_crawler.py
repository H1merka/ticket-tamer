"""Tests for agent/crawler.py — testable pure/async helpers."""

from __future__ import annotations

from agent.crawler import _product_card_to_text


class TestProductCardToText:
    def test_full_card(self):
        card = {
            "name": "СЕНСОН-СВ-5023",
            "description": "Стационарный газоанализатор",
            "specifications": {"Каналы": "4", "Масса": "1.5 кг"},
            "files": [
                {"type": "manual", "name": "Руководство.pdf"},
                {"type": "datasheet", "name": "Паспорт.pdf"},
            ],
        }
        text = _product_card_to_text(card)
        assert "Продукт: СЕНСОН-СВ-5023" in text
        assert "Описание: Стационарный газоанализатор" in text
        assert "Характеристики:" in text
        assert "Каналы: 4" in text
        assert "Документы:" in text
        assert "[manual] Руководство.pdf" in text

    def test_empty_card(self):
        text = _product_card_to_text({})
        assert text == ""

    def test_name_only(self):
        text = _product_card_to_text({"name": "ДГС ЭРИС-210"})
        assert text == "Продукт: ДГС ЭРИС-210"

    def test_specs_only(self):
        text = _product_card_to_text({"specifications": {"Масса": "2 кг"}})
        assert "Характеристики:" in text
        assert "Масса: 2 кг" in text

    def test_whitespace_trimmed(self):
        card = {"name": "  Test  ", "description": "  Desc  "}
        text = _product_card_to_text(card)
        assert "Продукт: Test" in text
        assert "Описание: Desc" in text
