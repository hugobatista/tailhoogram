"""Exception handlers and error responses."""

import logging
from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class WebhookVerificationError(Exception):
    """Raised when webhook signature verification fails."""

    pass


async def webhook_verification_error_handler(request: Request, exc: WebhookVerificationError) -> JSONResponse:
    """
    Handle webhook verification errors.

    Returns 401 Unauthorized to indicate invalid signature/timestamp.
    """
    logger.warning(f"Webhook verification failed for {request.method} {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Invalid webhook signature or timestamp"},
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions.

    Returns 500 Internal Server Error. Tailscale will retry.
    """
    logger.exception(f"Unexpected error processing {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Register exception handlers with FastAPI app.

    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(
        WebhookVerificationError,
        cast(
            "Callable[[Request, Exception], Awaitable[JSONResponse]]",
            webhook_verification_error_handler,
        ),
    )
    app.add_exception_handler(
        Exception,
        cast(
            "Callable[[Request, Exception], Awaitable[JSONResponse]]",
            generic_exception_handler,
        ),
    )
