"""Application configuration."""

import logging
import os
from collections.abc import Callable

logger = logging.getLogger(__name__)

EnvGetter = Callable[[str], str | None]


def _get_default_env_getter() -> EnvGetter:
    """Get the default environment variable getter.

    Returns:
        os.getenv function for environment variable access
    """
    return os.getenv


class Config:
    """Application configuration read from environment variables."""

    def __init__(
        self,
        tailscale_webhook_secret: str,
        telegram_bot_token: str,
        telegram_chat_id: str,
        webhook_timestamp_tolerance_seconds: int = 300,
    ):
        """Initialize configuration."""
        self.tailscale_webhook_secret = tailscale_webhook_secret
        self.webhook_timestamp_tolerance_seconds = webhook_timestamp_tolerance_seconds
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id

    @staticmethod
    def load(env_getter: EnvGetter | None = None) -> "Config":
        """Load configuration from environment variables.

        Args:
            env_getter: Callable that takes env var name and returns value or None.
                       Defaults to os.getenv if not provided.

        Returns:
            Config instance

        Raises:
            ValueError: If required env vars are missing
        """
        if env_getter is None:
            env_getter = _get_default_env_getter()

        # Load required webhook secret
        webhook_secret = env_getter("TAILSCALE_WEBHOOK_SECRET")
        if not webhook_secret:
            logger.error("TAILSCALE_WEBHOOK_SECRET environment variable not set")
            raise ValueError("TAILSCALE_WEBHOOK_SECRET is required")

        # Load optional webhook tolerance
        tolerance_str = env_getter("WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS") or "300"
        try:
            tolerance = int(tolerance_str)
        except ValueError:
            logger.warning(f"Invalid WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS: {tolerance_str}, using default 300")
            tolerance = 300

        # Load required Telegram config
        bot_token = env_getter("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
            raise ValueError("TELEGRAM_BOT_TOKEN is required")

        chat_id = env_getter("TELEGRAM_CHAT_ID")
        if not chat_id:
            logger.error("TELEGRAM_CHAT_ID environment variable not set")
            raise ValueError("TELEGRAM_CHAT_ID is required")

        return Config(
            tailscale_webhook_secret=webhook_secret,
            telegram_bot_token=bot_token,
            telegram_chat_id=chat_id,
            webhook_timestamp_tolerance_seconds=tolerance,
        )
