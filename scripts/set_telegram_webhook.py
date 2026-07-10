import argparse
import json
import os
import urllib.request

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Configure the Telegram webhook safely.")
    parser.add_argument("--url", required=True, help="Public HTTPS base URL")
    args = parser.parse_args()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not configured in .env")
    payload = {
        "url": f"{args.url.rstrip('/')}/telegram/webhook",
        "allowed_updates": ["message"],
        "drop_pending_updates": False,
    }
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if secret:
        payload["secret_token"] = secret
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/setWebhook",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        result = json.load(response)
    if not result.get("ok"):
        raise SystemExit("Telegram rejected the webhook configuration")
    print(f"Webhook configured: {payload['url']}")


if __name__ == "__main__":
    main()
