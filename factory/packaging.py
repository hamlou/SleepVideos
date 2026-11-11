import datetime as dt
from pathlib import Path

import requests

from . import media, state
from .config import Job, Settings
from .llm import LLM
from .log import log, step
from .script import parse_json

NICHE_QUERIES = ["boring history for sleep", "history for sleep", "sleep documentary history", "bedtime history story"]

FALLBACK_PATTERNS = [
    "Boring History For Sleep | Life in a Medieval Monastery at Night",
    "What Life Was Like in Ancient Rome After Dark | Sleep Documentary (3 Hours)",
    "Fall Asleep to the Quiet Life of a Victorian Lighthouse Keeper",
    "3 Hours of Cozy Medieval History to Fall Asleep To",
    "Why Medieval People Slept Twice a Night | Boring History for Sleep",
    "A Rainy Night in a 14th Century Village | History for Sleep",
    "The Most Boring Jobs in History (to fall asleep to)",
    "Sleep Like a Medieval Peasant | Calm History Documentary",
]


def niche_outliers(api_key: str, limit: int = 20) -> list[dict]:
    if not api_key:
        return []
    yt = "https://www.googleapis.com/youtube/v3"
    since = (dt.datetime.utcnow() - dt.timedelta(days=365)).strftime("%Y-%m-%dT00:00:00Z")
    ids: set[str] = set()
    for q in NICHE_QUERIES:
        r = requests.get(f"{yt}/search", params={
            "key": api_key, "q": q, "part": "id", "type": "video", "order": "viewCount",
            "videoDuration": "long", "publishedAfter": since, "maxResults": 25,
        }, timeout=30)
        r.raise_for_status()
        ids |= {i["id"]["videoId"] for i in r.json().get("items", [])}
    vids = []
    idl = list(ids)
    for i in range(0, len(idl), 50):
        r = requests.get(f"{yt}/videos", params={
            "key": api_key, "id": ",".join(idl[i:i + 50]), "part": "snippet,statistics",
        }, timeout=30)
        r.raise_for_status()
        vids += r.json().get("items", [])
    chans = list({v["snippet"]["channelId"] for v in vids})
    subs: dict[str, int] = {}
    for i in range(0, len(chans), 50):
        r = requests.get(f"{yt}/channels", params={
            "key": api_key, "id": ",".join(chans[i:i + 50]), "part": "statistics",
        }, timeout=30)
        r.raise_for_status()
        for c in r.json().get("items", []):
            subs[c["id"]] = int(c["statistics"].get("subscriberCount") or 0)
    out = []
    for v in vids:
        views = int(v["statistics"].get("viewCount") or 0)
        s = max(1000, subs.get(v["snippet"]["channelId"], 0))
        out.append({"title": v["snippet"]["title"], "views": views, "subs": s, "score": views / s})
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:limit]


def titles(llm: LLM, job: Job, chapters: list[dict], hours: float, refs: list[dict]) -> list[str]:
    step("titles")
    examples = "\n".join(f"- {r['title']}  ({r['views']:,} views, {r['score']:.1f}x channel size)" for r in refs) \
        or "\n".join(f"- {t}" for t in FALLBACK_PATTERNS)
    dur = f"{round(hours)} Hours" if hours >= 1.5 else f"{round(hours * 60)} Minutes"
    raw = llm.ask(
        f"You write YouTube titles for a calm 'history for sleep' channel.\n"
        f"Video topic: {job.topic}\nWorking title: {job.title}\nLength: {dur}\n"
        f"Chapters: {'; '.join(c['title'] for c in chapters)}\n\n"
        f"These are the best-performing titles in this niche right now (outliers = many views vs channel size):\n"
        f"{examples}\n\n"
        f"Study their structure (curiosity hook, 'for sleep' promise, duration, specific era/place). "
        f"Write 10 NEW titles for this video that copy those proven structures, not their words. "
        f"Rules: max 70 characters, accurate to the video content, no clickbait lies, no ALL CAPS words, nothing religious, "
        f"include the sleep promise, at least 4 include the length '({dur})'.\n"
        f"Then rank them by expected click-through for a sleepy viewer browsing at night.\n"
        f"Do NOT reuse the structure of these recent channel titles (variety avoids looking spammy):\n"
        + "\n".join(f"- {t}" for t in state.recent("title", 8)) + "\n"
        f"{state.playbook_text(['title_rules'])}\n"
        f'Return JSON: {{"ranked": ["best title", "...10 total"]}}',
        json_mode=True,
        validate=lambda t: len(parse_json(t).get("ranked", [])) >= 3,
    )
    ranked = [t.strip().strip('"') for t in parse_json(raw)["ranked"] if isinstance(t, str)]
    ranked = [t for t in ranked if 15 <= len(t) <= 100]
    return ranked[:10] or [job.title]


def thumbnail_brief(llm: LLM, job: Job, title: str, chapters: list[dict]) -> str:
    step("thumbnail master prompts")
    raw = llm.ask(
        f"You are a YouTube thumbnail art director for a calm 'history for sleep' channel.\n"
        f"Video title: {title}\nTopic: {job.topic}\nChapters: {'; '.join(c['title'] for c in chapters)}\n\n"
        f"{state.playbook_text(['thumbnail_rules'])}\n"
        f"Write 3 different thumbnail concepts. For each give:\n"
        f"- image_prompt: a complete, detailed prompt for an AI image tool (Midjourney / ChatGPT / Ideogram / Leonardo), "
        f"16:9, ONE clear focal subject placed on the right third, the left 40% dark and empty for text, cozy warm firelight "
        f"or lantern glow against deep night blue, painterly cinematic oil-painting style, high contrast so it reads at small size. "
        f"Describe ONLY what is visible (homes, fire, food, tools, weather, landscape); no towers, spires or places of worship; "
        f"no faces looking at camera; no text in the image.\n"
        f"- overlay_text: 2-4 words, max 18 characters, a specific TRUE curiosity hook from the topic, never repeating the title.\n"
        f"- design_notes: font style, text color, where to place it, one tip to make it pop.\n"
        f'Return JSON: {{"concepts": [{{"image_prompt": "...", "overlay_text": "...", "design_notes": "..."}}]}}',
        json_mode=True,
        validate=lambda t: len(parse_json(t).get("concepts", [])) >= 1,
    )
    concepts = parse_json(raw)["concepts"][:3]
    out = [f"# Thumbnail master prompts", "", f"**Video:** {title}", ""]
    for i, c in enumerate(concepts, 1):
        out += [f"## Concept {i}: \"{c.get('overlay_text', '')}\"", "", "**Image prompt (copy-paste):**", "```",
                str(c.get("image_prompt", "")).strip(), "```", "",
                f"**Text on thumbnail:** {c.get('overlay_text', '')}", "",
                f"**Design notes:** {c.get('design_notes', '')}", ""]
    log(f"  {len(concepts)} thumbnail concepts")
    return "\n".join(out)


def thumbnails(llm: LLM, imgs: media.Images, job: Job, title: str, fallback: Path | None, out: Path) -> list[Path]:
    step("thumbnails")
    try:
        raw = llm.ask(
            f"Design 3 different YouTube thumbnails for a calm history sleep video titled '{title}' about {job.topic}.\n"
            f"Proven sleep-niche style: ONE clear subject, cozy warm light against deep night blue, "
            f"lots of empty dark space on the left for text, no people looking at camera, painterly. Describe ONLY what is visible (homes, fire, food, tools, weather); never write 'no X' in a scene, and never include towers, spires or places of worship.\n"
            f"Text: 2-4 short words (max 18 characters total) that ADD a specific, TRUE curiosity hook drawn from "
            f"this topic's real details: a time, a number, an object or an odd custom. Never repeat the title. "
            f"Each of the 3 must use a different angle (time/number, odd fact, cozy promise).\n"
            f'Return JSON: {{"thumbs": [{{"scene": "image prompt, subject on right side", "text": "2-4 WORDS"}}]}}',
            json_mode=True,
            validate=lambda t: len(parse_json(t).get("thumbs", [])) >= 1,
        )
        concepts = parse_json(raw)["thumbs"][:3]
    except Exception as e:
        log(f"  thumbnail concepts fallback ({e})")
        concepts = [{"scene": job.topic, "text": "FALL ASLEEP"}]
    paths = []
    for i, c in enumerate(concepts, 1):
        base = out / f"thumb_base_{i}.jpg"
        prompt = f"{c.get('scene', job.topic)}, subject on the right third, dark empty left side, high contrast, glowing warm light"
        if not imgs.ai(prompt, 9000 + i, base, premium=True):
            if fallback is None:
                continue
            base = fallback
        dest = out / f"thumbnail_{i}.jpg"
        media.thumbnail(base, str(c.get("text", "FALL ASLEEP")), dest)
        paths.append(dest)
        if base != fallback:
            base.unlink(missing_ok=True)
    log(f"  {len(paths)} thumbnails")
    return paths


def review_sheet(out: Path, ranked: list[str], brief: str, refs: list[dict], vid: str | None) -> None:
    lines = ["# Review before publishing", ""]
    if vid:
        lines += [f"Studio: https://studio.youtube.com/video/{vid}/edit", ""]
    lines += ["## Titles (best first) — top 3 go into Test & Compare", ""]
    lines += [f"{i}. {t}" for i, t in enumerate(ranked, 1)]
    lines += ["", brief.replace("# Thumbnail master prompts", "## Thumbnail master prompts")]
    if refs:
        lines += ["", "## Niche outliers used as reference", ""]
        lines += [f"- {r['title']} — {r['views']:,} views, {r['score']:.1f}x" for r in refs]
    lines += ["", "## Publish checklist",
              "1. Skim the video (voice, images, no glitches)",
              "2. Make the thumbnail from a concept above, upload it, add titles 1-3 to Test & Compare",
              "3. Visibility → Schedule (evening in your audience's timezone)"]
    (out / "REVIEW.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
