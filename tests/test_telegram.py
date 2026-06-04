"""Tests for Telegram notification channel."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from models import NotificationPayload
from telegram import TelegramNotificationChannel


@pytest.mark.unit
class TestTelegramChannel:
    """Tests for Telegram notification channel."""

    @pytest.fixture
    def telegram_channel(self, telegram_bot_token, telegram_chat_id):
        """Create Telegram channel instance."""
        return TelegramNotificationChannel(
            bot_token=telegram_bot_token,
            chat_id=telegram_chat_id,
        )

    @pytest.fixture
    def sample_payload(self) -> NotificationPayload:
        """Sample notification payload."""
        from datetime import datetime

        return NotificationPayload(
            event_type="node.created",
            event_message="Node created: my-laptop",
            tailnet="example.com",
            timestamp=datetime.now(),
            raw_data={"nodeID": "12345", "nodeName": "my-laptop"},
        )

    def test_telegram_channel_initialization(self, telegram_channel, telegram_bot_token, telegram_chat_id):
        """Test Telegram channel initializes correctly."""
        assert telegram_channel.bot_token == telegram_bot_token
        assert telegram_channel.chat_id == telegram_chat_id

    def test_telegram_format_message(self, telegram_channel, sample_payload):
        """Test message formatting."""
        message = telegram_channel._format_message(sample_payload)

        assert "node.created" in message
        assert "example.com" in message
        assert "my-laptop" in message
        assert "<b>" in message  # HTML formatting
        assert "<code>" in message

    def test_telegram_format_message_without_details(self, telegram_channel, sample_payload):
        """Test message formatting skips details when raw_data is empty."""
        sample_payload.raw_data = {}

        message = telegram_channel._format_message(sample_payload)

        assert "Details" not in message

    def test_telegram_format_message_truncates(self, telegram_channel, sample_payload):
        """Test long values are truncated in message details."""
        sample_payload.raw_data["long_value"] = "x" * 150

        message = telegram_channel._format_message(sample_payload)

        assert "..." in message
        assert "x" * 150 not in message

    @pytest.mark.asyncio
    async def test_telegram_send_success(self, telegram_channel, sample_payload):
        """Test successful Telegram send."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client.post = AsyncMock(return_value=mock_response)
        telegram_channel.http_client = mock_client

        result = await telegram_channel.send(sample_payload)

        assert result is True
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_telegram_send_failure_http_error(self, telegram_channel, sample_payload):
        """Test Telegram send with HTTP error."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"

        mock_client.post = AsyncMock(return_value=mock_response)
        telegram_channel.http_client = mock_client

        result = await telegram_channel.send(sample_payload)

        assert result is False

    @pytest.mark.asyncio
    async def test_telegram_send_failure_request_error(self, telegram_channel, sample_payload):
        """Test Telegram send with request error."""
        import httpx

        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.RequestError("Connection error"))
        telegram_channel.http_client = mock_client

        result = await telegram_channel.send(sample_payload)

        assert result is False

    @pytest.mark.asyncio
    async def test_telegram_send_failure_unexpected_error(self, telegram_channel, sample_payload, monkeypatch):
        """Test Telegram send handles unexpected errors."""

        def boom(_payload):
            raise RuntimeError("boom")

        monkeypatch.setattr(telegram_channel, "_format_message", boom)

        result = await telegram_channel.send(sample_payload)

        assert result is False

    @pytest.mark.asyncio
    async def test_telegram_get_client_reuses_provided(self):
        """Test _get_client returns provided client."""
        mock_client = MagicMock()
        channel = TelegramNotificationChannel(
            bot_token="token",
            chat_id="chat-id",
            http_client=mock_client,
        )

        client = await channel._get_client()

        assert client is mock_client

    @pytest.mark.asyncio
    async def test_telegram_get_client_creates_default(self):
        """Test _get_client creates client when missing."""
        channel = TelegramNotificationChannel(
            bot_token="token",
            chat_id="chat-id",
        )

        client = await channel._get_client()

        assert client is channel.http_client

        await channel.close()

    @pytest.mark.asyncio
    async def test_telegram_channel_close(self, telegram_bot_token, telegram_chat_id):
        """Test channel cleanup."""
        channel = TelegramNotificationChannel(
            bot_token=telegram_bot_token,
            chat_id=telegram_chat_id,
        )

        mock_client = MagicMock()
        mock_client.aclose = AsyncMock()
        channel.http_client = mock_client
        channel._owns_client = True

        await channel.close()

        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_telegram_channel_close_no_ownership(self):
        """Test close does not close provided client."""
        mock_client = MagicMock()
        mock_client.aclose = AsyncMock()
        channel = TelegramNotificationChannel(
            bot_token="token",
            chat_id="chat-id",
            http_client=mock_client,
        )

        await channel.close()

        mock_client.aclose.assert_not_called()
