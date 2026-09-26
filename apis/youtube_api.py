import math
import os
import re
import socket
import threading
from datetime import datetime, timezone

import httplib2

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
from core import process_state
from core.logging import get_logger

logger = get_logger("apis.youtube_api")


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

    8s, not 15: run 74 spent 30 of its 37.8-second discovery watching `youtube` and
    `youtube_comments` each wait out the old timeout against a dead endpoint. A
    Data API call that has not answered in 8 seconds is not about to.
    """
    try:
        return max(3.0, float(os.getenv("YOUTUBE_API_TIMEOUT", "8")))
    except ValueError:
        return 8.0


# Process-level "the Data API is not answering" latch.
# ----------------------------------------------------
# `youtube` and `youtube_comments` both route through this module, so on run 74 a
# single unreachable endpoint cost two full socket timeouts. A read timeout is
# transient, so the session breaker in `register_signals` (which trips on hard
# statuses — quota, auth) never fires for it. This latch is the narrow version of
# that idea: once a call has actually timed out, later calls in the same process
# give up immediately instead of waiting out the timeout again.
#
# Deliberately narrow: only a timeout arms it. A quota or auth failure must not,
# because those already have their own handling, and a latch that armed on any
# error would disable a working signal for the rest of a session.
_API_UNREACHABLE = ""
_UNREACHABLE_LOCK = threading.Lock()
_TIMEOUT_MARKERS = ("timed out", "timeout")


def note_api_failure(exc: BaseException) -> None:
    """Arm the unreachable latch if `exc` is a socket/read timeout. Never raises."""
    global _API_UNREACHABLE
    message = str(exc) or exc.__class__.__name__
    is_timeout = isinstance(exc, TimeoutError | socket.timeout) or any(
        marker in message.lower() for marker in _TIMEOUT_MARKERS
    )
    if not is_timeout:
        return
    with _UNREACHABLE_LOCK:
        if not _API_UNREACHABLE:
            _API_UNREACHABLE = message
            logger.info("YouTube Data API marked unreachable for this run: %s", message)


def api_unreachable() -> str:
    """The timeout message that armed the latch, or "" while the API is answering."""
    with _UNREACHABLE_LOCK:
        return _API_UNREACHABLE


def reset_api_unreachable() -> None:
    """Clear the latch (tests, and the CLI's give-everything-another-chance path)."""
    global _API_UNREACHABLE
    with _UNREACHABLE_LOCK:
        _API_UNREACHABLE = ""


def _get_youtube_client():
    global _youtube_client
    if _youtube_client is not None:
        return _youtube_client
    with _client_lock:
        if _youtube_client is None:
            if _skip_live_youtube_client():
                raise RuntimeError("live YouTube client forbidden in tests (C9)")
            from googleapiclient.discovery import build

            # static_discovery=True uses the bundled doc — no googleapis HTTPS (C9).
            _youtube_client = build(
                "youtube",
                "v3",
                developerKey=_youtube_key(),
                cache_discovery=False,
                static_discovery=True,
                http=httplib2.Http(timeout=api_timeout()),
            )
    return _youtube_client


def _fresh_youtube_client():
    """Drop the cached client and build a new one (new socket). #781: one stale keep-alive
    connection timing out used to arm the latch and drop YouTube for the whole run."""
    global _youtube_client
    with _client_lock:
        _youtube_client = None
    return _get_youtube_client()


def _is_timeout(exc: BaseException) -> bool:
    message = (str(exc) or exc.__class__.__name__).lower()
    return isinstance(exc, TimeoutError | socket.timeout) or any(
        marker in message for marker in _TIMEOUT_MARKERS
    )


def _skip_live_youtube_client() -> bool:
    """Suite isolation (audit C9): never open googleapis HTTPS during tests."""
    return os.getenv("CONTENT_SKIP_YOUTUBE_WARMUP", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ) or os.getenv("CONTENT_FORBID_LIVE_YOUTUBE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def warmup_youtube_client():
    """Pay the slow google-api-client startup cost before discovery (optional)."""
    if _skip_live_youtube_client() or not _youtube_key():
        return
    try:
        _get_youtube_client()
    except Exception as exc:
        logger.debug("_get_youtube_client skipped: %s", exc)


def start_youtube_warmup_background():
    """Non-blocking warmup while the user reads prompts."""
    global _warmup_started
    if _skip_live_youtube_client() or _warmup_started or not _youtube_key():
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
    """The one call path `youtube` and `youtube_comments` share.

    Arming and checking the unreachable latch here is what stops one dead endpoint
    from costing two full socket timeouts, as it did on run 74. Callers already
    turn an exception into a transient-failure signal, so failing fast here reads
    downstream exactly like a timeout — it just costs no wall-clock.
    """
    reason = api_unreachable()
    if reason:
        raise TimeoutError(f"YouTube Data API already timed out this run ({reason})")

    def _call(client):
        return (
            client.search()
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

    try:
        return _call(youtube)
    except Exception as exc:
        if not _is_timeout(exc):
            note_api_failure(exc)
            raise
        first = exc
    # #781: one retry on a fresh connection before the latch arms - a single blip used to
    # drop `youtube` and `youtube_comments` for the whole run.
    logger.info("YouTube Data API timed out (%s); retrying once on a fresh connection", first)
    try:
        client = _fresh_youtube_client()
    except Exception as exc:
        # No second connection to try (or the suite forbids one): the first timeout stands.
        logger.debug("fresh YouTube client unavailable: %s", exc)
        note_api_failure(first)
        raise first from exc
    try:
        return _call(client)
    except Exception as exc:
        note_api_failure(exc)
        raise


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

    except Exception as e:
        http_status = 0
        is_http = False
        try:
            from googleapiclient.errors import HttpError

            if isinstance(e, HttpError):
                is_http = True
                http_status = e.resp.status if e.resp else 0
        except ImportError:
            pass
        body = str(e)
        if is_http:
            status, detail = classify_http(http_status, body)
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


# --- process-global state reset (#827) --------------------------------------
def _reset_process_state() -> None:
    global _youtube_client, _warmup_started, _API_UNREACHABLE
    with _client_lock:
        _youtube_client = None
        _warmup_started = False
    with _UNREACHABLE_LOCK:
        _API_UNREACHABLE = ""


process_state.register_reset("apis.youtube_api", _reset_process_state)
