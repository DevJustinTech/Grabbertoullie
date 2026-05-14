import pytest
from fastapi.testclient import TestClient
import hmac
import hashlib
import json
import sys
import os

# Mock the environment variable before importing main
os.environ["WHATSAPP_APP_SECRET"] = "test_secret"

from main import app

client = TestClient(app)

def generate_signature(secret: str, payload: bytes) -> str:
    expected_sig = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()
    return f"sha256={expected_sig}"

def test_webhook_missing_signature():
    payload = {"object": "whatsapp_business_account"}
    response = client.post("/webhook", json=payload)
    assert response.status_code == 403
    assert response.json()["detail"] == "Missing signature"

def test_webhook_invalid_signature():
    payload = {"object": "whatsapp_business_account"}
    headers = {"x-hub-signature-256": "sha256=invalid"}
    response = client.post("/webhook", json=payload, headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid signature"

def test_webhook_valid_signature():
    payload = {"object": "whatsapp_business_account"}
    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = generate_signature("test_secret", payload_bytes)

    headers = {"x-hub-signature-256": signature}
    # We use content=payload_bytes instead of json=payload to ensure exact byte match
    # for the signature validation since JSON serialization can vary in whitespace.
    response = client.post("/webhook", content=payload_bytes, headers=headers)

    # We expect 200 EVENT_RECEIVED as the payload matches the expected structure
    assert response.status_code == 200
    assert response.text == "EVENT_RECEIVED"
