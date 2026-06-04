import argparse
import hashlib
import hmac
import json
import os
import subprocess
import time

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Parse command line arguments
parser = argparse.ArgumentParser(description="Test Tailscale webhook")
parser.add_argument(
    "--endpoint",
    type=str,
    default="localhost:8000",
    help="Host:port for the webhook endpoint (default: localhost:8000)",
)
args = parser.parse_args()

# Configuration
webhook_secret = os.getenv("TAILSCALE_WEBHOOK_SECRET")
if not webhook_secret:
    print("Error: TAILSCALE_WEBHOOK_SECRET not found in environment variables or .env file")
    exit(1)
timestamp = int(time.time())

# Event payload
# using now to ensure timestamp is recent for testing, but in real usage this would come from Tailscale
timestamp = int(time.time())
event = {
    "timestamp": timestamp,
    "version": 1,
    "type": "node.created",
    "tailnet": "example.com",
    "message": "Node created: my-laptop",
    "data": {
        "actor": "user@example.com",
        "nodeID": "12345",
        "nodeName": "my-laptop",
    },
}

# Create request body (array of events)
body = json.dumps([event])

# Generate signature
signing_string = f"{timestamp}.{body}".encode()
secret_bytes = webhook_secret.encode("utf-8")
signature = hmac.new(secret_bytes, signing_string, hashlib.sha256).hexdigest()

# Construct curl command
url = f"http://{args.endpoint}/events"
headers = [f"Tailscale-Webhook-Signature: t={timestamp},v1={signature}", "Content-Type: application/json"]

# Execute curl command
subprocess.run(["curl", "-X", "POST", url, "-H", headers[0], "-H", headers[1], "-d", body, "-v"])
