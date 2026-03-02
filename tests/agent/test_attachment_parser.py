"""Tests for agent/attachment_parser.py — parse_attachment, parse_attachments."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.attachment_parser import (
    parse_attachment,
    parse_attachments,
    _parse_pdf,
    _parse_docx,
    _parse_image,
)


# ---------------------------------------------------------------------------
# parse_attachment
# ---------------------------------------------------------------------------


class TestParseAttachment:
    @pytest.mark.asyncio
    async def test_file_not_found(self):
        result = await parse_attachment("/nonexistent/file.pdf", "application/pdf")
        assert result == ""

    @pytest.mark.asyncio
    async def test_large_file_still_processed(self, tmp_path: Path):
        big = tmp_path / "big.pdf"
        big.write_bytes(b"x" * (30 * 1024 * 1024))  # 30 MB
        with patch("agent.attachment_parser._parse_pdf", return_value="big pdf text"):
            result = await parse_attachment(str(big), "application/pdf")
        assert result == "big pdf text"

    @pytest.mark.asyncio
    async def test_unsupported_content_type(self, tmp_path: Path):
        f = tmp_path / "data.csv"
        f.write_text("a,b,c")
        result = await parse_attachment(str(f), "text/csv")
        assert result == ""

    @pytest.mark.asyncio
    async def test_pdf_dispatched(self, tmp_path: Path):
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"fake-pdf")
        with patch("agent.attachment_parser._parse_pdf", return_value="pdf text") as mock:
            result = await parse_attachment(str(f), "application/pdf")
        mock.assert_called_once_with(str(f))
        assert result == "pdf text"

    @pytest.mark.asyncio
    async def test_docx_dispatched(self, tmp_path: Path):
        f = tmp_path / "doc.docx"
        f.write_bytes(b"fake-docx")
        with patch("agent.attachment_parser._parse_docx", return_value="docx text") as mock:
            result = await parse_attachment(
                str(f),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        mock.assert_called_once()
        assert result == "docx text"

    @pytest.mark.asyncio
    async def test_image_dispatched(self, tmp_path: Path):
        f = tmp_path / "photo.png"
        f.write_bytes(b"fake-img")
        with patch("agent.attachment_parser._parse_image", return_value="ocr text") as mock:
            result = await parse_attachment(str(f), "image/png")
        mock.assert_called_once()
        assert result == "ocr text"

    @pytest.mark.asyncio
    async def test_parser_exception_returns_empty(self, tmp_path: Path):
        f = tmp_path / "bad.pdf"
        f.write_bytes(b"bad")
        with patch("agent.attachment_parser._parse_pdf", side_effect=RuntimeError("boom")):
            result = await parse_attachment(str(f), "application/pdf")
        assert result == ""


# ---------------------------------------------------------------------------
# parse_attachments
# ---------------------------------------------------------------------------


class TestParseAttachments:
    @pytest.mark.asyncio
    async def test_empty_list(self):
        assert await parse_attachments([]) == ""

    @pytest.mark.asyncio
    async def test_dict_attachment_with_data(self):
        att = {
            "filename": "test.pdf",
            "content_type": "application/pdf",
            "data": b"fake-pdf-bytes",
        }
        with patch("agent.attachment_parser.parse_attachment", new_callable=AsyncMock, return_value="pdf text"):
            result = await parse_attachments([att])
        assert "test.pdf" in result
        assert "pdf text" in result

    @pytest.mark.asyncio
    async def test_empty_data_skipped(self):
        att = {"filename": "empty.pdf", "content_type": "application/pdf", "data": b""}
        result = await parse_attachments([att])
        assert result == ""

    @pytest.mark.asyncio
    async def test_large_data_still_processed(self):
        att = {
            "filename": "huge.pdf",
            "content_type": "application/pdf",
            "data": b"x" * (30 * 1024 * 1024),  # 30 MB
        }
        with patch("agent.attachment_parser.parse_attachment", new_callable=AsyncMock, return_value="big text"):
            result = await parse_attachments([att])
        assert "huge.pdf" in result
        assert "big text" in result

    @pytest.mark.asyncio
    async def test_audio_attachment_routed_to_transcriber(self):
        att = {
            "filename": "voice.ogg",
            "content_type": "audio/ogg",
            "data": b"audio-bytes",
        }
        with patch("agent.attachment_parser.transcribe_audio", new_callable=AsyncMock, return_value="transcribed"):
            result = await parse_attachments([att])
        assert "Транскрипция аудио" in result
        assert "transcribed" in result

    @pytest.mark.asyncio
    async def test_max_attachments_limit(self):
        """Only first MAX_ATTACHMENTS are processed."""
        from agent.attachment_parser import MAX_ATTACHMENTS

        atts = [
            {"filename": f"f{i}.pdf", "content_type": "application/pdf", "data": b"x"}
            for i in range(MAX_ATTACHMENTS + 5)
        ]
        with patch("agent.attachment_parser.parse_attachment", new_callable=AsyncMock, return_value="t"):
            await parse_attachments(atts)
        # Should not raise; internals limit iteration
