import logging
import os
from logging import StreamHandler as BaseStreamHandler
from typing import Any


class ConsoleHandler(BaseStreamHandler):
    """Handler for Cloudflare Workers that uses console methods."""

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record using appropriate console method."""
        msg = self.format(record)
        levelno = record.levelno

        try:
            # Access console from global scope in Workers environment
            console: Any = globals().get("console")
            if console is None:
                # Fallback: try to import from js module if running in workers
                try:
                    from js import console as js_console

                    console = js_console
                except ImportError:
                    # Not in a workers environment, fall back to standard handler
                    super().emit(record)
                    return

            if levelno >= logging.CRITICAL:
                console.error(msg)
            elif levelno >= logging.ERROR:
                console.error(msg)
            elif levelno >= logging.WARNING:
                console.warn(msg)
            elif levelno >= logging.INFO:
                console.info(msg)
            elif levelno >= logging.DEBUG:
                console.debug(msg)
            else:
                console.log(msg)  # NOTSET or custom levels
        except Exception:
            # Fallback to standard handler if console access fails
            super().emit(record)


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure logging for the application.

    Uses ConsoleHandler for Cloudflare Workers environments,
    falls back to StreamHandler for standard Python environments.

    Args:
        log_level: Logging level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    root_logger = logging.getLogger()

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Set the root logger level
    root_logger.setLevel(log_level)

    # Try to use ConsoleHandler first (for workers)
    handler = ConsoleHandler()

    # Set formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    # Add handler to root logger
    root_logger.addHandler(handler)

    # Suppress noisy logs from external libraries and that can compromise secrets
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


# Configure logging based on environment and log level
log_level = os.getenv("LOG_LEVEL", "INFO")
setup_logging(log_level)

logger = logging.getLogger(__name__)

try:
    from importlib.metadata import version

    __version__ = version("tailhoogram")
except Exception as e:
    logger.warning(f"Failed to load package metadata, using defaults: {e}")
    __version__ = "0.0.0.dev0"
