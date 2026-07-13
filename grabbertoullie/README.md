# grabbertoullie

Search multiple book sources in parallel for a direct download link (PDF/EPUB).

Given a title (and optionally an author/format), `grabbertoullie` queries
Anna's Archive, Z-Library, Open Library, Project Gutenberg, Standard Ebooks,
and Semantic Scholar concurrently, scores the matches, and returns the best
direct file link. Runs entirely on your machine — no server, no account.

## Install

```bash
pip install grabbertoullie
playwright install chromium   # one-time: Anna's Archive / Z-Library need a real browser
```

Requires Python 3.10+.

## CLI

```bash
grabbertoullie "somadina"                    # best match, any format
grabbertoullie "the great gatsby" -f epub    # force a format (pdf | epub | any)
grabbertoullie "atomic habits" -a "clear"    # narrow by author
grabbertoullie "dune" --all                  # show all ranked candidates
grabbertoullie "dune" --json                 # machine-readable output
```

A successful run prints the book, its format, the source, and the link:

```
✅ Somadina by Akwaeke Emezi
   Format : epub
   Source : Anna's Archive
   Link   : https://annas-archive.gl/md5/5a68415cf449fc8f562bc2a11e1605d3
```

Exit code is `0` on a hit, `1` when nothing is found.

## Python API

```python
import asyncio
from grabbertoullie import search

result = asyncio.run(search("somadina"))
if result["status"] == "success":
    print(result["file_url"], result["extension"], result["source"])
```

Synchronous helper and full candidate list:

```python
from grabbertoullie import search_sync, search_raw
import asyncio

print(search_sync("the great gatsby", fmt="epub"))
ranked = asyncio.run(search_raw("dune"))   # all candidates, best first
```

### `search(query, fmt=None, author=None, groq_api_key=None)`

Returns the single best match as a dict:

| key | meaning |
|-----|---------|
| `status` | `"success"` or `"fail"` |
| `book_name` | title (with author, when known) |
| `file_url` | direct download / detail link |
| `extension` | `"pdf"` or `"epub"` |
| `source` | which source it came from |

`fmt` is `"pdf"`, `"epub"`, or `"any"`. If omitted, the format is inferred from
the query and defaults to `"any"` — so an EPUB-only title isn't silently hidden
by a PDF filter.

## Optional: LLM query parsing

Query parsing works out of the box with a built-in regex parser. For smarter
parsing of messy queries (e.g. `"grab me that harry potter book by rowling"`),
set a [Groq](https://groq.com) key and it will be used automatically:

```bash
export GROQ_API_KEY=your_key        # CLI reads it from the environment
```

```python
search_sync("harry potter by rowling", groq_api_key="your_key")
```

## Notes

- Anna's Archive and Z-Library are fetched with a real (Playwright) browser to
  pass their bot checks, which is why `playwright install chromium` is required.
- Everything runs locally; downloads go directly from the source to you.
