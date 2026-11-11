# Sleep Video Factory

Fully automated long-form "history for sleep" videos on free GitHub Actions:
topic → research → outline → narration script → neural voice → paintings → rendered 1080p video → YouTube upload.

Runs daily at 02:07 Tunisia time (01:07 UTC) from `topics.txt`, or on demand.

## How it works

| Step | What | Free source |
|---|---|---|
| 1 Research | 80 micro-facts | LLM chain (below) |
| 2 Outline | N distinct chapters, batched 6 at a time | LLM chain |
| 3 Script | ~1,100 words per chapter, calm 2nd-person | LLM chain |
| 3 Voice | edge-tts neural voice, slowed and warmed | Microsoft Edge TTS |
| 3 Images | AI paintings + public-domain museum art | Cloudflare Flux, Pollinations, The Met |
| 4 Audio | voice + soft brown-noise rain bed, loudness-normalised | FFmpeg |
| 5 Video | 20 intro cuts, slow Ken Burns per image, dust particles, chapter titles | FFmpeg |
| 6 Publish | title, description, chapters, tags, thumbnail, AI disclosure | YouTube Data API |

**LLM chain**: the first provider that works is reused; failing ones (401/402/403/404) are skipped for the rest of the run.
`GitHub Models (built-in token)` → `Gemini` → `Groq` → `Cerebras` → `Mistral` → `OpenRouter` → `Cohere` → `Pollinations`.
With no secrets at all, GitHub Models + Pollinations still work.

## Setup (once)

### 1. Secrets (Settings → Secrets and variables → Actions)

| Secret | Needed? | Where to get it |
|---|---|---|
| `YOUTUBE_CLIENT_ID` | for upload | Google Cloud → APIs → enable *YouTube Data API v3* → Credentials → OAuth client (Web), redirect `https://developers.google.com/oauthplayground` |
| `YOUTUBE_CLIENT_SECRET` | for upload | same |
| `YOUTUBE_REFRESH_TOKEN` | for upload | [OAuth Playground](https://developers.google.com/oauthplayground) → ⚙ "Use your own OAuth credentials" → scope `https://www.googleapis.com/auth/youtube.upload` → exchange → copy refresh token |
| `GEMINI_API_KEY` | recommended | aistudio.google.com (comma-separate several keys) |
| `GROQ_API_KEY` | optional | console.groq.com |
| `CEREBRAS_API_KEY` | optional | cloud.cerebras.ai |
| `MISTRAL_API_KEY` | optional | console.mistral.ai (free tier) |
| `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_API_TOKEN` | recommended | dash.cloudflare.com → Workers AI (free daily quota), token with *Workers AI* permission. Better images than Pollinations. |
| `POLLINATIONS_TOKEN` | optional | auth.pollinations.ai (higher limits) |
| `MAKE_CALLBACK_WEBHOOK_URL` | optional | Make.com webhook, receives `{status, sheet_row_id, youtube_video_id, ...}` |

> ⚠️ **Refresh token dies after 7 days** if the Google OAuth consent screen is in *Testing*. Set it to **In production** (no review needed for your own channel), then mint the refresh token.
> Uploads via an unverified API project are locked **private** by YouTube until the project passes an audit. Private is the default here anyway — review, then publish.

### 2. Optional variables (Settings → Variables)
`NUM_CHAPTERS` (default 18 ≈ 2.5–3 h) · `VOICE_NAME` (default `en-US-AndrewMultilingualNeural`) · `PRIVACY_STATUS` (default `private`)

## Run

- **Test**: Actions → *Sleep Video Factory* → Run workflow → chapters `2` (~15 min video, ~20 min build).
- **Daily**: automatic. Takes the first line of `topics.txt`, moves it to `topics_done.txt` after success.
- **Make.com**: `repository_dispatch` type `build_sleep_video` with `client_payload` `{video_title, topic_lens, num_chapters, voice_name, sheet_row_id}`.

Every run uploads an artifact with `script.md`, `outline.json`, `metadata.json`, `thumbnail.jpg` (and `video.mp4` when YouTube secrets are missing).

## Local run

```bash
pip install -r requirements.txt   # plus ffmpeg on PATH
NUM_CHAPTERS=2 VIDEO_TITLE="..." TOPIC_LENS="..." python -m factory.main
```

## Monetization notes

YouTube's "inauthentic / mass-produced content" policy is the real risk for automated channels, not the tech.
What this pipeline already does: unique researched script per video, chapters, disclosure of synthetic voice (`containsSyntheticMedia`), public-domain credits, private-first uploads.
What you should still do: watch/skim each video before publishing, edit titles/thumbnails by hand, keep a consistent channel voice, and don't publish more than ~1/day.
