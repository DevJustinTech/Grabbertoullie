import asyncio
import socket
import ipaddress
import httpx
import time
from collections import OrderedDict
from urllib.parse import urlparse
from typing import Tuple, Dict
from fastapi import HTTPException

# ⚡ Bolt Performance Optimization:
# Cache DNS resolution results to avoid repeated thread pool usage and network latency
# during concurrent SSRF validation of URLs from the same domains.
# Using a bounded OrderedDict as an LRU cache and a short TTL (10s) to prevent memory leaks and DNS rebinding risks.
_dns_cache: 'OrderedDict[str, Tuple[float, bool, str]]' = OrderedDict()
DNS_CACHE_TTL = 10  # 10 seconds
MAX_CACHE_SIZE = 500

async def is_valid_url(url: str) -> Tuple[bool, str]:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return False, "Invalid URL scheme. Only HTTP and HTTPS are allowed."

        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL format."

        now = time.time()
        if hostname in _dns_cache:
            timestamp, valid, reason = _dns_cache.pop(hostname)
            if now - timestamp < DNS_CACHE_TTL:
                _dns_cache[hostname] = (timestamp, valid, reason) # Refresh position in LRU
                return valid, reason

        # Evict oldest if cache is full before adding new
        if len(_dns_cache) >= MAX_CACHE_SIZE:
            _dns_cache.popitem(last=False)

        # Optional: Resolve hostname to IP and check if it's public.
        # This prevents accessing localhost or internal networks.
        # Use asyncio.get_running_loop().getaddrinfo to prevent blocking the event loop
        # during DNS resolution.
        try:
            # Prevent SSRF: Resolve to IP and block private/loopback/restricted IPs.
            # Use getaddrinfo to support both IPv4 and IPv6 to prevent IPv6 bypasses.
            loop = asyncio.get_running_loop()
            addr_info = await loop.getaddrinfo(hostname, None)
            for res in addr_info:
                ip = res[4][0]
                ip_obj = ipaddress.ip_address(ip)
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_link_local or ip_obj.is_unspecified or not ip_obj.is_global:
                    _dns_cache[hostname] = (now, False, "Invalid or restricted URL domain/IP.")
                    return False, "Invalid or restricted URL domain/IP."
        except socket.gaierror:
            # DNS resolution failed or invalid format like octal/decimal IP that getaddrinfo rejects
            # but httpx might still fallback to and resolve incorrectly.
            _dns_cache[hostname] = (now, False, "Invalid or restricted URL domain/IP.")
            return False, "Invalid or restricted URL domain/IP."

        _dns_cache[hostname] = (now, True, "")
        return True, ""
    except Exception as e:
        return False, "An error occurred while validating the URL."

async def check_url_hook(request: httpx.Request):
    # Prevent SSRF by validating redirects using the same is_valid_url logic
    valid, reason = await is_valid_url(str(request.url))
    if not valid:
        # Instead of ValueError, we can raise an HTTPException so it is handled correctly by FastAPI
        raise HTTPException(status_code=400, detail=f"SSRF Attempt blocked: {reason}")
