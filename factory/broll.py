import random
from pathlib import Path

import requests

from .log import log
from .media import X264, duration, ff

QUERIES = {
    "fireplace": {"fire", "fireplace", "flames", "flame"},
    "fire flames wood": {"fire", "flames", "flame", "wood"},
    "embers": {"ember", "embers", "glow"},
    "campfire": {"campfire", "fire", "flames"},
    "candle flame": {"candle", "flame"},
    "snowflakes falling": {"snowflakes", "snow", "snowfall"},
    "raindrops leaves": {"raindrops", "rain", "drops"},
    "rain puddle": {"rain", "puddle", "drops"},
}
BAD_TAGS = {
    "christmas", "advent", "prayer", "church", "easter", "xmas", "santa", "religion", "religious", "cross",
    "jesus", "god", "angel", "mosque", "temple", "buddha", "cat", "dog", "pet", "city", "car", "traffic",
    "people", "woman", "man", "girl", "boy", "person", "phone", "laptop", "birthday", "party", "gift",
    "present", "stocking", "christmas tree", "decoration", "ornaments", "animated", "drawing", "cartoon",
    "neon", "street", "building", "skyscraper", "pillow", "festival", "holidays", "halloween", "valentine",
    "window", "tower", "skyline", "urban", "road", "house", "lamp", "light bulb", "kitchen", "food", "hand", "hands",
}
CREDIT = "Atmospheric footage: Pixabay (pixabay.com), Pixabay Content License"


class Broll:
    def __init__(self, key: str, work: Path, fps: int, seed: int):
        self.key, self.work, self.fps = key, work, fps
        self.rnd = random.Random(seed)
        self.sources: list[Path] = []
        self.cursor: dict[Path, float] = {}

    def fetch(self, n: int = 7) -> int:
        if not self.key:
            log("  no PIXABAY_API_KEY → no stock footage")
            return 0
        queries = self.rnd.sample(list(QUERIES), k=min(n, len(QUERIES)))
        used: set[int] = set()
        for q in queries:
            try:
                r = requests.get("https://pixabay.com/api/videos/", params={
                    "key": self.key, "q": q, "per_page": 30, "safesearch": "true", "video_type": "film",
                }, timeout=30)
                r.raise_for_status()
                hits = r.json().get("hits", [])
                self.rnd.shuffle(hits)
                for h in hits:
                    tags = {t.strip().lower() for t in h.get("tags", "").split(",")}
                    if h["id"] in used or tags & BAD_TAGS or not (tags & QUERIES[q]) or h.get("duration", 0) < 10:
                        continue
                    v = h["videos"]
                    pick = next((v[k] for k in ("large", "medium") if v.get(k, {}).get("width") == 1920
                                 and v[k].get("height") == 1080 and 0 < v[k].get("size", 0) < 60e6), None)
                    if not pick:
                        continue
                    raw = self.work / f"stock_{h['id']}.raw.mp4"
                    with requests.get(pick["url"], stream=True, timeout=120) as d:
                        d.raise_for_status()
                        with raw.open("wb") as f:
                            for chunk in d.iter_content(1 << 20):
                                f.write(chunk)
                    out = self.work / f"stock_{h['id']}.mp4"
                    ff("-i", str(raw), "-an",
                       "-vf", f"scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps={self.fps},"
                              "eq=saturation=0.9:brightness=-0.04,colorbalance=rm=0.06:bm=-0.06,vignette=PI/5,setsar=1,format=yuv420p",
                       "-g", str(self.fps * 2), *X264, str(out))
                    raw.unlink(missing_ok=True)
                    self.sources.append(out)
                    used.add(h["id"])
                    log(f"  stock '{q}': {h['duration']}s clip #{h['id']}")
                    break
            except Exception as e:
                log(f"  stock '{q}' failed: {str(e)[:120]}")
        return len(self.sources)

    def clip(self, sec: float, dest: Path) -> bool:
        if not self.sources:
            return False
        src = self.sources[self.rnd.randrange(len(self.sources))]
        length = duration(src)
        start = self.cursor.get(src, 0.0)
        if start + sec > length:
            start = 0.0
        self.cursor[src] = start + sec
        if sec > length:
            return False
        ff("-ss", f"{start:.2f}", "-i", str(src), "-t", f"{sec:.2f}", "-an",
           "-vf", f"fade=t=in:st=0:d=0.6,fade=t=out:st={max(0.0, sec - 0.6):.2f}:d=0.6",
           "-g", str(self.fps * 2), *X264, str(dest))
        return True
