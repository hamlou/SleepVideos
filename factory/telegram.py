import html
import os

import requests

from .log import log

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def enabled() -> bool:
    return bool(TOKEN and CHAT)


def api(method: str, **params):
    if not TOKEN:
        return None
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", json=params, timeout=60)
    if r.status_code != 200:
        log(f"  telegram {method} HTTP {r.status_code}: {r.text[:200]}")
        return None
    return r.json().get("result")


def esc(s) -> str:
    return html.escape(str(s or ""))


def send(text: str, buttons: list[list[tuple[str, str]]] | None = None, chat: str | None = None):
    if not enabled():
        return None
    chunks, cur = [], ""
    for para in text.split("\n\n"):
        if len(cur) + len(para) + 2 > 3900:
            chunks.append(cur)
            cur = ""
        cur += ("\n\n" if cur else "") + para
    chunks.append(cur)
    res = None
    for i, c in enumerate(chunks):
        params = {"chat_id": chat or CHAT, "text": c, "parse_mode": "HTML", "disable_web_page_preview": True}
        if buttons and i == len(chunks) - 1:
            params["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in buttons]}
        res = api("sendMessage", **params)
    return res


def download(file_id: str) -> bytes:
    f = api("getFile", file_id=file_id)
    if not f:
        raise RuntimeError("telegram getFile failed")
    r = requests.get(f"https://api.telegram.org/file/bot{TOKEN}/{f['file_path']}", timeout=120)
    r.raise_for_status()
    return r.content
