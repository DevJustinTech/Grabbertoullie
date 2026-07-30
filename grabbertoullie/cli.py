"""Command-line interface for Grabbertoullie.

    grabbertoullie "somadina"
    grabbertoullie "the great gatsby" --format epub
    grabbertoullie "atomic habits" --all
    grabbertoullie "dune" --json

Set GROQ_API_KEY in the environment to enable LLM query parsing; without it a
built-in regex parser is used.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys


def _force_utf8() -> None:
    # Windows terminals default to cp1252 and raise UnicodeEncodeError on the
    # emoji/box characters in the output. Force UTF-8 where the stream supports it.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def _print_result(result: dict) -> None:
    if result.get("status") == "success":
        print(f"\n✅ {result['book_name']}")
        print(f"   Format : {result.get('extension', '')}")
        print(f"   Source : {result.get('source', '')}")
        print(f"   Link   : {result.get('file_url', '')}\n")
    else:
        print(f"\n❌ {result.get('reason', 'No result.')}\n")


def _print_candidates(results: list) -> None:
    if not results:
        print("\n❌ No results found.\n")
        return
    print(f"\n✅ {len(results)} candidate(s), best first:\n")
    for i, r in enumerate(results, 1):
        fmt = "epub" if r.get("epub_url") else ("pdf" if r.get("pdf_url") else "?")
        link = r.get("epub_url") or r.get("pdf_url") or ""
        author = f" — {r['author']}" if r.get("author") else ""
        print(f"  [{i}] ({r.get('_score', 0):>4}) {r.get('title', '')}{author}")
        print(f"       {r.get('source', '')}  |  {fmt}")
        print(f"       {link}\n")


async def _run(args: argparse.Namespace) -> int:
    from . import search, search_raw

    if args.resolve_annas:
        from .annas_archive import resolve_slow_download

        url = await resolve_slow_download(args.resolve_annas)
        print(json.dumps({"download_url": url}))
        return 0 if url else 1

    groq = os.getenv("GROQ_API_KEY")
    if args.all:
        results = await search_raw(
            args.query, fmt=args.format, author=args.author, groq_api_key=groq
        )
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            _print_candidates(results)
        return 0 if results else 1

    result = await search(
        args.query, fmt=args.format, author=args.author, groq_api_key=groq
    )
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_result(result)
    return 0 if result.get("status") == "success" else 1


def main() -> None:
    _force_utf8()
    parser = argparse.ArgumentParser(
        prog="grabbertoullie",
        description="Search multiple book sources for a direct download link.",
    )
    parser.add_argument("query", nargs="?", help="Book title / author / ISBN")
    parser.add_argument(
        "--format", "-f",
        choices=["pdf", "epub", "any"],
        default=None,
        help="Preferred file format (default: inferred from the query)",
    )
    parser.add_argument("--author", "-a", default=None, help="Author name")
    parser.add_argument(
        "--all", action="store_true", help="Show all ranked candidates, not just the best"
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument(
        "--resolve-annas",
        metavar="MD5",
        default=None,
        help=(
            "Resolve an Anna's Archive md5 to its actual file URL by driving the "
            "slow-download flow (opens a visible browser window; can take up to "
            "~2 minutes). Prints {\"download_url\": ...} and ignores query/--all/--format."
        ),
    )
    args = parser.parse_args()

    if not args.query and not args.resolve_annas:
        parser.error("query is required unless --resolve-annas is given")

    try:
        sys.exit(asyncio.run(_run(args)))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
