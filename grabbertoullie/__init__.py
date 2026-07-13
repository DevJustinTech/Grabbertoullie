"""Grabbertoullie — search multiple book sources in parallel for direct
download links (PDF/EPUB).

Quick start:

    import asyncio
    from grabbertoullie import search

    result = asyncio.run(search("somadina"))
    print(result["file_url"])

Or synchronously:

    from grabbertoullie import search_sync
    print(search_sync("the great gatsby", fmt="epub"))
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from .llm import extract_metadata_from_query
from .pipeline import (
    perform_parallel_search,
    score_and_rank_results,
    format_best_result,
    needs_disambiguation,
    generate_disambiguation_payload,
    validate_url,
)
from .security import SSRFError

__version__ = "0.1.0"

__all__ = [
    "search",
    "search_sync",
    "search_raw",
    "perform_parallel_search",
    "score_and_rank_results",
    "format_best_result",
    "needs_disambiguation",
    "generate_disambiguation_payload",
    "validate_url",
    "SSRFError",
    "__version__",
]


async def _build_metadata(
    query: str,
    fmt: Optional[str],
    author: Optional[str],
    groq_api_key: Optional[str],
) -> Dict[str, Any]:
    # With no Groq key, extract_metadata_from_query falls back to a built-in
    # regex parser — so the library works fully offline of any LLM.
    metadata = await extract_metadata_from_query(query, groq_api_key or "")
    if fmt:
        metadata["format"] = fmt
    if author:
        metadata["author"] = author
    return metadata


async def search(
    query: str,
    fmt: Optional[str] = None,
    author: Optional[str] = None,
    groq_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Search all sources and return the single best match.

    Returns a dict with ``status`` == ``"success"`` (plus ``book_name``,
    ``file_url``, ``extension``, ``source``) or ``status`` == ``"fail"``.
    ``fmt`` is one of ``"pdf"``, ``"epub"``, ``"any"``; if omitted the format
    is inferred from the query (and defaults to ``"any"``).
    """
    metadata = await _build_metadata(query, fmt, author, groq_api_key)
    ranked = score_and_rank_results(await perform_parallel_search(metadata), metadata)
    if not ranked or ranked[0].get("_score", 0) <= 0:
        return {
            "status": "fail",
            "reason": "No results found from any search source.",
            "query": query,
        }
    return format_best_result(ranked[0], metadata.get("format", "any"))


async def search_raw(
    query: str,
    fmt: Optional[str] = None,
    author: Optional[str] = None,
    groq_api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return the full ranked list of candidate results (best first)."""
    metadata = await _build_metadata(query, fmt, author, groq_api_key)
    return score_and_rank_results(await perform_parallel_search(metadata), metadata)


def search_sync(query: str, **kwargs: Any) -> Dict[str, Any]:
    """Synchronous wrapper around :func:`search`."""
    return asyncio.run(search(query, **kwargs))
