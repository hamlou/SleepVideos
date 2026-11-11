import datetime as dt
import json
from pathlib import Path

DATA = Path("data")
VIDEOS = DATA / "videos"
QUEUE = DATA / "topic_queue.json"
PLAYBOOK = DATA / "playbook.json"
PENDING = DATA / "bot_pending.json"
REPORTS = DATA / "reports"
SETTINGS = DATA / "settings.json"
DEFAULT_SETTINGS = {"chapters": 18, "paused": False, "voice": "en-US-AndrewMultilingualNeural"}
MAX_QUEUE = 5

EMPTY_PLAYBOOK = {
    "version": 0,
    "updated": None,
    "videos_analyzed": 0,
    "topics_favor": [],
    "topics_avoid": [],
    "title_rules": [],
    "description_rules": [],
    "thumbnail_rules": [],
    "intro_rules": [],
    "script_rules": [],
    "notes": "No data yet. Follow the default style.",
}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def parse_time(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def settings() -> dict:
    return {**DEFAULT_SETTINGS, **read(SETTINGS, {})}


def playbook() -> dict:
    return {**EMPTY_PLAYBOOK, **read(PLAYBOOK, {})}


def playbook_text(keys: list[str]) -> str:
    pb = playbook()
    if not pb["videos_analyzed"]:
        return ""
    lines = [f"LESSONS FROM {pb['videos_analyzed']} ANALYZED VIDEOS OF THIS CHANNEL (follow them):"]
    for k in keys:
        if pb.get(k):
            lines.append(f"{k.replace('_', ' ')}: " + "; ".join(map(str, pb[k])))
    return "\n".join(lines) if len(lines) > 1 else ""


def video(vid: str) -> dict | None:
    return read(VIDEOS / f"{vid}.json", None)


def save_video(v: dict) -> None:
    write(VIDEOS / f"{v['id']}.json", v)
    write(DATA / "videos_index.json", [
        {"id": x["id"], "title": x.get("title", ""), "status": x.get("status"), "created": x.get("created"),
         "published": x.get("published"), "analyzed": x.get("analyzed"),
         "views": (x.get("stats") or {}).get("views"), "ctr": (x.get("stats") or {}).get("ctr_pct"),
         "verdict": (x.get("diagnosis") or {}).get("verdict")}
        for x in all_videos()
    ])


def all_videos() -> list[dict]:
    out = [read(p, None) for p in sorted(VIDEOS.glob("*.json"))] if VIDEOS.exists() else []
    return sorted((v for v in out if v), key=lambda v: v.get("created", ""))


def recent(field: str, n: int = 8) -> list[str]:
    return [v.get(field, "") for v in all_videos()[-n:] if v.get(field)]


def queue() -> list[dict]:
    return read(QUEUE, [])


def save_queue(q: list[dict]) -> None:
    write(QUEUE, q[:MAX_QUEUE])
