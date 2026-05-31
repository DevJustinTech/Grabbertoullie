import pytest
import asyncio
from services.security import is_valid_url

@pytest.mark.asyncio
async def test_is_valid_url():
    # Valid urls
    valid, reason = await is_valid_url("https://example.com")
    assert valid

    # Loopback / internal
    valid, reason = await is_valid_url("http://127.0.0.1")
    assert not valid

    valid, reason = await is_valid_url("http://localhost")
    assert not valid

    # SSRF bypass unroutable / unspecified
    valid, reason = await is_valid_url("http://0.0.0.0")
    assert not valid

    # Missing scheme
    valid, reason = await is_valid_url("example.com")
    assert not valid
