import json
import os
import subprocess
import sys
import urllib.request

from dotenv import load_dotenv


def configure_webhook(public_url: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Tunnel started; Telegram token is not configured, so the webhook was not changed.")
        return
    payload: dict[str, object] = {
        "url": f"{public_url}/telegram/webhook",
        "allowed_updates": ["message"],
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
        if not json.load(response).get("ok"):
            raise RuntimeError("Telegram rejected the webhook configuration")
    print(f"Webhook updated automatically: {payload['url']}")


def main() -> None:
    load_dotenv()
    command = ["npx.cmd" if os.name == "nt" else "npx", "--yes", "localtunnel", "--port", "8000"]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    try:
        assert process.stdout is not None
        for line in process.stdout:
            clean = line.strip()
            if clean:
                print(clean)
            marker = "your url is: "
            if marker in clean.lower():
                public_url = clean[clean.lower().index(marker) + len(marker) :].strip().rstrip("/")
                configure_webhook(public_url)
        raise SystemExit(process.wait())
    except KeyboardInterrupt:
        process.terminate()
        process.wait(timeout=5)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Could not start the development tunnel: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
