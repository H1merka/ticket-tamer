"""Attachment parser — extract text from PDF, DOCX, image, and audio files.

Supports:
  - PDF (text-based via PyPDF2, scanned via pdf2image + pytesseract)
  - DOCX (paragraphs + tables via python-docx)
  - Images (OCR via Pillow + pytesseract)
  - Audio (OGG, MP3, WAV via Whisper API — optional)
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from agent.audio_transcriber import is_audio, transcribe_audio

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
MAX_ATTACHMENTS = 10
OCR_TIMEOUT = 60  # seconds


@runtime_checkable
class AttachmentLike(Protocol):
    """Protocol for attachment objects (email_service.Attachment or dict)."""
    filename: str
    content_type: str
    data: bytes


async def parse_attachment(filepath: str, content_type: str) -> str:
    """Extract text from an attachment file based on its content type.

    Returns extracted text or empty string on failure.
    """
    path = Path(filepath)
    if not path.exists():
        logger.warning("Attachment file not found: %s", filepath)
        return ""

    size = path.stat().st_size
    if size > MAX_FILE_SIZE:
        logger.warning("Attachment too large (%d bytes): %s", size, filepath)
        return ""

    ct = content_type.lower()

    try:
        if "pdf" in ct:
            return _parse_pdf(filepath)
        elif "wordprocessingml" in ct or "msword" in ct or ct.endswith(".docx"):
            return _parse_docx(filepath)
        elif ct.startswith("image/"):
            return _parse_image(filepath)
        else:
            logger.warning("Unsupported content type '%s' for %s", content_type, filepath)
            return ""
    except Exception as exc:
        logger.error("Failed to parse attachment %s: %s", filepath, exc, exc_info=True)
        return ""


async def parse_attachments(
    attachments: list[Any],
) -> str:
    """Parse multiple attachments and concatenate extracted text.

    Accepts either Attachment dataclass objects (with .filename, .content_type,
    .data attributes) or dicts with keys: path, content_type, filename.

    Returns concatenated text with separators.
    """
    if not attachments:
        return ""

    texts: list[str] = []
    for i, att in enumerate(attachments[:MAX_ATTACHMENTS]):
        # Support both Attachment objects and dicts
        if isinstance(att, AttachmentLike):
            filename = att.filename or f"attachment_{i}"
            content_type = att.content_type or ""
            data = att.data
        elif isinstance(att, dict):
            filename = att.get("filename", f"attachment_{i}")
            content_type = att.get("content_type", "")
            data = att.get("data", b"")
            # Legacy dict path support
            if not data and att.get("path"):
                text = await parse_attachment(att["path"], content_type)
                if text.strip():
                    texts.append(f"\n\n--- Текст из вложения: {filename} ---\n\n{text.strip()}")
                continue
        else:
            # Try attribute access
            filename = getattr(att, "filename", f"attachment_{i}")
            content_type = getattr(att, "content_type", "")
            data = getattr(att, "data", b"")

        if not data:
            continue

        if len(data) > MAX_FILE_SIZE:
            logger.warning("Attachment too large (%d bytes): %s", len(data), filename)
            continue

        # Check for audio first
        if is_audio(content_type, filename):
            text = await transcribe_audio(data, filename)
            if text.strip():
                texts.append(f"\n\n--- Транскрипция аудио: {filename} ---\n\n{text.strip()}")
            continue

        # Write to temp file for file-based parsers
        suffix = Path(filename).suffix or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        try:
            text = await parse_attachment(tmp_path, content_type)
            if text.strip():
                texts.append(f"\n\n--- Текст из вложения: {filename} ---\n\n{text.strip()}")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    return "\n".join(texts)


def _parse_pdf(filepath: str) -> str:
    """Extract text from a PDF file, falling back to OCR for scanned pages."""
    from PyPDF2 import PdfReader

    reader = PdfReader(filepath)
    pages_text: list[str] = []

    for page in reader.pages:
        text = page.extract_text() or ""
        pages_text.append(text)

    full_text = "\n".join(pages_text).strip()

    # If text is too short, PDF is likely scanned — try OCR
    if len(full_text) < 50:
        logger.info("PDF appears scanned, attempting OCR: %s", filepath)
        full_text = _ocr_pdf(filepath)

    return full_text


def _ocr_pdf(filepath: str) -> str:
    """OCR a scanned PDF using pdf2image + pytesseract."""
    try:
        from pdf2image import convert_from_path
        import pytesseract

        images = convert_from_path(filepath)
        texts: list[str] = []
        for img in images:
            text = pytesseract.image_to_string(img, lang="rus+eng")
            texts.append(text)
        return "\n".join(texts).strip()
    except Exception as exc:
        logger.error("OCR failed for PDF %s: %s", filepath, exc)
        return ""


def _parse_docx(filepath: str) -> str:
    """Extract text from a DOCX file (paragraphs + tables)."""
    from docx import Document

    doc = Document(filepath)
    parts: list[str] = []

    # Paragraphs
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)

    # Tables
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    return "\n".join(parts)


def _parse_image(filepath: str) -> str:
    """OCR an image file using Pillow + pytesseract."""
    try:
        from PIL import Image
        import pytesseract

        img = Image.open(filepath)
        return pytesseract.image_to_string(img, lang="rus+eng").strip()
    except Exception as exc:
        logger.error("Image OCR failed for %s: %s", filepath, exc)
        return ""
