import math
import os
import re
import threading
from datetime import datetime, timezone

import httplib2
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from apis.signal_contract import (
    STATUS_NO_KEY,
    STATUS_OK,
    STATUS_QUOTA,
    classify_exception,
    classify_http,
    make_signal,
)
from apis.youtube_quota import (
    format_quota_detail,
    has_quota_for_search,
    record_usage,
    units_for_lightweight_search,
    units_per_search_call,
)


def _youtube_key() -> str:
    from config.settings import get_settings

    get_settings()
    return os.getenv("YOUTUBE_API_KEY", "").strip()


_youtube_client = None
_client_lock = threading.Lock()
_warmup_started = False

# One search.list call only (no videos.list) — faster, ~100 quota units
_LIGHTWEIGHT = os.getenv("YOUTUBE_LIGHTWEIGHT", "").lower() in ("1", "true", "yes")
_MAX_RESULTS = max(3, min(int(os.getenv("YOUTUBE_MAX_RESULTS", "10") or 10), 10))


def api_timeout() -> float:
    """Socket timeout for Data API calls.

    Without one, httplib2 uses the global default socket timeout — effectively
    unbounded — so a slow read stalls discovery and then surfaces as a hard ERROR
    ("The read operation timed out" killed the `youtube` signal on run 66). Bounded
    here so a slow call degrades into a normal transient-failure signal instead.
    """
    try:
        return max(3.0, float(os.getenv("YOUTUBE_API_TIMEOUT", "15")))
    except ValueError:
        return 15.0


def _get_youtube_client():
    global _youtube_client
    if _youtube_client is not None:
        return _youtube_client
    with _client_lock:
        if _youtube_client is None:
            # cache_discovery=False avoids disk cache; client is reused after first build
            _youtube_client = build(
                "youtube",
                "v3",
                developerKey=_youtube_key(),
                cache_discovery=False,
                http=httplib2.Http(timeout=api_timeout()),
            )
    return _youtube_client


def warmup_youtube_client():
    """Pay the slow google-api-client startup cost before discovery (optional)."""
    if not _youtube_key():
        return
    try:
        _get_youtube_client()
    except Exception:
        pass


def start_youtube_warmup_background():
    """Non-blocking warmup while the user reads prompts."""
    global _warmup_started
    if _warmup_started or not _youtube_key():
        return
    _warmup_started = True
    threading.Thread(target=warmup_youtube_client, daemon=True).start()


def _published_after_iso():
    return (
        datetime.now(timezone.utc)
        .replace(year=datetime.now(timezone.utc).year - 1)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def _search_videos(youtube, query: str):
    return (
        youtube.search()
        .list(
            q=query,
            part="snippet",
            type="video",
            maxResults=_MAX_RESULTS,
            order="relevance",
            publishedAfter=_published_after_iso(),
            fields="items(id/kind,id/videoId,snippet/title,snippet/publishedAt)",
        )
        .execute()
    )


def _lightweight_signal(search_response):
    items = [
        item
        for item in search_response.get("items", [])
        if item.get("id", {}).get("kind") == "youtube#video"
    ]
    titles = [
        item.get("snippet", {}).get("title")
        for item in items
        if item.get("snippet", {}).get("title")
    ]
    if not items:
        return make_signal(
            connected=True,
            active=True,
            score=0,
            confidence=0.6,
            data=None,
            status=STATUS_OK,
            status_detail="No videos returned (lightweight search)",
        )
    score = min(len(items) * (100 / max(_MAX_RESULTS, 1)), 100)
    record_usage(units=units_for_lightweight_search())
    return make_signal(
        connected=True,
        active=True,
        score=round(score, 2),
        confidence=0.75,
        data={"titles": titles, "mode": "lightweight"},
        status=STATUS_OK,
        status_detail=f"Lightweight search — {format_quota_detail()}",
    )


def search_youtube(query):
    if not _youtube_key():
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="Set YOUTUBE_API_KEY in .env",
        )

    if not has_quota_for_search():
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_QUOTA,
            status_detail=f"Daily quota exhausted — {format_quota_detail()}",
        )

    try:
        youtube = _get_youtube_client()
        search_response = _search_videos(youtube, query)

        if _LIGHTWEIGHT:
            return _lightweight_signal(search_response)

        video_ids = [
            item["id"]["videoId"]
            for item in search_response.get("items", [])
            if item.get("id", {}).get("kind") == "youtube#video"
        ]

        if not video_ids:
            return make_signal(
                connected=True,
                active=True,
                score=0,
                confidence=0.7,
                data=None,
                status=STATUS_OK,
                status_detail="No videos returned for query",
            )

        stats_response = (
            youtube.videos()
            .list(
                part="statistics,snippet",
                id=",".join(video_ids),
                fields="items(statistics/viewCount,snippet/title,snippet/publishedAt,snippet/description)",
            )
            .execute()
        )

        total_velocity = 0
        titles = []
        descriptions = []

        for item in stats_response.get("items", []):
            stats = item.get("statistics", {})
            snippet = item.get("snippet", {})

            view_count = int(stats.get("viewCount", 0))
            publish_date = snippet.get("publishedAt")

            if not publish_date:
                continue

            publish_datetime = datetime.fromisoformat(publish_date.replace("Z", "+00:00"))

            days_live = max(
                (datetime.now(timezone.utc) - publish_datetime).days,
                1,
            )

            velocity = view_count / days_live
            total_velocity += velocity

            titles.append(snippet.get("title"))
            descriptions.append((snippet.get("description") or "")[:600])

        avg_velocity = total_velocity / max(len(video_ids), 1)
        scaled_score = min(math.log1p(avg_velocity) * 10, 100)

        record_usage(units=units_per_search_call())

        return make_signal(
            connected=True,
            active=True,
            score=round(scaled_score, 2),
            confidence=0.9,
            data={"titles": titles, "descriptions": descriptions},
            status=STATUS_OK,
            status_detail=format_quota_detail(),
        )

    except HttpError as e:
        status_code = e.resp.status if e.resp else 0
        body = str(e)
        status, detail = classify_http(status_code, body)
        if "quota" in body.lower():
            status = STATUS_QUOTA
            detail = f"{detail} — {format_quota_detail()}"
        print(f"[YouTube API Error] {detail}")
        return make_signal(
            connected=False,
            active=False,
            status=status,
            status_detail=detail,
        )

    except Exception as e:
        status, detail = classify_exception(e)
        print(f"[YouTube API Error] {detail}")
        return make_signal(
            connected=False,
            active=False,
            status=status,
            status_detail=detail,
        )


_VIDEO_ID_RE = re.compile(
    r"""(?:
        youtu\.be/                         # short links
      | youtube\.com/(?:watch\?(?:.*&)?v=  # standard watch
                       |embed/|shorts/|v/) # embed / shorts / v
    )([A-Za-z0-9_-]{11})                   # the 11-char id
    """,
    re.VERBOSE,
)


def extract_youtube_video_id(text: str) -> str | None:
    """
    Pull a YouTube video id from a URL or accept a bare 11-char id.
    Returns None if nothing id-shaped is found.
    """
    text = (text or "").strip()
    if not text:
        return None
    match = _VIDEO_ID_RE.search(text)
    if match:
        return match.group(1)
    # Bare id (exactly 11 url-safe chars, no spaces)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", text):
        return text
    return None


def fetch_video_metadata(video_id_or_url: str) -> dict | None:
    """
    Look up a single YouTube video's snippet (title, channel, description).

    Accepts a watch/shorts/youtu.be URL or a bare video id. Returns
    {"video_id", "title", "channel", "description"} or None when the video
    can't be resolved (no key, bad id, quota, network error).
    """
    if not _youtube_key():
        return None
    video_id = extract_youtube_video_id(video_id_or_url)
    if not video_id:
        return None
    try:
        youtube = _get_youtube_client()
        response = (
            youtube.videos()
            .list(
                part="snippet",
                id=video_id,
                fields="items(snippet/title,snippet/channelTitle,snippet/description)",
            )
            .execute()
        )
        record_usage(units=1)  # videos.list is 1 unit
        items = response.get("items") or []
        if not items:
            return None
        snippet = items[0].get("snippet") or {}
        return {
            "video_id": video_id,
            "title": snippet.get("title") or "",
            "channel": snippet.get("channelTitle") or "",
            "description": (snippet.get("description") or "")[:600],
        }
    except Exception as exc:  # network/quota/HTTP — caller falls back to manual text
        print(f"[YouTube API] Could not fetch video {video_id}: {str(exc)[:120]}")
        return None
