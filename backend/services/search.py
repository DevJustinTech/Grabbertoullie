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

async def search_annas_archive(title: str, author: str = "") -> List[Dict[str, Any]]:
    logger.info(f"Searching Anna's Archive for title='{title}', author='{author}'")
    results = []

    query_parts = []
    if title:
        query_parts.append(title)
    if author:
        query_parts.append(author)

    if not query_parts:
        return results

    query_str = " ".join(query_parts)
    url = f"https://annas-archive.gl/search?q={query_str.replace(' ', '+')}"

    # We use curl_cffi to bypass basic anti-bot checks on Anna's Archive
    try:
        from curl_cffi.requests import AsyncSession
        from bs4 import BeautifulSoup

        async with AsyncSession(impersonate="chrome110") as s:
            resp = await s.get(url, timeout=15.0)
            if resp.status_code != 200:
                logger.warning(f"Anna's Archive returned status {resp.status_code}")
                return results

            soup = BeautifulSoup(resp.text, 'html.parser')
            md5_elements = soup.select('a[href^="/md5/"]')

            md5_list = []
            seen_md5s = set()

            for a in md5_elements:
                href = a.get('href')
                if href:
                    md5 = href.split('/')[-1]
                    if md5 and md5 not in seen_md5s:
                        seen_md5s.add(md5)

                        # Try to extract title/author from the element
                        item_title = title
                        item_author = author

                        title_elem = a.select_one('h3')
                        author_elem = a.select_one('.italic')

                        if title_elem and title_elem.text.strip():
                            item_title = title_elem.text.strip()
                        if author_elem and author_elem.text.strip():
                            item_author = author_elem.text.strip()

                        md5_list.append((md5, item_title, item_author))

            # Limit to top 3 unique MD5s to not hammer LibGen
            for md5, item_title, item_author in md5_list[:3]:
                # Now resolve against LibGen
                lg_mirrors = [
                    f"http://libgen.is/search.php?req={md5}&column=md5",
                    f"http://libgen.rs/search.php?req={md5}&column=md5",
                    f"http://libgen.st/search.php?req={md5}&column=md5"
                ]

                direct_link = None
                for lg_url in lg_mirrors:
                    try:
                        lg_resp = await s.get(lg_url, timeout=10.0)
                        if lg_resp.status_code == 200:
                            lg_soup = BeautifulSoup(lg_resp.text, 'html.parser')
                            # Find standard libgen download mirrors
                            mirrors = lg_soup.select('a[title="libgen.li"], a[title="Gen.lib.rus.ec"], a[title="Cloudflare"]')
                            if mirrors:
                                mirror_url = mirrors[0].get('href')

                                # Fetch the actual download page
                                mirror_resp = await s.get(mirror_url, timeout=10.0)
                                mirror_soup = BeautifulSoup(mirror_resp.text, 'html.parser')

                                # Extract GET link
                                dl_links = mirror_soup.select('#download a, h2 a')
                                for dl in dl_links:
                                    dl_href = dl.get('href')
                                    if dl_href:
                                        # If it's a relative link, prepend the base URL
                                        if dl_href.startswith('/'):
                                            base_url = "/".join(mirror_url.split('/')[:3])
                                            direct_link = base_url + dl_href
                                        elif not dl_href.startswith('http'):
                                            base_url = "/".join(mirror_url.split('/')[:3])
                                            direct_link = base_url + "/" + dl_href
                                        else:
                                            direct_link = dl_href
                                        break
                            if direct_link:
                                break # Found a link, stop trying mirrors
                    except Exception as e:
                        logger.debug(f"LibGen mirror {lg_url} failed: {e}")
                        continue

                if direct_link:
                    is_epub = "epub" in direct_link.lower()
                    is_pdf = "pdf" in direct_link.lower()

                    results.append({
                        "source": "Anna's Archive (via LibGen)",
                        "title": item_title,
                        "author": item_author,
                        "year": "",
                        "pdf_url": direct_link if is_pdf or not is_epub else "",
                        "epub_url": direct_link if is_epub else "",
                        "weight": 4 # High weight since it's a direct libgen match
                    })

    except Exception as e:
        logger.error(f"Anna's Archive search failed: {e}")

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
