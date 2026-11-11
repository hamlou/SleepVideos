"""Runs when any factory workflow fails: read the log, classify, auto-retry transient errors, explain on Telegram."""
import io
import os
import re
import sys
import zipfile

import requests

from . import telegram
from .config import Settings
from .llm import LLM
from .log import log

REPO = os.environ.get("GITHUB_REPOSITORY", "hamlou/SleepVideos")
API = f"https://api.github.com/repos/{REPO}/actions"
HDR = {"Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN', '')}", "Accept": "application/vnd.github+json"}

KNOWN = [
    (r"invalid_grant|Token has been expired or revoked|refresh token rejected", False,
     "YouTube login expired/revoked. Make a new refresh token in OAuth Playground (scopes: youtube + yt-analytics.readonly) "
     "and send it to me in the bot: ⚙️ Settings → YouTube token."),
    (r"quotaExceeded|exceeded your .*quota.*youtube|uploadLimitExceeded", False,
     "YouTube daily API quota reached. Nothing to fix: tomorrow's run will work."),
    (r"Every LLM provider failed|AllProvidersFailed", True, "All free AI writers were down at the same time. Retrying."),
    (r"TTS failed|No audio was received", True, "The free voice service refused too many requests. Retrying."),
    (r"ReadTimeout|ConnectionError|Connection reset|503|502|Temporary failure|getaddrinfo", True,
     "A network/service hiccup. Retrying."),
    (r"No space left on device", False, "The GitHub machine ran out of disk. Lower chapters in ⚙️ Settings."),
    (r"The job running on runner .* has exceeded the maximum execution time|timed out after", False,
     "The run hit GitHub's time limit. Lower chapters in ⚙️ Settings (e.g. 14)."),
]


def run_log(run_id: str) -> str:
    r = requests.get(f"{API}/runs/{run_id}/logs", headers=HDR, timeout=60)
    if r.status_code != 200:
        return ""
    text = []
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        for n in z.namelist():
            if n.endswith(".txt"):
                text.append(z.read(n).decode("utf-8", "replace"))
    full = "\n".join(text)
    errs = [l for l in full.splitlines() if re.search(r"Error|Traceback|error|failed|✗|⚠", l)]
    return "\n".join(errs[-60:])[-6000:]


def main() -> int:
    run_id = os.environ["FAILED_RUN_ID"]
    name = os.environ.get("FAILED_RUN_NAME", "workflow")
    attempt = int(os.environ.get("FAILED_RUN_ATTEMPT", "1"))
    url = os.environ.get("FAILED_RUN_URL", "")
    excerpt = run_log(run_id)
    log(f"failure in {name} attempt {attempt}")
    hint, retry = None, False
    for pat, transient, msg in KNOWN:
        if re.search(pat, excerpt, re.I):
            hint, retry = msg, transient
            break
    try:
        explain = LLM(Settings()).ask(
            "Explain this GitHub Actions failure of an automated YouTube video pipeline to a non-programmer in 3 short "
            "sentences: what broke, whether it fixes itself, and the exact action the owner should take (or 'nothing').\n"
            f"Known hint: {hint}\nLog excerpt:\n{excerpt[-4000:]}"
        )
    except Exception:
        explain = hint or "Could not analyze the log automatically."
    will_retry = retry and attempt < 2
    if will_retry:
        requests.post(f"{API}/runs/{run_id}/rerun-failed-jobs", headers=HDR, timeout=30)
    telegram.send(
        f"🩺 <b>Watcher: {telegram.esc(name)} failed</b> (attempt {attempt})\n\n{telegram.esc(explain)}\n\n"
        + ("🔁 Retrying automatically now." if will_retry else "⏸ Not retrying automatically.")
        + (f"\n\nLog: {url}" if url else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
