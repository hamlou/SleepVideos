import json
import shutil
import sys
import tempfile
from pathlib import Path

import requests

from . import audio, broll, media, packaging, script, youtube
from .config import Settings, load_job, mark_queue_done
from .llm import LLM
from .log import log, step

GAP = 2.5
INTRO_CUTS = 20
INTRO_CUT_SEC = 6.0
STOCK_SEC = 8.0
INTRO_MOTIONS = ["pan_lr", "push", "pan_rl", "tilt_up", "pull"]
GENERIC_ART = ["candlelight interior", "moonlight landscape", "night scene", "evening interior",
               "quiet library", "winter evening", "rain landscape", "fireside"]


def ts(sec: float, long: bool) -> str:
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if long else f"{m:02d}:{s:02d}"


def write_out(out: Path, name: str, data) -> None:
    p = out / name
    p.write_text(data if isinstance(data, str) else json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def run() -> int:
    s = Settings()
    s.out_dir.mkdir(parents=True, exist_ok=True)
    media.ensure_tools()
    job = load_job()
    if not job:
        log("No job: topics.txt queue empty and no VIDEO_TITLE/TOPIC_LENS given. Nothing to do.")
        return 0
    log(f"JOB: {job.title} | {job.chapters} chapters | voice {job.voice} | privacy {job.privacy}")
    write_out(s.out_dir, "job.json", job.__dict__)
    youtube.check_auth(s)

    llm = LLM(s)
    work = Path(tempfile.mkdtemp(prefix="sleep_"))
    try:
        notes = script.research(llm, job)
        write_out(s.out_dir, "research.txt", notes)
        chapters = script.outline(llm, job, notes)
        write_out(s.out_dir, "outline.json", chapters)

        step("titles + thumbnail prompts")
        imgs = media.Images(s)
        try:
            refs = packaging.niche_outliers(s.yt_api_key)
            log(f"  {len(refs)} niche outliers" if refs else "  no YOUTUBE_API_KEY → built-in title patterns")
        except Exception as e:
            log(f"  niche research failed ({str(e)[:150]})")
            refs = []
        try:
            ranked = packaging.titles(llm, job, chapters, job.chapters * 11.5 / 60, refs)
        except Exception as e:
            log(f"  title generation failed ({e})")
            ranked = [job.title]
        title = ranked[0]
        try:
            brief = packaging.thumbnail_brief(llm, job, title, chapters)
        except Exception as e:
            log(f"  thumbnail brief failed ({e})")
            brief = "(thumbnail brief unavailable)"
        write_out(s.out_dir, "THUMBNAIL_PROMPTS.md", brief)

        step(f"3/6 scripts + voice + images ({len(chapters)} chapters)")
        voice = audio.Voice(job.voice, s.azure_key, s.azure_region)
        gap_mp3 = work / "gap.mp3"
        media.silence(gap_mp3, GAP)
        voice_files: list[Path] = []
        durations: list[float] = []
        chapter_imgs: list[list[Path]] = []
        full_script: list[str] = []
        tail = ""
        for i, ch in enumerate(chapters, 1):
            log(f"chapter {i}/{len(chapters)}: {ch['title']}")
            text = script.write_chapter(llm, job, ch, i, len(chapters), tail)
            tail = " ".join(text.split()[-50:])
            full_script.append(f"## {i}. {ch['title']}\n\n{text}")
            write_out(s.out_dir, "script.md", f"# {job.title}\n\n" + "\n\n".join(full_script))
            log(f"  {len(text.split())} words")

            vo = work / f"vo_{i:03d}.mp3"
            dur = voice.chapter(text, work, f"c{i:03d}", vo)
            voice_files.append(vo)
            durations.append(dur + (GAP if i < len(chapters) else 0))
            log(f"  voice {dur / 60:.1f} min")

            got: list[Path] = []
            for k, prompt in enumerate(ch.get("image_prompts", [])[:2]):
                dest = work / f"img_{i:03d}_{k}.jpg"
                if imgs.ai(prompt, i * 100 + k, dest):
                    got.append(dest)
            for k in range(3 - len(got)):
                dest = work / f"img_{i:03d}_art{k}.jpg"
                q = ch.get("art_query") or " ".join(job.topic.split()[:3])
                for query in (q, " ".join(q.split()[:2]), GENERIC_ART[(i + k) % len(GENERIC_ART)]):
                    if imgs.painting(query, dest):
                        got.append(dest)
                        break
            if not got:
                dest = work / f"img_{i:03d}_fb.jpg"
                imgs.fallback(dest, i)
                got.append(dest)
            chapter_imgs.append(got)
            log(f"  {len(got)} images")

        step("4/6 audio master")
        vlist = work / "voice.txt"
        entries = []
        for i, vo in enumerate(voice_files):
            entries.append(vo)
            if i < len(voice_files) - 1:
                entries.append(gap_mp3)
        vlist.write_text("".join(f"file '{p.as_posix()}'\n" for p in entries), encoding="utf-8")
        master = work / "master.m4a"
        audio.master(vlist, sum(durations), work, master, seed=len(job.title))
        durations[0] += audio.LEAD_IN
        durations[-1] += audio.TAIL
        total = media.duration(master)
        log(f"  total {total / 60:.1f} min")

        step("5/6 visuals")
        overlay = work / "particles.mp4"
        media.particles(overlay, s.fps)
        flat = [p for group in chapter_imgs for p in group]
        stock = broll.Broll(s.pixabay_key, work, s.fps, seed=len(job.title))
        stock.fetch(7)
        intro_n = min(INTRO_CUTS, int(min(durations[0] - 20, total * 0.25) // INTRO_CUT_SEC)) if durations[0] > 40 else 0
        jobs, segs = [], []
        for k in range(intro_n):
            dest = work / f"seg_intro_{k:03d}.mp4"
            if k % 2 == 1 and stock.clip(INTRO_CUT_SEC, dest):
                segs.append(dest)
                continue
            jobs.append(dict(image=flat[k % len(flat)], sec=INTRO_CUT_SEC, dest=dest, overlay=overlay, fps=s.fps,
                             motion=INTRO_MOTIONS[k % len(INTRO_MOTIONS)]))
            segs.append(dest)
        for i, (ch, dur, group) in enumerate(zip(chapters, durations, chapter_imgs), 1):
            vis = dur - intro_n * INTRO_CUT_SEC if i == 1 else dur
            opener = work / f"seg_{i:03d}_stock.mp4"
            if i > 1 and vis > 60 and stock.clip(STOCK_SEC, opener):
                segs.append(opener)
                vis -= STOCK_SEC
            per = vis / len(group)
            for k, img in enumerate(group):
                dest = work / f"seg_{i:03d}_{k}.mp4"
                label = f"Chapter {i}  -  {ch['title']}" if k == 0 else ""
                jobs.append(dict(image=img, sec=per, dest=dest, overlay=overlay, fps=s.fps, label=label))
                segs.append(dest)
        log(f"  rendering {len(jobs)} segments")
        media.render_parallel(jobs)
        slist = work / "segs.txt"
        slist.write_text("".join(f"file '{p.as_posix()}'\n" for p in segs), encoding="utf-8")
        final = work / "final.mp4"
        media.mux(slist, master, final)
        log(f"  final {final.stat().st_size / 1e9:.2f} GB, {media.duration(final) / 60:.1f} min")

        step("6/6 publish")
        meta = script.metadata(llm, job, chapters)
        long = total >= 3600
        clock, marks = 0.0, []
        for ch, dur in zip(chapters, durations):
            marks.append(f"{ts(clock, long)} {ch['title']}")
            clock += dur
        credits = "\n".join(f"• {c}" for c in imgs.credits[:25])
        description = (
            f"{meta['description'].strip()}\n\n"
            f"🕯️ Chapters\n" + "\n".join(marks) + "\n\n"
            "Narration voice is synthetic. Script researched and written with AI assistance, then reviewed. "
            "Visuals are AI-generated paintings and public-domain artworks.\n"
            + (f"\nArtwork credits:\n{credits}\n" if credits else "")
            + f"\n{audio.FIRE_CREDIT}\n"
            + (f"{broll.CREDIT}\n" if stock.sources else "")
            + "\n#sleep #history #sleepstory"
        )
        write_out(s.out_dir, "metadata.json", {**meta, "title": title, "title_options": ranked,
                                                "reference_outliers": refs, "description_full": description})

        vid = None
        if s.youtube_ready:
            vid = youtube.upload(s, final, None, title, description, meta["tags"], job.privacy)
        else:
            shutil.move(str(final), s.out_dir / "video.mp4")
            log("  saved out/video.mp4 (no YouTube secrets)")
        packaging.review_sheet(s.out_dir, ranked, brief, refs, vid)

        if s.callback_url:
            try:
                requests.post(s.callback_url, json={
                    "status": "completed", "sheet_row_id": job.sheet_row, "title": title, "title_options": ranked[:3],
                    "thumbnail_prompts": brief,
                    "duration_hours": round(total / 3600, 2), "youtube_video_id": vid,
                    "youtube_studio_url": f"https://studio.youtube.com/video/{vid}/edit" if vid else None,
                }, timeout=30)
            except Exception as e:
                log(f"  callback failed: {e}")
        if job.from_queue:
            mark_queue_done(job.title)
        write_out(s.out_dir, "result.json", {"youtube_id": vid, "minutes": round(total / 60, 1)})
        log("DONE ✓")
        return 0
    except Exception:
        if s.callback_url:
            try:
                requests.post(s.callback_url, json={"status": "failed", "sheet_row_id": job.sheet_row, "title": job.title}, timeout=30)
            except Exception:
                pass
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(run())
