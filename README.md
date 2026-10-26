# 🌙 SleepVideos Factory

100% Free ($0.00/Month, ZERO Credit Card Required), production-grade automated YouTube sleep documentary generator and private uploader running entirely on free GitHub Actions compute, open-source FFmpeg procedural rendering, and multi-tier free AI engines.

---

## 🏛️ Authentic "Sleepless Historian" Script Architecture

This engine produces genuine, hypnotic, monetizable sleep documentaries following strict sleep-study guidelines:
1. **Continuous 2nd-Person Invisible Time-Traveler Immersion:** Listener is cast as "you" safely and quietly walking through candlelit cloisters, nocturnal workshops, and rain-swept courtyards.
2. **Sleep-Friendly Lexical Filtering (Zero Cortisol Spikes):** Explicitly filters out jarring, sudden, or violent vocabulary. Everyday hardships are reframed into dry, understated observational wit.
3. **5-Sense Micro-History Density:** Every section weaves tactile sensory anchors (warm beeswax, damp wool, ink on vellum, glowing tallow candles, rain against leaded glass).
4. **Non-Overlapping Room Progression:** Each chapter covers a unique physical chamber or nighttime trade to prevent repetitive phrasing across 2.5–3 hour long-form videos.
5. **Stage Cue & Header Scrubber:** Automatically strips markdown formatting, bracketed sound cues (`[Pause]`), and chapter headings before passing to `edge-tts`.

---

## 🎞️ 100% Key-Free Procedural Visual Engine (No Pexels Needed)

- **Procedural Golden Embers (`fetch_or_create_particle_overlay`):** Uses FFmpeg `lavfi` temporal noise, bicubic scaling, Gaussian blur, and warm color balance to generate 1080p floating golden embers on a black screen.
- **20 Dynamic Camera Cuts (00:00–02:00):** Renders 20 distinct 6-second dynamic camera cuts (pan left, pan right, lantern tilt-up, diagonal drift, push-in, and pull-out) with subtle candle-flicker light modulation from Flux paintings.
- **Synced Ken Burns Chapters:** Loops slow, soothing zoom-in and zoom-out cycles with chapter labels for the duration of each chapter.

---

## ⚡ 8-Tier Zero-Credit-Card Free LLM Waterfall

To ensure 100% uptime with zero billing or credit cards:
1. **Google AI Studio (`gemini-2.5-flash` with Search Grounding):** Step 1 research only (1 call/video).
2. **Google AI Studio Gemma 3 (`gemma-3-27b-it`):** 14,400 free calls/day per key with multi-key rotation.
3. **GroqCloud Free Tier:** Versatile Llama 3.3 70B & 8B instant fallbacks.
4. **Cohere Trial Key:** 1,000 free calls/month (`command-r-plus-08-2024`).
5. **Hugging Face Token:** Free serverless inference router (`Qwen2.5-72B`, `Llama-3.3-70B`).
6. **Cerebras / OpenRouter:** High-speed free tier options.
7. **GitHub Models API:** Built-in `GITHUB_TOKEN` calling `gpt-4o-mini` & `Meta-Llama-3.3-70B-Instruct`.
8. **Pollinations.ai Free Engine:** Zero signup, zero API key, zero-card automated fallback.

---

## 🔑 GitHub Repository Secrets Configuration

Add these under **Repository Settings → Secrets and variables → Actions → New repository secret**:

| Secret Name | Purpose | Required / Default |
|---|---|---|
| `GEMINI_API_KEY` | Google AI Studio Keys (supports comma-separated rotation: `key1,key2,key3`) | Highly Recommended |
| `COHERE_API_KEY` | Cohere Trial Key | Fallback (No Card) |
| `HF_TOKEN` | Hugging Face Free Inference Token | Fallback (No Card) |
| `GROQ_API_KEY` | GroqCloud Free API Key | Optional Fallback |
| `YOUTUBE_CLIENT_ID` | OAuth 2.0 Web Client ID from Google Cloud Console | Required for Upload |
| `YOUTUBE_CLIENT_SECRET` | OAuth 2.0 Web Client Secret | Required for Upload |
| `YOUTUBE_REFRESH_TOKEN` | OAuth 2.0 Refresh Token (from Google OAuth 2.0 Playground) | Required for Upload |
| `MAKE_CALLBACK_WEBHOOK_URL` | Make.com Scenario 2 Webhook URL to update Google Sheets / notify | Optional |
| `PEXELS_API_KEY` | Pexels Stock Video API Key | Optional (FFmpeg procedural engine active) |

---

## 🚀 How to Run

### Manual Dispatch (GitHub Actions Tab):
1. Navigate to **Actions** → **Zero-Dollar Daily YouTube Sleep Video Factory**.
2. Click **Run workflow**.
3. Choose `num_chapters`:
   - `2` or `3` for a quick 15-20 minute test build.
   - `18` for a full 2.5–3 hour sleep documentary.
4. When finished, your video will be waiting in **YouTube Studio** as a **Private Draft** with chapters, tags, and Synthetic Media disclosure already pre-filled.

### Automated Daily Dispatch (Make.com):
- Import `make_com_sleep_video_blueprint.json` into Make.com to trigger daily video generation from your Google Sheets topic queue.
