import json
import re

from .config import Job
from .llm import LLM
from .log import log, step

STYLE = """
NARRATION RULES (sleep documentary, calm "boring history" style):
1. Second-person present tense. The listener is an invisible, completely safe observer drifting through the setting at night.
2. Low arousal only. Never use violent, alarming or loud words. Hardship is described with dry, understated, gentle wit.
3. Every paragraph weaves at least two soft sensory details (woodsmoke, beeswax, damp wool, rain on glass, quill on vellum, amber light).
4. Long, unhurried, flowing sentences. Occasional quiet humour about mundane routines.
5. Historically accurate, specific micro-details: names of tools, materials, prices, routines. No invented quotes.
6. Output ONLY spoken prose. No headings, no titles, no lists, no markdown, no stage directions, no [brackets].
""".strip()


def parse_json(raw: str) -> dict:
    from json_repair import repair_json

    s = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    i = s.find("{")
    out = repair_json(s[i:] if i >= 0 else s, return_objects=True)
    if isinstance(out, list):
        out = next((x for x in out if isinstance(x, dict)), {})
    if not isinstance(out, dict):
        raise ValueError("no JSON object in reply")
    return out


def _valid_json(key: str):
    def check(raw: str) -> bool:
        try:
            return bool(parse_json(raw).get(key))
        except Exception:
            return False
    return check


def clean_narration(raw: str) -> str:
    out = []
    for line in raw.splitlines():
        s = line.strip()
        is_heading = bool(re.match(r"^(chapter|part)\s+\w+[:.]?", s, re.I)) and len(s) < 80
        if not s or s.startswith(("#", "---", "***")) or is_heading:
            continue
        s = re.sub(r"\[[^\]]*\]|\([^)]*(pause|music|sound)[^)]*\)", "", s, flags=re.I)
        s = re.sub(r"[*_`>]+", "", s).strip()
        if s:
            out.append(s)
    return "\n\n".join(out)


def research(llm: LLM, job: Job) -> str:
    step("1/6 research")
    return llm.ask(
        f"You are the lead researcher for a calm, long-form history sleep documentary.\n"
        f"Topic: {job.topic}\n"
        f"List 80 specific, accurate, lesser-known micro-facts about lived daily and nightly reality: "
        f"architecture and lighting, heating, clothing and bedding, food and drink, trades and tools, "
        f"routines, rules, sounds, smells, weather and small superstitions. "
        f"Avoid battles and dramatic politics. One fact per line, plain text."
    )


def outline(llm: LLM, job: Job, notes: str) -> list[dict]:
    step(f"2/6 outline ({job.chapters} chapters)")
    chapters: list[dict] = []
    batch = 3
    while len(chapters) < job.chapters:
        n = min(batch, job.chapters - len(chapters))
        start = len(chapters) + 1
        used = "; ".join(c["title"] for c in chapters) or "none yet"
        raw = llm.ask(
            f"Plan chapters {start}-{start + n - 1} of a {job.chapters}-chapter sleep documentary titled "
            f"'{job.title}' about: {job.topic}.\n"
            f"Chapters already planned (do NOT repeat their place or routine): {used}.\n"
            f"Every chapter = one distinct physical space or nightly routine, in a gentle walking order.\n"
            f"Return JSON: {{\"chapters\": [{{\"title\": \"short evocative title\", "
            f"\"setting\": \"room, hour, weather, smells, sounds\", "
            f"\"facts\": \"6-10 micro-facts from the notes used ONLY in this chapter\", "
            f"\"bridge\": \"how the listener drifts to the next space\", "
            f"\"art_query\": \"2-4 word search for a matching public-domain museum painting\", "
            f"\"image_prompts\": [\"3 detailed scene descriptions\"]}}]}}\n"
            f"Each image prompt: one concrete scene, warm candle or lantern light, deep blue night shadows, "
            f"historical oil painting style, no people's faces in close-up, no text.\n\n"
            f"Research notes:\n{notes[:9000]}",
            json_mode=True,
            validate=_valid_json("chapters"),
        )
        got = parse_json(raw)["chapters"][:n]
        for c in got:
            c.setdefault("title", f"Chapter {len(chapters) + 1}")
            c.setdefault("image_prompts", [])
            chapters.append(c)
        log(f"  planned {len(chapters)}/{job.chapters}")
    return chapters


def write_chapter(llm: LLM, job: Job, ch: dict, idx: int, total: int, prev_tail: str) -> str:
    opening = (
        "Open with a slow, soothing induction: invite the listener to get comfortable, let the jaw soften, "
        "breathe out, and let the present day fade before stepping into the past."
        if idx == 1
        else f"Continue seamlessly from where the previous chapter ended, with no reset or greeting:\n\"{prev_tail}\""
    )
    closing = (
        "Slow down even further in the last two paragraphs, let the final candle dim, and leave the listener resting until morning."
        if idx == total
        else f"End with a gentle sensory transition toward: {ch.get('bridge', 'the next quiet room')}."
    )
    facts = ch.get("facts", "")
    if isinstance(facts, list):
        facts = "; ".join(map(str, facts))
    prompt = (
        f"Write chapter {idx} of {total}, '{ch['title']}', of the sleep documentary '{job.title}'.\n\n{STYLE}\n\n"
        f"Length: 1,000 to 1,200 words.\nSetting: {ch.get('setting', '')}\n"
        f"Use these facts (and only these): {facts}\n"
        f"Opening: {opening}\nClosing: {closing}\n\nBegin the narration now."
    )
    text = llm.ask(prompt, validate=lambda t: len(t.split()) >= 650)
    return clean_narration(text)


def metadata(llm: LLM, job: Job, chapters: list[dict]) -> dict:
    step("metadata")
    titles = "; ".join(c["title"] for c in chapters)
    try:
        raw = llm.ask(
            f"Write YouTube metadata for a long calm history sleep documentary titled '{job.title}' "
            f"about {job.topic}. Chapters: {titles}.\n"
            f"Return JSON: {{\"description\": \"3 short warm paragraphs, keyword-rich but natural, no timestamps, no hashtags\", "
            f"\"tags\": [\"15 search tags\"], \"thumbnail_text\": \"2-4 word hook in caps\"}}",
            json_mode=True,
            validate=_valid_json("description"),
        )
        meta = parse_json(raw)
    except Exception as e:
        log(f"  metadata fallback ({e})")
        meta = {}
    meta.setdefault("description", f"Drift into deep sleep with a slow, calm journey through {job.topic}.")
    meta.setdefault("tags", ["sleep", "history for sleep", "boring history", "sleep documentary", "bedtime story"])
    meta.setdefault("thumbnail_text", "FALL ASLEEP")
    meta["tags"] = [t[:30] for t in meta["tags"] if isinstance(t, str)][:20]
    return meta
