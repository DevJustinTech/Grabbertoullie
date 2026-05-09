import pytest
from fastapi.testclient import TestClient
import hmac
import hashlib
import json
import sys
from unittest.mock import MagicMock

# Mock necessary dependencies
sys.modules['services.llm'] = MagicMock()
sys.modules['services.pipeline'] = MagicMock()
sys.modules['services.security'] = MagicMock()

import main
main.WHATSAPP_APP_SECRET = "test_secret"

from main import app

client = TestClient(app)

def test_webhook_auth_success():
    payload = {"object": "whatsapp_business_account", "entry": []}
    body = json.dumps(payload).encode("utf-8")

    signature = hmac.new(
        "test_secret".encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()

    headers = {
        "X-Hub-Signature-256": f"sha256={signature}",
        "Content-Type": "application/json"
    }

    response = client.post("/webhook", content=body, headers=headers)
    assert response.status_code == 200
    assert response.text == "EVENT_RECEIVED"

def test_webhook_auth_missing_signature():
    payload = {"object": "whatsapp_business_account", "entry": []}

    response = client.post("/webhook", json=payload)
    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid signature format"}

def test_webhook_auth_invalid_signature():
    payload = {"object": "whatsapp_business_account", "entry": []}
    body = json.dumps(payload).encode("utf-8")

    headers = {
        "X-Hub-Signature-256": "sha256=invalid_signature",
        "Content-Type": "application/json"
    }

    response = client.post("/webhook", content=body, headers=headers)
    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid signature"}
