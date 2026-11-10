from pathlib import Path

from .config import Settings
from .log import log

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _service(s: Settings):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=s.yt_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=s.yt_client_id,
        client_secret=s.yt_client_secret,
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def check_auth(s: Settings) -> None:
    if not s.youtube_ready:
        log("YouTube secrets missing → video will be saved as workflow artifact only")
        return
    try:
        _service(s)
        log("YouTube auth OK")
    except Exception as e:
        raise RuntimeError(
            f"YouTube refresh token rejected ({e}). If your OAuth app is in 'Testing' mode, tokens expire "
            f"after 7 days: publish the consent screen to 'In production' and mint a new refresh token."
        ) from e


def upload(s: Settings, video: Path, thumb: Path | None, title: str, description: str, tags: list[str], privacy: str) -> str:
    from googleapiclient.http import MediaFileUpload

    yt = _service(s)
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:4990],
            "tags": tags,
            "categoryId": "27",
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
        },
    }
    req = yt.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(video), mimetype="video/mp4", chunksize=64 * 1024 * 1024, resumable=True),
    )
    resp = None
    while resp is None:
        status, resp = req.next_chunk(num_retries=5)
        if status:
            log(f"  upload {int(status.progress() * 100)}%")
    vid = resp["id"]
    log(f"  uploaded https://youtu.be/{vid}")
    if thumb and thumb.exists():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb), mimetype="image/jpeg")).execute()
            log("  thumbnail set")
        except Exception as e:
            log(f"  thumbnail skipped (verify phone on channel to enable custom thumbnails): {str(e)[:150]}")
    return vid
