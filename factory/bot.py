"""Heavy bot actions dispatched by the Cloudflare Worker (repository_dispatch: bot_action)."""
import json
import os
import sys
import tempfile
from pathlib import Path

from . import state, telegram, topics, youtube
from .config import Settings
from .llm import LLM
from .log import log


def _jpeg(raw: bytes, dest: Path) -> Path:
    from PIL import Image

    src = dest.with_suffix(".src")
    src.write_bytes(raw)
    img = Image.open(src).convert("RGB")
    img.thumbnail((1280, 1280))
    if abs(img.width / img.height - 16 / 9) > 0.05:
        w, h = img.size
        tw, th = (w, int(w * 9 / 16)) if w / h < 16 / 9 else (int(h * 16 / 9), h)
        img = img.crop(((w - tw) // 2, (h - th) // 2, (w + tw) // 2, (h + th) // 2))
    q = 92
    while True:
        img.save(dest, "JPEG", quality=q)
        if dest.stat().st_size < 2_000_000 or q < 50:
            return dest
        q -= 8


def thumbnail(s: Settings, vid: str, file_id: str, concept: str) -> None:
    v = state.video(vid)
    if not v:
        telegram.send(f"⚠️ I don't know video {vid}.")
        return
    with tempfile.TemporaryDirectory() as d:
        img = _jpeg(telegram.download(file_id), Path(d) / "thumb.jpg")
        youtube.set_thumbnail(s, vid, img)
    youtube.publish(s, vid)
    v.update(status="public", published=state.now(), thumb_concept=concept)
    state.save_video(v)
    telegram.send(f"🚀 <b>Live!</b> {telegram.esc(v['title'])}\nhttps://youtu.be/{vid}\n"
                  f"Thumbnail = concept {concept}. I'll analyze it 72h from now.")


def publish(s: Settings, vid: str) -> None:
    v = state.video(vid)
    youtube.publish(s, vid)
    v.update(status="public", published=state.now(), thumb_concept="none")
    state.save_video(v)
    telegram.send(f"🚀 <b>Live without custom thumbnail</b>\nhttps://youtu.be/{vid}")


def edit_meta(s: Settings, vid: str, field: str, value: str) -> None:
    v = state.video(vid)
    yt = youtube._service(s)
    cur = yt.videos().list(part="snippet", id=vid).execute()["items"][0]["snippet"]
    snip = {k: cur[k] for k in ("title", "description", "categoryId", "tags", "defaultLanguage") if k in cur}
    snip[field] = value[:100] if field == "title" else value[:4990]
    yt.videos().update(part="snippet", body={"id": vid, "snippet": snip}).execute()
    v[field] = snip[field]
    v.setdefault("edits", []).append({"field": field, "at": state.now()})
    state.save_video(v)
    telegram.send(f"✏️ {field.capitalize()} updated on YouTube.")


def replan(s: Settings) -> None:
    q = topics.replan(LLM(s))
    telegram.send("🗂 New topic plan:\n" + "\n".join(f"{i}. {telegram.esc(t['title'])}" for i, t in enumerate(q, 1)))


def main() -> int:
    payload = json.loads(os.environ.get("BOT_PAYLOAD") or "{}")
    action = payload.get("action")
    s = Settings()
    log(f"bot action: {action}")
    try:
        if action == "thumbnail":
            thumbnail(s, payload["vid"], payload["file_id"], str(payload.get("concept", "?")))
        elif action == "publish":
            publish(s, payload["vid"])
        elif action == "edit":
            edit_meta(s, payload["vid"], payload["field"], payload["value"])
        elif action == "replan":
            replan(s)
        else:
            log("unknown action")
    except Exception as e:
        telegram.send(f"❌ Action <b>{telegram.esc(action)}</b> failed:\n<code>{telegram.esc(str(e)[:500])}</code>")
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
