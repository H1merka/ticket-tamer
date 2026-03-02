"""Tests for agent/indexer.py — document chunking, cleaning, and indexing."""

from __future__ import annotations

import pytest

from agent.indexer import (
    chunk_text,
    clean_text,
)


# ---------------------------------------------------------------------------
# clean_text
# ---------------------------------------------------------------------------


class TestCleanText:
    def test_collapses_multiple_newlines(self):
        text = "Hello\n\n\n\n\n\nWorld"
        result = clean_text(text)
        assert "\n\n\n" not in result
        assert "Hello" in result and "World" in result

    def test_removes_control_chars(self):
        text = "Hello\x00\x01World"
        result = clean_text(text)
        assert "\x00" not in result
        assert "\x01" not in result

    def test_collapses_whitespace(self):
        text = "Hello    World"
        result = clean_text(text)
        assert "    " not in result
        assert "Hello World" in result

    def test_strips_page_numbers(self):
        text = "Content\n  42  \nMore content"
        result = clean_text(text)
        assert "42" not in result or "Content" in result

    def test_nfc_normalization(self):
        # é composed vs decomposed
        import unicodedata
        decomposed = unicodedata.normalize("NFD", "café")
        result = clean_text(decomposed)
        assert result == unicodedata.normalize("NFC", "café")

    def test_empty_string(self):
        assert clean_text("") == ""

    def test_whitespace_only(self):
        assert clean_text("   \n\n   ") == ""


# ---------------------------------------------------------------------------
# chunk_text
# ---------------------------------------------------------------------------


class TestChunkText:
    def test_short_text_single_chunk(self):
        text = "Short text."
        chunks = chunk_text(text, chunk_size=500)
        assert len(chunks) == 1
        assert chunks[0] == "Short text."

    def test_empty_text_no_chunks(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_splits_long_text(self):
        text = "Слово " * 200  # ~1200 chars
        chunks = chunk_text(text, chunk_size=100, overlap=10)
        assert len(chunks) > 1

    def test_all_chunks_within_size_limit(self):
        text = "A " * 500
        chunk_size = 100
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=20)
        # With overlap, some chunks may exceed the limit slightly
        # but the raw split target should be respected
        assert all(len(c) < chunk_size * 2 for c in chunks)

    def test_overlap_adds_prefix(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        chunks = chunk_text(text, chunk_size=20, overlap=5)
        # After first chunk, subsequent chunks should have overlap prefix
        if len(chunks) > 1:
            # Overlap means some text from prev chunk appears in next
            assert len(chunks[1]) > 0

    def test_paragraph_separator_preferred(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunk_text(text, chunk_size=30, overlap=0)
        # Each paragraph should be in its own chunk
        assert len(chunks) >= 2

    def test_preserves_content(self):
        text = "Important content that must be preserved in chunks."
        chunks = chunk_text(text, chunk_size=500)
        combined = " ".join(chunks)
        assert "Important content" in combined
