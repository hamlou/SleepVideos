import re

from . import state
from .config import DONE_FILE, QUEUE_FILE
from .llm import LLM
from .log import log, step
from .script import parse_json

RULES = (
    "Everyday life in a specific place and era, at night or in the evening: homes, food, crafts, trades, travel, "
    "weather, nature, small routines. Strictly NO religion of any kind (no churches, mosques, temples, "
    "monasteries, clergy, prayer, gods, holy days), no wars, battles, disasters, crime or death."
)


def _manual() -> dict | None:
    if not QUEUE_FILE.exists():
        return None
    lines = QUEUE_FILE.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not s.startswith("#") and "|" in s:
            title, topic = (p.strip() for p in s.split("|", 1))
            QUEUE_FILE.write_text("\n".join(lines[:i] + lines[i + 1:]) + "\n", encoding="utf-8")
            return {"title": title, "topic": topic, "source": "manual"}
    return None


def _done_titles() -> list[str]:
    done = [d.split("|")[0].strip() for d in DONE_FILE.read_text(encoding="utf-8").splitlines()] if DONE_FILE.exists() else []
    return done + [v.get("working_title", v.get("title", "")) for v in state.all_videos()]


def generate(llm: LLM, n: int, avoid: list[str]) -> list[dict]:
    if n <= 0:
        return []
    lessons = state.playbook_text(["topics_favor", "topics_avoid"])
    used = "\n".join(f"- {t}" for t in avoid[-80:] if t) or "- none yet"
    raw = llm.ask(
        f"Plan {n} new topics for a calm 'history for sleep' YouTube channel (2-3 hour slow narrated videos).\n"
        f"{RULES}\nVary eras and world regions, but lean toward what the lessons say works.\n"
        f"{lessons}\n\nAlready made or planned (never repeat or closely resemble):\n{used}\n\n"
        f'Return JSON: {{"topics": [{{"title": "short evocative working title, max 60 chars", '
        f'"topic": "one line with place, century and 5-6 concrete everyday subjects", '
        f'"why": "one short reason this should perform well"}}]}}',
        json_mode=True,
        validate=lambda t: len(parse_json(t).get("topics", [])) >= 1,
    )
    out = []
    for t in parse_json(raw)["topics"][:n]:
        title = re.sub(r"[|\n]", " ", str(t.get("title", ""))).strip()[:80]
        topic = re.sub(r"[|\n]", " ", str(t.get("topic", ""))).strip()
        if title and topic:
            out.append({"title": title, "topic": topic, "why": str(t.get("why", "")), "source": "planner",
                        "playbook_version": state.playbook()["version"]})
    return out


def refill(llm: LLM) -> list[dict]:
    q = state.queue()
    missing = state.MAX_QUEUE - len(q)
    if missing > 0:
        q += generate(llm, missing, _done_titles() + [x["title"] for x in q])
        state.save_queue(q)
        log(f"  topic queue: {len(q)}/{state.MAX_QUEUE}")
    return q


def replan(llm: LLM) -> list[dict]:
    step("re-planning topics with the new playbook")
    state.save_queue([])
    return refill(llm)


def next_topic(llm: LLM) -> dict:
    m = _manual()
    if m:
        log(f"  manual topic from topics.txt: {m['title']}")
        return m
    q = state.queue()
    if not q:
        q = refill(llm)
    pick, rest = q[0], q[1:]
    state.save_queue(rest)
    return pick


def mark_done(title: str, topic: str) -> None:
    with DONE_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{title} | {topic}\n")
