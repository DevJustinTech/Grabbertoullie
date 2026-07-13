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
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
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
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
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


# ── Slow-download resolver (headed browser) ──────────────────────────────────

# Anna's Archive protects its "slow download" partner-server pages with a
# browser-verification challenge that a *headless* browser cannot pass, so the
# resolver launches a headed (visible) browser by default. Override with the
# ANNAS_HEADLESS=1 environment variable (not recommended — the challenge will
# usually fail headless).
import os as _os

_ANNAS_HEADLESS = _os.getenv("ANNAS_HEADLESS", "0") == "1"

# Footer/nav links that live on the slow_download page but are NOT the file.
_NON_FILE_HOSTS = ("wikipedia.org", "reddit.com", "t.me", "annas-archive")


async def _extract_download_now(page) -> Optional[str]:
    """Return the direct file URL from a resolved slow_download page, if present."""
    # Preferred: the anchor whose text is "Download now".
    hrefs = await page.eval_on_selector_all(
        "a",
        "els => els.filter(e => /download now/i.test(e.textContent || '')).map(e => e.href)"
    )
    for h in hrefs:
        if h and not any(host in h for host in _NON_FILE_HOSTS):
            return h

    # Fallback: any external link that points straight at a book file.
    all_hrefs = await page.eval_on_selector_all("a[href^='http']", "els => els.map(e => e.href)")
    for h in all_hrefs:
        if any(host in h for host in _NON_FILE_HOSTS):
            continue
        path = h.lower().split("?")[0]
        if any(path.endswith(f".{ext}") for ext in ("pdf", "epub", "mobi", "azw3", "cbr", "cbz")):
            return h
    return None


async def _try_slow_server(page, md5: str, server: int, poll_seconds: int = 30) -> Optional[str]:
    """Open one slow-download partner page and wait for its direct link to appear."""
    target = f"{BASE_URL}/slow_download/{md5}/0/{server}"
    await page.goto(target, wait_until="domcontentloaded", timeout=30000)

    waited = 0.0
    while waited < poll_seconds:
        await page.wait_for_timeout(2500)
        waited += 2.5
        try:
            body = (await page.inner_text("body")).lower()
            # Headless challenge dead-end — bail immediately so we can try elsewhere.
            if "could not verify your browser" in body:
                return None
            link = await _extract_download_now(page)
            if link:
                return link
        except Exception:
            # The countdown page navigates/refreshes to reveal the link, which can
            # destroy the execution context mid-read. Ignore and retry next poll.
            continue
    return None


async def resolve_slow_download(md5: str, servers=(0, 1, 2, 3), headless: Optional[bool] = None) -> Optional[str]:
    """
    Resolve a book's direct download URL from Anna's Archive by driving the
    slow-download flow in a real browser: load the /md5/ page, open a partner
    server, wait for the browser check + countdown to clear, and read out the
    revealed "Download now" link. Tries several partner servers in order.
    """
    if headless is None:
        headless = _ANNAS_HEADLESS

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            user_agent=HEADERS["User-Agent"],
            extra_http_headers={"Accept-Language": HEADERS["Accept-Language"]},
        )
        page = await context.new_page()
        try:
            await page.goto(f"{BASE_URL}/md5/{md5}", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1500)
            for server in servers:
                try:
                    link = await _try_slow_server(page, md5, server)
                    if link:
                        return link
                except Exception as exc:
                    print(f"slow server {server} failed: {exc}")
                    continue
            return None
        finally:
            await browser.close()


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