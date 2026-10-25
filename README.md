# 🌙 SleepVideos Factory

Production-hardened, automated YouTube sleep video generator and private uploader running 100% on free GitHub Actions compute and free AI API tiers.

## ⚙️ Architecture & Multi-Tier LLM Router

This workflow solves Google AI Studio's 20 request/day free limit by routing through a 6-tier free failover engine:
1. **Google AI Studio (`gemini-2.5-flash` with Google Search Grounding):** Used only for Step 1 research (1 call per video) to fetch 100 real facts.
2. **Cerebras Cloud Free Tier (`llama-3.3-70b` / `qwen-3-32b`):** 1,000,000 free tokens/day at 2,600+ tokens/sec for chapter drafting.
3. **Google AI Studio Gemma 3 (`gemma-3-27b-it`):** 14,400 free requests/day using the same Google AI key.
4. **GroqCloud Free Tier (`llama-3.3-70b-versatile` / `gpt-oss-120b` / `llama-3.1-8b`):** 800,000 combined tokens/day.
5. **Mistral La Plateforme Experiment Plan:** 1 Billion free tokens/month.
6. **OpenRouter Free Tier:** Automatic traffic-congestion load balancer across free open models.

## 🔑 Required Repository Secrets

Add the following under **GitHub Repo Settings → Secrets and variables → Actions → New repository secret**:

| Secret Name | Description | Required? |
|---|---|---|
| `GEMINI_API_KEY` | Google AI Studio Key (for Google Search facts & Gemma 3) | Recommended |
| `CEREBRAS_API_KEY` | Cerebras Cloud Key (1M free tokens/day for chapter drafting) | Recommended |
| `GROQ_API_KEY` | GroqCloud Key (800K free tokens/day) | Optional failover |
| `MISTRAL_API_KEY` | Mistral API Key (1B free tokens/month) | Optional failover |
| `OPENROUTER_API_KEY` | OpenRouter Key | Optional failover |
| `PEXELS_API_KEY` | Pexels Free API Key (for opening video motion clips) | Required |
| `YOUTUBE_CLIENT_ID` | Google Cloud Console OAuth 2.0 Client ID | Required |
| `YOUTUBE_CLIENT_SECRET` | Google Cloud Console OAuth 2.0 Client Secret | Required |
| `YOUTUBE_REFRESH_TOKEN` | OAuth 2.0 Refresh Token (never expires) | Required |
| `MAKE_CALLBACK_WEBHOOK_URL` | Make.com Webhook URL (for completion callback/notification) | Optional |

## 🚀 How to Run

### Manual Test Run (GitHub UI):
1. Navigate to **Actions** → **Zero-Dollar Daily YouTube Sleep Video Factory**.
2. Click **Run workflow**.
3. Select `num_chapters`:
   - `2` for a quick 15-minute test render.
   - `18` for full ~3-hour bedtime documentary.

### Automated Trigger (Make.com):
- The Make.com scenario triggers this workflow daily via GitHub `repository_dispatch` with type `build_sleep_video`, reading topics from Google Sheets.
