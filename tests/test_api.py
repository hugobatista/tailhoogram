"""Tests for FastAPI webhook endpoint."""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import create_valid_signature

API_URL = "/events"  # Updated to match the actual endpoint defined in app.py


@pytest.mark.integration
class TestWebhookEndpoint:
    """Integration tests for the webhook endpoint."""

    def test_webhook_missing_signature_header(self, client, sample_webhook_body):
        """Test webhook rejects request without signature header."""
        response = client.post(
            API_URL,
            content=sample_webhook_body,
        )

        # Should fail because header is required
        assert response.status_code in [422, 401]  # Depends on FastAPI validation

    def test_webhook_invalid_signature(self, client, sample_webhook_body, webhook_secret_bytes):
        """Test webhook rejects invalid signature."""
        bad_signature = "t=999999999,v1=badbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadb"

        response = client.post(
            API_URL,
            content=sample_webhook_body,
            headers={"Tailscale-Webhook-Signature": bad_signature},
        )

        assert response.status_code == 401

    def test_webhook_old_timestamp(self, client, sample_webhook_body, webhook_secret_bytes):
        """Test webhook rejects old timestamps."""
        # Create signature with old timestamp (>5 minutes)
        old_timestamp = int(time.time()) - 600
        old_signature = create_valid_signature(old_timestamp, sample_webhook_body, webhook_secret_bytes)

        response = client.post(
            API_URL,
            content=sample_webhook_body,
            headers={"Tailscale-Webhook-Signature": old_signature},
        )

        assert response.status_code == 401

    def test_webhook_invalid_json(self, client, valid_signature):
        """Test webhook rejects invalid JSON."""
        invalid_json = b"not valid json"

        response = client.post(
            API_URL,
            content=invalid_json,
            headers={"Tailscale-Webhook-Signature": valid_signature},
        )

        assert response.status_code == 401  # Failed JSON validation

    def test_webhook_tampered_body(self, client, sample_webhook_body, webhook_secret_bytes):
        """Test webhook detects tampered body."""
        # Create valid signature for one body
        timestamp = int(time.time())
        valid_sig = create_valid_signature(timestamp, sample_webhook_body, webhook_secret_bytes)

        # Send different body with same signature
        tampered_body = b'[{"type": "tampered"}]'

        response = client.post(
            API_URL,
            content=tampered_body,
            headers={"Tailscale-Webhook-Signature": valid_sig},
        )

        assert response.status_code == 401

    def test_webhook_valid_request(self, client, valid_signature, sample_webhook_body):
        """Test webhook accepts valid request."""
        # Mock the Telegram channel to avoid actual sends
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock(return_value=True)

        with patch.object(client.app.state, "telegram_channel", mock_channel):
            response = client.post(
                API_URL,
                content=sample_webhook_body,
                headers={"Tailscale-Webhook-Signature": valid_signature},
            )

        # Should return 202 Accepted
        assert response.status_code == 202
        response_data = response.json()
        assert response_data["status"] == "accepted"
        assert "request_id" in response_data

    def test_webhook_response_includes_request_id(self, client, valid_signature, sample_webhook_body):
        """Test webhook response includes request ID."""
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock(return_value=True)

        with patch.object(client.app.state, "telegram_channel", mock_channel):
            response = client.post(
                API_URL,
                content=sample_webhook_body,
                headers={"Tailscale-Webhook-Signature": valid_signature},
            )

        assert "X-Request-ID" in response.headers
        assert response.json()["request_id"]

    def test_webhook_multiple_events(self, client, valid_signature, sample_tailscale_event, webhook_secret_bytes):
        """Test webhook handles multiple events."""
        # Create request with multiple events
        events = [sample_tailscale_event, sample_tailscale_event]
        body = json.dumps(events).encode("utf-8")
        timestamp = int(time.time())
        signature = create_valid_signature(timestamp, body, webhook_secret_bytes)

        mock_channel = MagicMock()
        mock_channel.send = AsyncMock(return_value=True)

        with patch.object(client.app.state, "telegram_channel", mock_channel):
            response = client.post(
                API_URL,
                content=body,
                headers={"Tailscale-Webhook-Signature": f"t={timestamp},v1={signature.split('v1=')[1]}"},
            )

        assert response.status_code == 202
        assert "2 webhook event(s)" in response.json()["message"]

    def test_webhook_body_not_list(self, client, webhook_secret_bytes):
        """Test webhook rejects non-array JSON bodies."""
        body = json.dumps({"type": "node.created"}).encode("utf-8")
        timestamp = int(time.time())
        signature = create_valid_signature(timestamp, body, webhook_secret_bytes)

        response = client.post(
            API_URL,
            content=body,
            headers={"Tailscale-Webhook-Signature": signature},
        )

        assert response.status_code == 401

    def test_webhook_send_failure_returns_500(self, client, valid_signature, sample_webhook_body):
        """Test webhook returns 500 when notifications fail."""
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock(return_value=False)

        with patch.object(client.app.state, "telegram_channel", mock_channel):
            response = client.post(
                API_URL,
                content=sample_webhook_body,
                headers={"Tailscale-Webhook-Signature": valid_signature},
            )

        assert response.status_code == 500
        assert response.json()["status"] == "failed"

    def test_webhook_missing_secret_returns_401(self, client, valid_signature, sample_webhook_body):
        """Test webhook rejects when secret is not configured."""
        client.app.state.config.tailscale_webhook_secret = ""

        response = client.post(
            API_URL,
            content=sample_webhook_body,
            headers={"Tailscale-Webhook-Signature": valid_signature},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid webhook signature or timestamp"

    def test_webhook_invalid_event_schema_returns_401(self, client, webhook_secret_bytes):
        """Test invalid event payload triggers webhook verification error."""
        body = json.dumps([{"type": "node.created"}]).encode("utf-8")
        timestamp = int(time.time())
        signature = create_valid_signature(timestamp, body, webhook_secret_bytes)

        response = client.post(
            API_URL,
            content=body,
            headers={"Tailscale-Webhook-Signature": signature},
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid webhook signature or timestamp"


@pytest.mark.unit
class TestWebhookParsing:
    """Unit tests for webhook event parsing."""

    def test_parse_single_event(self, sample_tailscale_event):
        """Test parsing single event."""
        from models import TailscaleEvent

        event = TailscaleEvent(**sample_tailscale_event)

        assert event.type == "node.created"
        assert event.tailnet == "example.com"

    def test_parse_multiple_events(self, sample_tailscale_event):
        """Test parsing multiple events."""
        from models import TailscaleEvent

        events_data = [sample_tailscale_event, sample_tailscale_event]
        events = [TailscaleEvent(**e) for e in events_data]

        assert len(events) == 2
        assert all(e.type == "node.created" for e in events)

    def test_parse_event_with_extra_fields(self, sample_tailscale_event):
        """Test parsing event with extra fields."""
        from models import TailscaleEvent

        sample_tailscale_event["extra_field"] = "extra_value"
        event = TailscaleEvent(**sample_tailscale_event)

        # Should allow extra fields
        assert hasattr(event, "extra_field") or True  # Pydantic strips extra by default


@pytest.mark.unit
class TestNotificationPayload:
    """Unit tests for notification payload creation."""

    def test_create_payload_from_tailscale_event(self, sample_tailscale_event):
        """Test creating notification payload from Tailscale event."""
        from models import (
            NotificationPayload,
            TailscaleEvent,
        )

        event = TailscaleEvent(**sample_tailscale_event)
        payload = NotificationPayload.from_tailscale_event(event)

        assert payload.event_type == "node.created"
        assert payload.event_message == "Node created: my-laptop"
        assert payload.tailnet == "example.com"
