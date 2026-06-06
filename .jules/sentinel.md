## 2025-05-02 - SSRF Protection Requires Global IP Check
**Vulnerability:** The application's SSRF protection in `backend/main.py` verified IPs against private, loopback, multicast, reserved, and link-local ranges, but failed to block `0.0.0.0`, `::`, or shared network IPs (e.g. `100.64.0.1`), allowing an attacker to bypass the proxy.
**Learning:** `ipaddress.is_private` does not cover all unroutable or internal IPs in Python. Specifically, `0.0.0.0` has `is_unspecified = True` and is not considered private or reserved.
**Prevention:** When validating IP addresses for SSRF prevention, enforce `ip_obj.is_global` (to guarantee public routability) and explicitly reject `ip_obj.is_unspecified`.
## 2024-05-18 - [SSRF Bypass via IPv6 Loopback]
**Vulnerability:** Server-Side Request Forgery (SSRF) bypass through IPv6 addresses (`[::1]`) in URL validation logic.
**Learning:** `socket.gethostbyname` in Python only resolves IPv4 addresses and raises `socket.gaierror` for IPv6 addresses. Catching this error and silently passing allows attackers to bypass SSRF protections by supplying IPv6 equivalents of loopback or private addresses.
**Prevention:** Always use `socket.getaddrinfo` to resolve hostnames, as it supports both IPv4 and IPv6 resolution. Iterate over all returned IPs and ensure none fall into restricted categories.

## 2024-05-24 - [Remove Hardcoded API Keys]
**Vulnerability:** Real API keys like `GROQ_API_KEY` were hardcoded in the `backend/.env` file, which was tracked in the git repository.
**Learning:** Checking in `.env` files with actual API keys exposes sensitive credentials. It highlights the importance of always creating a dummy `.env.example` file and ensuring `.env` is listed in `.gitignore` from the very start of a project.
**Prevention:** Make sure all `.env` files are in `.gitignore` across the entire project structure and only track template files like `.env.example`.

## 2024-05-24 - [SSRF Bypass via Redirects]
**Vulnerability:** Server-Side Request Forgery (SSRF) bypass due to `httpx.AsyncClient` following redirects without re-validating the new destination URLs.
**Learning:** URL validation at the endpoint level only checks the initial URL. If an HTTP client is configured to follow redirects (`follow_redirects=True`), it will automatically traverse to the new location without running the application's validation logic, allowing attackers to use an external URL that redirects to internal/private IPs.
**Prevention:** Intercept all requests, including redirects, by utilizing `event_hooks` (e.g., `event_hooks={"request": [check_url_hook]}`) in HTTP clients like `httpx` to run validation on every request attempt.

## 2024-05-28 - [SSRF Bypass via DNS Resolution Failures]
**Vulnerability:** An SSRF bypass where malicious formats of IP addresses (e.g., `2130706433` for `127.0.0.1`) caused `socket.getaddrinfo` to throw `socket.gaierror`. The previous validation code swallowed this error and incorrectly marked the URL as safe.
**Learning:** `httpx` and internal C libraries may still resolve and connect to these IP addresses even if `socket.getaddrinfo` rejects them. Failsafe mechanisms must fail closed. Also, global `httpx.AsyncClient` objects used in background tasks must explicitly hook into validation routines to prevent unauthenticated SSRF loops.
**Prevention:** Catch `socket.gaierror` and `return False` in URL validation, and ensure all HTTP clients initialize with `event_hooks={"request": [check_url_hook]}`.
## 2025-02-18 - Prevented Information Leakage and HTTP Header Injection in Backend Endpoints
**Vulnerability:** Fast API string exceptions were leaked directly to the client via `HTTPException` detail fields and server-sent events (SSE). In addition, dynamically resolved `Content-Disposition` filenames in the download proxy lacked sanitization, creating an HTTP header injection and unescaped quotes vulnerability.
**Learning:** Due to how FastAPI and Python format raw exceptions as strings (`str(e)`), raising `HTTPException(detail=str(e))` inherently leaks sensitive internal states or trace paths to the end user. Furthermore, proxying content dynamically requires sanitizing headers since variables implicitly injected without escaping create header injection risks.
**Prevention:** Do not return explicit stack trace details via generic exception blocks. Instead, log the raw exception internally and map the response to a safe user-facing message. When building headers, aggressively strip characters like `\n`, `\r`, and `"` using `re.sub(r'[\r\n"]', '_', filename)`.
## 2024-05-28 - Missing Webhook Signature Validation Let Attackers Spoof Events
**Vulnerability:** The WhatsApp webhook endpoint (`/webhook`) blindly accepted incoming payloads without validating the `X-Hub-Signature-256` HMAC signature provided by the Meta platform.
**Learning:** For webhooks receiving data over the internet, failing to validate cryptographic signatures allows an attacker to spoof incoming messages or actions without needing to authenticate. Additionally, when implementing HMAC-SHA256 validation in frameworks like FastAPI, using `await request.json()` *before* signature validation mutates the raw request body bytes, causing the HMAC hash to fail when comparing against the header.
**Prevention:** Always implement signature validation for external webhooks. Read raw bytes directly from the request (`await request.body()`) to compute the signature, compare securely using `hmac.compare_digest()` to prevent timing attacks, and only parse the JSON body after validation passes.
## 2025-05-27 - [Overly Permissive CORS Configuration]
**Vulnerability:** The application was configured with `allow_origins=["*"]` alongside `allow_credentials=True` in `CORSMiddleware`, which is inherently insecure and allows unauthorized domains to exploit cross-origin requests using user credentials.
**Learning:** Using wildcard origins with credentials is treated as a severe security anti-pattern. Modern security tools (and the underlying Starlette implementation) often strictly block this misconfiguration at startup, but even if bypassed, it creates severe CSRF and data exposure risks.
**Prevention:** Explicitly restrict CORS origins. For dynamic environments, parse an environment variable containing allowed origins (e.g., `os.getenv("ALLOWED_ORIGINS")`) and map them correctly.

## 2025-10-18 - [SSRF Bypass via Missing Event Hooks & Weak IP Checks]
**Vulnerability:** Attackers could bypass SSRF protections because global `httpx.AsyncClient` instances lacked `event_hooks={"request": [check_url_hook]}`, preventing redirects from being validated. Additionally, URL validation failed to properly block unroutable IPs like `0.0.0.0` and did not fail closed on `socket.gaierror`.
**Learning:** URL validation must occur strictly via HTTP client hooks so redirects are inherently secured. When validating IP addresses, using `ip_obj.is_private` is insufficient as `0.0.0.0` evaluates as `is_unspecified`. Lastly, `socket.gaierror` must return `False` rather than silently passing.
**Prevention:** Apply `event_hooks={"request": [check_url_hook]}` globally on all HTTP clients, return `False` upon `socket.gaierror`, and strictly enforce `not ip_obj.is_global` or `ip_obj.is_unspecified`.

## 2025-02-18 - Prevented Information Leakage in API Endpoints
**Vulnerability:** Fast API error handlers in `get_agent_response` were leaking `e.response.text` and `repr(e)` directly to the client JSON payload.
**Learning:** Verbose stringified exceptions returned via HTTP directly expose internal API trace paths and responses to the end user.
**Prevention:** Replace explicit stack trace details with safe, generic user-facing messages in the JSON payload, while securely logging the raw exception trace directly to the server console.

## 2026-06-06 - Prevent Header Injection in Proxy Endpoints
**Vulnerability:** The `/api/download` endpoint blindly proxied all upstream HTTP headers from the destination server via `dict(response.headers)`. This could allow a malicious server to inject dangerous headers (like `Set-Cookie` leading to XSS or account takeover, or caching directives).
**Learning:** Blindly copying all upstream headers in a proxy endpoint introduces Header Injection and XSS vulnerabilities, because the server forwards untrusted headers.
**Prevention:** When proxying HTTP responses in Python/FastAPI (e.g., `/api/download`), never blindly copy all upstream headers. Always use a strict allow-list (e.g., `content-type`, `content-length`), force safe defaults if missing (e.g. `application/octet-stream` for `content-type`), and normalize header keys to lowercase before merging to prevent duplicate header conflicts.
