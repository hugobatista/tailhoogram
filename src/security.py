"""Security utilities for webhook signature verification."""

import hashlib
import hmac
import json
import logging
import time

logger = logging.getLogger(__name__)


def parse_signature_header(signature_header: str) -> tuple[str | None, int | None]:
    """
    Parse Tailscale webhook signature header.

    Format: t=<timestamp>,v1=<signature>

    Args:
        signature_header: Value of Tailscale-Webhook-Signature header

    Returns:
        Tuple of (signature, timestamp) or (None, None) if parsing fails
    """
    try:
        parts = signature_header.split(",")
        timestamp = None
        signature = None

        for part in parts:
            if part.startswith("t="):
                timestamp = int(part[2:])
            elif part.startswith("v1="):
                signature = part[3:]

        if timestamp is None or signature is None:
            logger.warning("Invalid signature header format")
            return None, None

        return signature, timestamp
    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse signature header: {e}")
        return None, None


def validate_timestamp(timestamp: int, tolerance_seconds: int = 300) -> bool:
    """
    Validate webhook timestamp to prevent replay attacks.

    Args:
        timestamp: Unix epoch timestamp from webhook
        tolerance_seconds: How old a timestamp can be (default 5 minutes)

    Returns:
        True if timestamp is recent (within tolerance), False otherwise
    """
    current_time = int(time.time())
    age = current_time - timestamp

    if age < 0:
        logger.warning(f"Timestamp is in future (age: {age}s)")
        return False

    if age > tolerance_seconds:
        logger.warning(f"Timestamp too old (age: {age}s, tolerance: {tolerance_seconds}s)")
        return False

    return True


def compute_signature(timestamp: int, body: bytes, secret: bytes) -> str:
    """
    Compute HMAC-SHA256 signature for webhook verification.

    Args:
        timestamp: Unix epoch timestamp
        body: Raw request body (bytes)
        secret: Webhook secret (bytes)

    Returns:
        Hex-encoded HMAC-SHA256 signature
    """
    timestamp_bytes = str(timestamp).encode("utf-8")
    signing_string = timestamp_bytes + b"." + body
    signature = hmac.new(secret, signing_string, hashlib.sha256).hexdigest()
    return signature


def verify_signature(
    signature_header: str,
    body: bytes,
    secret: bytes,
    timestamp_tolerance_seconds: int = 300,
) -> bool:
    """
    Verify Tailscale webhook signature.

    Performs constant-time comparison to prevent timing attacks.

    Args:
        signature_header: Value of Tailscale-Webhook-Signature header
        body: Raw request body (bytes)
        secret: Webhook secret from Tailscale dashboard (bytes)
        timestamp_tolerance_seconds: Allow timestamps up to this age (seconds)

    Returns:
        True if signature is valid and timestamp is recent, False otherwise
    """
    # Parse signature header
    provided_signature, timestamp = parse_signature_header(signature_header)

    if provided_signature is None or timestamp is None:
        logger.warning("Could not parse signature header")
        return False

    # Validate timestamp (replay attack prevention)
    if not validate_timestamp(timestamp, timestamp_tolerance_seconds):
        logger.warning(
            "Rejected webhook due to timestamp (received=%s, tolerance=%ss)",
            timestamp,
            timestamp_tolerance_seconds,
        )
        return False

    # Compute expected signature
    expected_signature = compute_signature(timestamp, body, secret)

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(expected_signature, provided_signature):
        logger.warning(
            "Signature mismatch (timestamp=%s, body_len=%s)",
            timestamp,
            len(body),
        )
        return False

    logger.debug("Signature verification successful")
    return True


def validate_json_body(body: bytes) -> bool:
    """
    Validate that body is valid JSON.

    Args:
        body: Raw request body

    Returns:
        True if valid JSON, False otherwise
    """
    try:
        json.loads(body)
        return True
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in request body: {e}")
        return False
