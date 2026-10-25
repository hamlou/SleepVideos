#!/usr/bin/env python3
"""100% Free ($0.00/Month) Production-Hardened Sleep Video Generator & YouTube Uploader.

Upgraded with the 6-Tier "Never Run Out of Credits" Free LLM Router:
  - Why single Gemini 2.5 Flash keys fail: Google AI Studio reduced `gemini-2.5-flash` free
    tier to ~20 requests/day (and a 3-hour 18-chapter script needs 20 calls).
  - Out-of-the-Box Solution Implemented Here:
    1. Step 1 (Research ONLY - 1 request/video): Uses `gemini-2.5-flash` with Google Search
       grounding (consumes only 1 of your 20 daily Flash calls!).
    2. Chapters & Outline Primary Engine #1 — Cerebras Cloud Free Tier (`CEREBRAS_API_KEY`):
       1,000,000 FREE tokens/day permanently (no credit card) on `llama-3.3-70b` / `qwen-3-32b`
       at 2,600+ tokens/sec (enough for 28 full 3-hour scripts every day!).
    3. Chapters & Outline Primary Engine #2 — Google AI Studio `gemma-3-27b-it` (`GEMINI_API_KEY`):
       Uses your exact same Google AI Studio API key, but calls `gemma-3-27b-it`, which gets
       14,400 FREE requests/day (instead of 20 on Flash)! Also supports comma-separated multiple
       keys (`key1,key2,key3`) for automatic key rotation.
    4. Chapters & Outline Primary Engine #3 — GroqCloud Free Tier (`GROQ_API_KEY`):
       No credit card required; rotates across `llama-3.3-70b-versatile` (100K tokens/day),
       `openai/gpt-oss-120b` (200K tokens/day), and `llama-3.1-8b-instant` (500K tokens/day,
       14,400 RPD).
    5. Chapters & Outline Primary Engine #4 — Mistral La Plateforme Free Tier (`MISTRAL_API_KEY`):
       1 BILLION free tokens/month on `mistral-large-latest` / `mistral-small-latest` (auto-paced
       for Mistral's 2 RPM batch limit).
    6. Chapters & Outline Primary Engine #5 — OpenRouter Free Auto-Router (`OPENROUTER_API_KEY`):
       Cycles through `openrouter/free`, `nvidia/nemotron-3-super-120b-a12b:free`,
       `qwen/qwen3.8-27b:free`, and `google/gemma-3-27b-it:free`.
"""

import itertools
import json
import os
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
# 1. FREE API KEYS (Supports comma-separated multi-key rotation, e.g. "k1,k2")
# ==============================================================================
GEMINI_API_KEYS = [
    k.strip() for k in os.environ.get("GEMINI_API_KEY", "").split(",") if k.strip()
]
CEREBRAS_API_KEYS = [
    k.strip() for k in os.environ.get("CEREBRAS_API_KEY", "").split(",") if k.strip()
]
GROQ_API_KEYS = [
    k.strip() for k in os.environ.get("GROQ_API_KEY", "").split(",") if k.strip()
]
MISTRAL_API_KEYS = [
    k.strip() for k in os.environ.get("MISTRAL_API_KEY", "").split(",") if k.strip()
]
OPENROUTER_API_KEYS = [
    k.strip() for k in os.environ.get("OPENROUTER_API_KEY", "").split(",") if k.strip()
]

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

# Round-robin key cyclers so multiple free keys distribute load evenly
_gemini_cycle = itertools.cycle(GEMINI_API_KEYS) if GEMINI_API_KEYS else None
_cerebras_cycle = itertools.cycle(CEREBRAS_API_KEYS) if CEREBRAS_API_KEYS else None
_groq_cycle = itertools.cycle(GROQ_API_KEYS) if GROQ_API_KEYS else None
_mistral_cycle = itertools.cycle(MISTRAL_API_KEYS) if MISTRAL_API_KEYS else None
_openrouter_cycle = itertools.cycle(OPENROUTER_API_KEYS) if OPENROUTER_API_KEYS else None


def _call_openai_compatible(
    url: str,
    api_key: str,
    model: str,
    prompt: str,
    extra_headers: Optional[Dict[str, str]] = None,
    min_delay_sec: float = 0.0,
) -> Optional[str]:
    """Helper for OpenAI-compatible endpoints (Cerebras, Groq, Mistral, OpenRouter)."""
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
            print(f"  [Info] {model} returned HTTP {resp.status_code}; rotating to next free model...")
    except Exception as exc:
        print(f"  [Info] {model} request exception ({exc}); rotating to next free model...")
    return None


def _call_google_ai_studio(
    api_key: str,
    model: str,
    prompt: str,
    use_search_grounding: bool = False,
    json_mode: bool = False,
) -> Optional[str]:
    """Calls Google AI Studio (`gemini-2.5-flash` or `gemma-3-27b-it` with 14,400 RPD)."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    is_gemma = model.startswith("gemma")
    payload: Dict = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7},
    }
    # Note: gemma-3-27b-it does not support responseMimeType or google_search tools
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


def call_free_llm(prompt: str, use_search_grounding: bool = False, json_mode: bool = False) -> str:
    """Zero-Quota-Fear 6-Tier Free LLM Waterfall Router.

    - Only uses `gemini-2.5-flash` when `use_search_grounding=True` (1 call per video!).
    - For all other 19 calls (outline + 18 long chapters), rotates automatically across:
      1. Cerebras Free Tier (1,000,000 tokens/day free: `llama-3.3-70b`, `llama3.1-8b`)
      2. Google AI Studio `gemma-3-27b-it` (14,400 requests/day free on your Gemini key!)
      3. GroqCloud Free Tier (`llama-3.3-70b-versatile`, `openai/gpt-oss-120b`, `llama-3.1-8b-instant`)
      4. Mistral Free Experiment Tier (1,000,000,000 tokens/month free: `mistral-small-latest`)
      5. OpenRouter `:free` Auto-Router (`openrouter/free`, `nvidia/nemotron-3-super-120b-a12b:free`,
         `qwen/qwen3.8-27b:free`, `google/gemma-3-27b-it:free`)
      6. `gemini-2.5-flash-lite` / `gemini-2.5-flash` as final reserve.
    """
    if json_mode:
        prompt = (
            f"{prompt}\n\nIMPORTANT: Return ONLY raw, valid JSON with no markdown code fences "
            f"and no conversational text before or after the JSON object."
        )

    # If live Google Search Grounding is requested (Step 1 only = 1 call/video), try Gemini Flash first
    if use_search_grounding and _gemini_cycle:
        for _ in range(len(GEMINI_API_KEYS)):
            key = next(_gemini_cycle)
            res = _call_google_ai_studio(key, "gemini-2.5-flash", prompt, use_search_grounding=True)
            if res:
                return res

    # TIER 1: Cerebras Cloud Free Tier (1,000,000 free tokens/day, 2,600 tok/s)
    if _cerebras_cycle:
        for model in ("llama-3.3-70b", "qwen-3-32b", "llama3.1-8b"):
            key = next(_cerebras_cycle)
            res = _call_openai_compatible(
                "https://api.cerebras.ai/v1/chat/completions", key, model, prompt
            )
            if res:
                return res

    # TIER 2: Google AI Studio `gemma-3-27b-it` (14,400 free requests/day on the same GEMINI_API_KEY!)
    if _gemini_cycle:
        for _ in range(len(GEMINI_API_KEYS)):
            key = next(_gemini_cycle)
            res = _call_google_ai_studio(key, "gemma-3-27b-it", prompt, use_search_grounding=False)
            if res:
                return res

    # TIER 3: GroqCloud Free Tier (100K-500K tokens/day across 3 separate model buckets)
    if _groq_cycle:
        for model in ("llama-3.3-70b-versatile", "openai/gpt-oss-120b", "llama-3.1-8b-instant"):
            key = next(_groq_cycle)
            res = _call_openai_compatible(
                "https://api.groq.com/openai/v1/chat/completions", key, model, prompt
            )
            if res:
                return res

    # TIER 4: Mistral La Plateforme Free Tier (1 Billion tokens/month, paced at 2 RPM = 31s)
    if _mistral_cycle:
        for model in ("mistral-small-latest", "open-mistral-nemo"):
            key = next(_mistral_cycle)
            res = _call_openai_compatible(
                "https://api.mistral.ai/v1/chat/completions",
                key,
                model,
                prompt,
                min_delay_sec=31.0,
            )
            if res:
                return res

    # TIER 5: OpenRouter `:free` Multi-Model Pool + `openrouter/free` Auto-Router
    if _openrouter_cycle:
        free_models = [
            "openrouter/free",
            "nvidia/nemotron-3-super-120b-a12b:free",
            "qwen/qwen3.8-27b:free",
            "google/gemma-3-27b-it:free",
            "meta-llama/llama-3.3-70b-instruct:free",
        ]
        for model in free_models:
            key = next(_openrouter_cycle)
            res = _call_openai_compatible(
                "https://openrouter.ai/api/v1/chat/completions", key, model, prompt
            )
            if res:
                return res

    # TIER 6: Final reserve fallback to `gemini-2.5-flash-lite` / `gemini-2.5-flash`
    if _gemini_cycle:
        for model in ("gemini-2.5-flash-lite", "gemini-2.5-flash"):
            key = next(_gemini_cycle)
            res = _call_google_ai_studio(key, model, prompt, use_search_grounding=False, json_mode=json_mode)
            if res:
                return res

    raise RuntimeError(
        "All configured free LLM tiers were exhausted or no API key was provided. "
        "Add at least one free key (CEREBRAS_API_KEY, GEMINI_API_KEY, GROQ_API_KEY, "
        "MISTRAL_API_KEY, or OPENROUTER_API_KEY) in GitHub Secrets."
    )


def extract_json_object(raw_text: str) -> Dict:
    """Safely extracts a JSON object even if an open-weights model wraps it in markdown."""
    cleaned = raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            return json.loads(match.group(0))
        raise


def step_1_research_and_outline(topic: str, num_chapters: int) -> List[Dict]:
    """Pulls 100 grounded facts (1 Flash call) and builds the chapter outline via high-quota models."""
    print(f"[1/6] Researching 100 verified historical/scientific facts for: {topic} ...")
    research_prompt = (
        f"Perform deep historical and sensory research on: '{topic}'. "
        f"Extract 100 specific, lesser-known, historically accurate facts, sensory details, tools, "
        f"architectural features, clothing textures, sounds, and daily routines from academic and primary sources. "
        f"Avoid generic Wikipedia overview summaries; focus on micro-history and lived human details."
    )
    verified_facts = call_free_llm(research_prompt, use_search_grounding=True, json_mode=False)
    time.sleep(4)

    print(f"[2/6] Building {num_chapters}-chapter JSON master outline ...")
    outline_prompt = (
        f"Using ONLY the verified research notes below on '{topic}', create a {num_chapters}-chapter "
        f"sleep documentary outline. Return ONLY valid JSON matching this exact schema:\n"
        f'{{"chapters": [{{"chapter_num": 1, "chapter_title": "...", "assigned_facts": "...", '
        f'"pexels_video_query": "dark rain window night", '
        f'"scene_image_prompts": ["prompt 1", "prompt 2", "prompt 3"]}}]}}\n\n'
        f"Each scene_image_prompt must describe a rich 16:9 widescreen historical oil painting with warm amber "
        f"lantern light and deep midnight blue shadows, ending with 'cozy nocturnal lighting, 16:9 widescreen, "
        f"text-free, no watermarks'.\n\nResearch Notes:\n{verified_facts}"
    )
    raw_json = call_free_llm(outline_prompt, use_search_grounding=False, json_mode=True)
    return extract_json_object(raw_json)["chapters"]


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
    """Downloads a free 1920x1080 Flux illustration from Pollinations.ai (with fallback canvas)."""
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


def fetch_pexels_clips(queries: List[str], work_dir: str, target_count: int = 20) -> List[str]:
    """Fetches 20 free HD atmospheric video clips from Pexels API for Minutes 0:00–2:00."""
    if not PEXELS_API_KEY:
        return []
    clip_paths: List[str] = []
    headers = {"Authorization": PEXELS_API_KEY}

    for q in queries:
        if len(clip_paths) >= target_count:
            break
        try:
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params={"query": q, "orientation": "landscape", "size": "medium", "per_page": 3},
                timeout=30,
            )
            if resp.status_code != 200:
                continue
            for vid in resp.json().get("videos", []):
                if len(clip_paths) >= target_count:
                    break
                files = sorted(vid.get("video_files", []), key=lambda x: abs((x.get("width") or 0) - 1920))
                if not files:
                    continue
                dl_url = files[0]["link"]
                raw_path = os.path.join(work_dir, f"pexels_raw_{len(clip_paths):03d}.mp4")
                norm_path = os.path.join(work_dir, f"seg_intro_{len(clip_paths):03d}.mp4")
                with requests.get(dl_url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(raw_path, "wb") as f:
                        for chunk in r.iter_content(1024 * 1024):
                            if chunk:
                                f.write(chunk)
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", raw_path,
                        "-t", "6",
                        "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=yuv420p",
                        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                        norm_path,
                    ],
                    check=True,
                )
                os.remove(raw_path)
                clip_paths.append(norm_path)
        except Exception:
            continue
    return clip_paths


def fetch_or_create_particle_overlay(work_dir: str) -> Optional[str]:
    """Fetches a black-background particle/ember overlay video from Pexels API for Screen blending."""
    if not PEXELS_API_KEY:
        return None
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
                norm_p = os.path.join(work_dir, "particles_norm.mp4")
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
    return None


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
        pexels_queries: List[str] = []
        last_ending = "Tonight, let your shoulders drop, let the outside world fade, and step quietly into the past."

        print(f"[3/6] Writing {len(chapters)} chapters + generating neural voiceovers & Flux 16:9 visuals ...")
        for idx, ch in enumerate(chapters, start=1):
            ch_prompt = (
                f"Write Chapter {idx}: '{ch['chapter_title']}' for our sleep documentary '{VIDEO_TITLE}'. "
                f"Write between 1,050 and 1,150 words of continuous spoken narration (no headers, no bullets, "
                f"no [Music] tags). Use a calm, soothing, second-person sensory storytelling tone ('you walk slowly...'), "
                f"gentle dry humor, and simple grammar. Incorporate these verified facts: {ch['assigned_facts']}. "
                f"Transition smoothly from the end of the previous chapter: '{last_ending}'."
            )
            ch_script = call_free_llm(ch_prompt, use_search_grounding=False, json_mode=False).strip()
            last_ending = " ".join(ch_script.split()[-40:])
            time.sleep(2)

            vo_path = os.path.join(work_dir, f"vo_{idx:03d}.mp3")
            vtt_path = os.path.join(work_dir, f"vo_{idx:03d}.vtt")
            generate_free_voiceover_and_subtitles(ch_script, vo_path, vtt_path, VOICE_NAME)
            vo_files.append(vo_path)
            chapter_durations.append(get_media_duration(vo_path))

            pexels_queries.append(ch.get("pexels_video_query", "rain night lantern"))
            ch_imgs: List[str] = []
            for p_idx, img_prompt in enumerate(ch.get("scene_image_prompts", [])[:3]):
                img_path = os.path.join(work_dir, f"img_{idx:03d}_{p_idx}.jpg")
                download_pollinations_flux_image(img_prompt, img_path, seed=idx * 100 + p_idx)
                ch_imgs.append(img_path)
            chapter_images.append(ch_imgs)

        print("[4/6] Concatenating voiceovers and mixing -28dB ambient bed ...")
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

        print("[5/6] Rendering 20 opening video clips + Chapter-Synced Ken Burns scenes with Screen particles ...")
        intro_clips = fetch_pexels_clips(pexels_queries, work_dir, target_count=20)
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