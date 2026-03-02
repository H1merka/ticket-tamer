"""Tests for agent/kb_lookup.py — RAG retrieval pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.kb_lookup import (
    COSINE_THRESHOLD,
    KBMatch,
    _merge_and_boost,
    build_query,
)


# ---------------------------------------------------------------------------
# build_query
# ---------------------------------------------------------------------------


class TestBuildQuery:
    def test_both_fields(self):
        result = build_query("Прибор не работает", "ДГС ЭРИС-210")
        assert "Прибор не работает" in result
        assert "ДГС ЭРИС-210" in result

    def test_description_only(self):
        result = build_query("Ошибка E05", None)
        assert result == "Ошибка E05"

    def test_device_only(self):
        result = build_query(None, "СЕНСОН-СД")
        assert result == "СЕНСОН-СД"

    def test_both_none_returns_empty(self):
        assert build_query(None, None) == ""

    def test_empty_strings(self):
        assert build_query("", "") == ""


# ---------------------------------------------------------------------------
# _merge_and_boost
# ---------------------------------------------------------------------------


class TestMergeAndBoost:
    def test_official_docs_get_boost(self):
        official = [
            KBMatch(article_id=1, content="A", score=0.5, source_type="official_docs"),
        ]
        history = [
            KBMatch(article_id=2, content="B", score=0.5, source_type="support_history"),
        ]
        result = _merge_and_boost(official, history)

        # official_docs × 1.5 = 0.75, support_history × 1.0 = 0.5
        assert result[0].article_id == 1
        assert result[0].score == pytest.approx(0.75)
        assert result[1].article_id == 2
        assert result[1].score == pytest.approx(0.5)

    def test_filters_below_threshold(self):
        official = [
            KBMatch(article_id=1, content="low", score=0.1, source_type="official_docs"),
        ]
        # 0.1 × 1.5 = 0.15 < 0.3 threshold
        result = _merge_and_boost(official, [])
        assert len(result) == 0

    def test_deduplicates_by_article_id(self):
        official = [
            KBMatch(article_id=1, content="A", score=0.8, source_type="official_docs"),
            KBMatch(article_id=1, content="A2", score=0.6, source_type="official_docs"),
        ]
        result = _merge_and_boost(official, [])
        article_ids = [m.article_id for m in result]
        assert article_ids.count(1) == 1

    def test_keeps_none_article_id_individually(self):
        """Chunks without article_id are not deduplicated."""
        matches = [
            KBMatch(article_id=None, content="A", score=0.8, source_type="official_docs"),
            KBMatch(article_id=None, content="B", score=0.7, source_type="official_docs"),
        ]
        result = _merge_and_boost(matches, [])
        assert len(result) == 2

    def test_returns_max_10(self):
        official = [
            KBMatch(article_id=i, content=f"C{i}", score=0.8, source_type="official_docs")
            for i in range(15)
        ]
        result = _merge_and_boost(official, [])
        assert len(result) <= 10

    def test_sorted_descending_by_score(self):
        official = [
            KBMatch(article_id=1, content="low", score=0.3, source_type="official_docs"),
            KBMatch(article_id=2, content="high", score=0.9, source_type="official_docs"),
        ]
        result = _merge_and_boost(official, [])
        assert result[0].score >= result[-1].score


# ---------------------------------------------------------------------------
# find_best_matches — integration (mocked DB + LLM)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_best_matches_empty_query():
    """Empty description and body → returns empty list."""
    from agent.kb_lookup import find_best_matches

    mock_db = AsyncMock()
    result = await find_best_matches(mock_db, description=None, device_type=None, body="")
    assert result == []


@pytest.mark.asyncio
async def test_find_best_matches_with_results():
    """Full pipeline with mocked embed + DB + rerank."""
    from agent.kb_lookup import find_best_matches

    fake_vector = [0.1] * 1024

    mock_db = AsyncMock()
    # Mock DB execute to return empty result sets (no actual pgvector)
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("agent.kb_lookup.embed_text", new_callable=AsyncMock, return_value=fake_vector):
        result = await find_best_matches(
            mock_db,
            description="Прибор не включается",
            device_type="ДГС",
        )

    # With empty DB results, returns empty
    assert result == []
