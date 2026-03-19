[![GitHub Tag](https://img.shields.io/github/v/tag/hugobatista/tailhoogram?logo=github&label=latest)](https://go.hugobatista.com/gh/tailhoogram/releases)
[![Test](https://go.hugobatista.com/gh/tailhoogram/actions/workflows/test.yml/badge.svg)](https://go.hugobatista.com/gh/tailhoogram/actions/workflows/test.yml)
[![Lint](https://go.hugobatista.com/gh/tailhoogram/actions/workflows/lint.yml/badge.svg)](https://go.hugobatista.com/gh/tailhoogram/actions/workflows/lint.yml)

# TailHoogram

**Sends Tailscale events to Telegram using Cloudflare Workers**

Tailscale natively supports Slack, Discord, Google Chat, and Mattermost—but not Telegram. 

**TailHoogram bridges that gap with secure webhook processing**, sending the event to Telegram.
Can be deployed on Cloudflare Workers, even with the free tier.


## Quick Start

**Prerequisites:** Python 3.12+, `uv`, Tailscale account, Telegram bot token

```bash
# Install
uv sync --all-extras

# Configure (.env file)
TAILSCALE_WEBHOOK_SECRET=your-secret
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id

# Run locally with pywrangler
uv run pywrangler dev

# Deploy to Cloudflare Workers
uv run pywrangler secret put TAILSCALE_WEBHOOK_SECRET
uv run pywrangler secret put TELEGRAM_BOT_TOKEN
uv run pywrangler secret put TELEGRAM_CHAT_ID
uv run pywrangler deploy
```

Note: If you use linux secret service, namely `secret-tool`, you can skip the `.env` file step and use [secret-tool-run](https://go.hugobatista.com/gh/secret-tool-run) to automatically load secrets from your vault.

```bash
# Run with secrets from vault
secret-tool-run uv run pywrangler dev
```


**Tailscale Setup:**
1. Go to Tailscale admin → Webhooks
2. Create webhook pointing to `https://your-domain/events`
3. Copy the secret and set as `TAILSCALE_WEBHOOK_SECRET`
4. Hit "Test" to verify

## Testing locally  

Test your webhook endpoint locally using the included test script:

```bash
# Test default endpoint (localhost:8000)
python test-endpoint.py

# Test custom endpoint
python test-endpoint.py --endpoint example.com:8080
```

The script automatically loads `TAILSCALE_WEBHOOK_SECRET` from your `.env` file and sends a properly signed test webhook.

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TAILSCALE_WEBHOOK_SECRET` | Secret from Tailscale webhook setup | Yes |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | Yes |
| `TELEGRAM_CHAT_ID` | Target chat ID | Yes |

## Security

- **HMAC-SHA256 signature verification** on every webhook
- **Replay protection** (5-minute timestamp window)
- **Firewall recommendation:** Restrict to Tailscale IP ranges ([docs](https://tailscale.com/docs/reference/faq/firewall-ports))

## Example Notification

```
🔔 Tailscale Event

Type: policyUpdate
Tailnet: hugo-tailscale
Message: Tailnet policy file updated
Time: 2026-02-15T09:33:14.089607+00:00

Details:
  url: https://login.tailscale.com/admin/acls
  actor: hugobatista
```


## License

MIT
