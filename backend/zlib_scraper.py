"""
zlib_scraper.py  —  Z-Library scraper for Grabbertoullie
---------------------------------------------------------------
Drop into your backend/ folder.

CLI test:
    python zlib_scraper.py "Atomic Habits" --ext pdf --full
    python zlib_scraper.py "Atomic Habits" --ext epub --full

From your FastAPI agent:
    from zlib_scraper import find_best_download, search_books, get_book_info

    book = await find_best_download("Atomic Habits", file_type="pdf")
    if book and book["download_url"]:
        download_url = book["download_url"]
"""

from __future__ import annotations

import asyncio
import argparse
from dataclasses import dataclass, asdict
from typing import Optional

from playwright.async_api import async_playwright  # pyre-ignore
from bs4 import BeautifulSoup  # pyre-ignore

# ── Constants ─────────────────────────────────────────────────────────────────

BASE_URLS = [
    "https://z-lib.sk",
    "https://z-library.sk",
    "https://1lib.sk",
]

SUPPORTED_FORMATS = {"pdf", "epub", "cbr", "cbz", "mobi", "azw3"}


# ── Data models ───────────────────────────────────────────────────────────────

@dataclass
class BookResult:
    title: str
    author: str
    publisher: str
    info: str           # e.g. "English · epub · 4.44 MB · 2018"
    format: str         # pdf | epub | cbr | cbz
    thumbnail: Optional[str]
    link: str           # full URL to book detail page
    md5: str            # usually the ID for z-lib


@dataclass
class BookDetail(BookResult):
    mirror_page: Optional[str]   # Not strictly used the same way for z-lib
    download_url: Optional[str]  # final direct file URL
    description: Optional[str]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean(text: Optional[str]) -> str:
    return (text or "").strip()


async def _get_working_base_url(page) -> str:
    """Finds the first working base URL that doesn't timeout."""
    for url in BASE_URLS:
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            if response and response.status < 400:
                 # It might return a 503 for cloudflare, but Playwright will bypass it
                 # Wait a bit to let CF pass
                 try:
                     await page.wait_for_selector("div.input-wrap, input[search]", timeout=10000)
                     return url
                 except Exception:
                     # Maybe wait_for_selector failed, but page is loaded
                     pass
        except Exception:
            continue
    raise ConnectionError("Could not reach any Z-Library mirrors.")


# ── Step 1 — Search ───────────────────────────────────────────────────────────

async def search_books(
    query: str,
    file_type: str = "",
    content: str = "",
    sort: str = "",
    enable_filters: bool = True,
) -> list[dict]:
    """
    Search Z-Library. Returns list of BookResult dicts.
    """
    q = query.strip().replace(" ", "%20")

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            # Let's try to go directly to search
            base_url = BASE_URLS[0]
            success = False
            for url in BASE_URLS:
                search_url = f"{url}/s/{q}"
                try:
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)

                    # wait for z-bookcard, OR check if "No books found"
                    # wait_for_selector will timeout if neither is found
                    try:
                        await page.wait_for_selector("z-bookcard, div.notFoundTitle", timeout=15000)
                    except Exception:
                        pass # proceed to parse HTML anyway, might be empty or CF blocked

                    base_url = url
                    success = True
                    break
                except Exception as e:
                    continue

            if not success:
                raise ConnectionError("Failed to bypass Cloudflare or load search results from mirrors.")

            html = await page.content()
            results = _parse_search(html, base_url, file_type)

        finally:
            await browser.close()

    return results


def _parse_search(html: str, base_url: str, file_type: str) -> list[dict]:
    """Parse search results page."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict] = []

    books = soup.find_all("z-bookcard")
    for book in books:
        attrs = book.attrs

        # Extract attributes from the custom element
        title_slot = book.find("div", attrs={"slot": "title"})
        title = title_slot.get_text(strip=True) if title_slot else attrs.get("title", "Unknown")

        author_slot = book.find("div", attrs={"slot": "author"})
        author = author_slot.get_text(strip=True) if author_slot else attrs.get("author", "Unknown")

        href = attrs.get("href", "")
        if not href:
            continue

        publisher = attrs.get("publisher", "Unknown")
        language = attrs.get("language", "Unknown")
        year = attrs.get("year", "")
        ext = attrs.get("extension", "")
        size = attrs.get("filesize", "")
        book_id = attrs.get("id", "")

        # Info line
        info_parts = [p for p in (language, ext, size, year) if p]
        info = " · ".join(info_parts)

        fmt = ext.lower()

        if file_type and file_type.lower() != fmt:
            continue

        img_tag = book.find("img")
        thumbnail = img_tag.get("data-src") or img_tag.get("src") if img_tag else None

        full_link = f"{base_url}{href}" if href.startswith("/") else href

        results.append(asdict(BookResult( # pyre-ignore
            title=title,
            author=author,
            publisher=publisher,
            info=info,
            format=fmt,
            thumbnail=thumbnail,
            link=full_link,
            md5=book_id,
        )))

    return results


# ── Step 2 — Book detail page ─────────────────────────────────────────────────

async def get_book_info(book_url: str) -> dict:  # pyre-ignore
    """
    Fetch a book's detail page and return a BookDetail dict.
    Automatically grabs the download URL.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            await page.goto(book_url, wait_until="domcontentloaded", timeout=20000)
            try:
                await page.wait_for_selector(".addDownloadedBook", timeout=15000)
            except Exception:
                pass # Proceed anyway

            html = await page.content()
            detail = _parse_book_detail(html, book_url)

            # The download url might be a relative path, let's make it absolute based on the domain
            from urllib.parse import urlparse
            parsed_uri = urlparse(book_url)
            base = f"{parsed_uri.scheme}://{parsed_uri.netloc}"

            if detail["download_url"] and detail["download_url"].startswith("/"):
                detail["download_url"] = base + detail["download_url"]

            return detail
        except Exception as exc:
            raise ConnectionError(f"Cannot reach Z-Library detail page: {exc}") from exc
        finally:
            await browser.close()


def _parse_book_detail(html: str, url: str) -> dict:
    """Parse the detail page for metadata + download link."""
    soup = BeautifulSoup(html, "html.parser")

    title = "Unknown"
    title_tag = soup.find("h1", itemprop="name")
    if title_tag:
        title = _clean(title_tag.get_text())

    author = "Unknown"
    author_tag = soup.find("a", itemprop="author")
    if author_tag:
        author = _clean(author_tag.get_text())

    publisher = "Unknown"
    pub_tag = soup.find("a", href=lambda h: h and "/publisher/" in h)
    if pub_tag:
        publisher = _clean(pub_tag.get_text())

    # Formats usually under "property_value"
    fmt = "Unknown"
    info = ""
    prop_year = soup.find("div", class_="property_year")
    if prop_year:
        val = prop_year.find(class_="property_value")
        if val: info += _clean(val.get_text()) + " "

    desc_tag = soup.find("div", id="bookDescriptionBox")
    description = _clean(desc_tag.get_text()) if desc_tag else None

    img = soup.find("img", class_="cover")
    thumbnail = img.get("src") if img else None

    # Download URL
    download_url = None
    dl_btn = soup.find("a", class_=lambda c: c and "addDownloadedBook" in c)
    if dl_btn:
        download_url = dl_btn.get("href")

    return asdict(BookDetail( # pyre-ignore
        title=title,
        author=author,
        publisher=publisher,
        info=info,
        format=fmt,
        thumbnail=thumbnail,
        link=url,
        md5=url.split("/")[-2] if len(url.split("/")) > 2 else "",
        mirror_page=None,
        download_url=download_url,
        description=description,
    ))


# ── One-shot convenience ──────────────────────────────────────────────────────

async def find_best_download(query: str, file_type: str = "epub") -> Optional[dict]:
    """
    Full pipeline: search → pick first result → get detail → extract download URL.
    """
    results = await search_books(query, file_type=file_type)
    if not results:
        return None
    detail = await get_book_info(results[0]["link"])
    return detail if detail.get("download_url") else None


# ── CLI ───────────────────────────────────────────────────────────────────────

async def _cli(query: str, ext: str, full: bool) -> None:
    print(f"\n🔍 Searching Z-Library for: '{query}'  (format: {ext or 'any'})\n")

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

        dl = detail.get("download_url")
        if dl:
            print(f"\n📥 Direct download URL:\n   {dl}\n")
        else:
            print("\n⚠️  Could not resolve direct URL — CAPTCHA or Login may be required.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Z-Library scraper")
    parser.add_argument("query", help="Book title / author / ISBN")
    parser.add_argument(
        "--ext", default="",
        choices=["epub", "pdf", "cbr", "cbz", "mobi", "azw3", ""],
        help="File format filter",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Also fetch detail page and resolve the direct download URL",
    )
    args = parser.parse_args()
    asyncio.run(_cli(args.query, args.ext, args.full))
