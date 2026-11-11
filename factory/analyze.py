"""72h-after-publish analysis → per-video diagnosis → playbook update → topic re-plan."""
import datetime as dt
import json
import sys

from . import state, telegram, topics, youtube
from .config import Settings
from .llm import LLM
from .log import log, step
from .script import parse_json

WAIT_HOURS = 72


def _ts(sec: float) -> str:
    h, r = divmod(int(sec), 3600)
    return f"{h}:{r // 60:02d}:{r % 60:02d}"


def retention_summary(v: dict, ret: list[dict]) -> dict:
    if not ret:
        return {}
    dur = v.get("duration_sec") or 1
    pts = sorted((float(r["elapsedVideoTimeRatio"]), float(r["audienceWatchRatio"]),
                  float(r.get("relativeRetentionPerformance") or 0)) for r in ret)

    def at(sec):
        ratio = sec / dur
        return round(min(pts, key=lambda p: abs(p[0] - ratio))[1] * 100, 1)

    drops = sorted(((pts[i][1] - pts[i + 1][1], pts[i][0]) for i in range(len(pts) - 1)), reverse=True)[:5]
    chap = v.get("chapters", [])

    def chapter_at(ratio):
        t = ratio * dur
        cur = None
        for c in chap:
            if c["start"] <= t:
                cur = c["title"]
        return cur

    return {
        "still_watching_pct": {"30s": at(30), "1min": at(60), "2min": at(120), "5min": at(300),
                               "15min": at(900), "30min": at(1800), "60min": at(3600)},
        "biggest_drops": [{"at": _ts(r * dur), "lost_pct": round(d * 100, 1), "chapter": chapter_at(r)} for d, r in drops if d > 0],
        "relative_to_similar_videos_avg": round(sum(p[2] for p in pts) / len(pts), 2),
    }


def collect(s: Settings, v: dict) -> dict:
    pub = state.parse_time(v["published"])
    raw = youtube.analytics(s, v["id"], pub)
    core, imp = raw["core"], raw["impressions"]
    return {
        "hours_live": round((dt.datetime.now(dt.timezone.utc) - pub).total_seconds() / 3600),
        "views": core.get("views"),
        "watch_hours": round((core.get("estimatedMinutesWatched") or 0) / 60, 1),
        "avg_view_minutes": round((core.get("averageViewDuration") or 0) / 60, 1),
        "avg_view_pct": core.get("averageViewPercentage"),
        "likes": core.get("likes"), "subs_gained": core.get("subscribersGained"),
        "impressions": imp.get("videoThumbnailImpressions"),
        "ctr_pct": imp.get("videoThumbnailImpressionsClickRate"),
        "traffic": {t["insightTrafficSourceType"]: t["views"] for t in raw["traffic"][:6]},
        "retention": retention_summary(v, raw["retention"]),
    }


def diagnose(llm: LLM, v: dict, data: dict, history: list[dict]) -> dict:
    past = [{"title": h["title"], "topic": h["topic"][:120], "thumb_concept": h.get("thumb_concept"),
             **{k: h["stats"].get(k) for k in ("views", "ctr_pct", "avg_view_pct", "impressions")}}
            for h in history if h.get("stats") and h["id"] != v["id"]][-15:]
    brief = v.get("thumbnail_brief", "")
    concept = v.get("thumb_concept")
    used = next((c for c in brief.split("## Concept ")[1:] if c.startswith(f"{concept}:")), "") if concept else ""
    raw = llm.ask(
        "You are a YouTube growth analyst for a calm 'history for sleep' channel (2-3 hour narrated videos).\n"
        "Sleep-niche context: good CTR is 4-10%; average view % is naturally low for 3-hour videos because people "
        "fall asleep (10-25% is normal, above 25% is great); the first 2 minutes decide retention; sleepers keep "
        "the video playing, so long watch time is the goal. Small channels get few impressions at first, so be careful "
        "not to over-read tiny numbers.\n\n"
        f"VIDEO: {v['title']}\nTOPIC: {v['topic']}\nPLAYBOOK VERSION USED: v{v.get('playbook_version')}\n"
        f"THUMBNAIL CONCEPT USED: {used[:600] or concept}\n"
        f"CHAPTERS: {json.dumps(v.get('chapters', [])[:20])}\n"
        f"STATS AFTER {data['hours_live']}h PUBLIC: {json.dumps({k: v2 for k, v2 in data.items() if k != 'hours_live'})}\n"
        f"OTHER VIDEOS OF THIS CHANNEL: {json.dumps(past)}\n\n"
        "Diagnose: did people not CLICK (impressions vs CTR → title/thumbnail problem), or click and LEAVE "
        "(retention → hook/intro/pacing/topic problem), or both? Where exactly did they leave and why might that be?\n"
        'Return JSON: {"verdict": "worked | average | did not work | too early to tell", '
        '"click_problem": "...", "retention_problem": "...", "what_worked": ["..."], "what_failed": ["..."], '
        '"lessons": {"topics_favor": [], "topics_avoid": [], "title_rules": [], "description_rules": [], '
        '"thumbnail_rules": [], "intro_rules": [], "script_rules": []}, "summary_for_owner": "4-6 plain sentences"}',
        json_mode=True,
        validate=lambda t: bool(parse_json(t).get("verdict")),
    )
    return parse_json(raw)


def update_playbook(llm: LLM, reports: list[dict]) -> dict:
    old = state.playbook()
    analyzed = [v for v in state.all_videos() if v.get("stats")]
    table = [{"title": v["title"], "topic": v["topic"][:100], "verdict": v.get("diagnosis", {}).get("verdict"),
              **{k: v["stats"].get(k) for k in ("views", "ctr_pct", "avg_view_pct", "watch_hours")}} for v in analyzed]
    raw = llm.ask(
        "You maintain the PLAYBOOK of a 'history for sleep' YouTube channel: short, concrete rules that the "
        "automated video pipeline follows for topics, titles, descriptions, thumbnail prompts, intros and scripts.\n"
        f"CURRENT PLAYBOOK: {json.dumps({k: old[k] for k in state.EMPTY_PLAYBOOK if k not in ('version', 'updated')})}\n"
        f"ALL ANALYZED VIDEOS: {json.dumps(table)}\n"
        f"NEW DIAGNOSES: {json.dumps([r.get('lessons', {}) | {'verdict': r.get('verdict')} for r in reports])}\n\n"
        "Update the playbook. KEEP rules that results support, REMOVE or soften rules contradicted by results, ADD "
        "rules only with evidence. With fewer than 5 analyzed videos, prefer small cautious changes and mark them "
        "'(tentative)'. Max 6 rules per list, each under 25 words, concrete and actionable. Never add anything "
        "religious. Keep the channel identity: calm, cozy, second-person, everyday historical life.\n"
        'Return JSON with exactly these keys: {"topics_favor": [], "topics_avoid": [], "title_rules": [], '
        '"description_rules": [], "thumbnail_rules": [], "intro_rules": [], "script_rules": [], '
        '"notes": "2-3 sentences on the current strategy", "changes": ["what changed and why"]}',
        json_mode=True,
        validate=lambda t: "title_rules" in parse_json(t),
    )
    new = parse_json(raw)
    pb = {**old, **{k: new.get(k, old[k]) for k in state.EMPTY_PLAYBOOK if k not in ("version", "updated", "videos_analyzed")}}
    pb.update(version=old["version"] + 1, updated=state.now(), videos_analyzed=len(analyzed))
    state.write(state.REPORTS / f"playbook_v{pb['version']}.json", {**pb, "changes": new.get("changes", [])})
    state.write(state.PLAYBOOK, pb)
    return {**pb, "changes": new.get("changes", [])}


def due(force: bool) -> list[dict]:
    out = []
    for v in state.all_videos():
        if v.get("status") != "public" or v.get("analyzed") or not v.get("published"):
            continue
        age = (dt.datetime.now(dt.timezone.utc) - state.parse_time(v["published"])).total_seconds() / 3600
        if force or age >= WAIT_HOURS:
            out.append(v)
    return out


def run(force: bool = False) -> int:
    s = Settings()
    todo = due(force)
    if not todo:
        log("nothing to analyze yet")
        if force:
            telegram.send("🔍 Nothing to analyze: no public video is old enough yet.")
        return 0
    llm = LLM(s)
    history, reports = state.all_videos(), []
    for v in todo:
        step(f"analyzing {v['id']} · {v['title']}")
        data = collect(s, v)
        diag = diagnose(llm, v, data, history)
        v.update(stats=data, diagnosis=diag, analyzed=state.now())
        state.save_video(v)
        reports.append(diag)
        st = data
        telegram.send(
            f"📈 <b>72h report</b>: {telegram.esc(v['title'])}\n"
            f"Verdict: <b>{telegram.esc(diag.get('verdict'))}</b>\n"
            f"Views {st.get('views')} · CTR {st.get('ctr_pct')}% · impressions {st.get('impressions')} · "
            f"avg viewed {st.get('avg_view_pct')}% · watch {st.get('watch_hours')} h · subs +{st.get('subs_gained')}\n\n"
            f"{telegram.esc(diag.get('summary_for_owner', ''))}\n\n"
            f"👍 {telegram.esc('; '.join(diag.get('what_worked', [])[:3]))}\n"
            f"👎 {telegram.esc('; '.join(diag.get('what_failed', [])[:3]))}"
        )
    pb = update_playbook(llm, reports)
    telegram.send(
        f"🧠 <b>Playbook v{pb['version']}</b> ({pb['videos_analyzed']} videos analyzed)\n"
        + "\n".join(f"• {telegram.esc(c)}" for c in pb.get("changes", [])[:8])
        + f"\n\n{telegram.esc(pb.get('notes', ''))}"
    )
    q = topics.replan(llm)
    telegram.send("🗂 Topics re-planned with the new playbook:\n" + "\n".join(f"{i}. {telegram.esc(t['title'])}" for i, t in enumerate(q, 1)))
    return 0


if __name__ == "__main__":
    sys.exit(run(force="--force" in sys.argv))
