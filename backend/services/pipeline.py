import asyncio
import logging
from typing import Dict, Any, List
# pyre-ignore[21]
import httpx
# pyre-ignore[21]
from rapidfuzz import fuzz
# pyre-ignore[21]
from .search import (
    search_zlibrary
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

async def perform_parallel_search(metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Executes searches across multiple sources in parallel.
    """
    title = metadata.get("title", "")
    author = metadata.get("author", "")

    logger.info(f"Starting parallel search for: {title} {author}")

    results = await asyncio.gather(
        search_zlibrary(title, author, metadata.get("format", "any")),
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
    Returns a similarity score between 0.0 and 1.0 using rapidfuzz token_sort_ratio.
    This handles misspellings, slightly different wording, and ignores word order.
    """
    if not a or not b:
        return 0.0
    return fuzz.token_sort_ratio(a.lower(), b.lower()) / 100.0


def _author_similarity(a: str, b: str) -> float:
    """
    Returns a similarity score between 0.0 and 1.0 using rapidfuzz token_set_ratio.
    This is great for matching "J.K. Rowling" with "Rowling, J.K." or "Joanne K Rowling".
    """
    if not a or not b:
        return 0.0
    return fuzz.token_set_ratio(a.lower(), b.lower()) / 100.0


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
        if similarity >= 0.85:
            score += 30
            if target_title == res_title:
                score += 15  # Bonus for exact string match
        elif similarity >= 0.65:
            score += 10       # Partial credit for a loose match
        else:
            # Hard penalty: result title shares almost nothing with the query.
            score -= 50
    # ─────────────────────────────────────────────────────────────────────────

    # Author match
    if target_author:
        if res_author:
            author_sim = _author_similarity(target_author, res_author)
            if author_sim >= 0.8:
                score += 25
            elif author_sim >= 0.5:
                score += 5
            else:
                # Severe penalty if the authors are clearly different
                score -= 60
        else:
            # Slight penalty if user asked for an author but result has none
            score -= 10

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
    Triggers if the query was marked fuzzy, OR if the top candidates
    have very close scores (indicating ambiguity).
    """
    if not ranked_results:
        return False

    good_candidates = [r for r in ranked_results if r.get("_score", 0) > 0]

    if len(good_candidates) <= 1:
        return False

    if metadata.get("fuzzy", False):
        return True

    # If not fuzzy, but the top two candidates are very close in score, we should disambiguate
    top_score = good_candidates[0].get("_score", 0)
    runner_up_score = good_candidates[1].get("_score", 0)

    # If the second best is within 15 points of the best, it's ambiguous
    if top_score - runner_up_score <= 15:
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