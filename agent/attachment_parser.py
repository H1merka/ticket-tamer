"""Attachment parser — extract text from PDF, DOCX, and image files.

Supports:
  - PDF (text-based via PyPDF2, scanned via pdf2image + pytesseract)
  - DOCX (paragraphs + tables via python-docx)
  - Images (OCR via Pillow + pytesseract)
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
MAX_ATTACHMENTS = 10
OCR_TIMEOUT = 60  # seconds


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
    attachments: list[dict],
) -> str:
    """Parse multiple attachments and concatenate extracted text.

    Each attachment dict should have keys: path, content_type, filename.
    Returns concatenated text with separators.
    """
    if not attachments:
        return ""

    texts: list[str] = []
    for i, att in enumerate(attachments[:MAX_ATTACHMENTS]):
        filepath = att.get("path", "")
        content_type = att.get("content_type", "")
        filename = att.get("filename", f"attachment_{i}")

        text = await parse_attachment(filepath, content_type)
        if text.strip():
            texts.append(
                f"\n\n--- Текст из вложения: {filename} ---\n\n{text.strip()}"
            )

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
