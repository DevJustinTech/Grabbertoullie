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

import json
import hmac
import hashlib
import main

@pytest.mark.asyncio
async def test_webhook_signature_validation(monkeypatch):
    monkeypatch.setattr(main, "WHATSAPP_APP_SECRET", "test_secret")

    payload = {"object": "whatsapp_business_account"}
    raw_payload = json.dumps(payload).encode('utf-8')

    expected_signature = hmac.new(
        "test_secret".encode("utf-8"),
        raw_payload,
        hashlib.sha256
    ).hexdigest()

    valid_headers = {
        "X-Hub-Signature-256": f"sha256={expected_signature}",
        "Content-Type": "application/json"
    }

    invalid_headers = {
        "X-Hub-Signature-256": "sha256=invalid_signature",
        "Content-Type": "application/json"
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Valid signature should return 200 EVENT_RECEIVED
        response = await ac.post("/webhook", content=raw_payload, headers=valid_headers)
        assert response.status_code == 200
        assert response.text == "EVENT_RECEIVED"

        # Invalid signature should raise 403
        response = await ac.post("/webhook", content=raw_payload, headers=invalid_headers)
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid signature"
