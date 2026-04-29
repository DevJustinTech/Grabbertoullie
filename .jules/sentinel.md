## 2024-05-18 - [SSRF Bypass via IPv6 Loopback]
**Vulnerability:** Server-Side Request Forgery (SSRF) bypass through IPv6 addresses (`[::1]`) in URL validation logic.
**Learning:** `socket.gethostbyname` in Python only resolves IPv4 addresses and raises `socket.gaierror` for IPv6 addresses. Catching this error and silently passing allows attackers to bypass SSRF protections by supplying IPv6 equivalents of loopback or private addresses.
**Prevention:** Always use `socket.getaddrinfo` to resolve hostnames, as it supports both IPv4 and IPv6 resolution. Iterate over all returned IPs and ensure none fall into restricted categories.
