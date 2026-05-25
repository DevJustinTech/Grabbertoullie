import pytest
import hmac
import hashlib
import json
from httpx import AsyncClient, ASGITransport

@pytest.fixture(autouse=True)
def mock_whatsapp_secret(monkeypatch):
    monkeypatch.setattr("main.WHATSAPP_APP_SECRET", "test_secret")

@pytest.mark.asyncio
async def test_webhook_signature_missing():
    from main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/webhook", json={"object": "whatsapp_business_account"})
        assert response.status_code == 403
        assert response.json()["detail"] == "Missing signature"

@pytest.mark.asyncio
async def test_webhook_signature_invalid():
    from main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = {"x-hub-signature-256": "sha256=invalidsignature"}
        response = await ac.post("/webhook", json={"object": "whatsapp_business_account"}, headers=headers)
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid signature"

@pytest.mark.asyncio
async def test_webhook_signature_valid():
    from main import app
    transport = ASGITransport(app=app)

    payload = {"object": "whatsapp_business_account", "entry": []}
    raw_body = json.dumps(payload).encode("utf-8")

    expected_signature = hmac.new(
        "test_secret".encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    headers = {"x-hub-signature-256": f"sha256={expected_signature}"}

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Pass the raw content directly to ensure it matches the json dumping perfectly
        response = await ac.post("/webhook", content=raw_body, headers=headers)
        assert response.status_code == 200
        assert response.text == "EVENT_RECEIVED"
