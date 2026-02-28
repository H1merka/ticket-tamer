"""Crawler for eriskip.com — downloads product PDF manuals and indexes them.

Usage:
    Standalone:  python -m agent.crawler
    Scheduled:   APScheduler job (weekly)
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.knowledge_base import KnowledgeBaseArticle

logger = logging.getLogger(__name__)

BASE_URL = "https://eriskip.com"
PRODUCTS_URL = f"{BASE_URL}/ru/products"
DOCS_DIR = Path("docs/eriskip")


async def _fetch_page(client: httpx.AsyncClient, url: str) -> str | None:
    """GET a page and return HTML text, or None on error."""
    try:
        resp = await client.get(url, follow_redirects=True, timeout=30)
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPError as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return None


async def _download_file(client: httpx.AsyncClient, url: str, dest: Path) -> bool:
    """Download a file to *dest*. Returns True on success."""
    try:
        async with client.stream("GET", url, follow_redirects=True, timeout=60) as resp:
            resp.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                async for chunk in resp.aiter_bytes(8192):
                    f.write(chunk)
        return True
    except httpx.HTTPError as exc:
        logger.warning("Failed to download %s: %s", url, exc)
        return False


def _extract_product_links(html: str) -> list[str]:
    """Extract individual product page URLs from the products catalog."""
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        # Product pages typically live under /ru/products/ or /ru/catalog/
        if "/ru/products/" in href or "/ru/catalog/" in href:
            full = urljoin(BASE_URL, href)
            if full not in links:
                links.append(full)
    return links


def _extract_pdf_links(html: str, page_url: str) -> list[str]:
    """Find PDF download links on a product page."""
    soup = BeautifulSoup(html, "html.parser")
    pdfs: list[str] = []
    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        if href.lower().endswith(".pdf"):
            pdfs.append(urljoin(page_url, href))
    return pdfs


async def _already_indexed(db: AsyncSession, url: str) -> bool:
    """Check if a document with this URL is already in the KB."""
    result = await db.execute(
        select(KnowledgeBaseArticle.id).where(KnowledgeBaseArticle.url == url).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def crawl_eriskip() -> list[str]:
    """Crawl eriskip.com product catalog and download + index PDF manuals.

    Returns list of indexed file paths.
    """
    from agent.indexer import index_document

    indexed: list[str] = []
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(
        headers={"User-Agent": "TicketTamer/1.0 (hackathon bot)"},
    ) as client:
        # Step 1: get product catalog
        catalog_html = await _fetch_page(client, PRODUCTS_URL)
        if not catalog_html:
            logger.error("Cannot fetch product catalog at %s", PRODUCTS_URL)
            return indexed

        product_links = _extract_product_links(catalog_html)
        logger.info("Found %d product links on catalog page", len(product_links))

        # Step 2: visit each product page, find PDFs
        pdf_urls: list[str] = []
        for link in product_links:
            page_html = await _fetch_page(client, link)
            if not page_html:
                continue
            for pdf_url in _extract_pdf_links(page_html, link):
                if pdf_url not in pdf_urls:
                    pdf_urls.append(pdf_url)

        logger.info("Found %d unique PDF links across products", len(pdf_urls))

        # Step 3: download & index each PDF
        async with async_session_factory() as db:
            for pdf_url in pdf_urls:
                # Deduplication: skip already-indexed docs
                if await _already_indexed(db, pdf_url):
                    logger.debug("Already indexed: %s", pdf_url)
                    continue

                filename = Path(urlparse(pdf_url).path).name or "manual.pdf"
                dest = DOCS_DIR / filename

                if not await _download_file(client, pdf_url, dest):
                    continue

                try:
                    article_id, chunks = await index_document(
                        db,
                        str(dest),
                        source_type="official_docs",
                        category="general",
                        url=pdf_url,
                    )
                    if article_id:
                        indexed.append(str(dest))
                        logger.info(
                            "Indexed %s → article_id=%d, %d chunks",
                            filename, article_id, chunks,
                        )
                except Exception:
                    logger.exception("Error indexing %s", dest)

            await db.commit()

    logger.info("Crawled eriskip.com: indexed %d documents", len(indexed))
    return indexed


# ---------------------------------------------------------------------------
# CLI entry-point: python -m agent.crawler
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
    result = asyncio.run(crawl_eriskip())
    print(f"Indexed {len(result)} documents: {result}")
