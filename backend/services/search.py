import os
import re
import json
import httpx # type: ignore
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from bs4 import BeautifulSoup # type: ignore
from zlib_scraper import search_books, get_book_info

logger = logging.getLogger(__name__)

WORD_RE = re.compile(r'\w+')

async def search_open_library(title: str, author: str = "") -> List[Dict[str, Any]]:
    logger.info(f"Searching Open Library for title='{title}', author='{author}'")
    results = []

    query = []
    if title:
        query.append(f"title={title.replace(' ', '+')}")
    if author:
        query.append(f"author={author.replace(' ', '+')}")

    if not query:
        return []

    url = f"https://openlibrary.org/search.json?{'&'.join(query)}&limit=5"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

            for doc in data.get("docs", []):
                has_fulltext = doc.get("has_fulltext", False)
                ia_ids = doc.get("ia", [])

                if not ia_ids:
                    continue

                for ia_id in ia_ids[:2]:
                    pdf_url = f"https://archive.org/download/{ia_id}/{ia_id}.pdf"
                    epub_url = f"https://archive.org/download/{ia_id}/{ia_id}.epub"

                    results.append({
                        "source": "Open Library",
                        "title": doc.get("title", ""),
                        "author": doc.get("author_name", [""])[0] if doc.get("author_name") else "",
                        "year": str(doc.get("first_publish_year", "")),
                        "pdf_url": pdf_url,
                        "epub_url": epub_url,
                        "weight": 2
                    })

    except Exception as e:
        logger.error(f"Open Library search failed: {e}")

    return results

async def search_standard_ebooks(title: str) -> List[Dict[str, Any]]:
    logger.info(f"Searching Standard Ebooks for title='{title}'")
    results = []

    url = f"https://standardebooks.org/ebooks?query={title.replace(' ', '+')}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')
            items = soup.select('ol.ebooks-list li')

            for item in items[:5]:
                title_elem = item.select_one('p.title a')
                author_elem = item.select_one('p.author a')

                if not title_elem: continue

                item_title = title_elem.text.strip()
                item_author = author_elem.text.strip() if author_elem else ""

                link = title_elem.get('href')
                if not link: continue

                book_url = f"https://standardebooks.org{link}"
                book_resp = await client.get(book_url)
                book_resp.raise_for_status()
                book_soup = BeautifulSoup(book_resp.text, 'html.parser')

                epub_link_elem = book_soup.select_one('a[href$=".epub"]')
                if epub_link_elem:
                    epub_url = f"https://standardebooks.org{epub_link_elem.get('href')}"

                    results.append({
                        "source": "Standard Ebooks",
                        "title": item_title,
                        "author": item_author,
                        "year": "",
                        "pdf_url": "",
                        "epub_url": epub_url,
                        "weight": 3
                    })

    except Exception as e:
        logger.error(f"Standard Ebooks search failed: {e}")

    return results

async def search_project_gutenberg(title: str, author: str = "") -> List[Dict[str, Any]]:
    logger.info(f"Searching Project Gutenberg for title='{title}', author='{author}'")
    results = []

    query_parts = []
    if title:
        query_parts.append(title)
    if author:
        query_parts.append(author)

    if not query_parts:
        return results

    query_str = " ".join(query_parts)
    url = f"https://gutendex.com/books?search={query_str.replace(' ', '%20')}"

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

            for book in data.get("results", [])[:5]:
                book_title = book.get("title", "")
                authors = [a.get("name", "") for a in book.get("authors", [])]
                book_author = authors[0] if authors else ""

                formats = book.get("formats", {})

                epub_url = formats.get("application/epub+zip")
                if not epub_url:
                    for key, val in formats.items():
                        if "epub" in key:
                            epub_url = val
                            break

                pdf_url = formats.get("application/pdf", "")

                if epub_url or pdf_url:
                    results.append({
                        "source": "Project Gutenberg",
                        "title": book_title,
                        "author": book_author,
                        "year": "",
                        "pdf_url": pdf_url,
                        "epub_url": epub_url,
                        "weight": 3
                    })

    except Exception as e:
        logger.error(f"Project Gutenberg search failed: {e}")

    return results

async def search_semantic_scholar(title: str, author: str = "") -> List[Dict[str, Any]]:
    logger.info(f"Searching Semantic Scholar for title='{title}', author='{author}'")
    results = []

    query_parts = []
    if title:
        query_parts.append(title)
    if author:
        query_parts.append(author)

    if not query_parts:
        return results

    query_str = " ".join(query_parts)
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={query_str.replace(' ', '%20')}&fields=title,authors,year,isOpenAccess,openAccessPdf&limit=5"

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url)

            if resp.status_code == 429:
                logger.warning("Semantic Scholar rate limit hit, skipping.")
                return results

            resp.raise_for_status()
            data = resp.json()

            for paper in data.get("data", []):
                if paper.get("isOpenAccess"):
                    pdf_info = paper.get("openAccessPdf")
                    pdf_url = pdf_info.get("url") if pdf_info else ""

                    if pdf_url:
                        paper_title = paper.get("title", "")
                        authors = [a.get("name", "") for a in paper.get("authors", [])]
                        paper_author = authors[0] if authors else ""
                        year = str(paper.get("year", ""))

                        results.append({
                            "source": "Semantic Scholar",
                            "title": paper_title,
                            "author": paper_author,
                            "year": year,
                            "pdf_url": pdf_url,
                            "epub_url": "",
                            "weight": 2
                        })

    except Exception as e:
        logger.error(f"Semantic Scholar search failed: {e}")

    return results


def _title_matches(query_title: str, result_title: str) -> bool:
    """
    Returns True if result_title is a plausible match for query_title.
    Requires at least 80% of the query title's words to appear in the result title.
    This prevents e.g. an Italian press-summary PDF from matching "Somadina".
    """
    if not query_title or not result_title:
        return False
    q_words = set(WORD_RE.findall(query_title.lower()))
    r_words = set(WORD_RE.findall(result_title.lower()))
    if not q_words:
        return False
    overlap = q_words & r_words
    return len(overlap) / len(q_words) >= 0.8


async def search_zlibrary(title: str, author: str = "", fmt: str = "any") -> List[Dict[str, Any]]:
    logger.info(f"Searching Z-Library for title='{title}', author='{author}', format='{fmt}'")
    results = []

    query_parts = []
    if title:
        query_parts.append(title)
    if author:
        query_parts.append(author)

    if not query_parts:
        return results

    query_str = " ".join(query_parts)

    file_type = ""
    if fmt and fmt.lower() in ["pdf", "epub"]:
        file_type = fmt.lower()

    try:
        zlib_results = await search_books(query_str, file_type=file_type)

        for item in zlib_results[:3]: # Limit to top 3 to avoid excessive scraping
            link = item.get("link")
            if not link:
                continue

            try:
                info = await get_book_info(link)
                download_url = info.get("download_url")

                if download_url:
                    item_title = item.get("title", "")
                    item_author = item.get("author", "")
                    item_format = item.get("format", "").lower()

                    results.append({
                        "source": "Z-Library",
                        "title": item_title,
                        "author": item_author,
                        "year": "",
                        "pdf_url": download_url if item_format == "pdf" else "",
                        "epub_url": download_url if item_format == "epub" else "",
                        "weight": 4
                    })
            except Exception as e:
                logger.error(f"Failed to get info for Z-Library book '{item.get('title')}': {e}")

    except Exception as e:
        logger.error(f"Z-Library search failed: {e}")

    return results


async def search_serper_fallback(query: str, serper_api_key: str) -> List[Dict[str, Any]]:
    logger.info(f"Searching Serper fallback for query='{query}'")
    results = []

    if not serper_api_key or serper_api_key == "your_serper_api_key_here":
        return results

    dork_query = f'"{query}" (ext:pdf OR ext:epub) -site:pinterest.com'

    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": dork_query})
    headers = {
        'X-API-KEY': serper_api_key,
        'Content-Type': 'application/json'
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, content=payload)
            response.raise_for_status()
            data = response.json()

            for item in data.get("organic", [])[:5]:
                link = item.get("link", "")

                if link.endswith('.pdf') or link.endswith('.epub'):
                    results.append({
                        "source": "Serper",
                        "title": item.get("title", ""),
                        "author": "",
                        "year": "",
                        "pdf_url": link if link.endswith('.pdf') else "",
                        "epub_url": link if link.endswith('.epub') else "",
                        "weight": 1
                    })

    except Exception as e:
        logger.error(f"Serper API error: {e}")

    return results
