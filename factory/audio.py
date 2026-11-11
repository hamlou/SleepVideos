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

    def _azure(self, sents: list[str], dest: Path) -> list[float]:
        brk = f"<break time='{int(SENTENCE_GAP * 1000)}ms'/>"
        body = brk.join(escape(t) for t in sents)
        ssml = (
            f"<speak version='1.0' xml:lang='en-US'><voice name='{self.voice}'>"
            f"<prosody rate='{RATE}' pitch='{PITCH}'>{body}</prosody></voice></speak>"
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
            timeout=180,
        )
        if r.status_code != 200 or len(r.content) < 500:
            raise RuntimeError(f"azure tts HTTP {r.status_code}: {r.text[:120]}")
        dest.write_bytes(r.content)
        return []

    async def _edge(self, sents: list[str], dest: Path) -> list[float]:
        import edge_tts

        audio_bytes, cuts = bytearray(), []
        com = edge_tts.Communicate(" ".join(sents), self.voice, rate=RATE, pitch=PITCH, boundary="SentenceBoundary")
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
            elif chunk["type"] == "SentenceBoundary":
                cuts.append((chunk["offset"] + chunk["duration"]) / 1e7)
        if len(audio_bytes) < 500:
            raise RuntimeError("No audio was received")
        dest.write_bytes(bytes(audio_bytes))
        return cuts[:-1]

    def _with_pauses(self, raw: Path, cuts: list[float], dest: Path) -> None:
        if not cuts:
            raw.replace(dest)
            return
        edges = [0.0] + cuts + [None]
        parts, labels = [], []
        for i in range(len(edges) - 1):
            a, b = edges[i], edges[i + 1]
            trim = f"atrim=start={a:.3f}" + (f":end={b + 0.05:.3f}" if b is not None else "")
            parts.append(f"[0]{trim},asetpts=PTS-STARTPTS[s{i}]")
            labels.append(f"[s{i}]")
            if b is not None:
                parts.append(f"anullsrc=r=24000:cl=mono,atrim=duration={SENTENCE_GAP}[g{i}]")
                labels.append(f"[g{i}]")
        graph = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(labels)}:v=0:a=1[o]"
        ff("-i", str(raw), "-filter_complex", graph, "-map", "[o]", "-ar", "24000", "-ac", "1",
           "-c:a", "libmp3lame", "-b:a", "64k", str(dest))
        raw.unlink(missing_ok=True)

    async def _para(self, sents: list[str], dest: Path, sem: asyncio.Semaphore) -> bool:
        async with sem:
            raw = dest.with_suffix(".raw.mp3")
            for attempt in range(15):
                try:
                    if self.engine == "azure":
                        cuts = await asyncio.to_thread(self._azure, sents, raw)
                    else:
                        cuts = await self._edge(sents, raw)
                    await asyncio.to_thread(self._with_pauses, raw, cuts, dest)
                    await asyncio.sleep(1.0)
                    return True
                except Exception as e:
                    if attempt >= 5:
                        log(f"  tts retry {attempt + 1}: {str(e)[:80]}")
                await asyncio.sleep(min(20, 2 + attempt * 1.5))
            log(f"  ⚠ skipped paragraph after 15 tries: {sents[0][:60]}")
            return False

    def chapter(self, text: str, work: Path, tag: str, dest: Path) -> float:
        gap = work / "gap_p.mp3"
        if not gap.exists():
            ff("-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{PARAGRAPH_GAP}", "-c:a", "libmp3lame", "-b:a", "64k", str(gap))
        jobs = []
        for pi, para in enumerate(p for p in text.split("\n\n") if p.strip()):
            sents = sentences(para)
            if sents:
                jobs.append((sents, work / f"{tag}_{pi:03d}.mp3"))

        async def run():
            sem = asyncio.Semaphore(4)
            return await asyncio.gather(*(self._para(t, f, sem) for t, f in jobs))

        ok = asyncio.run(run())
        good = [f for (_, f), g in zip(jobs, ok) if g]
        if len(good) < len(jobs) * 0.85:
            raise RuntimeError(f"TTS failed for {len(jobs) - len(good)}/{len(jobs)} paragraphs")
        order = []
        for f in good:
            order += [f, gap]
        lst = work / f"{tag}_list.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in order[:-1]), encoding="utf-8")
        ff("-f", "concat", "-safe", "0", "-i", str(lst), "-ar", "24000", "-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k", str(dest))
        for f in good:
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
