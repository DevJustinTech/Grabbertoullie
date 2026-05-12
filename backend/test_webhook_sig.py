import os
import pytest
from httpx import AsyncClient, ASGITransport
import hmac
import hashlib
import json

@pytest.fixture(autouse=True)
def setup_env_and_reload(monkeypatch):
    import sys
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "test_secret")
    # Force reload of main module so it picks up the patched env var
    if "main" in sys.modules:
        del sys.modules["main"]

@pytest.mark.asyncio
async def test_webhook_signature():
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        payload = {"object": "whatsapp_business_account"}
        raw_body = json.dumps(payload).encode("utf-8")

        # Test missing signature
        response = await ac.post("/webhook", content=raw_body)
        assert response.status_code == 401

        # Test invalid signature
        response = await ac.post("/webhook", content=raw_body, headers={"X-Hub-Signature-256": "sha256=invalid"})
        assert response.status_code == 401

        # Test valid signature
        signature = "sha256=" + hmac.new(
            b"test_secret",
            raw_body,
            hashlib.sha256
        ).hexdigest()

        response = await ac.post("/webhook", content=raw_body, headers={"X-Hub-Signature-256": signature})
        assert response.status_code == 200
        assert response.text == "EVENT_RECEIVED"
