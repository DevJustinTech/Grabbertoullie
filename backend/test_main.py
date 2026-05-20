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

import hmac
import hashlib

@pytest.mark.asyncio
async def test_webhook_signature_missing():
    transport = ASGITransport(app=app)
    # Patch WHATSAPP_APP_SECRET at the module level in main
    import main
    original_secret = main.WHATSAPP_APP_SECRET
    main.WHATSAPP_APP_SECRET = "test_secret"
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/webhook", json={"object": "whatsapp_business_account"})
            assert response.status_code == 401
            assert "Missing signature" in response.json()["detail"]
    finally:
        main.WHATSAPP_APP_SECRET = original_secret

@pytest.mark.asyncio
async def test_webhook_signature_invalid():
    transport = ASGITransport(app=app)
    import main
    original_secret = main.WHATSAPP_APP_SECRET
    main.WHATSAPP_APP_SECRET = "test_secret"
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            headers = {"x-hub-signature-256": "sha256=invalid_signature"}
            response = await ac.post("/webhook", json={"object": "whatsapp_business_account"}, headers=headers)
            assert response.status_code == 401
            assert "Invalid signature" in response.json()["detail"]
    finally:
        main.WHATSAPP_APP_SECRET = original_secret

@pytest.mark.asyncio
async def test_webhook_signature_valid():
    transport = ASGITransport(app=app)
    import main
    original_secret = main.WHATSAPP_APP_SECRET
    main.WHATSAPP_APP_SECRET = "test_secret"
    try:
        payload = b'{"object":"whatsapp_business_account","entry":[]}'
        expected_signature = hmac.new(
            "test_secret".encode("utf-8"),
            payload,
            hashlib.sha256
        ).hexdigest()

        headers = {"x-hub-signature-256": f"sha256={expected_signature}"}
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/webhook", content=payload, headers=headers)
            assert response.status_code == 200
            assert response.text == "EVENT_RECEIVED"
    finally:
        main.WHATSAPP_APP_SECRET = original_secret
