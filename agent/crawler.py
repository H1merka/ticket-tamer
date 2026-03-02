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
_INDEXABLE_EXTS = {".pdf", ".doc", ".docx", ".html", ".htm", ".txt", ".xls", ".xlsx"}


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
    """Crawl eriskip.com product catalog and site-wide pages, index into KB.

    Pipeline:
      1. Discover all product URLs via product_parser (handles pagination
         and the correct /ru/product/<slug> URL pattern).
      2. Parse each product page: name, description, specs, file links.
      3. Index product card text as ``official_docs`` (priority=10).
      4. Download & index supported document files (PDF, DOCX, XLS, XLSX, etc.)
         as ``official_docs`` (priority=10), with the file type from
         product_parser's ``classify_file`` used as the KB category.
      5. Crawl additional site sections (about, news, support, FAQ, etc.)
         and index their content.

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

        # ------------------------------------------------------------------
        # Step 5: crawl additional site sections
        # ------------------------------------------------------------------
        logger.info("Crawling additional eriskip.com sections …")
        await _crawl_site_sections(client, db=None, indexed=indexed)

    logger.info("Crawled eriskip.com: indexed %d items total", len(indexed))
    return indexed


# ---------------------------------------------------------------------------
# Additional site sections crawler
# ---------------------------------------------------------------------------

# Pages beyond the product catalog to index
_EXTRA_SECTIONS = [
    "https://eriskip.com/ru/about",
    "https://eriskip.com/ru/news",
    "https://eriskip.com/ru/support",
    "https://eriskip.com/ru/faq",
    "https://eriskip.com/ru/contacts",
    "https://eriskip.com/ru/services",
    "https://eriskip.com/ru/solutions",
    "https://eriskip.com/ru/training",
]


async def _crawl_site_sections(
    client: httpx.AsyncClient,
    db: AsyncSession | None = None,
    indexed: list[str] | None = None,
) -> list[str]:
    """Crawl non-product site sections and index their text content."""
    from agent.indexer import index_text
    from bs4 import BeautifulSoup

    if indexed is None:
        indexed = []

    own_session = db is None
    if own_session:
        db = async_session_factory()
        await db.__aenter__()

    try:
        for section_url in _EXTRA_SECTIONS:
            page_key = f"page:{section_url}"
            if await _already_indexed(db, page_key):
                logger.debug("Section already indexed: %s", section_url)
                continue

            try:
                resp = await client.get(
                    section_url, follow_redirects=True, timeout=30,
                )
                if resp.status_code != 200:
                    logger.warning(
                        "Section %s returned status %d — skipping",
                        section_url, resp.status_code,
                    )
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                # Remove boilerplate
                for tag in soup(
                    ["script", "style", "nav", "footer", "header", "aside"]
                ):
                    tag.decompose()

                text = soup.get_text(separator="\n", strip=True)
                if len(text) < 50:
                    continue

                title = soup.find("h1")
                title_text = title.get_text(strip=True) if title else section_url

                article_id, n_chunks = await index_text(
                    db,
                    text,
                    source_type="official_docs",
                    category="site_content",
                    priority=8,
                    title=title_text,
                )
                if article_id:
                    article = await db.get(KnowledgeBaseArticle, article_id)
                    if article:
                        article.url = page_key
                    indexed.append(page_key)
                    logger.info(
                        "Indexed section '%s' → article=%d, %d chunks",
                        title_text, article_id, n_chunks,
                    )
                await db.commit()

            except Exception:
                logger.exception("Error crawling section %s", section_url)

        # Crawl paginated news/articles if the main page has pagination
        await _crawl_paginated_section(
            client, db,
            base_url="https://eriskip.com/ru/news",
            category="news",
            indexed=indexed,
        )
    finally:
        if own_session:
            await db.__aexit__(None, None, None)

    return indexed


async def _crawl_paginated_section(
    client: httpx.AsyncClient,
    db: AsyncSession,
    base_url: str,
    category: str,
    indexed: list[str],
    max_pages: int = 20,
) -> None:
    """Crawl a section that may have paginated sub-pages (e.g. news)."""
    from agent.indexer import index_text
    from agent.product_parser import _find_next_page
    from bs4 import BeautifulSoup

    current_url: str | None = base_url
    page_num = 0

    while current_url and page_num < max_pages:
        page_num += 1
        try:
            resp = await client.get(
                current_url, follow_redirects=True, timeout=30,
            )
            if resp.status_code != 200:
                break

            soup = BeautifulSoup(resp.text, "html.parser")

            # Find article-like links on the listing page
            article_links: list[str] = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                from urllib.parse import urljoin
                full = urljoin(base_url, href)
                # Heuristic: links that look like individual articles
                if (
                    full.startswith(base_url.rstrip("/"))
                    and full != base_url
                    and not full.endswith("/news")
                    and "page=" not in full
                    and full not in article_links
                ):
                    article_links.append(full)

            # Index each sub-article
            for link in article_links:
                link_key = f"page:{link}"
                if await _already_indexed(db, link_key):
                    continue

                try:
                    art_resp = await client.get(
                        link, follow_redirects=True, timeout=30,
                    )
                    if art_resp.status_code != 200:
                        continue

                    art_soup = BeautifulSoup(art_resp.text, "html.parser")
                    for tag in art_soup(
                        ["script", "style", "nav", "footer", "header", "aside"]
                    ):
                        tag.decompose()

                    text = art_soup.get_text(separator="\n", strip=True)
                    if len(text) < 50:
                        continue

                    title_el = art_soup.find("h1")
                    title_text = (
                        title_el.get_text(strip=True) if title_el else link
                    )

                    article_id, n = await index_text(
                        db, text,
                        source_type="official_docs",
                        category=category,
                        priority=6,
                        title=title_text,
                    )
                    if article_id:
                        article = await db.get(
                            KnowledgeBaseArticle, article_id,
                        )
                        if article:
                            article.url = link_key
                        indexed.append(link_key)
                        logger.info(
                            "Indexed %s article '%s' → %d, %d chunks",
                            category, title_text, article_id, n,
                        )
                    await asyncio.sleep(1.0)
                except Exception:
                    logger.exception("Error indexing %s", link)

            await db.commit()

            # Next page
            next_url = _find_next_page(soup, current_url)
            if next_url and next_url != current_url:
                current_url = next_url
                await asyncio.sleep(1.5)
            else:
                break

        except Exception:
            logger.exception("Error crawling %s page %d", category, page_num)
            break


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
