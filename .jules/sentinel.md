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
## 2025-05-24 - Webhook Signature Validation Vulnerability
**Vulnerability:** Missing HMAC-SHA256 signature validation on the WhatsApp incoming webhook (`/webhook` POST endpoint).
**Learning:** Webhooks that blindly trust incoming POST payloads without verifying signatures are vulnerable to forgery. An attacker can craft a fake payload to trigger backend logic. For FastAPI, validation requires fetching `await request.body()` instead of `await request.json()` to preserve the raw bytes over which the signature was originally computed, avoiding validation failures caused by JSON parsing differences. Additionally, checking `hmac.compare_digest()` protects against timing attacks.
**Prevention:** Always implement signature validation for all incoming webhooks. Retrieve raw request bytes before any framework parsing, use `hmac.compare_digest` for secure string comparison, and configure explicit secrets (like `WHATSAPP_APP_SECRET`).
