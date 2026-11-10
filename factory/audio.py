import asyncio
import random
import re
import time
from pathlib import Path
from xml.sax.saxutils import escape

import requests

from .log import log
from .media import ff

ASSETS = Path(__file__).resolve().parent.parent / "assets"
FIRE_FILE = ASSETS / "fire_campfire.ogg"
FIRE_CREDIT = (
    'Fire ambience: "Campfire sound ambience" by Glaneur de sons (freesound.org), '
    "CC BY 3.0 https://creativecommons.org/licenses/by/3.0/ (looped and mixed)"
)

RATE, PITCH = "-25%", "-8Hz"
SENTENCE_GAP, PARAGRAPH_GAP = 0.9, 1.8
LEAD_IN, TAIL = 6.0, 12.0

VOICE_FX = (
    "aresample=44100,highpass=f=70,lowpass=f=6500,"
    "acompressor=threshold=-24dB:ratio=3:attack=20:release=250,"
    "equalizer=f=250:t=q:w=1:g=2,equalizer=f=3500:t=q:w=1.5:g=-4,equalizer=f=3000:t=q:w=1.4:g=2.5,"
    "aecho=0.8:0.6:40:0.08"
)


def sentences(paragraph: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?…])\s+", paragraph) if len(s.strip()) > 1]


class Voice:
    def __init__(self, voice: str, azure_key: str = "", azure_region: str = ""):
        self.voice, self.azure_key, self.azure_region = voice, azure_key, azure_region
        self.engine = "azure" if azure_key and azure_region else "edge"
        log(f"voice: {voice} via {self.engine}")

    def _azure(self, text: str, dest: Path) -> None:
        ssml = (
            f"<speak version='1.0' xml:lang='en-US'><voice name='{self.voice}'>"
            f"<prosody rate='{RATE}' pitch='{PITCH}'>{escape(text)}</prosody></voice></speak>"
        )
        r = requests.post(
            f"https://{self.azure_region}.tts.speech.microsoft.com/cognitiveservices/v1",
            headers={
                "Ocp-Apim-Subscription-Key": self.azure_key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
                "User-Agent": "sleep-factory",
            },
            data=ssml.encode("utf-8"),
            timeout=120,
        )
        if r.status_code != 200 or len(r.content) < 500:
            raise RuntimeError(f"azure tts HTTP {r.status_code}: {r.text[:120]}")
        dest.write_bytes(r.content)

    async def _edge(self, text: str, dest: Path) -> None:
        import edge_tts

        await edge_tts.Communicate(text, self.voice, rate=RATE, pitch=PITCH).save(str(dest))

    async def _one(self, text: str, dest: Path, sem: asyncio.Semaphore) -> None:
        async with sem:
            for attempt in range(6):
                try:
                    if self.engine == "azure":
                        await asyncio.to_thread(self._azure, text, dest)
                    else:
                        await self._edge(text, dest)
                    if dest.exists() and dest.stat().st_size > 500:
                        return
                except Exception as e:
                    if attempt >= 2:
                        log(f"  tts retry {attempt + 1}: {str(e)[:100]}")
                await asyncio.sleep(3 * (attempt + 1))
            raise RuntimeError(f"TTS failed for: {text[:60]}")

    def chapter(self, text: str, work: Path, tag: str, dest: Path) -> float:
        gaps = {}
        for name, sec in (("s", SENTENCE_GAP), ("p", PARAGRAPH_GAP)):
            g = work / f"gap_{name}.mp3"
            if not g.exists():
                ff("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{sec}", "-c:a", "libmp3lame", "-b:a", "48k", str(g))
            gaps[name] = g
        jobs, order = [], []
        for pi, para in enumerate(p for p in text.split("\n\n") if p.strip()):
            for si, sent in enumerate(sentences(para)):
                f = work / f"{tag}_{pi:03d}_{si:03d}.mp3"
                jobs.append((sent, f))
                order += [f, gaps["s"]]
            if order:
                order[-1] = gaps["p"]

        async def run():
            sem = asyncio.Semaphore(4)
            await asyncio.gather(*(self._one(t, f, sem) for t, f in jobs))

        asyncio.run(run())
        lst = work / f"{tag}_list.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in order), encoding="utf-8")
        ff("-f", "concat", "-safe", "0", "-i", str(lst), "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k", str(dest))
        for _, f in jobs:
            f.unlink(missing_ok=True)
        lst.unlink(missing_ok=True)
        from .media import duration
        return duration(dest)


def _fire_loop(work: Path) -> Path | None:
    if not FIRE_FILE.exists():
        log("  fire asset missing, skipping fire")
        return None
    out = work / "fire_loop.wav"
    ff(
        "-i", str(FIRE_FILE),
        "-filter_complex",
        "[0]aformat=sample_rates=44100:channel_layouts=stereo,asplit=2[a][b];"
        "[a]atrim=start=4,asetpts=PTS-STARTPTS[body];[b]atrim=end=4,asetpts=PTS-STARTPTS[head];"
        "[body][head]acrossfade=d=4:c1=tri:c2=tri,highpass=f=60,lowpass=f=7000",
        str(out),
    )
    return out


def _thunder(work: Path) -> Path:
    out = work / "thunder.wav"
    ff(
        "-f", "lavfi", "-i", "anoisesrc=d=12:c=brown:r=44100:a=1:seed=14",
        "-af",
        "lowpass=f=110,lowpass=f=110,highpass=f=25,"
        "volume='if(lt(t,1.8),pow(t/1.8,2),exp(-(t-1.8)/2.6))':eval=frame,volume=4,"
        "aecho=0.8:0.7:180|420:0.35|0.25,loudnorm=I=-30",
        "-ac", "2", str(out),
    )
    return out


def master(voice_list: Path, voice_len: float, work: Path, dest: Path, seed: int = 1) -> float:
    total = LEAD_IN + voice_len + TAIL
    rnd = random.Random(seed)
    fire = _fire_loop(work)
    thunder = _thunder(work)
    times, t = [], rnd.uniform(25, 90)
    while t < total - 20:
        times.append(t)
        t += rnd.uniform(180, 420)
    lead_ms = int(LEAD_IN * 1000)

    inputs = [
        "-f", "concat", "-safe", "0", "-i", str(voice_list),
        "-f", "lavfi", "-i", f"anoisesrc=d={total + 1:.2f}:c=pink:r=44100:a=0.6:seed=11",
        "-f", "lavfi", "-i", f"anoisesrc=d={total + 1:.2f}:c=brown:r=44100:a=0.5:seed=12",
        "-f", "lavfi", "-i", f"aevalsrc='if(lt(random(0),0.0025),(random(1)-0.5),0)':s=44100:d={total + 1:.2f}",
        "-i", str(thunder),
    ]
    graph = [
        f"[0]{VOICE_FX},loudnorm=I=-19:TP=-2:LRA=9,aformat=channel_layouts=stereo,adelay={lead_ms}|{lead_ms}[v]",
        "[1]highpass=f=500,lowpass=f=7000,volume='0.5*(0.8+0.2*sin(2*PI*t/13))':eval=frame[rh]",
        "[2]lowpass=f=400,highpass=f=60,volume=0.4[rb]",
        "[3]highpass=f=2500,lowpass=f=9000,volume=1.5,aecho=0.6:0.4:12|23:0.3|0.2[rd]",
        "[rh][rb][rd]amix=inputs=3:normalize=0,equalizer=f=2500:t=q:w=1.2:g=-4,loudnorm=I=-34,aformat=channel_layouts=stereo[rain]",
    ]
    mix = ["[v]", "[rain]"]
    if times:
        graph.append(f"[4]asplit={len(times)}" + "".join(f"[t{i}]" for i in range(len(times))))
        for i, tt in enumerate(times):
            ms = int(tt * 1000)
            graph.append(f"[t{i}]volume={rnd.uniform(0.5, 0.85):.2f},adelay={ms}|{ms}[th{i}]")
            mix.append(f"[th{i}]")
    if fire:
        inputs += ["-stream_loop", "-1", "-i", str(fire)]
        graph.append("[5]loudnorm=I=-34,aformat=channel_layouts=stereo[fire]")
        mix.append("[fire]")
    graph.append(
        "".join(mix) + f"amix=inputs={len(mix)}:normalize=0:duration=first,"
        f"afade=t=in:d=4,afade=t=out:st={total - TAIL + 2:.2f}:d={TAIL - 2:.2f},alimiter=limit=0.9[a]"
    )
    pad = f"[0]apad=pad_dur={TAIL + LEAD_IN + 1:.2f}"
    graph[0] = graph[0].replace("[0]", pad + ",", 1)
    ff(*inputs, "-filter_complex", ";".join(graph), "-map", "[a]", "-t", f"{total:.2f}",
       "-c:a", "aac", "-b:a", "192k", str(dest))
    log(f"  audio: voice {voice_len / 60:.1f} min + rain, {'fire, ' if fire else ''}{len(times)} thunder rolls")
    return total
