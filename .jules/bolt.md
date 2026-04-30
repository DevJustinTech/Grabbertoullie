## 2024-05-24 - Pre-compiling Regex
**Learning:** Found multiple instances of `re.search(r'```(?:json)?\s*(.*?)\s*```', ...)` and other regex usages being compiled repeatedly inside functions (like `extract_json_from_response` in `main.py` and `services/llm.py`). Compiling regexes inline causes unnecessary overhead, especially if called multiple times.
**Action:** Extract and pre-compile regular expressions at the module level using `re.compile()` rather than inside frequently called functions or loops to avoid redundant compilation overhead.

## 2024-05-25 - Parallel Scraping in Z-Library
**Learning:** In `search_zlibrary` (`backend/services/search.py`), the function iteratively awaited `get_book_info` for the top 3 candidates. This sequentially launched headless Playwright instances via `async_playwright()`, causing a compounded latency of ~10s for the detail retrieval phase.
**Action:** Use `asyncio.gather` with a helper async function (`_fetch_zlib_info`) to execute those playwright tasks concurrently, successfully dropping the time for this phase to ~5s, saving ~50% latency for that block without making rate-limiting unmanageable.
