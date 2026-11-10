import asyncio
import base64
import random
import re
import shutil
import subprocess
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from .config import Settings
from .log import log

UA = {"User-Agent": "SleepVideosFactory/2.0 (+https://github.com)"}
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "C:/Windows/Fonts/georgiab.ttf",
]
X264 = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", "-video_track_timescale", "30000"]


def ff(*args: str) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)[:400]}\n{r.stderr[-1500:]}")


def duration(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], text=True
    )
    return float(out.strip())


def font() -> str | None:
    f = next((f for f in FONT_CANDIDATES if Path(f).exists()), None)
    return f.replace(":", "\\:") if f else None


def _esc(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9 .!?&\-]", "", text)


class Images:
    def __init__(self, s: Settings):
        self.s = s
        self.ai_dead: set[str] = set()
        self.art_seen: set[str] = set()
        self.credits: list[str] = []

    def _cloudflare(self, prompt: str, seed: int) -> bytes | None:
        if not (self.s.cf_account and self.s.cf_token):
            return None
        r = requests.post(
            f"https://api.cloudflare.com/client/v4/accounts/{self.s.cf_account}/ai/run/@cf/black-forest-labs/flux-1-schnell",
            headers={"Authorization": f"Bearer {self.s.cf_token}"},
            json={"prompt": prompt, "steps": 8, "seed": seed},
            timeout=120,
        )
        if r.status_code in (401, 402, 403, 429):
            self.ai_dead.add("cloudflare")
            log(f"  cloudflare images disabled (HTTP {r.status_code})")
            return None
        r.raise_for_status()
        return base64.b64decode(r.json()["result"]["image"])

    def _pollinations(self, prompt: str, seed: int) -> bytes | None:
        url = (
            f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}"
            f"?width=1920&height=1080&model=flux&nologo=true&seed={seed}"
        )
        hdr = {**UA, **({"Authorization": f"Bearer {self.s.pollinations_token}"} if self.s.pollinations_token else {})}
        gap = 16 - (time.time() - getattr(self, "_poll_last", 0))
        if not self.s.pollinations_token and gap > 0:
            time.sleep(gap)
        self._poll_last = time.time()
        r = requests.get(url, headers=hdr, timeout=150)
        if r.status_code in (401, 403) or (r.status_code == 402 and "FREE_LIMIT" not in r.text):
            self.ai_dead.add("pollinations")
            log(f"  pollinations images disabled (HTTP {r.status_code})")
            return None
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("image") and len(r.content) > 20000:
            return r.content
        log(f"  pollinations image HTTP {r.status_code} {r.headers.get('content-type', '')} {len(r.content)}B")
        return None

    def ai(self, prompt: str, seed: int, dest: Path) -> bool:
        full = f"{prompt}, wide cinematic composition, rich oil painting, warm candlelight, deep blue shadows, no text, no watermark"
        for name, fn in (("cloudflare", self._cloudflare), ("pollinations", self._pollinations)):
            if name in self.ai_dead:
                continue
            for attempt in range(3):
                try:
                    data = fn(full, seed)
                    if data:
                        raw = dest.with_suffix(".src")
                        raw.write_bytes(data)
                        normalize(raw, dest, cover=True)
                        raw.unlink(missing_ok=True)
                        return True
                    if name in self.ai_dead:
                        break
                except Exception as e:
                    log(f"  {name} image try {attempt + 1}: {str(e)[:120]}")
                time.sleep((4 * (attempt + 1)))
        return False

    def painting(self, query: str, dest: Path) -> bool:
        met = "https://collectionapi.metmuseum.org/public/collection"
        try:
            r = requests.get(
                f"{met}/v1.1/search",
                params={"q": query, "hasImages": "true", "isPublicDomain": "true", "limit": 25},
                headers=UA,
                timeout=30,
            )
            r.raise_for_status()
            ids = [i for i in (r.json().get("objectIDs") or []) if str(i) not in self.art_seen]
            objs = []
            for oid in ids[:12]:
                o = requests.get(f"{met}/v1/objects/{oid}", headers=UA, timeout=30)
                if o.status_code == 200:
                    d = o.json()
                    if d.get("isPublicDomain") and (d.get("primaryImage") or d.get("primaryImageSmall")):
                        objs.append(d)
            objs.sort(key=lambda d: d.get("classification") not in ("Paintings", "Drawings"))
            for d in objs:
                img = requests.get(d.get("primaryImage") or d["primaryImageSmall"], headers=UA, timeout=90)
                if img.status_code != 200 or len(img.content) < 20000:
                    continue
                self.art_seen.add(str(d["objectID"]))
                raw = dest.with_suffix(".src")
                raw.write_bytes(img.content)
                normalize(raw, dest, cover=False)
                raw.unlink(missing_ok=True)
                self.credits.append(
                    f"{d.get('title')} - {d.get('artistDisplayName') or 'Unknown artist'} "
                    f"({d.get('objectDate') or 'n.d.'}), The Metropolitan Museum of Art, Public Domain"
                )
                return True
            log(f"  no usable painting for '{query}'")
        except Exception as e:
            log(f"  painting search '{query}' failed: {str(e)[:120]}")
        return False

    def fallback(self, dest: Path, seed: int) -> None:
        hue = random.Random(seed).randint(-15, 15)
        try:
            ff(
                "-f", "lavfi", "-i", "gradients=s=1920x1080:c0=0x0b1026:c1=0x3a2412:x0=0:y0=0:x1=1920:y1=1080",
                "-vf", f"hue=h={hue},vignette=PI/4", "-frames:v", "1", str(dest),
            )
        except RuntimeError:
            ff("-f", "lavfi", "-i", "color=c=0x14172b:s=1920x1080", "-vf", "vignette=PI/4", "-frames:v", "1", str(dest))


def normalize(src: Path, dest: Path, cover: bool) -> None:
    if cover:
        vf = "crop=iw:ih*0.93:0:0,scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,vignette=PI/5,setsar=1"
        ff("-i", str(src), "-vf", vf, "-q:v", "2", str(dest))
        return
    ff(
        "-i", str(src),
        "-filter_complex",
        "[0]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,gblur=sigma=40,eq=brightness=-0.12[bg];"
        "[0]scale=1920:1080:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,vignette=PI/5,setsar=1",
        "-q:v", "2", str(dest),
    )


def tts(text: str, voice: str, dest: Path) -> None:
    import edge_tts

    async def run():
        await edge_tts.Communicate(text, voice, rate="-12%", pitch="-3Hz").save(str(dest))

    for attempt in range(5):
        try:
            asyncio.run(run())
            if dest.exists() and dest.stat().st_size > 10000:
                return
        except Exception as e:
            log(f"  tts try {attempt + 1}: {str(e)[:120]}")
        time.sleep((10 * (attempt + 1)))
    raise RuntimeError("edge-tts failed 5 times")


def silence(dest: Path, sec: float) -> None:
    ff("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{sec}", "-c:a", "libmp3lame", "-b:a", "48k", str(dest))


def particles(dest: Path, fps: int, sec: int = 20) -> None:
    dots = dest.with_name("dots.png")
    ff(
        "-f", "lavfi", "-i", "color=c=black:s=1920x1080",
        "-vf", "format=gray,geq=lum='if(gt(random(1),0.99965),255,0)'",
        "-frames:v", "1", str(dots),
    )
    speed = 1 / (sec * fps)
    ff(
        "-loop", "1", "-framerate", str(fps), "-i", str(dots),
        "-vf",
        f"scroll=vertical={speed:.8f}:horizontal=0,"
        "split[a][b];[a]gblur=sigma=6[glow];[b]gblur=sigma=1.2[core];[glow][core]blend=all_mode=lighten,"
        "format=gbrp,colorchannelmixer=rr=1.0:gg=0.62:bb=0.22,eq=brightness=0.02:contrast=1.6,format=yuv420p",
        "-t", str(sec), *X264, str(dest),
    )
    dots.unlink(missing_ok=True)


MOTIONS = {
    "in_out": ("if(lte(on,{h}),1+0.12*on/{h},1.12-0.12*(on-{h})/{h})", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    "pan_lr": ("1.15", "(iw-iw/zoom)*on/{n}", "(ih-ih/zoom)/2"),
    "pan_rl": ("1.15", "(iw-iw/zoom)*(1-on/{n})", "(ih-ih/zoom)/2"),
    "tilt_up": ("1.15", "(iw-iw/zoom)/2", "(ih-ih/zoom)*(1-on/{n})"),
    "push": ("1+0.15*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    "pull": ("1.15-0.15*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
}


def clip(
    image: Path, sec: float, dest: Path, overlay: Path, fps: int,
    motion: str = "in_out", label: str = "", cycle: float = 30.0,
) -> None:
    cyc = min(cycle, sec) if motion == "in_out" else sec
    n = max(2, int(cyc * fps))
    z, x, y = (e.format(h=n // 2, n=n) for e in MOTIONS[motion])
    base = dest.with_suffix(".cycle.mp4")
    ff(
        "-i", str(image), "-stream_loop", "-1", "-i", str(overlay),
        "-filter_complex",
        f"[0]scale=2400:1350,zoompan=z='{z}':x='{x}':y='{y}':d={n}:s=1920x1080:fps={fps},format=yuv420p[v];"
        "[1]format=yuv420p[p];[v][p]blend=c0_mode=screen:c0_opacity=0.6:c1_mode=normal:c1_opacity=1:c2_mode=normal:c2_opacity=1[o]",
        "-map", "[o]", "-frames:v", str(n), "-g", str(fps * 2), *X264, str(base),
    )
    parts = [base]
    f = font()
    if label and f:
        head = dest.with_suffix(".head.mp4")
        ff(
            "-i", str(base),
            "-vf",
            f"drawtext=fontfile='{f}':text='{_esc(label)}':fontcolor=0xFFF1D6:fontsize=38:x=80:y=h-110:"
            f"shadowcolor=black@0.7:shadowx=2:shadowy=2:alpha='if(lt(t,1.5),t/1.5,if(lt(t,7),1,max(0,(8.5-t)/1.5)))'",
            "-g", str(fps * 2), *X264, str(head),
        )
        parts = [head]
    if sec <= cyc + 0.05 and parts[0] is base:
        base.replace(dest)
        return
    loops = int(sec // cyc) + 1
    lst = dest.with_suffix(".txt")
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts + [base] * loops), encoding="utf-8")
    ff("-f", "concat", "-safe", "0", "-i", str(lst), "-t", f"{sec:.3f}", "-c", "copy", str(dest))
    for p in {base, *parts, lst}:
        p.unlink(missing_ok=True)


def render_parallel(jobs: list[dict], workers: int = 3) -> None:
    with ThreadPoolExecutor(workers) as ex:
        for fut in [ex.submit(clip, **j) for j in jobs]:
            fut.result()


def master_audio(voice_list: Path, total: float, dest: Path) -> None:
    fade = max(0.0, total - 12)
    ff(
        "-f", "concat", "-safe", "0", "-i", str(voice_list),
        "-f", "lavfi", "-i", f"anoisesrc=d={total + 1:.2f}:c=brown:r=44100:a=0.5",
        "-filter_complex",
        "[0]aresample=44100,highpass=f=70,lowpass=f=9000,"
        "equalizer=f=3500:t=q:w=1.2:g=-3,loudnorm=I=-19:TP=-2:LRA=9[v];"
        "[1]highpass=f=60,lowpass=f=700,volume=0.06,aformat=channel_layouts=mono[r];"
        f"[v][r]amix=inputs=2:duration=first:normalize=0,afade=t=in:d=3,afade=t=out:st={fade:.2f}:d=12[a]",
        "-map", "[a]", "-ac", "2", "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}", str(dest),
    )


def mux(seg_list: Path, audio: Path, dest: Path) -> None:
    ff(
        "-f", "concat", "-safe", "0", "-i", str(seg_list), "-i", str(audio),
        "-map", "0:v", "-map", "1:a", "-c", "copy", "-shortest", "-movflags", "+faststart", str(dest),
    )


def thumbnail(image: Path, text: str, dest: Path) -> None:
    f = font()
    words = _esc(text.upper()).split()
    lines = [" ".join(words[: (len(words) + 1) // 2]), " ".join(words[(len(words) + 1) // 2:])]
    draws = ""
    if f:
        for i, ln in enumerate(l for l in lines if l):
            draws += (
                f",drawtext=fontfile='{f}':text='{ln}':fontsize=112:fontcolor=0xFFE7B0:borderw=6:bordercolor=black@0.85:"
                f"x=70:y=h*0.52+{i}*130"
            )
    ff(
        "-i", str(image),
        "-vf", f"scale=1280:720,eq=brightness=-0.05:saturation=1.15,vignette=PI/4{draws}",
        "-q:v", "3", "-frames:v", "1", str(dest),
    )


def ensure_tools() -> None:
    for t in ("ffmpeg", "ffprobe"):
        if not shutil.which(t):
            raise RuntimeError(f"{t} not on PATH")
