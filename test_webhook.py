import pytest
from httpx import AsyncClient, ASGITransport
import os
os.environ["WHATSAPP_VERIFY_TOKEN"] = ""
os.environ["WHATSAPP_APP_SECRET"] = ""
import main
from main import app

@pytest.mark.asyncio
async def test_webhook_fail_closed():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/webhook?hub.mode=subscribe&hub.verify_token=test")
        assert response.status_code == 500

        response = await ac.post("/webhook", headers={"X-Hub-Signature-256": "test"}, json={"test": "data"})
        assert response.status_code == 500
