import pytest
from fastapi.testclient import TestClient
import main
from unittest.mock import patch

def test_webhook_bypass():
    with patch("main.WHATSAPP_APP_SECRET", None):
        client = TestClient(main.app)
        headers = {"X-Hub-Signature-256": "fake_signature"}
        body = {
            "object": "whatsapp_business_account",
            "entry": [{"changes": [{"value": {"messages": [{"type": "text", "from": "123", "text": {"body": "hello"}}]}}]}]
        }
        response = client.post("/webhook", headers=headers, json=body)
        assert response.status_code == 500
        assert "Webhook secret not configured" in response.json()["detail"]
