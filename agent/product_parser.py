"""Async parser for eriskip.com product cards.

Extracts product name, description, specifications and file links
from individual product pages and the catalog listing.

Based on parsing logic from the `parsing` branch, converted to async httpx.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://eriskip.com"
PRODUCTS_URL = f"{BASE_URL}/ru/products"


# ---------------------------------------------------------------------------
# File type classification
# ---------------------------------------------------------------------------

def classify_file(url: str) -> str:
    """Classify a document by its URL / filename."""
    url_lower = url.lower()
    if any(kw in url_lower for kw in ("manual", "guide", "руководство", "эксплуатации")):
        return "manual"
    if any(kw in url_lower for kw in ("certificate", "сертификат", "atex", "iecex")):
        return "certificate"
    if any(kw in url_lower for kw in ("drawing", "схема", "diagram", "подключени")):
        return "scheme"
    if any(kw in url_lower for kw in ("firmware", "прошивка", "update")):
        return "firmware"
    if any(kw in url_lower for kw in ("software", "приложени", "application")):
        return "software"
    if any(kw in url_lower for kw in ("datasheet", "паспорт")):
        return "datasheet"
    ext = Path(urlparse(url).path).suffix.lower()
    if ext in (".zip", ".rar"):
        return "archive"
    if ext == ".dwg":
        return "cad_drawing"
    return "other"


# ---------------------------------------------------------------------------
# Product card parser
# ---------------------------------------------------------------------------

_FILE_RE = re.compile(
    r"\.(pdf|zip|rar|exe|doc|docx|xls|xlsx|ppt|pptx|dwg)$", re.IGNORECASE
)


async def parse_product_page(
    client: httpx.AsyncClient,
    product_url: str,
    *,
    retries: int = 3,
) -> dict[str, Any] | None:
    """Fetch and parse a single product page.

    Returns dict with keys: url, name, description, specifications, files
    or *None* on failure.
    """
    html = await _fetch(client, product_url, retries=retries)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    return {
        "url": product_url,
        "name": _extract_name(soup),
        "description": _extract_description(soup),
        "specifications": _extract_specifications(soup),
        "files": _extract_files(soup, product_url),
    }


# ---------------------------------------------------------------------------
# Catalog crawler  (async, with pagination)
# ---------------------------------------------------------------------------

async def collect_product_urls(
    client: httpx.AsyncClient,
    start_url: str = PRODUCTS_URL,
    *,
    delay: float = 1.0,
) -> list[str]:
    """Crawl the product catalog (with pagination) and return all product URLs."""
    product_urls: list[str] = []
    current_url: str | None = start_url
    page_num = 1

    while current_url:
        logger.info("Catalog page %d: %s", page_num, current_url)
        html = await _fetch(client, current_url)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")

        # Collect product links ------------------------------------------
        found: list[str] = []

        # Method 1: links inside <h3> tags
        for h3 in soup.find_all("h3"):
            a = h3.find("a", href=True)
            if a:
                found.append(a["href"])

        # Method 2: elements with "product" in class name
        for a in soup.find_all("a", href=True, class_=re.compile(r"product")):
            if a["href"] not in found:
                found.append(a["href"])

        # Method 3: links containing /product/, /item/, /p/ in href
        if not found:
            for a in soup.find_all("a", href=True):
                href: str = a["href"]
                if "/product/" in href or "/item/" in href or "/p/" in href:
                    found.append(href)

        # De-duplicate & convert to absolute
        for link in set(found):
            full = urljoin(BASE_URL, link)
            if full not in product_urls and not _is_catalog_page(full):
                product_urls.append(full)

        # Pagination ------------------------------------------------------
        next_url = _find_next_page(soup, current_url)
        if next_url and next_url != current_url:
            current_url = next_url
            page_num += 1
            await asyncio.sleep(delay)
        else:
            current_url = None

    logger.info("Collected %d product URLs from catalog", len(product_urls))
    return product_urls


async def crawl_product_cards(
    client: httpx.AsyncClient,
    product_urls: list[str] | None = None,
    *,
    delay: float = 1.5,
) -> list[dict[str, Any]]:
    """Parse all product cards. If *product_urls* is None, collects them first."""
    if product_urls is None:
        product_urls = await collect_product_urls(client, delay=delay)

    products: list[dict[str, Any]] = []
    for idx, url in enumerate(product_urls, 1):
        logger.info("Parsing product %d/%d: %s", idx, len(product_urls), url)
        data = await parse_product_page(client, url)
        if data:
            products.append(data)
        await asyncio.sleep(delay)

    logger.info("Parsed %d product cards", len(products))
    return products


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _fetch(
    client: httpx.AsyncClient,
    url: str,
    *,
    retries: int = 3,
) -> str | None:
    for attempt in range(1, retries + 1):
        try:
            resp = await client.get(url, follow_redirects=True, timeout=30)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as exc:
            logger.warning("Fetch %s attempt %d/%d failed: %s", url, attempt, retries, exc)
            if attempt < retries:
                await asyncio.sleep(2 * attempt)
    logger.error("Could not fetch %s after %d attempts", url, retries)
    return None


def _extract_name(soup: BeautifulSoup) -> str:
    for tag in ("h1", "h2"):
        el = soup.find(tag)
        if el:
            return el.get_text(strip=True)
    title = soup.find("title")
    return title.get_text(strip=True) if title else ""


def _extract_description(soup: BeautifulSoup) -> str:
    # Try dedicated description block
    desc = soup.find("div", class_=re.compile(r"product.?desc|description", re.I))
    if desc:
        return desc.get_text(strip=True, separator="\n")
    # Fallback: first <p>
    p = soup.find("p")
    return p.get_text(strip=True) if p else ""


def _extract_specifications(soup: BeautifulSoup) -> dict[str, str]:
    specs: dict[str, str] = {}

    # Table-based specs
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                val = cells[1].get_text(strip=True)
                if key:
                    specs[key] = val

    # List-based specs  (ul with key: value items)
    for ul in soup.find_all("ul", class_=re.compile(r"spec", re.I)):
        for li in ul.find_all("li"):
            text = li.get_text(strip=True)
            if ":" in text:
                k, v = text.split(":", 1)
                specs[k.strip()] = v.strip()
            else:
                specs[f"item_{len(specs)}"] = text

    return specs


def _extract_files(soup: BeautifulSoup, page_url: str) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for a in soup.find_all("a", href=True):
        href: str = a["href"]
        if _FILE_RE.search(href):
            file_url = urljoin(page_url, href)
            if file_url in seen_urls:
                continue
            seen_urls.add(file_url)
            file_name = Path(urlparse(file_url).path).name or href
            link_text = a.get_text(strip=True) or file_name
            files.append({
                "type": classify_file(file_url),
                "name": link_text,
                "url": file_url,
            })

    return files


def _find_next_page(soup: BeautifulSoup, start_url: str) -> str | None:
    """Detect next page link. Handles several pagination patterns:
    - Text links: "Следующая", "Next", ">", "»"
    - Numeric pagination with current page marker
    - Query-string pagination (?page=N) used by eriskip.com
    """
    # 1. Link with text like "Следующая", "Next", ">", "»"
    nxt = soup.find("a", string=re.compile(r"Следующая|Next|»", re.I))
    if nxt and nxt.get("href"):
        return urljoin(start_url, nxt["href"])

    # 2. Numeric pagination — <div class="pagination"> / <nav> / <ul class="pagination">
    for container in soup.find_all(
        ["div", "nav", "ul"],
        class_=re.compile(r"pagination|pager", re.I),
    ):
        # Find active/current page element
        current = container.find(
            ["span", "li", "a"],
            class_=re.compile(r"active|current", re.I),
        )
        if current:
            try:
                cur_num = int(re.search(r"\d+", current.get_text()).group())
                next_num = cur_num + 1
                # Look for a link with the next number
                next_a = container.find("a", string=re.compile(rf"^\s*{next_num}\s*$"))
                if next_a and next_a.get("href"):
                    return urljoin(start_url, next_a["href"])
            except (ValueError, AttributeError):
                pass

    # 3. Query-string fallback: find ?page=N links and pick the smallest N
    #    greater than current (current determined from start_url or default 1)
    current_page = 1
    page_match = re.search(r"[?&]page=(\d+)", start_url)
    if page_match:
        current_page = int(page_match.group(1))
    candidates: list[tuple[int, str]] = []
    for a in soup.find_all("a", href=re.compile(r"[?&]page=\d+")):
        href = a["href"]
        m = re.search(r"[?&]page=(\d+)", href)
        if m:
            n = int(m.group(1))
            if n > current_page:
                candidates.append((n, urljoin(start_url, href)))
    if candidates:
        candidates.sort()
        return candidates[0][1]

    return None


def _is_catalog_page(url: str) -> bool:
    """Return True if *url* looks like a catalog/listing page, not a product."""
    path = urlparse(url).path.rstrip("/")
    # /ru/products or /ru/products?page=2 — catalog listing
    if path.endswith("/products") or path.endswith("/catalog"):
        return True
    if "/category/" in path or "/page/" in path:
        return True
    # Query-only pagination of catalog (e.g. /ru/products?page=2)
    if re.search(r"/products\?page=\d+", url):
        return True
    return False


# ---------------------------------------------------------------------------
# CLI entry-point:  python -m agent.product_parser
# ---------------------------------------------------------------------------

async def _main() -> None:
    async with httpx.AsyncClient(
        headers={"User-Agent": "TicketTamer/1.0 (hackathon bot)"},
    ) as client:
        products = await crawl_product_cards(client)
        import json
        print(json.dumps(products, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
    asyncio.run(_main())
