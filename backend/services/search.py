import os
import json
import httpx
import logging
import asyncio
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup # type: ignore

logger = logging.getLogger(__name__)

async def search_open_library(title: str, author: str = "") -> List[Dict[str, Any]]:
    logger.info(f"Searching Open Library for title='{title}', author='{author}'")
    results = []

    # Construct query
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
                # Filter for things that might actually have full text or we can build an archive.org link
                # Open Library items often link to archive.org

                # Check if it has full text availability
                has_fulltext = doc.get("has_fulltext", False)
                ia_ids = doc.get("ia", []) # Internet Archive IDs

                if not ia_ids:
                    continue

                for ia_id in ia_ids[:2]: # Take up to 2 IA IDs per doc
                    # Construct direct PDF/EPUB links from Internet Archive
                    pdf_url = f"https://archive.org/download/{ia_id}/{ia_id}.pdf"
                    epub_url = f"https://archive.org/download/{ia_id}/{ia_id}.epub"

                    results.append({
                        "source": "Open Library",
                        "title": doc.get("title", ""),
                        "author": doc.get("author_name", [""])[0] if doc.get("author_name") else "",
                        "year": str(doc.get("first_publish_year", "")),
                        "pdf_url": pdf_url,
                        "epub_url": epub_url,
                        "weight": 2 # Medium weight
                    })

    except Exception as e:
        logger.error(f"Open Library search failed: {e}")

    return results

async def search_standard_ebooks(title: str) -> List[Dict[str, Any]]:
    logger.info(f"Searching Standard Ebooks for title='{title}'")
    results = []

    # Standard Ebooks uses an OPDS feed that we can search
    # url = f"https://standardebooks.org/opds/all?query={title}"
    # However, standardebooks search through OPDS is sometimes tricky to parse without an XML parser.
    # We can also scrape the regular search page which is often more reliable if OPDS isn't well documented.

    url = f"https://standardebooks.org/ebooks?query={title.replace(' ', '+')}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()

            # Simple parsing using string matching or we'll need bs4.
            # Assuming bs4 is available as it's common. Let's add it to requirements if not.
            soup = BeautifulSoup(resp.text, 'html.parser')

            items = soup.select('ol.ebooks-list li')
            for item in items[:5]: # Top 5
                # Extract title and author
                title_elem = item.select_one('p.title a')
                author_elem = item.select_one('p.author a')

                if not title_elem: continue

                item_title = title_elem.text.strip()
                item_author = author_elem.text.strip() if author_elem else ""

                # The href usually looks like /ebooks/author-name/title-name
                link = title_elem.get('href')
                if not link: continue

                # Standard Ebooks predictable download URLs:
                # https://standardebooks.org/ebooks/author-name/title-name/downloads/author-name_title-name.epub
                # We can just fetch the book page and extract the exact epub link.
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
                        "year": "", # Standard Ebooks are typically public domain / old
                        "pdf_url": "", # They don't typically offer PDF
                        "epub_url": epub_url,
                        "weight": 3 # Highest weight, beautifully formatted
                    })

    except Exception as e:
        logger.error(f"Standard Ebooks search failed: {e}")

    return results

async def search_serper_fallback(query: str, serper_api_key: str) -> List[Dict[str, Any]]:
    logger.info(f"Searching Serper fallback for query='{query}'")
    results = []

    if not serper_api_key or serper_api_key == "your_serper_api_key_here":
        return results

    # We construct a Dork just for the fallback
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

                # We only want direct links in the fallback ideally, but the scorer will penalize non-direct links anyway.
                if link.endswith('.pdf') or link.endswith('.epub'):
                    results.append({
                        "source": "Serper",
                        "title": item.get("title", ""),
                        "author": "",
                        "year": "",
                        "pdf_url": link if link.endswith('.pdf') else "",
                        "epub_url": link if link.endswith('.epub') else "",
                        "weight": 1 # Lowest weight
                    })

    except Exception as e:
        logger.error(f"Serper API error: {e}")

    return results
