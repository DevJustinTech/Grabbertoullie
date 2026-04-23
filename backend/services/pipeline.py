import asyncio
import logging
import re
from typing import Dict, Any, List
# pyre-ignore[21]
import httpx
# pyre-ignore[21]
from .search import (
    search_open_library,
    search_standard_ebooks,
    search_project_gutenberg,
    search_semantic_scholar,
    search_annas_archive,
    search_serper_fallback
)

logger = logging.getLogger(__name__)

async def validate_url(url: str) -> bool:
    """
    Validates a URL to check if it's accessible.
    First uses HEAD, falls back to GET stream if HEAD returns 405.
    """
    if not url:
        return False
    try:
        async with httpx.AsyncClient() as client:
            r = await client.head(url, timeout=5, follow_redirects=True)
            if r.status_code == 405:
                async with client.stream("GET", url, timeout=5, follow_redirects=True) as r_get:
                    return r_get.status_code < 400
            return r.status_code < 400
    except Exception as e:
        logger.debug(f"Validation failed for {url}: {e}")
        return False
    
    # Catch-all return to satisfy Pyre path analysis over async with
    return False

async def perform_parallel_search(metadata: Dict[str, Any], serper_api_key: str) -> List[Dict[str, Any]]:
    """
    Executes searches across multiple sources in parallel.
    """
    title = metadata.get("title", "")
    author = metadata.get("author", "")
    original_query = f"{title} {author}".strip()

    logger.info(f"Starting parallel search for: {original_query}")

    results = await asyncio.gather(
        search_standard_ebooks(title),
        search_open_library(title, author),
        search_project_gutenberg(title, author),
        search_semantic_scholar(title, author),
        search_annas_archive(title, author),
        search_serper_fallback(original_query, serper_api_key),
        return_exceptions=True
    )

    all_results = []
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            logger.error(f"Search source {i} failed with exception: {res}")
        elif isinstance(res, list):
            all_results.extend(res)

    return all_results


def _title_similarity(a: str, b: str) -> float:
    """
    Returns the fraction of words in the shorter title that appear in the longer.
    E.g. query="Somadina", result="Sommario Rassegna Stampa" → 0.0 (no overlap).
    """
    a_words = set(re.findall(r'\w+', a.lower()))
    b_words = set(re.findall(r'\w+', b.lower()))
    if not a_words or not b_words:
        return 0.0
    shorter = a_words if len(a_words) <= len(b_words) else b_words
    longer  = b_words if len(a_words) <= len(b_words) else a_words
    overlap = shorter & longer
    return len(overlap) / len(shorter)


def calculate_score(result: Dict[str, Any], metadata: Dict[str, Any]) -> int:
    """
    Scores a result based on how well it matches the metadata.
    """
    score = 0
    target_title  = metadata.get("title",  "").lower()
    target_author = metadata.get("author", "").lower()
    target_format = metadata.get("format", "pdf").lower()

    res_title  = result.get("title",  "").lower()
    res_author = result.get("author", "").lower()

    # Base weight from the source
    score += result.get("weight", 0) * 10

    # ── Title match (tightened) ───────────────────────────────────────────────
    if target_title:
        similarity = _title_similarity(target_title, res_title)
        if similarity >= 0.8:
            score += 20
            if target_title == res_title:
                score += 10  # Bonus for exact match
        elif similarity >= 0.5:
            score += 5       # Partial credit for a loose match
        else:
            # Hard penalty: result title shares almost nothing with the query.
            # This is what catches the Italian PDF vs "Somadina" case.
            score -= 40
    # ─────────────────────────────────────────────────────────────────────────

    # Author match
    if target_author and target_author in res_author:
        score += 15

    # Format match (crucial)
    has_target_format = False
    if target_format == "epub" and result.get("epub_url"):
        has_target_format = True
    elif target_format == "pdf" and result.get("pdf_url"):
        has_target_format = True
    elif target_format == "any" and (result.get("epub_url") or result.get("pdf_url")):
        has_target_format = True

    if has_target_format:
        score += 30
    else:
        score -= 50

    result["_score"] = score
    return score


def score_and_rank_results(results: List[Dict[str, Any]], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Scores and sorts the results.
    """
    for res in results:
        calculate_score(res, metadata)

    ranked = sorted(results, key=lambda x: x.get("_score", 0), reverse=True)
    return ranked


def format_best_result(best: Dict[str, Any], target_format: str) -> Dict[str, Any]:
    """
    Formats the final winning result for the frontend.
    """
    file_url = best.get("pdf_url") if target_format == "pdf" else best.get("epub_url")
    if target_format == "any":
        file_url = best.get("epub_url") or best.get("pdf_url")
        target_format = "epub" if best.get("epub_url") else "pdf"

    if not file_url:
        file_url = best.get("epub_url") or best.get("pdf_url")
        target_format = "epub" if best.get("epub_url") else "pdf"

    book_name = best.get("title", "Unknown Book")
    if best.get("author"):
        book_name += f" by {best.get('author')}"

    return {
        "status": "success",
        "book_name": book_name,
        "file_url": file_url,
        "extension": target_format,
        "source": best.get("source")
    }


def needs_disambiguation(ranked_results: List[Dict[str, Any]], metadata: Dict[str, Any]) -> bool:
    """
    Determines if we need to ask the user to clarify.
    """
    if not ranked_results:
        return False

    if metadata.get("fuzzy", False):
        good_candidates = [r for r in ranked_results if r.get("_score", 0) > 0]
        if len(good_candidates) > 1:
            return True

    return False


def generate_disambiguation_payload(ranked_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Creates the disambiguation response.
    """
    candidates = []
    seen = set()

    for res in ranked_results:
        if res.get("_score", 0) < 0:
            continue

        title  = res.get("title",  "").strip()
        author = res.get("author", "").strip()
        year   = res.get("year",   "")

        sig = f"{title}|{author}".lower()
        if sig in seen:
            continue
        seen.add(sig)

        display_text = title
        if year:
            display_text += f" ({year})"
        if author:
            display_text += f" - {author}"

        candidates.append({
            "title":      display_text,
            "raw_title":  title,
            "raw_author": author,
            "source":     res.get("source")
        })

        if len(candidates) >= 4:
            break

    return {
        "status":     "disambiguation_required",
        "candidates": candidates
    }