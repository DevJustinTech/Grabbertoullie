import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_ssrf_protection():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/download?url=http://127.0.0.1/internal")
        assert response.status_code == 400
        assert "Invalid or restricted URL" in response.json()["detail"]

        response = await ac.get("/api/download?url=http://localhost/internal")
        assert response.status_code == 400
        assert "Invalid or restricted URL" in response.json()["detail"]

        response = await ac.get("/api/download?url=http://[::1]/internal")
        assert response.status_code == 400
        assert "Invalid or restricted URL" in response.json()["detail"]

        response = await ac.get("/api/download?url=http://[0:0:0:0:0:0:0:1]/internal")
        assert response.status_code == 400
        assert "Invalid or restricted URL" in response.json()["detail"]

        response = await ac.get("/api/download?url=http://169.254.169.254/latest/meta-data/")
        assert response.status_code == 400
        assert "Invalid or restricted URL" in response.json()["detail"]

        response = await ac.get("/api/download?url=file:///etc/passwd")
        assert response.status_code == 400
        assert "Invalid URL scheme" in response.json()["detail"]

@pytest.mark.asyncio
async def test_ssrf_redirect_protection():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # httpbin.org/redirect-to redirects to the provided URL parameter
        # This will test if our httpx client follows the redirect to an internal IP and catches it
        response = await ac.get("/api/download?url=http://httpbin.org/redirect-to?url=http://169.254.169.254/")

        assert response.status_code == 400
        assert "SSRF Attempt blocked" in response.json()["detail"] or "Invalid or restricted URL domain/IP" in response.json()["detail"]

from main import is_valid_url

@pytest.mark.asyncio
async def test_is_valid_url():
    valid, reason = await is_valid_url("http://google.com")
    assert valid

@pytest.mark.asyncio
async def test_is_invalid_url():
    valid, reason = await is_valid_url("http://localhost")
    assert not valid
