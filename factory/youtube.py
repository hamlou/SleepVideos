import datetime as dt
from pathlib import Path

from .config import Settings
from .log import log


def _creds(s: Settings):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token=None,
        refresh_token=s.yt_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=s.yt_client_id,
        client_secret=s.yt_client_secret,
    )
    creds.refresh(Request())
    return creds


def _service(s: Settings, api: str = "youtube", version: str = "v3"):
    from googleapiclient.discovery import build

    return build(api, version, credentials=_creds(s), cache_discovery=False)


def check_auth(s: Settings) -> None:
    if not s.youtube_ready:
        log("YouTube secrets missing → video will be saved as workflow artifact only")
        return
    try:
        _creds(s)
        log("YouTube auth OK")
    except Exception as e:
        raise RuntimeError(
            f"YouTube refresh token rejected ({e}). Mint a new refresh token in OAuth Playground "
            f"and update the YOUTUBE_REFRESH_TOKEN secret."
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
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True},
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
        set_thumbnail(s, vid, thumb)
    return vid


def set_thumbnail(s: Settings, vid: str, image: Path) -> None:
    from googleapiclient.http import MediaFileUpload

    _service(s).thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(image), mimetype="image/jpeg")).execute()
    log(f"  thumbnail set on {vid}")


def publish(s: Settings, vid: str) -> None:
    yt = _service(s)
    cur = yt.videos().list(part="status", id=vid).execute()["items"][0]["status"]
    body = {"id": vid, "status": {
        "privacyStatus": "public",
        "selfDeclaredMadeForKids": cur.get("selfDeclaredMadeForKids", False),
        "containsSyntheticMedia": True,
        "embeddable": cur.get("embeddable", True),
        "license": cur.get("license", "youtube"),
        "publicStatsViewable": cur.get("publicStatsViewable", True),
    }}
    yt.videos().update(part="status", body=body).execute()
    log(f"  {vid} is now public")


def status(s: Settings, vid: str) -> dict | None:
    items = _service(s).videos().list(part="status,statistics,snippet", id=vid).execute().get("items", [])
    return items[0] if items else None


def analytics(s: Settings, vid: str, published: dt.datetime) -> dict:
    ya = _service(s, "youtubeAnalytics", "v2")
    start = published.date().isoformat()
    end = dt.date.today().isoformat()

    def q(**kw):
        try:
            r = ya.reports().query(ids="channel==MINE", startDate=start, endDate=end, filters=f"video=={vid}", **kw).execute()
            cols = [c["name"] for c in r.get("columnHeaders", [])]
            return [dict(zip(cols, row)) for row in r.get("rows", [])]
        except Exception as e:
            log(f"  analytics query {kw.get('metrics', '')[:40]} failed: {str(e)[:150]}")
            return []

    core = q(metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,subscribersGained,shares,comments")
    impressions = q(metrics="videoThumbnailImpressions,videoThumbnailImpressionsClickRate")
    retention = q(dimensions="elapsedVideoTimeRatio", metrics="audienceWatchRatio,relativeRetentionPerformance")
    traffic = q(dimensions="insightTrafficSourceType", metrics="views,estimatedMinutesWatched", sort="-views")
    return {
        "core": core[0] if core else {},
        "impressions": impressions[0] if impressions else {},
        "retention": retention,
        "traffic": traffic,
    }
