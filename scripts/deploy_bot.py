"""One-time setup: deploy the Telegram bot Worker to Cloudflare and connect everything.

Env: CF_ACCOUNT_ID, CF_WORKERS_TOKEN, TELEGRAM_BOT_TOKEN, BOT_GH_TOKEN (for the Worker),
     GH_ADMIN_TOKEN (to write GitHub secrets), GH_REPO (owner/repo). Optional TELEGRAM_CHAT_ID.
"""
import base64
import json
import os
import secrets
import sys
from pathlib import Path

import requests
from nacl import encoding, public

E = os.environ
CF = f"https://api.cloudflare.com/client/v4/accounts/{E['CF_ACCOUNT_ID']}"
CFH = {"Authorization": f"Bearer {E['CF_WORKERS_TOKEN']}"}
TG = f"https://api.telegram.org/bot{E['TELEGRAM_BOT_TOKEN']}"
REPO = E.get("GH_REPO", "hamlou/SleepVideos")
NAME = "sleep-factory-bot"


def ok(r, what):
    if r.status_code >= 300 or (r.headers.get("content-type", "").startswith("application/json") and r.json().get("success") is False):
        sys.exit(f"{what} failed: {r.status_code} {r.text[:400]}")
    print(f"✓ {what}")
    return r


def chat_id() -> str:
    if E.get("TELEGRAM_CHAT_ID"):
        return E["TELEGRAM_CHAT_ID"]
    requests.post(f"{TG}/deleteWebhook", timeout=30)
    ups = requests.get(f"{TG}/getUpdates", timeout=30).json().get("result", [])
    ids = [u["message"]["chat"]["id"] for u in ups if u.get("message")]
    if not ids:
        sys.exit("No message found: open your bot in Telegram, press Start (or send 'hi'), then run again.")
    return str(ids[-1])


def gh_secret(name: str, value: str) -> None:
    h = {"Authorization": f"Bearer {E['GH_ADMIN_TOKEN']}", "Accept": "application/vnd.github+json"}
    k = requests.get(f"https://api.github.com/repos/{REPO}/actions/secrets/public-key", headers=h, timeout=30).json()
    box = public.SealedBox(public.PublicKey(k["key"].encode(), encoding.Base64Encoder()))
    enc = base64.b64encode(box.encrypt(value.encode())).decode()
    ok(requests.put(f"https://api.github.com/repos/{REPO}/actions/secrets/{name}", headers=h,
                    json={"encrypted_value": enc, "key_id": k["key_id"]}, timeout=30), f"GitHub secret {name}")


def main():
    me = requests.get(f"{TG}/getMe", timeout=30).json()
    if not me.get("ok"):
        sys.exit("Telegram bot token is invalid.")
    print(f"✓ bot @{me['result']['username']}")
    chat = chat_id()
    print(f"✓ your chat id {chat}")
    hook_secret = secrets.token_urlsafe(24)

    code = (Path(__file__).resolve().parent.parent / "bot" / "worker.js").read_text(encoding="utf-8")
    meta = {"main_module": "worker.js", "compatibility_date": "2025-01-01",
            "bindings": [{"type": "plain_text", "name": "GH_REPO", "text": REPO}]}
    ok(requests.put(f"{CF}/workers/scripts/{NAME}", headers=CFH, files={
        "metadata": (None, json.dumps(meta), "application/json"),
        "worker.js": ("worker.js", code, "application/javascript+module"),
    }, timeout=60), "Worker uploaded")
    for k, v in {"TELEGRAM_BOT_TOKEN": E["TELEGRAM_BOT_TOKEN"], "TELEGRAM_CHAT_ID": chat,
                 "GH_TOKEN": E["BOT_GH_TOKEN"], "WEBHOOK_SECRET": hook_secret}.items():
        ok(requests.put(f"{CF}/workers/scripts/{NAME}/secrets", headers=CFH,
                        json={"name": k, "text": v, "type": "secret_text"}, timeout=30), f"Worker secret {k}")
    ok(requests.post(f"{CF}/workers/scripts/{NAME}/subdomain", headers=CFH, json={"enabled": True}, timeout=30), "workers.dev route")
    sub = requests.get(f"{CF}/workers/subdomain", headers=CFH, timeout=30).json().get("result", {}).get("subdomain")
    if not sub:
        sys.exit("Your Cloudflare account has no workers.dev subdomain yet: open dash.cloudflare.com → Workers once, then rerun.")
    url = f"https://{NAME}.{sub}.workers.dev"
    r = requests.post(f"{TG}/setWebhook", json={"url": url, "secret_token": hook_secret,
                                                 "allowed_updates": ["message", "callback_query"]}, timeout=30).json()
    if not r.get("ok"):
        sys.exit(f"setWebhook failed: {r}")
    print(f"✓ Telegram → {url}")
    requests.post(f"{TG}/setMyCommands", json={"commands": [{"command": "menu", "description": "Open the control panel"},
                                                             {"command": "cancel", "description": "Cancel what I'm waiting for"}]}, timeout=30)
    gh_secret("TELEGRAM_BOT_TOKEN", E["TELEGRAM_BOT_TOKEN"])
    gh_secret("TELEGRAM_CHAT_ID", chat)
    requests.post(f"{TG}/sendMessage", json={"chat_id": chat, "text": "✅ Sleep Factory bot is connected. Send /menu"}, timeout=30)
    print("ALL DONE")


if __name__ == "__main__":
    main()
