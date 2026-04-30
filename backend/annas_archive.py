"""
annas_archive.py  —  Anna's Archive scraper for Grabbertoullie
---------------------------------------------------------------
Drop into your backend/ folder.

CLI test:
    python annas_archive.py "Atomic Habits" --ext pdf --full
    python annas_archive.py "Atomic Habits" --ext epub --full

From your FastAPI agent:
    from annas_archive import find_best_download, search_books, get_book_info

    book = await find_best_download("Atomic Habits", file_type="pdf")
    if book and book["download_url"]:
        download_url = book["download_url"]
"""

from __future__ import annotations

import asyncio
import argparse
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Optional

from playwright.async_api import async_playwright  # pyre-ignore
from bs4 import BeautifulSoup

# ── Constants ─────────────────────────────────────────────────────────────────

BASE_URL = "https://annas-archive.gl"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

SUPPORTED_FORMATS = {"pdf", "epub", "cbr", "cbz"}


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class BookResult:
    title: str
    author: str
    publisher: str
    info: str           # e.g. "✅ English [en] · PDF · 6.2MB · 2018"
    format: str         # pdf | epub | cbr | cbz
    thumbnail: Optional[str]
    link: str           # full URL to /md5/ page
    md5: str


@dataclass
class BookDetail(BookResult):
    mirror_page: Optional[str]   # /slow_download/.../2 full URL
    download_url: Optional[str]  # final direct file URL
    description: Optional[str]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_md5(path: str) -> str:
    return path.rstrip("/").split("/")[-1]


def _detect_format(text: str) -> str:
    t = text.lower()
    for fmt in ("pdf", "cbr", "cbz"):
        if fmt in t:
            return fmt
    return "epub"


def _clean(text: Optional[str]) -> str:
    return (text or "").strip()


# ── Step 1 — Search ───────────────────────────────────────────────────────────

async def search_books(
    query: str,
    file_type: str = "",
    content: str = "",
    sort: str = "",
    enable_filters: bool = True,
) -> list[dict]:
    """
    Search Anna's Archive. Returns list of BookResult dicts.

    Args:
        query:          Book title / author / ISBN
        file_type:      "pdf" | "epub" | "cbr" | "cbz" | "" (any)
        content:        "book" | "magazine" | "" (any)
        sort:           "newest" | "oldest" | "largest" | "smallest" | ""
        enable_filters: False = plain search with no filters
    """
    q = query.strip().replace(" ", "+")

    if not enable_filters or not any([content, sort, file_type]):
        url = f"{BASE_URL}/search?q={q}"
    else:
        url = f"{BASE_URL}/search?index=&q={q}&content={content}&ext={file_type}&sort={sort}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=HEADERS["User-Agent"],
            extra_http_headers={"Accept-Language": HEADERS["Accept-Language"]}
        )
        page = await context.new_page()

        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if response and response.status >= 400:
                raise ConnectionError(f"HTTP {response.status} reaching Anna's Archive")
            html = await page.content()
        except Exception as exc:
            raise ConnectionError(f"Error reaching Anna's Archive: {exc}") from exc
        finally:
            await browser.close()

    return _parse_search(html, file_type)


def _parse_search(html: str, file_type: str) -> list[dict]:
    """
    Parse search results page.

    Confirmed HTML structure (from debug output):
    Each result is a row div:
      <div class="flex pt-3 pb-3 border-b ...">
        <a href="/md5/...">          ← cover anchor: has img + data-content divs
          <img src="...">
          <div data-content="Title">   (class: text-violet-900)
          <div data-content="Author">  (class: text-amber-900)
        </a>
        <div class="max-w-full ...">   ← text block div (NOT an anchor)
          <div class="... font-mono">upload/path/file.pdf</div>  ← file path
          <a href="/md5/...">Title text</a>
          <a href="/search?q=Author">Author</a>
          <a href="/search?q=Publisher">Publisher, Year</a>
          <div class="... text-gray-600 ...">Description</div>
          <div class="text-gray-800 ...">✅ English [en] · PDF · 6.2MB · 2018</div>
        </div>
      </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict] = []
    seen: set[str] = set()

    # Each row is a flex div containing a border-b class
    for row in soup.find_all("div", class_=lambda c: c and "border-b" in c and "flex" in c):
        # Find the cover anchor to get href, title, author, thumbnail
        cover_anchor = row.find("a", href=lambda h: h and h.startswith("/md5/"))
        if not cover_anchor:
            continue

        href = cover_anchor["href"]
        if href in seen:
            continue
        seen.add(href)

        # Title and author from data-content attributes
        title_div = cover_anchor.find("div", class_=lambda c: c and "text-violet-900" in c)
        author_div = cover_anchor.find("div", class_=lambda c: c and "text-amber-900" in c)
        title = _clean(title_div.get("data-content") if title_div else "")
        author = _clean(author_div.get("data-content") if author_div else "Unknown")

        img = cover_anchor.find("img")
        thumbnail = img.get("src") if img else None

        if not title:
            continue

        # Text block div (sibling of cover anchor)
        text_block = cover_anchor.find_next_sibling("div")

        info = ""
        publisher = "Unknown"
        description = ""

        if text_block:
            # Info line: "✅ English [en] · PDF · 6.2MB · 2018 · ..."
            # It's in a div with text-gray-800 and font-semibold
            info_div = text_block.find(
                "div",
                class_=lambda c: c and "text-gray-800" in c and "font-semibold" in c
            )
            if info_div:
                info = _clean(info_div.get_text())

            # Publisher: the /search?q= anchor that isn't the author
            pub_anchors = text_block.find_all("a", href=lambda h: h and h.startswith("/search?q="))
            for pa in pub_anchors:
                text = _clean(pa.get_text())
                # Author anchor will match what we already have; publisher is the other one
                if text and text != author and author not in text:
                    publisher = text
                    break

            # Description
            desc_div = text_block.find(
                "div",
                class_=lambda c: c and "text-gray-600" in c
            )
            if desc_div:
                description = _clean(desc_div.get_text())

        # Format detection from info line (most reliable) then file path
        fmt = _detect_format(info)

        # Format filter
        if file_type:
            if file_type.lower() not in info.lower() and file_type != fmt:
                continue
        elif fmt not in SUPPORTED_FORMATS:
            continue

        results.append(asdict(BookResult( # pyre-ignore
            title=title,
            author=author,
            publisher=publisher,
            info=info,
            format=fmt,
            thumbnail=thumbnail,
            link=BASE_URL + href,
            md5=_get_md5(href),
        )))

    return results


# ── Step 2 — Book detail page ─────────────────────────────────────────────────

async def get_book_info(book_url: str) -> dict:  # pyre-ignore
    """
    Fetch a book's /md5/ detail page and return a BookDetail dict.
    Also automatically resolves the mirror page to get the final download URL.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=HEADERS["User-Agent"],
            extra_http_headers={"Accept-Language": HEADERS["Accept-Language"]}
        )
        page = await context.new_page()

        try:
            response = await page.goto(book_url, wait_until="domcontentloaded", timeout=30000)
            if response and response.status >= 400:
                raise ConnectionError(f"HTTP {response.status} reaching Anna's Archive")
            html = await page.content()

            detail = _parse_book_detail(html, book_url)

            # Step 3: follow mirror_page to extract the real download URL
            if detail["mirror_page"]:
                detail["download_url"] = await _resolve_download_url(page, detail["mirror_page"])

            return detail
        except Exception as exc:
            raise ConnectionError(f"Error reaching Anna's Archive: {exc}") from exc
        finally:
            await browser.close()


def _parse_book_detail(html: str, url: str) -> dict:
    """Parse the /md5/ detail page for metadata + mirror link."""
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup

    # Mirror — priority 1: slow_download ending in /2
    mirror_page: Optional[str] = None
    for a in main.find_all("a", href=True):
        h = a["href"]
        if h.startswith("/slow_download") and h.endswith("/2"):
            mirror_page = BASE_URL + h
            break

    # Priority 2: IPFS
    if not mirror_page:
        for a in main.find_all("a", href=True):
            h = a["href"]
            if h.startswith("/ipfs_downloads"):
                mirror_page = BASE_URL + h
                break

    # Metadata
    title = ""
    for cls_combo in (["text-3xl", "font-bold"], ["text-2xl", "font-bold"]):
        tag = main.find("div", class_=lambda c: c and all(x in c for x in cls_combo))
        if tag:
            title = _clean(tag.get_text())
            break

    author_tag = main.find("div", class_=lambda c: c and "italic" in c)
    author = _clean(author_tag.get_text()) if author_tag else "Unknown"

    info_tag = main.find("div", class_=lambda c: c and "text-sm" in c and "text-gray-500" in c)
    info = _clean(info_tag.get_text()) if info_tag else ""

    pub_tag = main.find("div", class_=lambda c: c and "text-md" in c)
    publisher = _clean(pub_tag.get_text()) if pub_tag else "Unknown"

    img = main.find("img")
    thumbnail = img.get("src") if img else None

    desc_tag = main.find("div", class_=lambda c: c and "text-gray-600" in c)
    description = _clean(desc_tag.get_text()) if desc_tag else None

    return asdict(BookDetail( # pyre-ignore
        title=title or "Unknown",
        author=author,
        publisher=publisher,
        info=info,
        format=_detect_format(info or title),
        thumbnail=thumbnail,
        link=url,
        md5=_get_md5(url),
        mirror_page=mirror_page,
        download_url=None,
        description=description,
    ))


# ── Step 3 — Resolve mirror page → actual file URL ───────────────────────────

async def _resolve_download_url(page, mirror_page_url: str) -> Optional[str]:
    """
    Fetch the slow_download page and pull out the direct file URL.
    The page shows: "To download, copy this URL..." followed by the real link.
    """
    try:
        response = await page.goto(mirror_page_url, wait_until="domcontentloaded", timeout=30000)
        if response and response.status >= 400:
            return None
        html = await page.content()
    except Exception:
        return None

    return _extract_download_url(html)


def _extract_download_url(html: str) -> Optional[str]:
    """
    Extract the direct file URL from the slow_download page.
    The real URL is an external http link (not annas-archive) pointing to a file host.
    """
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("http"):
            continue
        if "annas-archive" in href:
            continue
        # Ends with a known file extension
        if any(href.lower().endswith(f".{ext}") for ext in ("pdf", "epub", "cbr", "cbz", "mobi")):
            return href
        # Extension appears mid-URL (e.g. .pdf~/ or .pdf?)
        lower = href.lower()
        if any(f".{ext}" in lower for ext in ("pdf", "epub", "cbr", "cbz")):
            return href

    # Fallback: any long external URL (file hosts use bare IP:port URLs)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and "annas-archive" not in href and len(href) > 60:
            return href

    return None


# ── One-shot convenience ──────────────────────────────────────────────────────

async def find_best_download(query: str, file_type: str = "epub") -> Optional[dict]:
    """
    Full pipeline: search → pick first result → get detail → resolve download URL.
    Returns BookDetail dict with download_url populated, or None.

    Usage in your FastAPI route:
        book = await find_best_download("Atomic Habits", file_type="pdf")
        if book and book["download_url"]:
            return {"url": book["download_url"], "title": book["title"]}
    """
    results = await search_books(query, file_type=file_type)
    if not results:
        return None
    detail = await get_book_info(results[0]["link"])
    return detail if detail.get("download_url") else None


# ── CLI ───────────────────────────────────────────────────────────────────────

async def _cli(query: str, ext: str, full: bool) -> None:
    print(f"\n🔍 Searching Anna's Archive for: '{query}'  (format: {ext or 'any'})\n")

    try:
        results = await search_books(query, file_type=ext)
    except ConnectionError as e:
        print(f"❌ {e}")
        return

    if not results:
        print("❌ No results found.")
        return

    print(f"✅ {len(results)} result(s) found.\n")
    for i, b in enumerate(results[:5], 1): # pyre-ignore
        print(f"  [{i}] {b['title']}")
        print(f"       Author    : {b['author']}")
        print(f"       Publisher : {b['publisher']}")
        print(f"       Format    : {b['format']}  |  {b['info']}")
        print(f"       Link      : {b['link']}\n")

    if full:
        print("📄 Fetching detail + resolving download URL for top result...\n")
        try:
            detail = await get_book_info(results[0]["link"])
        except ConnectionError as e:
            print(f"❌ {e}")
            return

        print(f"  Mirror page  : {detail.get('mirror_page') or 'None'}")

        dl = detail.get("download_url")
        if dl:
            print(f"\n📥 Direct download URL:\n   {dl}\n")
        else:
            print("\n⚠️  Could not resolve direct URL — CAPTCHA may be required.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Anna's Archive scraper")
    parser.add_argument("query", help="Book title / author / ISBN")
    parser.add_argument(
        "--ext", default="epub",
        choices=["epub", "pdf", "cbr", "cbz", ""],
        help="File format filter (default: epub)",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Also fetch detail page and resolve the direct download URL",
    )
    args = parser.parse_args()
    asyncio.run(_cli(args.query, args.ext, args.full))