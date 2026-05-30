import asyncio
import socket
import ipaddress
import httpx
from urllib.parse import urlparse
from typing import Tuple
from fastapi import HTTPException

async def is_valid_url(url: str) -> Tuple[bool, str]:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return False, "Invalid URL scheme. Only HTTP and HTTPS are allowed."

        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL format."

        try:
            loop = asyncio.get_running_loop()
            addr_info = await loop.getaddrinfo(hostname, None)
            for res in addr_info:
                ip = res[4][0]
                ip_obj = ipaddress.ip_address(ip)
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_link_local or ip_obj.is_unspecified or not ip_obj.is_global:
                    return False, "Invalid or restricted URL domain/IP."
        except socket.gaierror:
            return False, "Invalid or restricted URL domain/IP."

        return True, ""
    except Exception as e:
        return False, str(e)

async def check_url_hook(request: httpx.Request):
    valid, reason = await is_valid_url(str(request.url))
    if not valid:
        raise HTTPException(status_code=400, detail=f"SSRF Attempt blocked: {reason}")
