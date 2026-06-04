import asyncio
import socket
import ipaddress
import httpx
import time
from collections import OrderedDict
from urllib.parse import urlparse
from typing import Tuple
from fastapi import HTTPException

_dns_cache = OrderedDict()
_DNS_CACHE_TTL = 300
_DNS_CACHE_MAX_SIZE = 1000

async def is_valid_url(url: str) -> Tuple[bool, str]:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return False, "Invalid URL scheme. Only HTTP and HTTPS are allowed."

        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL format."

        # Optional: Resolve hostname to IP and check if it's public.
        # This prevents accessing localhost or internal networks.
        # Use asyncio.get_running_loop().getaddrinfo to prevent blocking the event loop
        # during DNS resolution.
        try:
            current_time = time.time()
            addr_info = None
            if hostname in _dns_cache:
                timestamp, cached_addr_info = _dns_cache[hostname]
                if current_time - timestamp < _DNS_CACHE_TTL:
                    addr_info = cached_addr_info
                    _dns_cache.move_to_end(hostname)
                else:
                    del _dns_cache[hostname]

            if addr_info is None:
                # Prevent SSRF: Resolve to IP and block private/loopback/restricted IPs.
                # Use getaddrinfo to support both IPv4 and IPv6 to prevent IPv6 bypasses.
                loop = asyncio.get_running_loop()
                addr_info = await loop.getaddrinfo(hostname, None)
                _dns_cache[hostname] = (current_time, addr_info)
                if len(_dns_cache) > _DNS_CACHE_MAX_SIZE:
                    _dns_cache.popitem(last=False)

            for res in addr_info:
                ip = res[4][0]
                ip_obj = ipaddress.ip_address(ip)
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_link_local or ip_obj.is_unspecified or not ip_obj.is_global:
                    return False, "Invalid or restricted URL domain/IP."
        except socket.gaierror:
            # DNS resolution failed or invalid format like octal/decimal IP that getaddrinfo rejects
            # but httpx might still fallback to and resolve incorrectly.
            return False, "Invalid or restricted URL domain/IP."

        return True, ""
    except Exception as e:
        return False, "An error occurred while validating the URL."

async def check_url_hook(request: httpx.Request):
    # Prevent SSRF by validating redirects using the same is_valid_url logic
    valid, reason = await is_valid_url(str(request.url))
    if not valid:
        # Instead of ValueError, we can raise an HTTPException so it is handled correctly by FastAPI
        raise HTTPException(status_code=400, detail=f"SSRF Attempt blocked: {reason}")
