#!/usr/bin/env python3
"""100% Free ($0.00/Month, ZERO Credit Card, ZERO Pexels Key Needed) Sleep Video Worker.

Upgraded Production Engine:
  1. Authentic 'Sleepless Historian' / 'Boring History for Sleep' Script Architecture:
     - Continuous 2nd-person present-tense immersion ("you drift quietly through...").
     - Sleep-friendly lexical filtering (zero jarring/harsh words; gentle, dry, understated wit).
     - 5-sense low-arousal micro-history (beeswax, damp wool, rain on leaded glass, quill on vellum).
     - Strict Section Lock: 1,050–1,150 words per chapter, zero headers/tags, seamless sensory bridges.
  2. 100% Key-Free FFmpeg Procedural Particle & 20-Cut Dynamic Intro Engine (No Pexels Key Needed!):
     - Because Pexels paused new API keys, this worker automatically synthesizes a 1080p black-screen
       floating golden ember/dust overlay (`fetch_or_create_particle_overlay`) AND renders 20 distinct
       6-second multi-directional camera cuts (pan left, pan right, tilt up, diagonal drift, push-in,
       pull-out with warm candle-flicker modulation) for Minutes 00:00–02:00!
  3. 8-Tier Zero-Credit-Card Free LLM Waterfall:
     - Automatically filters `GEMINI_API_KEY` to valid `AIzaSy...` keys (ignoring stray OAuth strings),
       rotates across `gemma-3-27b-it` (14,400 RPD/key = 43,200 RPD across 3 keys!), Cohere Trial Key,
       Hugging Face Token, GitHub Models (`GITHUB_TOKEN`), and Pollinations No-Key API.
"""

import itertools
import json
import os
import random
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
from typing import Dict, List, Optional, Tuple

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ==============================================================================
# 1. ZERO-CARD API KEYS (Automatically filters GEMINI_API_KEY for valid AIzaSy keys)
# ==============================================================================
_raw_gemini_keys = [
    k.strip() for k in os.environ.get("GEMINI_API_KEY", "").split(",") if k.strip()
]
GEMINI_API_KEYS = [k for k in _raw_gemini_keys if k.startswith("AIza")] or _raw_gemini_keys

GROQ_API_KEYS = [
    k.strip() for k in os.environ.get("GROQ_API_KEY", "").split(",") if k.strip()
]
COHERE_API_KEYS = [
    k.strip() for k in os.environ.get("COHERE_API_KEY", "").split(",") if k.strip()
]
HF_TOKENS = [
    k.strip() for k in os.environ.get("HF_TOKEN", "").split(",") if k.strip()
]
CEREBRAS_API_KEYS = [
    k.strip() for k in os.environ.get("CEREBRAS_API_KEY", "").split(",") if k.strip()
]
OPENROUTER_API_KEYS = [
    k.strip() for k in os.environ.get("OPENROUTER_API_KEY", "").split(",") if k.strip()
]
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()

# Optional: Works 100% WITHOUT Pexels API Key thanks to built-in FFmpeg Procedural Engine!
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
MAKE_CALLBACK_WEBHOOK_URL = os.environ.get("MAKE_CALLBACK_WEBHOOK_URL", "").strip()

# Non-expiring YouTube OAuth2 Refresh Credentials (set in GitHub Secrets)
YOUTUBE_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()

# Job Payload from Make.com `repository_dispatch`
SHEET_ROW_ID = int(os.environ.get("SHEET_ROW_ID", "2"))
VIDEO_TITLE = os.environ.get(
    "VIDEO_TITLE",
    "Boring History For Sleep: A Rainy Night in a 14th-Century Monastery",
)
TOPIC_LENS = os.environ.get(
    "TOPIC_LENS",
    "Daily nocturnal routines, scriptorium candle-making, and rain-lit cloisters of a 14th-century medieval monastery",
)
NUM_CHAPTERS = int(os.environ.get("NUM_CHAPTERS", "18"))
VOICE_NAME = os.environ.get("VOICE_NAME", "en-US-AndrewMultilingualNeural")

_gemini_cycle = itertools.cycle(GEMINI_API_KEYS) if GEMINI_API_KEYS else None
_groq_cycle = itertools.cycle(GROQ_API_KEYS) if GROQ_API_KEYS else None
_cohere_cycle = itertools.cycle(COHERE_API_KEYS) if COHERE_API_KEYS else None
_hf_cycle = itertools.cycle(HF_TOKENS) if HF_TOKENS else None
_cerebras_cycle = itertools.cycle(CEREBRAS_API_KEYS) if CEREBRAS_API_KEYS else None
_openrouter_cycle = itertools.cycle(OPENROUTER_API_KEYS) if OPENROUTER_API_KEYS else None


# ==============================================================================
# 2. MASTER "SLEEPLESS HISTORIAN" / "BORING HISTORY FOR SLEEP" PROMPT ENGINE
# ==============================================================================
SLEEPLESS_HISTORIAN_STYLE_GUIDE = """
MANDATORY SLEEP-DOCUMENTARY NARRATION RULES ('THE SLEEPLESS HISTORIAN' ARCHITECTURE):
1. SECOND-PERSON INVISIBLE TIME-TRAVELER IMMERSION:
   - Write in continuous second-person present tense ('you walk slowly...', 'you notice the faint warmth...').
   - Treat the listener as an invisible, unbothered, completely safe observer drifting through the historical setting at night.
2. SLEEP-FRIENDLY LEXICAL FILTERING (ZERO CORTISOL SPIKES):
   - NEVER use harsh, violent, loud, or jarring words (forbidden: 'horrific', 'terrifying', 'screaming', 'brutal', 'massacre', 'shocking', 'panic', 'excruciating').
   - Soften any historical hardship into dry, calm, understated academic observations ('an unfortunate bureaucratic miscalculation', 'a rather tedious Tuesday', 'peculiar medieval housekeeping').
3. FIVE-SENSE LOW-AROUSAL MICRO-HISTORY:
   - Every single paragraph MUST weave at least two gentle sensory details: the scent of damp wool, beeswax, or woodsmoke; the soft rhythmic patter of rain against leaded glass; the quiet scratch of a goose-quill on vellum; the amber glow of tallow candles.
4. HYPNOTIC CADENCE & GENTLE DRY WIT:
   - Use long, unhurried, flowing sentences mixed with quiet, observational dry wit about mundane historical routines (uncomfortable mattresses, overly complicated tax ledgers, lukewarm barley soup).
5. PURE SPOKEN NARRATION (STRICT SECTION LOCK):
   - Output ONLY pure spoken prose ready for a voice actor.
   - ZERO markdown headings (# or ##), ZERO chapter titles inside the body, ZERO bullet points, ZERO numbered lists, and ZERO stage directions like [Pause], [Music], or [Sound of rain].
   - Never say 'In conclusion', 'To summarize', or 'Thank you for listening' until the final paragraph of the final chapter.
""".strip()


def _call_openai_compatible(
    url: str,
    api_key: str,
    model: str,
    prompt: str,
    extra_headers: Optional[Dict[str, str]] = None,
    min_delay_sec: float = 0.0,
) -> Optional[str]:
    """Helper for OpenAI-compatible endpoints."""
    if min_delay_sec > 0:
        time.sleep(min_delay_sec)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            if text and len(text.strip()) > 20:
                return text.strip()
        else:
            print(f"  [Info] {model} returned HTTP {resp.status_code}; trying next free model...")
    except Exception as exc:
        print(f"  [Info] {model} exception ({exc}); trying next free model...")
    return None


def _call_google_ai_studio(
    api_key: str,
    model: str,
    prompt: str,
    use_search_grounding: bool = False,
    json_mode: bool = False,
) -> Optional[str]:
    """Calls Google AI Studio (`gemini-2.5-flash` or `gemma-3-27b-it` with 14,400 RPD/key, no card)."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    is_gemma = model.startswith("gemma")
    payload: Dict = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7},
    }
    if json_mode and not is_gemma:
        payload["generationConfig"]["responseMimeType"] = "application/json"
    if use_search_grounding and not is_gemma and not json_mode:
        payload["tools"] = [{"google_search": {}}]

    try:
        resp = requests.post(url, json=payload, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            if text and len(text.strip()) > 20:
                return text.strip()
        else:
            print(f"  [Info] Google AI Studio ({model}) HTTP {resp.status_code}; rotating...")
    except Exception as exc:
        print(f"  [Info] Google AI Studio ({model}) exception ({exc}); rotating...")
    return None


def _call_cohere_trial(api_key: str, prompt: str) -> Optional[str]:
    """Calls Cohere v2 Chat API using the free no-credit-card Trial key (1,000 calls/month)."""
    try:
        resp = requests.post(
            "https://api.cohere.com/v2/chat",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "command-r-plus-08-2024",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            },
            timeout=120,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data.get("message", {}).get("content", [])
            if content and content[0].get("text"):
                return content[0]["text"].strip()
    except Exception as exc:
        print(f"  [Info] Cohere Trial API exception ({exc}); rotating...")
    return None


def _call_pollinations_no_key_llm(prompt: str) -> Optional[str]:
    """100% Free, No-Signup, No-API-Key, No-Credit-Card LLM fallback via Pollinations.ai!"""
    for model in ("openai", "mistral", "llama"):
        res = _call_openai_compatible(
            "https://text.pollinations.ai/openai",
            "dummy-no-key-needed",
            model,
            f"{prompt}\n\n(Seed: {random.randint(1000, 999999)})",
            min_delay_sec=2.0,
        )
        if res:
            return res
    return None


def call_free_llm(prompt: str, use_search_grounding: bool = False, json_mode: bool = False) -> str:
    """Zero-Credit-Card Free LLM Waterfall Router."""
    if json_mode:
        prompt = (
            f"{prompt}\n\nIMPORTANT: Return ONLY raw, valid JSON with no markdown code fences "
            f"and no conversational text before or after the JSON object."
        )

    # 1. If Google Search Grounding is requested (Step 1 only = 1 call/video), try Gemini Flash first
    if use_search_grounding and _gemini_cycle:
        for _ in range(len(GEMINI_API_KEYS)):
            key = next(_gemini_cycle)
            res = _call_google_ai_studio(key, "gemini-2.5-flash", prompt, use_search_grounding=True)
            if res:
                return res

    # 2. Google AI Studio `gemma-3-27b-it` (14,400 FREE requests/day per key, NO credit card!)
    if _gemini_cycle:
        for _ in range(len(GEMINI_API_KEYS)):
            key = next(_gemini_cycle)
            res = _call_google_ai_studio(key, "gemma-3-27b-it", prompt, use_search_grounding=False)
            if res:
                return res

    # 3. GroqCloud Free Tier (if provided)
    if _groq_cycle:
        for model in ("llama-3.3-70b-versatile", "openai/gpt-oss-120b", "llama-3.1-8b-instant"):
            key = next(_groq_cycle)
            res = _call_openai_compatible(
                "https://api.groq.com/openai/v1/chat/completions", key, model, prompt
            )
            if res:
                return res

    # 4. Cohere Free Trial Key (NO credit card required: 1,000 calls/month)
    if _cohere_cycle:
        key = next(_cohere_cycle)
        res = _call_cohere_trial(key, prompt)
        if res:
            return res

    # 5. Hugging Face Free Token (NO credit card required)
    if _hf_cycle:
        key = next(_hf_cycle)
        for model in ("Qwen/Qwen2.5-72B-Instruct", "meta-llama/Llama-3.3-70B-Instruct"):
            res = _call_openai_compatible(
                "https://router.huggingface.co/v1/chat/completions", key, model, prompt
            )
            if res:
                return res

    # 6. Cerebras / OpenRouter (if provided)
    if _cerebras_cycle:
        for model in ("llama-3.3-70b", "llama3.1-8b"):
            key = next(_cerebras_cycle)
            res = _call_openai_compatible(
                "https://api.cerebras.ai/v1/chat/completions", key, model, prompt
            )
            if res:
                return res

    if _openrouter_cycle:
        for model in ("openrouter/free", "google/gemma-3-27b-it:free"):
            key = next(_openrouter_cycle)
            res = _call_openai_compatible(
                "https://openrouter.ai/api/v1/chat/completions", key, model, prompt
            )
            if res:
                return res

    # 7. Built-In GitHub Models API (Uses automatic GITHUB_TOKEN — 0 signup, 0 card!)
    if GITHUB_TOKEN:
        for model in ("gpt-4o-mini", "Meta-Llama-3.3-70B-Instruct"):
            res = _call_openai_compatible(
                "https://models.inference.ai.azure.com/chat/completions",
                GITHUB_TOKEN,
                model,
                prompt,
            )
            if res:
                return res

    # 8. Built-In Pollinations.ai No-Key Text API (0 signup, 0 API key, 0 credit card!)
    res = _call_pollinations_no_key_llm(prompt)
    if res:
        return res

    raise RuntimeError("All free LLM endpoints failed. Check your internet connection.")


def extract_json_object(raw_text: str) -> Dict:
    """Safely extracts a JSON object even if a model wraps it in markdown."""
    cleaned = raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            return json.loads(match.group(0))
        raise


def clean_spoken_narration(raw_text: str) -> str:
    """Strips any accidental markdown headings, stage tags, or asterisks before TTS."""
    lines = []
    for line in raw_text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("---"):
            continue
        # Remove bracketed stage directions like [Pause] or [Soft rain]
        s = re.sub(r"\[[^\]]*\]", "", s)
        # Remove markdown bold/italics asterisks
        s = s.replace("**", "").replace("*", "")
        if s.strip():
            lines.append(s.strip())
    return "\n\n".join(lines)


def step_1_research_and_outline(topic: str, num_chapters: int) -> List[Dict]:
    """Pulls 100 grounded historical micro-facts and builds the non-overlapping chapter outline."""
    print(f"[1/6] Researching 100 verified micro-history & sensory facts for: {topic} ...")
    research_prompt = (
        f"You are the lead historical researcher for 'The Sleepless Historian' / 'Boring History for Sleep'.\n"
        f"Perform deep historical, material-culture, and sensory research on: '{topic}'.\n"
        f"Extract 100 specific, lesser-known, historically accurate micro-facts organized into:\n"
        f"  - Nocturnal architecture, lighting (tallow vs. beeswax candles, rushlights, oil lamps), and heating\n"
        f"  - Clothing fabrics, bed linens, mattresses, and evening hygiene routines\n"
        f"  - Food preparation, hearth tools, earthenware, and late-evening drinks or remedies\n"
        f"  - Mundane trades, guild rules, ledgers, ink-making, parchment preparation, and night-watch duties\n"
        f"  - Ambient sounds, weather patterns, smells, and quiet domestic superstitions.\n"
        f"Avoid textbook battles or high-drama politics; focus 100% on calm, lived, mundane daily and nightly reality."
    )
    verified_facts = call_free_llm(research_prompt, use_search_grounding=True, json_mode=False)
    time.sleep(3)

    print(f"[2/6] Building {num_chapters}-chapter non-overlapping JSON master outline ...")
    outline_prompt = (
        f"Using ONLY the verified historical research notes below on '{topic}', create a {num_chapters}-chapter "
        f"sleep documentary outline in the style of 'Boring History for Sleep' / 'The Sleepless Historian'.\n"
        f"CRITICAL RULE: Every chapter MUST cover a completely distinct physical space or mundane routine so "
        f"the narrator never repeats a sub-topic.\n"
        f"Return ONLY valid JSON matching this exact schema:\n"
        f'{{"chapters": [{{"chapter_num": 1, "chapter_title": "...", '
        f'"sensory_setting": "Specific room/location, time of night, weather, smells, and sounds", '
        f'"assigned_facts": "Detailed historical micro-facts locked exclusively to this chapter", '
        f'"closing_bridge_cue": "How the listener quietly walks from this space into the next chapter", '
        f'"scene_image_prompts": ["prompt 1", "prompt 2", "prompt 3"]}}]}}\n\n'
        f"Each scene_image_prompt must describe a rich 16:9 widescreen historical oil painting with warm amber "
        f"candle or lantern light and deep midnight blue shadows, contrasting wide architectural views with "
        f"intimate close-ups of historical tools/textures, ending with 'cozy nocturnal lighting, 16:9 widescreen, "
        f"masterpiece oil painting, text-free, no watermarks'.\n\nResearch Notes:\n{verified_facts}"
    )
    raw_json = call_free_llm(outline_prompt, use_search_grounding=False, json_mode=True)
    return extract_json_object(raw_json)["chapters"]


def build_sleepless_historian_chapter_prompt(
    ch: Dict, idx: int, total_chapters: int, last_ending: str
) -> str:
    """Builds the exact 'Sleepless Historian' / 'Boring History for Sleep' chapter generation prompt."""
    is_first = idx == 1
    is_last = idx == total_chapters

    opening_rule = (
        "Begin with a gentle, soothing induction that invites the listener to close their eyes, "
        "unclench their jaw, let the modern world fade away, and step quietly into the historical setting."
        if is_first
        else f"Continue seamlessly from the exact final sentences of the previous chapter without any heading or reset:\n\"{last_ending}\""
    )
    closing_rule = (
        "In the final two paragraphs, gradually slow the pacing even further, dimming the last candle "
        "and leaving the listener resting peacefully in the quiet night until morning."
        if is_last
        else f"End the chapter with a smooth sensory transition sentence that guides the listener toward: {ch.get('closing_bridge_cue', 'the next quiet room along the corridor')}."
    )

    return (
        f"You are the master scriptwriter for 'Boring History for Sleep' and 'The Sleepless Historian'.\n"
        f"Write Chapter {idx} of {total_chapters} ('{ch['chapter_title']}') for the sleep documentary '{VIDEO_TITLE}'.\n\n"
        f"{SLEEPLESS_HISTORIAN_STYLE_GUIDE}\n\n"
        f"CHAPTER {idx} LOCKED PARAMETERS:\n"
        f"- Target Length: Between 1,050 and 1,150 words of continuous, unhurried spoken prose.\n"
        f"- Sensory Setting: {ch.get('sensory_setting', 'Quiet nocturnal historical setting with rain and candlelight')}\n"
        f"- Assigned Historical Facts (Cover ONLY these facts; do not drift into other chapters): {ch.get('assigned_facts', '')}\n"
        f"- Opening Instruction: {opening_rule}\n"
        f"- Closing Instruction: {closing_rule}\n\n"
        f"Write the complete 1,050–1,150 word spoken narration for Chapter {idx} now:"
    )


def generate_free_voiceover_and_subtitles(
    text: str, out_mp3_path: str, out_vtt_path: str, voice: str = VOICE_NAME
) -> Tuple[str, str]:
    """Generates sleepy narration + exact timestamped subtitles (.vtt) using edge-tts + warm EQ."""
    raw_mp3 = out_mp3_path + ".raw.mp3"
    txt_file = out_mp3_path + ".txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write(text)

    subprocess.run(
        [
            "edge-tts",
            "--voice", voice,
            "--rate=-14%",
            "--pitch=-3Hz",
            "--file", txt_file,
            "--write-media", raw_mp3,
            "--write-subtitles", out_vtt_path,
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", raw_mp3,
            "-af", "lowpass=f=7500,highpass=f=75,loudnorm=I=-16:TP=-1.5:LRA=11",
            "-c:a", "libmp3lame", "-b:a", "192k",
            out_mp3_path,
        ],
        check=True,
    )
    os.remove(raw_mp3)
    os.remove(txt_file)
    return out_mp3_path, out_vtt_path


def download_pollinations_flux_image(prompt: str, dest_path: str, seed: int) -> str:
    """Downloads a free 1920x1080 Flux illustration from Pollinations.ai (0 signup, 0 card)."""
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1920&height=1080&model=flux&nologo=true&seed={seed}"
    for attempt in range(4):
        try:
            r = requests.get(url, timeout=90)
            if r.status_code == 200 and len(r.content) > 10000:
                with open(dest_path, "wb") as f:
                    f.write(r.content)
                return dest_path
        except Exception:
            pass
        time.sleep(6 * (attempt + 1))

    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "color=c=#0f172a:s=1920x1080:d=1",
            "-frames:v", "1", dest_path,
        ],
        check=True,
    )
    return dest_path


def fetch_or_create_particle_overlay(work_dir: str) -> str:
    """Creates a 1080p black-background floating golden ember/dust overlay video.

    - If PEXELS_API_KEY is provided, attempts to download a particle overlay from Pexels first.
    - If PEXELS_API_KEY is blank (since Pexels paused new API keys!), automatically synthesizes
      a 100% key-free 15-second 1080p warm golden ember & dust overlay directly in FFmpeg!
    """
    norm_p = os.path.join(work_dir, "particles_norm.mp4")
    if PEXELS_API_KEY:
        try:
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                headers={"Authorization": PEXELS_API_KEY},
                params={"query": "particles black background", "orientation": "landscape", "per_page": 2},
                timeout=30,
            )
            if resp.status_code == 200:
                vids = resp.json().get("videos", [])
                if vids and vids[0].get("video_files"):
                    files = sorted(vids[0]["video_files"], key=lambda x: abs((x.get("width") or 0) - 1920))
                    raw_p = os.path.join(work_dir, "particles_raw.mp4")
                    with requests.get(files[0]["link"], stream=True, timeout=60) as r:
                        r.raise_for_status()
                        with open(raw_p, "wb") as f:
                            for chunk in r.iter_content(1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                    subprocess.run(
                        [
                            "ffmpeg", "-y", "-i", raw_p, "-t", "15",
                            "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=yuv420p",
                            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", norm_p,
                        ],
                        check=True,
                    )
                    os.remove(raw_p)
                    return norm_p
        except Exception:
            pass

    print("  [Key-Free Particle Engine] Synthesizing 1080p warm golden dust/ember overlay in FFmpeg ...")
    # Synthesizes sparse warm golden bokeh/ember particles drifting on a pure black background
    # by thresholding low-resolution temporal noise, upscaling with soft Gaussian blur, and tinting warm gold.
    ember_filter = (
        "noise=alls=100:allf=t,"
        "lut=y='if(gt(val,250),255,0)':u=128:v=128,"
        "scale=1920:1080:flags=bicubic,"
        "gblur=sigma=3.2,"
        "colorbalance=rs=0.65:gs=0.25:bs=-0.55:rm=0.55:gm=0.20:bm=-0.45,"
        "tmix=frames=5:weights='1 2 3 2 1',"
        "fps=30,format=yuv420p"
    )
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=320x180:r=15:d=15",
            "-vf", ember_filter,
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            norm_p,
        ],
        check=True,
    )
    return norm_p


def generate_key_free_dynamic_intro_clips(
    chapter_images: List[List[str]],
    work_dir: str,
    particle_overlay_path: Optional[str],
    target_count: int = 20,
    fps: int = 30,
) -> List[str]:
    """Generates 20 distinct 6-second dynamic camera cuts for Minutes 00:00–02:00 WITHOUT Pexels!

    Cycles across the historical Flux paintings using 6 distinct cinematic camera movements
    (Pan Left->Right, Pan Right->Left, Tilt Bottom->Top, Diagonal Drift, Fast Push-In, Pull-Out)
    plus subtle warm candle-flicker light modulation and Screen-blended golden embers.
    """
    flat_images = [img for ch_list in chapter_images for img in ch_list if os.path.isfile(img)]
    if not flat_images:
        return []

    print(f"  [Key-Free Intro Engine] Rendering {target_count} dynamic 6-second camera cuts (00:00–02:00) ...")
    clip_paths: List[str] = []
    frames = 6 * fps  # 180 frames per 6-second clip

    motion_profiles = [
        # 0: Horizontal Pan Left -> Right
        ("1.18", f"(iw-iw/zoom)*(on/{frames})", "(ih-ih/zoom)/2"),
        # 1: Horizontal Pan Right -> Left
        ("1.18", f"(iw-iw/zoom)*(1-on/{frames})", "(ih-ih/zoom)/2"),
        # 2: Vertical Tilt Bottom -> Top (lantern rising)
        ("1.18", "(iw-iw/zoom)/2", f"(ih-ih/zoom)*(1-on/{frames})"),
        # 3: Diagonal Drift Top-Left -> Bottom-Right
        ("1.20", f"(iw-iw/zoom)*(on/{frames})", f"(ih-ih/zoom)*(on/{frames})"),
        # 4: Cinematic Push-In Toward Center
        (f"1.0+0.18*(on/{frames})", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
        # 5: Cinematic Pull-Out From Center
        (f"1.18-0.18*(on/{frames})", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),
    ]

    for i in range(target_count):
        src_img = flat_images[i % len(flat_images)]
        z_expr, x_expr, y_expr = motion_profiles[i % len(motion_profiles)]
        raw_clip = os.path.join(work_dir, f"intro_raw_{i:03d}.mp4")
        out_clip = os.path.join(work_dir, f"seg_intro_{i:03d}.mp4")

        # Subtle warm candle-flicker brightness modulation + dynamic camera motion
        vf = (
            f"scale=2560:1440,"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s=1920x1080:fps={fps},"
            f"eq=brightness='0.015*sin(2*PI*t/1.8)':saturation=1.05,"
            f"vignette=PI/5,format=yuv420p"
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-loop", "1", "-i", src_img,
                "-vf", vf, "-t", "6",
                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                raw_clip,
            ],
            check=True,
        )

        if particle_overlay_path and os.path.isfile(particle_overlay_path):
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", raw_clip,
                    "-stream_loop", "-1", "-i", particle_overlay_path,
                    "-filter_complex",
                    "[0:v][1:v]blend=all_mode='screen':all_opacity=0.28,format=yuv420p[vout]",
                    "-map", "[vout]", "-t", "6",
                    "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    out_clip,
                ],
                check=True,
            )
            os.remove(raw_clip)
        else:
            os.replace(raw_clip, out_clip)

        clip_paths.append(out_clip)

    return clip_paths


def get_media_duration(file_path: str) -> float:
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", file_path,
        ],
        text=True,
    ).strip()
    return float(out)


def render_fast_ken_burns_boomerang(
    image_path: str,
    target_duration_sec: float,
    output_path: str,
    particle_overlay_path: Optional[str] = None,
    chapter_label: str = "",
    fps: int = 30,
) -> None:
    """Renders a 30s seamless zoom-in/zoom-out cycle and loops it to `target_duration_sec`."""
    cycle_sec = min(30.0, target_duration_sec)
    half_frames = max(1, int((cycle_sec / 2.0) * fps))
    total_cycle_frames = half_frames * 2

    zoom_expr = (
        f"if(lte(on,{half_frames}),"
        f"1.0+0.14*(on/{half_frames}),"
        f"1.14-0.14*((on-{half_frames})/{half_frames}))"
    )
    safe_label = re.sub(r"[^a-zA-Z0-9 :,\-]", "", chapter_label)[:55]
    drawtext_filter = (
        f",drawtext=text='{safe_label}':fontcolor=white@0.75:fontsize=26:"
        f"x=60:y=h-70:enable='lt(t,8)'"
        if safe_label
        else ""
    )

    base_cycle_mp4 = output_path + ".cycle.mp4"
    vf_filter = (
        f"scale=2560:1440,"
        f"zoompan=z='{zoom_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={total_cycle_frames}:s=1920x1080:fps={fps},"
        f"vignette=PI/5,format=yuv420p{drawtext_filter}"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", image_path,
            "-vf", vf_filter, "-t", f"{cycle_sec:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            base_cycle_mp4,
        ],
        check=True,
    )

    if particle_overlay_path and os.path.isfile(particle_overlay_path):
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-stream_loop", "-1", "-i", base_cycle_mp4,
                "-stream_loop", "-1", "-i", particle_overlay_path,
                "-filter_complex",
                "[0:v][1:v]blend=all_mode='screen':all_opacity=0.28,format=yuv420p[vout]",
                "-map", "[vout]",
                "-t", f"{target_duration_sec:.2f}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                output_path,
            ],
            check=True,
        )
    else:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-stream_loop", "-1", "-i", base_cycle_mp4,
                "-t", f"{target_duration_sec:.2f}",
                "-c", "copy",
                output_path,
            ],
            check=True,
        )
    os.remove(base_cycle_mp4)


def synthesize_pink_noise_rain_bed(output_aac_path: str, duration_sec: float) -> str:
    """Synthesizes a 100% original, zero-Content-ID nocturnal rain & warm drone bed in FFmpeg."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anoisesrc=d={duration_sec:.2f}:c=pink:r=44100:a=0.04",
            "-af", "lowpass=f=1100,highpass=f=110,tremolo=f=0.12:d=0.25",
            "-c:a", "aac", "-b:a", "128k",
            output_aac_path,
        ],
        check=True,
    )
    return output_aac_path


def get_youtube_service():
    """Builds an authenticated YouTube Data API v3 client using non-expiring Refresh Token."""
    if YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN:
        creds = Credentials(
            token=None,
            refresh_token=YOUTUBE_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=YOUTUBE_CLIENT_ID,
            client_secret=YOUTUBE_CLIENT_SECRET,
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )
        creds.refresh(Request())
        return build("youtube", "v3", credentials=creds)

    if os.path.isfile("youtube_token.json"):
        creds = Credentials.from_authorized_user_file(
            "youtube_token.json", ["https://www.googleapis.com/auth/youtube.upload"]
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return build("youtube", "v3", credentials=creds)

    return None


def upload_private_youtube_draft(video_path: str, title: str, description: str, chapter_timestamps_text: str) -> Optional[str]:
    """Uploads the 2–4h MP4 to YouTube as PRIVATE with Synthetic Media disclosed & chapter timestamps."""
    youtube = get_youtube_service()
    if not youtube:
        print("No YouTube OAuth credentials configured; skipping direct upload.")
        return None

    full_description = f"{description}\n\nChapters:\n00:00 Introduction\n{chapter_timestamps_text}"
    body = {
        "snippet": {
            "title": title[:100],
            "description": full_description[:4900],
            "tags": ["sleep stories", "boring history for sleep", "fall asleep", "bedtime history", "history documentary"],
            "categoryId": "27",
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
        },
    }
    media = MediaFileUpload(video_path, mimetype="video/mp4", chunksize=50 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response["id"]


def format_timestamp(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}" if hrs > 0 else f"{mins:02d}:{secs:02d}"


def run_zero_dollar_pipeline() -> None:
    work_dir = tempfile.mkdtemp(prefix="free_sleep_pipeline_")
    try:
        chapters = step_1_research_and_outline(TOPIC_LENS, NUM_CHAPTERS)
        particle_overlay = fetch_or_create_particle_overlay(work_dir)

        vo_files: List[str] = []
        chapter_durations: List[float] = []
        chapter_images: List[List[str]] = []
        last_ending = "Tonight, let your shoulders drop, let the outside world fade, and step quietly into the past."

        print(f"[3/6] Writing {len(chapters)} chapters ('Sleepless Historian' style) + edge-tts + Flux 16:9 visuals ...")
        for idx, ch in enumerate(chapters, start=1):
            ch_prompt = build_sleepless_historian_chapter_prompt(ch, idx, len(chapters), last_ending)
            raw_script = call_free_llm(ch_prompt, use_search_grounding=False, json_mode=False)
            ch_script = clean_spoken_narration(raw_script)
            last_ending = " ".join(ch_script.split()[-45:])
            time.sleep(2)

            vo_path = os.path.join(work_dir, f"vo_{idx:03d}.mp3")
            vtt_path = os.path.join(work_dir, f"vo_{idx:03d}.vtt")
            generate_free_voiceover_and_subtitles(ch_script, vo_path, vtt_path, VOICE_NAME)
            vo_files.append(vo_path)
            chapter_durations.append(get_media_duration(vo_path))

            ch_imgs: List[str] = []
            for p_idx, img_prompt in enumerate(ch.get("scene_image_prompts", [])[:3]):
                img_path = os.path.join(work_dir, f"img_{idx:03d}_{p_idx}.jpg")
                download_pollinations_flux_image(img_prompt, img_path, seed=idx * 100 + p_idx)
                ch_imgs.append(img_path)
            chapter_images.append(ch_imgs)

        print("[4/6] Concatenating voiceovers and mixing -28dB ambient pink-noise rain bed ...")
        vo_list_txt = os.path.join(work_dir, "vo_list.txt")
        with open(vo_list_txt, "w", encoding="utf-8") as f:
            for vf in vo_files:
                f.write(f"file '{vf}'\n")
        combined_vo = os.path.join(work_dir, "combined_vo.mp3")
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", vo_list_txt, "-c", "copy", combined_vo], check=True)
        for vf in vo_files:
            os.remove(vf)

        total_duration = get_media_duration(combined_vo)
        ambient_path = os.path.join(work_dir, "ambient_bed.m4a")
        synthesize_pink_noise_rain_bed(ambient_path, min(300.0, total_duration))

        master_audio = os.path.join(work_dir, "master_audio.m4a")
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", combined_vo, "-stream_loop", "-1", "-i", ambient_path,
                "-filter_complex", "[0:a]volume=1.0[vo];[1:a]volume=-28dB[amb];[vo][amb]amix=inputs=2:duration=first[aout]",
                "-map", "[aout]", "-c:a", "aac", "-b:a", "192k", "-t", f"{total_duration:.2f}", master_audio,
            ],
            check=True,
        )
        os.remove(combined_vo)
        os.remove(ambient_path)

        print("[5/6] Rendering 20 dynamic 6-second intro cuts (00:00–02:00) + Chapter-Synced Ken Burns scenes ...")
        intro_clips = generate_key_free_dynamic_intro_clips(
            chapter_images, work_dir, particle_overlay, target_count=20
        )
        elapsed_intro = sum(get_media_duration(c) for c in intro_clips)

        all_segments = list(intro_clips)
        chapter_timestamps_lines: List[str] = []
        running_clock = 0.0

        for idx, (ch, ch_dur, ch_imgs) in enumerate(zip(chapters, chapter_durations, chapter_images), start=1):
            chapter_timestamps_lines.append(f"{format_timestamp(running_clock)} Chapter {idx}: {ch['chapter_title']}")
            running_clock += ch_dur

            effective_ch_dur = max(15.0, ch_dur - elapsed_intro) if idx == 1 else ch_dur
            sec_per_img = effective_ch_dur / max(1, len(ch_imgs))

            for p_idx, img_p in enumerate(ch_imgs):
                seg_mp4 = os.path.join(work_dir, f"seg_ch_{idx:03d}_{p_idx}.mp4")
                label = f"Chapter {idx}: {ch['chapter_title']}" if p_idx == 0 else ""
                render_fast_ken_burns_boomerang(
                    image_path=img_p,
                    target_duration_sec=sec_per_img,
                    output_path=seg_mp4,
                    particle_overlay_path=particle_overlay,
                    chapter_label=label,
                    fps=30,
                )
                os.remove(img_p)
                all_segments.append(seg_mp4)

        seg_list_txt = os.path.join(work_dir, "seg_list.txt")
        with open(seg_list_txt, "w", encoding="utf-8") as f:
            for s in all_segments:
                f.write(f"file '{s}'\n")

        final_mp4 = os.path.join(work_dir, "final_sleep_video.mp4")
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", seg_list_txt, "-i", master_audio,
                "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy",
                "-t", f"{total_duration:.2f}", "-movflags", "+faststart", final_mp4,
            ],
            check=True,
        )

        print("[6/6] Uploading Private draft to YouTube & triggering Make.com Scenario 2 callback ...")
        yt_id = upload_private_youtube_draft(
            final_mp4,
            VIDEO_TITLE,
            f"Settle in and fall asleep to {TOPIC_LENS}.",
            "\n".join(chapter_timestamps_lines),
        )
        if MAKE_CALLBACK_WEBHOOK_URL:
            requests.post(
                MAKE_CALLBACK_WEBHOOK_URL,
                json={
                    "status": "completed",
                    "sheet_row_id": SHEET_ROW_ID,
                    "duration_hours": round(total_duration / 3600.0, 2),
                    "youtube_video_id": yt_id,
                    "youtube_studio_url": f"https://studio.youtube.com/video/{yt_id}/edit" if yt_id else None,
                },
                timeout=30,
            )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    run_zero_dollar_pipeline()
