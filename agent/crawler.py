"""Crawler for eriskip.com — parses product cards, downloads documents,
and indexes everything into the knowledge base.

Delegates URL discovery (with pagination) and HTML parsing to
:mod:`agent.product_parser`, which correctly handles the eriskip.com
catalog structure (/ru/product/<slug> URLs, multi-page listings).

Usage:
    Standalone:  python -m agent.crawler
    Scheduled:   APScheduler job (weekly)
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.knowledge_base import KnowledgeBaseArticle

logger = logging.getLogger(__name__)

DOCS_DIR = Path("docs/eriskip")

# File extensions the indexer can process (load_document supports these)
_INDEXABLE_EXTS = {".pdf", ".doc", ".docx", ".html", ".htm", ".txt"}

# Skip files larger than this (bytes) — large scanned PDFs cause OCR to hang
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _download_file(
    client: httpx.AsyncClient,
    url: str,
    dest: Path,
    *,
    retries: int = 3,
) -> bool:
    """Download a file to *dest*. Returns True on success."""
    for attempt in range(1, retries + 1):
        try:
            async with client.stream(
                "GET", url, follow_redirects=True, timeout=60,
            ) as resp:
                resp.raise_for_status()
                dest.parent.mkdir(parents=True, exist_ok=True)
                with open(dest, "wb") as f:
                    async for chunk in resp.aiter_bytes(8192):
                        f.write(chunk)
            return True
        except httpx.HTTPError as exc:
            logger.warning(
                "Download %s attempt %d/%d failed: %s",
                url, attempt, retries, exc,
            )
            if attempt < retries:
                await asyncio.sleep(2 * attempt)
    return False


async def _already_indexed(db: AsyncSession, url: str) -> bool:
    """Check if a document with this URL is already in the KB."""
    result = await db.execute(
        select(KnowledgeBaseArticle.id)
        .where(KnowledgeBaseArticle.url == url)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


def _product_card_to_text(product: dict) -> str:
    """Convert a parsed product card dict to indexable plain text."""
    parts: list[str] = []

    name = product.get("name", "").strip()
    if name:
        parts.append(f"Продукт: {name}")

    desc = product.get("description", "").strip()
    if desc:
        parts.append(f"Описание: {desc}")

    specs = product.get("specifications", {})
    if specs:
        specs_lines = [f"  {k}: {v}" for k, v in specs.items()]
        parts.append("Характеристики:\n" + "\n".join(specs_lines))

    files = product.get("files", [])
    if files:
        file_lines = [f"  [{f['type']}] {f['name']}" for f in files]
        parts.append("Документы:\n" + "\n".join(file_lines))

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Main crawl pipeline
# ---------------------------------------------------------------------------

async def crawl_eriskip() -> list[str]:
    """Crawl eriskip.com product catalog and index into KB.

    Pipeline:
      1. Discover all product URLs via product_parser (handles pagination
         and the correct /ru/product/<slug> URL pattern).
      2. Parse each product page: name, description, specs, file links.
      3. Index product card text as ``official_docs`` (priority=10).
      4. Download & index supported document files (PDF, DOCX, etc.)
         as ``official_docs`` (priority=10), with the file type from
         product_parser's ``classify_file`` used as the KB category.

    Returns list of indexed items (``card:<url>`` keys + file paths).
    """
    from agent.indexer import index_document, index_text
    from agent.product_parser import crawl_product_cards

    indexed: list[str] = []
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(
        headers={"User-Agent": "TicketTamer/1.0 (hackathon bot)"},
    ) as client:

        # ------------------------------------------------------------------
        # Step 1-2: discover product URLs (with pagination) and parse cards
        # ------------------------------------------------------------------
        logger.info("Starting eriskip.com product catalog crawl …")
        try:
            products = await crawl_product_cards(client, delay=1.0)
        except Exception:
            logger.exception("Failed to crawl product cards")
            return indexed

        logger.info("Parsed %d product cards from catalog", len(products))

        # ------------------------------------------------------------------
        # Step 3-4: index text + documents into KB
        # ------------------------------------------------------------------
        async with async_session_factory() as db:
            for i, product in enumerate(products, 1):
                product_url = product.get("url", "")
                product_name = product.get("name", "unknown")

                # --- 3. Index product card text --------------------------
                card_key = f"card:{product_url}"
                if not await _already_indexed(db, card_key):
                    card_text = _product_card_to_text(product)
                    if card_text and len(card_text) >= 20:
                        try:
                            article_id, n_chunks = await index_text(
                                db,
                                card_text,
                                source_type="official_docs",
                                category="product_info",
                                priority=10,
                                title=product_name,
                            )
                            if article_id:
                                article = await db.get(
                                    KnowledgeBaseArticle, article_id,
                                )
                                if article:
                                    article.url = card_key
                                indexed.append(card_key)
                                logger.info(
                                    "Indexed card '%s' → article=%d, %d chunks",
                                    product_name, article_id, n_chunks,
                                )
                        except Exception:
                            logger.exception(
                                "Error indexing card for %s", product_name,
                            )
                else:
                    logger.debug("Card already indexed: %s", product_name)

                # --- 4. Download & index document files ------------------
                for file_info in product.get("files", []):
                    file_url = file_info.get("url", "")
                    if not file_url:
                        continue

                    # Only process formats the indexer can handle
                    ext = Path(urlparse(file_url).path).suffix.lower()
                    if ext not in _INDEXABLE_EXTS:
                        logger.debug(
                            "Skipping non-indexable file (%s): %s", ext, file_url,
                        )
                        continue

                    if await _already_indexed(db, file_url):
                        logger.debug("Already indexed file: %s", file_url)
                        continue

                    filename = (
                        Path(urlparse(file_url).path).name
                        or f"document{ext}"
                    )
                    dest = DOCS_DIR / filename

                    if not await _download_file(client, file_url, dest):
                        continue

                    # Skip files that are too large (OCR on big scanned
                    # PDFs can hang for hours on a CPU-only container)
                    file_size = dest.stat().st_size
                    if file_size > MAX_FILE_SIZE:
                        logger.warning(
                            "Skipping oversized file '%s' (%.1f MB > %.1f MB limit)",
                            filename,
                            file_size / 1024 / 1024,
                            MAX_FILE_SIZE / 1024 / 1024,
                        )
                        dest.unlink(missing_ok=True)
                        continue

                    try:
                        article_id, n_chunks = await index_document(
                            db,
                            str(dest),
                            source_type="official_docs",
                            category=file_info.get("type", "general"),
                            url=file_url,
                        )
                        if article_id:
                            indexed.append(str(dest))
                            logger.info(
                                "Indexed file '%s' [%s] → article=%d, %d chunks",
                                filename,
                                file_info.get("type", "?"),
                                article_id,
                                n_chunks,
                            )
                    except Exception:
                        logger.exception("Error indexing file %s", dest)

                # Commit after each product so progress is saved
                # even if the process is interrupted later
                await db.commit()
                logger.info(
                    "Committed product %d/%d: %s",
                    i, len(products), product_name,
                )

    logger.info("Crawled eriskip.com: indexed %d items total", len(indexed))
    return indexed


# ---------------------------------------------------------------------------
# CLI entry-point: python -m agent.crawler
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(name)s | %(message)s",
    )
    result = asyncio.run(crawl_eriskip())
    print(f"Indexed {len(result)} items: {result}")
