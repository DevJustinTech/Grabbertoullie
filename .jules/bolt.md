## 2024-05-24 - Pre-compiling Regex
**Learning:** Found multiple instances of `re.search(r'```(?:json)?\s*(.*?)\s*```', ...)` and other regex usages being compiled repeatedly inside functions (like `extract_json_from_response` in `main.py` and `services/llm.py`). Compiling regexes inline causes unnecessary overhead, especially if called multiple times.
**Action:** Extract and pre-compile regular expressions at the module level using `re.compile()` rather than inside frequently called functions or loops to avoid redundant compilation overhead.

## 2024-05-25 - Parallel Scraping in Z-Library
**Learning:** In `search_zlibrary` (`backend/services/search.py`), the function iteratively awaited `get_book_info` for the top 3 candidates. This sequentially launched headless Playwright instances via `async_playwright()`, causing a compounded latency of ~10s for the detail retrieval phase.
**Action:** Use `asyncio.gather` with a helper async function (`_fetch_zlib_info`) to execute those playwright tasks concurrently, successfully dropping the time for this phase to ~5s, saving ~50% latency for that block without making rate-limiting unmanageable.

## 2025-02-27 - httpx.AsyncClient Instantiation Overhead
**Learning:** During concurrent validation of book URLs using `asyncio.gather` in `chat_stream_generator` (which calls `validate_url`), a new `httpx.AsyncClient` was instantiated on every iteration inside a `for` loop. This caused a significant overhead (spinning up and tearing down the client machinery, including its internal connection pools and states). Benchmarks showed that initializing 50 clients takes ~2-3 seconds, whereas executing requests with a shared client takes ~0.03 seconds.
**Action:** Use a module-level `httpx.AsyncClient` instance for multiple asynchronous outbound requests when working with heavily concurrent HTTP tasks instead of recreating it via `async with httpx.AsyncClient()` dynamically inside task worker functions.

## 2024-05-25 - Async DNS Resolution Event Loop Blocking
**Learning:** Using `socket.getaddrinfo` synchronously in an async route handler or event hook blocks the event loop. Given this API receives concurrent requests that involve SSRF mitigation using `is_valid_url`, blocking the event loop on DNS resolution significantly degraded concurrency and throughput.
**Action:** Use `await asyncio.get_running_loop().getaddrinfo(...)` when doing DNS lookups inside the async event loop to keep the process non-blocking and highly concurrent.
## 2024-05-04 - Unblocking Asyncio DNS Resolution
**Learning:** `socket.getaddrinfo` is a synchronous system call in Python that blocks the entire asyncio event loop during execution, potentially stalling concurrent incoming requests in ASGI frameworks like FastAPI if DNS resolution is slow.
**Action:** When performing DNS validation in asynchronous endpoints, use `await asyncio.get_running_loop().getaddrinfo(...)` to offload the blocking call to the loop's default thread pool.

## 2024-05-27 - Memoizing Next.js/React Messages
**Learning:** Found that rendering a large array of complex chat messages directly inside a parent component (`page.tsx`) that also tracks rapidly changing state like the chat input (`setInput`) causes the entire history to re-render on every single keystroke.
**Action:** Extract the complex iterated UI component (`MessageItem`) into its own component file and wrap it in `React.memo()`. Also wrap any functions passed down as props (like `handleSendMessage` or `handleDownload`) in `useCallback` to preserve reference identity. This prevents the large DOM sub-trees from thrashing during unrelated state updates.
