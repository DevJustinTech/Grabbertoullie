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
