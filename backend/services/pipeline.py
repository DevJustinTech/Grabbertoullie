import asyncio
import logging
from typing import Dict, Any, List
from .search import search_open_library, search_standard_ebooks, search_serper_fallback

logger = logging.getLogger(__name__)

async def perform_parallel_search(metadata: Dict[str, Any], serper_api_key: str) -> List[Dict[str, Any]]:
    """
    Executes searches across multiple sources in parallel.
    """
    title = metadata.get("title", "")
    author = metadata.get("author", "")

    # We always pass the full query to Serper as a fallback
    original_query = f"{title} {author}".strip()

    logger.info(f"Starting parallel search for: {original_query}")

    # Run all searches concurrently
    results = await asyncio.gather(
        search_standard_ebooks(title),
        search_open_library(title, author),
        search_serper_fallback(original_query, serper_api_key),
        return_exceptions=True
    )

    all_results = []

    # Flatten results and handle exceptions
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            logger.error(f"Search source {i} failed with exception: {res}")
        elif isinstance(res, list):
            all_results.extend(res)

    return all_results

def calculate_score(result: Dict[str, Any], metadata: Dict[str, Any]) -> int:
    """
    Scores a result based on how well it matches the metadata.
    """
    score = 0
    target_title = metadata.get("title", "").lower()
    target_author = metadata.get("author", "").lower()
    target_format = metadata.get("format", "pdf").lower()

    res_title = result.get("title", "").lower()
    res_author = result.get("author", "").lower()

    # Base weight from the source
    score += result.get("weight", 0) * 10

    # Title match
    if target_title and target_title in res_title:
        score += 20
        if target_title == res_title:
            score += 10 # Bonus for exact match

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
        # Huge penalty if it doesn't have the desired format
        score -= 50

    result["_score"] = score
    return score

def score_and_rank_results(results: List[Dict[str, Any]], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Scores and sorts the results.
    """
    for res in results:
        calculate_score(res, metadata)

    # Sort by score descending
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
        # Fallback if preferred format missing but another exists
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
        # We need to make sure we actually have good distinct candidates
        # to show. If we only have 1 good result, don't bother disambiguating.
        good_candidates = [r for r in ranked_results if r.get("_score", 0) > 0]
        if len(good_candidates) > 1:
            return True

    # Also disambiguate if the top scores are very close and not perfectly matched
    # Or if there are multiple very similar items.
    # For now, relying on the 'fuzzy' flag from LLM is the safest bet.
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

        # Create a unique identifier to avoid duplicates in the UI
        title = res.get("title", "").strip()
        author = res.get("author", "").strip()
        year = res.get("year", "")

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
            "title": display_text,
            "raw_title": title,
            "raw_author": author,
            "source": res.get("source")
        })

        if len(candidates) >= 4:
            break

    return {
        "status": "disambiguation_required",
        "candidates": candidates
    }
