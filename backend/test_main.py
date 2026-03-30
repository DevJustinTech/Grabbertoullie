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

        response = await ac.get("/api/download?url=http://169.254.169.254/latest/meta-data/")
        assert response.status_code == 400
        assert "Invalid or restricted URL" in response.json()["detail"]

        response = await ac.get("/api/download?url=file:///etc/passwd")
        assert response.status_code == 400
        assert "Invalid URL scheme" in response.json()["detail"]
