import os
import re
import json
import httpx # type: ignore
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from bs4 import BeautifulSoup # type: ignore

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
    encoded_query = query_str.replace(' ', '+')

    ANNAS_MIRROR = "https://annas-archive.gl"

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
            )
            page = await context.new_page()

            url = f"{ANNAS_MIRROR}/search?q={encoded_query}"
            try:
                r = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                if r and r.status >= 400:
                    logger.error(f"Anna's Archive returned {r.status}")
                    return results
                resp_text = await page.content()
            except Exception as e:
                logger.error(f"Anna's Archive search request failed: {e}")
                return results
            finally:
                await browser.close()

            soup = BeautifulSoup(resp_text, 'html.parser')
            md5_elements = soup.select('a[href^="/md5/"]')

            md5_list: List[Tuple[str, str, str]] = []
            seen_md5s = set()

            for a in md5_elements:
                href = a.get('href')
                if not href:
                    continue

                md5 = href.split('/')[-1]
                if not md5 or md5 in seen_md5s:
                    continue
                seen_md5s.add(md5)

                item_title = ""
                item_author = ""

                # Try to extract title/author
                title_elem = (
                    a.select_one('h3') or
                    a.select_one('[class*="title"]') or
                    a.select_one('div > div:first-child > div:first-child')
                )
                author_elem = (
                    a.select_one('.italic') or
                    a.select_one('[class*="author"]') or
                    a.select_one('div > div:first-child > div:nth-child(2)')
                )

                if title_elem:
                    item_title = title_elem.get_text(separator=" ", strip=True)
                if author_elem:
                    item_author = author_elem.get_text(separator=" ", strip=True)

                if item_title and not _title_matches(title, item_title):
                    logger.debug(f"Skipping MD5 {md5}: scraped title '{item_title}' doesn't match query title '{title}'")
                    continue

                if not item_title:
                    item_title = title
                if not item_author:
                    item_author = author

                md5_list.append((md5, item_title, item_author))

            # Limit to top 3 unique MD5s
            for idx, (md5, item_title, item_author) in enumerate(md5_list):
                if idx >= 3:
                    break

                # Fetch the MD5 detail page
                md5_url = f"{ANNAS_MIRROR}/md5/{md5}"
                try:
                    md5_resp = await s.get(md5_url, timeout=15.0)
                    if md5_resp.status_code != 200:
                        continue

                    md5_soup = BeautifulSoup(md5_resp.text, 'html.parser')

                    direct_link: Optional[str] = None
                    possible_links: List[str] = []

                    # Look for external mirrors like libgen or IPFS
                    for link in md5_soup.find_all('a'):
                        l_href = link.get('href', '')
                        if l_href == '#' or not l_href:
                            continue

                        l_text = link.text.strip().lower()

                        if 'libgen.li' in l_text and 'ads.php' in l_href:
                            possible_links.append(l_href)
                        elif ('libgen.is' in l_text or 'libgen.rs' in l_text) and 'md5=' in l_href:
                            possible_links.append(l_href)
                        elif 'ipfs' in l_text and l_href.startswith('/ipfs_downloads/'):
                            possible_links.append(f"{ANNAS_MIRROR}{l_href}")
                        elif l_href.startswith('ipfs://'):
                            possible_links.append(l_href)

                    # Sort possible links to prioritize libgen
                    def link_priority(url: str) -> int:
                        if 'libgen' in url:
                            return 0
                        if 'ipfs_downloads' in url:
                            return 1
                        return 2

                    possible_links.sort(key=link_priority)

                    for l_href in possible_links:
                        if 'libgen.li' in l_href:
                            try:
                                lg_resp = await s.get(l_href, timeout=10.0)
                                if lg_resp.status_code == 200:
                                    lg_soup = BeautifulSoup(lg_resp.text, 'html.parser')
                                    dl_links = lg_soup.select('#download a, h2 a, a[href*="get.php"]')
                                    for dl in dl_links:
                                        dl_href = dl.get('href')
                                        if dl_href:
                                            if dl_href.startswith('/'):
                                                parts = l_href.split('/')
                                                base_url = f"{parts[0]}//{parts[2]}"
                                                direct_link = base_url + dl_href
                                            elif not dl_href.startswith('http'):
                                                parts = l_href.split('/')
                                                base_url = f"{parts[0]}//{parts[2]}"
                                                direct_link = base_url + "/" + dl_href
                                            else:
                                                direct_link = dl_href
                                            break
                            except Exception as e:
                                logger.debug(f"Failed to fetch libgen.li from {l_href}: {e}")
                        elif 'libgen.is' in l_href or 'libgen.rs' in l_href:
                            try:
                                lg_resp = await s.get(l_href, timeout=10.0)
                                if lg_resp.status_code == 200:
                                    lg_soup = BeautifulSoup(lg_resp.text, 'html.parser')
                                    dl_links = lg_soup.select('#download a, h2 a')
                                    for dl in dl_links:
                                        dl_href = dl.get('href')
                                        if dl_href:
                                            if dl_href.startswith('/'):
                                                parts = l_href.split('/')
                                                base_url = f"{parts[0]}//{parts[2]}"
                                                direct_link = base_url + dl_href
                                            elif not dl_href.startswith('http'):
                                                parts = l_href.split('/')
                                                base_url = f"{parts[0]}//{parts[2]}"
                                                direct_link = base_url + "/" + dl_href
                                            else:
                                                direct_link = dl_href
                                            break
                            except Exception as e:
                                logger.debug(f"Failed to fetch libgen mirror from {l_href}: {e}")
                        elif l_href.startswith('ipfs://'):
                            cid = l_href.replace('ipfs://', '')
                            direct_link = f"https://ipfs.io/ipfs/{cid}"
                        else:
                            # It's an Anna's Archive IPFS download page, which might have direct links
                            direct_link = l_href

                        if direct_link:
                            break

                    if isinstance(direct_link, str):
                        is_epub = "epub" in direct_link.lower() or "epub" in md5_resp.text.lower()
                        is_pdf = "pdf" in direct_link.lower() or "pdf" in md5_resp.text.lower()

                        # Try to guess extension from the Anna's Archive page if not in URL
                        if not is_epub and not is_pdf:
                            if "epub" in item_title.lower() or "epub" in item_author.lower():
                                is_epub = True
                            else:
                                is_pdf = True

                        results.append({
                            "source": "Anna's Archive",
                            "title": item_title,
                            "author": item_author,
                            "year": "",
                            "pdf_url": direct_link if is_pdf or not is_epub else "",
                            "epub_url": direct_link if is_epub else "",
                            "weight": 4
                        })

                except Exception as e:
                    logger.debug(f"Failed to process MD5 {md5}: {e}")

    except Exception as e:
        logger.error(f"Anna's Archive search failed: {e}")

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
