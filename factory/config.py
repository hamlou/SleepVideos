import os
from dataclasses import dataclass, field
from pathlib import Path


def _keys(name: str) -> list[str]:
    return [k.strip() for k in os.environ.get(name, "").split(",") if k.strip()]


def _env(name: str, default: str = "") -> str:
    v = os.environ.get(name, "").strip()
    return v or default


@dataclass
class Job:
    title: str
    topic: str
    chapters: int
    voice: str
    sheet_row: str
    privacy: str
    from_queue: bool = False


@dataclass
class Settings:
    github_token: str = field(default_factory=lambda: _env("GITHUB_TOKEN"))
    gemini: list[str] = field(default_factory=lambda: _keys("GEMINI_API_KEY"))
    groq: list[str] = field(default_factory=lambda: _keys("GROQ_API_KEY"))
    cerebras: list[str] = field(default_factory=lambda: _keys("CEREBRAS_API_KEY"))
    openrouter: list[str] = field(default_factory=lambda: _keys("OPENROUTER_API_KEY"))
    mistral: list[str] = field(default_factory=lambda: _keys("MISTRAL_API_KEY"))
    cohere: list[str] = field(default_factory=lambda: _keys("COHERE_API_KEY"))
    pollinations_token: str = field(default_factory=lambda: _env("POLLINATIONS_TOKEN"))
    hf_token: str = field(default_factory=lambda: _env("HF_TOKEN"))
    pixabay_key: str = field(default_factory=lambda: _env("PIXABAY_API_KEY"))
    cf_account: str = field(default_factory=lambda: _env("CLOUDFLARE_ACCOUNT_ID"))
    cf_token: str = field(default_factory=lambda: _env("CLOUDFLARE_API_TOKEN"))
    yt_client_id: str = field(default_factory=lambda: _env("YOUTUBE_CLIENT_ID"))
    yt_client_secret: str = field(default_factory=lambda: _env("YOUTUBE_CLIENT_SECRET"))
    yt_refresh_token: str = field(default_factory=lambda: _env("YOUTUBE_REFRESH_TOKEN"))
    azure_key: str = field(default_factory=lambda: _env("AZURE_SPEECH_KEY"))
    azure_region: str = field(default_factory=lambda: _env("AZURE_SPEECH_REGION"))
    yt_api_key: str = field(default_factory=lambda: _env("YOUTUBE_API_KEY"))
    callback_url: str = field(default_factory=lambda: _env("MAKE_CALLBACK_WEBHOOK_URL"))
    out_dir: Path = field(default_factory=lambda: Path(_env("OUT_DIR", "out")).resolve())
    fps: int = 30
    width: int = 1920
    height: int = 1080

    @property
    def youtube_ready(self) -> bool:
        return bool(self.yt_client_id and self.yt_client_secret and self.yt_refresh_token)


QUEUE_FILE = Path("topics.txt")
DONE_FILE = Path("topics_done.txt")
