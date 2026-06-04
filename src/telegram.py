"""Telegram notification channel."""

import logging

import httpx

from models import NotificationPayload

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org"


class TelegramNotificationChannel:
    """Telegram bot notification channel."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        http_client: httpx.AsyncClient | None = None,
    ):
        """
        Initialize Telegram notification channel.

        Args:
            bot_token: Telegram bot token from @BotFather
            chat_id: Target chat ID (numeric or username with @)
            http_client: Optional httpx.AsyncClient for testing
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.http_client = http_client
        self._owns_client = http_client is None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=10.0)
        return self.http_client

    async def close(self) -> None:
        """Close HTTP client if we own it."""
        if self._owns_client and self.http_client is not None:
            await self.http_client.aclose()

    def _format_message(self, payload: NotificationPayload) -> str:
        """
        Format notification payload as Telegram message.

        Args:
            payload: Notification payload

        Returns:
            Formatted message text
        """
        lines = [
            "🔔 <b>Tailscale Event</b>",
            "",
            f"<b>Type:</b> <code>{payload.event_type}</code>",
            f"<b>Tailnet:</b> {payload.tailnet}",
            f"<b>Message:</b> {payload.event_message}",
            f"<b>Time:</b> {payload.timestamp.isoformat()}",
        ]

        raw_data = payload.raw_data
        if raw_data:
            lines.append("")
            lines.append("<b>Details:</b>")
            append_line = lines.append
            for key, value in raw_data.items():
                # Truncate long values
                if isinstance(value, str):
                    value_str = value
                else:
                    value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:97] + "..."
                append_line(f"  {key}: <code>{value_str}</code>")

        return "\n".join(lines)

    async def send(self, payload: NotificationPayload) -> bool:
        """
        Send notification to Telegram.

        Args:
            payload: Notification payload

        Returns:
            True if send successful, False otherwise
        """
        client = await self._get_client()

        try:
            message = self._format_message(payload)

            url = f"{TELEGRAM_API_URL}/bot{self.bot_token}/sendMessage"

            response = await client.post(
                url,
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
            )

            if response.status_code == 200:
                logger.info(f"Successfully sent Telegram notification for event {payload.event_type}")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False

        except httpx.RequestError as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False
        except Exception as e:
            logger.exception(f"Unexpected error sending Telegram notification: {e}")
            return False
