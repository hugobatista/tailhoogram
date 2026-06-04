"""FastAPI application with webhook endpoint."""

import contextlib
import logging
import uuid

from fastapi import FastAPI, Header, Request, status
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter, ValidationError

from config import Config, EnvGetter, _get_default_env_getter
from exception_handlers import (
    WebhookVerificationError,
    setup_exception_handlers,
)
from models import NotificationPayload, TailscaleEvent
from security import verify_signature

logger = logging.getLogger(__name__)
_EVENTS_ADAPTER = TypeAdapter(list[TailscaleEvent])


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown.

    Handles resource cleanup on shutdown.
    """
    # Startup
    yield
    # Shutdown
    telegram_channel = app.state.telegram_channel
    if telegram_channel is not None:
        await telegram_channel.close()


async def process_webhook_events(
    events: list[TailscaleEvent],
    telegram_channel,
) -> bool:
    """
    Process Tailscale webhook events.

    Sends each event to Telegram if configured.

    Args:
        events: List of TailscaleEvent to process
        telegram_channel: TelegramNotificationChannel instance or None

    Returns:
        True if all events processed successfully, False if any failed
    """
    if telegram_channel is None:
        logger.warning("Telegram channel not configured, skipping notifications")
        return True

    logger.info("Processing %s webhook events", len(events))

    all_success = True
    send_notification = telegram_channel.send
    for event in events:
        try:
            payload = NotificationPayload.from_tailscale_event(event)

            # Send to Telegram channel
            success = await send_notification(payload)

            if not success:
                logger.error("Failed to send notification for event %s", event.type)
                all_success = False
            else:
                logger.info("Successfully sent event %s to Telegram", event.type)

        except Exception as e:
            logger.exception("Error processing webhook event: %s", e)
            all_success = False

    return all_success


def create_app(
    env_getter: EnvGetter | None = None,
) -> FastAPI:
    """
    Create and configure FastAPI application.

    Args:
        env_getter: Callable that takes an env var name and returns its value or None.
                   Defaults to os.getenv if not provided.

    Returns:
        Configured FastAPI app instance

    Raises:
        ValueError: If required configuration is missing
    """
    if env_getter is None:
        env_getter = _get_default_env_getter()

    # Load configuration
    try:
        config = Config.load(env_getter)
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise

    # Initialize Telegram channel
    try:
        from telegram import TelegramNotificationChannel

        telegram_channel = TelegramNotificationChannel(
            bot_token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
        )
        logger.info("Telegram notification channel initialized")
    except Exception as e:
        logger.error(f"Failed to create Telegram channel: {e}")
        raise

    # Create FastAPI app
    app = FastAPI(lifespan=lifespan)

    # Set up exception handlers
    setup_exception_handlers(app)

    # Store config and Telegram channel in app state
    app.state.config = config
    app.state.telegram_channel = telegram_channel

    # Define webhook endpoint
    @app.post("/events", status_code=status.HTTP_202_ACCEPTED)
    async def webhook_tailscale(
        request: Request,
        tailscale_webhook_signature: str = Header(..., alias="Tailscale-Webhook-Signature"),
    ) -> JSONResponse:
        """
        Receive and process Tailscale webhooks.

        This endpoint:
        1. Verifies the signature using HMAC-SHA256
        2. Validates timestamp to prevent replay attacks
        3. Processes events during the request
        4. Returns 202 Accepted on success

        If notification delivery fails, the endpoint returns 500 to allow
        Tailscale to retry the webhook.

        Args:
            request: HTTP request
            tailscale_webhook_signature: Signature header from Tailscale

        Returns:
            JSON response with status
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Get raw body for signature verification
        body = await request.body()

        # Verify signature
        secret = app.state.config.tailscale_webhook_secret
        if not secret:
            raise WebhookVerificationError("Webhook secret not configured")
        secret_bytes = secret.encode("utf-8")
        if not verify_signature(
            tailscale_webhook_signature,
            body,
            secret_bytes,
            app.state.config.webhook_timestamp_tolerance_seconds,
        ):
            raise WebhookVerificationError("Signature verification failed")

        # Parse events
        try:
            events = _EVENTS_ADAPTER.validate_json(body)
            logger.info("Validated %s webhook events", len(events))

        except (ValidationError, ValueError, TypeError) as e:
            logger.error("Failed to parse webhook events: %s", e)
            raise WebhookVerificationError(f"Invalid event data: {e}") from e

        # Process events
        success = await process_webhook_events(events, app.state.telegram_channel)

        if not success:
            # Return 500 to allow Tailscale to retry
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "status": "failed",
                    "message": "Failed to process one or more events",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )

        # Return 202 Accepted
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "status": "accepted",
                "message": f"Received {len(events)} webhook event(s), processed successfully",
                "request_id": request_id,
            },
            headers={"X-Request-ID": request_id},
        )

    return app
