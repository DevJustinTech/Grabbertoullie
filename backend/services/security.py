import socket
import ipaddress
import httpx
from urllib.parse import urlparse
from typing import Tuple
from fastapi import HTTPException

def is_valid_url(url: str) -> Tuple[bool, str]:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return False, "Invalid URL scheme. Only HTTP and HTTPS are allowed."

        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL format."

        # Optional: Resolve hostname to IP and check if it's public.
        # This prevents accessing localhost or internal networks.
        # Since resolving every time can be complex asynchronously, we block obvious local IPs.
        try:
            # Prevent SSRF: Resolve to IP and block private/loopback/restricted IPs.
            # Use getaddrinfo to support both IPv4 and IPv6 to prevent IPv6 bypasses.
            addr_info = socket.getaddrinfo(hostname, None)
            for res in addr_info:
                ip = res[4][0]
                ip_obj = ipaddress.ip_address(ip)
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_link_local:
                    return False, "Invalid or restricted URL domain/IP."
        except socket.gaierror:
            # DNS resolution failed or invalid format like octal/decimal IP that getaddrinfo rejects
            # but httpx might still fallback to and resolve incorrectly.
            return False, "Invalid or restricted URL domain/IP."

        return True, ""
    except Exception as e:
        return False, str(e)

async def check_url_hook(request: httpx.Request):
    # Prevent SSRF by validating redirects using the same is_valid_url logic
    valid, reason = is_valid_url(str(request.url))
    if not valid:
        # Instead of ValueError, we can raise an HTTPException so it is handled correctly by FastAPI
        raise HTTPException(status_code=400, detail=f"SSRF Attempt blocked: {reason}")
