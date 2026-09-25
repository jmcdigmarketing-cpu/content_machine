"""
Free signal backends — alternatives to paid Apify actors for signals where a
free source carries the same fields the signal scores on.

Currently:
  - YouTube (`youtube_competitors`) via yt-dlp: keyless, hybrid flat-search +
    full-extract-top-N. See docs/agent_reach_evaluation.md for the spike that
    validated field parity (spikes/yt_backend_poc.py is the reference proof).
  - Reddit (`reddit`) via Reddit's official OAuth API: free "script app"
    credentials (REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET), app-only
    client-credentials grant, 100 req/min free tier. The sanctioned path — the
    keyless www.reddit.com JSON endpoints are 403-blocked for bots.

Every fetcher here returns items in the exact schema the corresponding Apify
signal already parses, and NEVER raises — callers get [] on failure so a
free-backend outage degrades to "no results," not a crash. (Reddit's fetcher
additionally returns None on a 429 so the caller can surface STATUS_RATE_LIMIT
and let the breaker's timed cooldown kick in.)
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

import requests

from core.logging import get_logger

logger = get_logger("apis.free_backends")


def signal_backend() -> str:
    """SIGNAL_BACKEND=apify (default, unchanged behavior) | free | auto.

    free  = free backend only, no Apify credits spent, no fallback on empty.
    auto  = free backend first, falls back to Apify on empty/unavailable.
    """
    return os.getenv("SIGNAL_BACKEND", "apify").strip().lower()


def youtube_available() -> bool:
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        return False
    return True


def _yt_top_n() -> int:
    try:
        return int(os.getenv("YT_FREE_TOP_N", "5"))
    except ValueError:
        return 5


def _yt_search_n() -> int:
    try:
        return int(os.getenv("YT_FREE_SEARCH_N", "15"))
    except ValueError:
        return 15


def _iso_date(upload_date: str | None) -> str | None:
    """yt-dlp gives 'YYYYMMDD'; emit full ISO datetime (the signal's _days_since
    only parses dates with a 'T' time component — see docs/agent_reach_evaluation.md)."""
    if upload_date and len(upload_date) == 8 and upload_date.isdigit():
        return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}T12:00:00"
    return None


class _YtdlpLogger:
    """Swallow yt-dlp's stderr writes and count what mattered.

    `quiet` and `no_warnings` do NOT stop extractor errors: yt-dlp writes those
    directly to stderr unless a logger is supplied, which is why run 73 printed
    three "Sign in to confirm your age" paragraphs through the discovery spinner.
    The failures are real - those competitor videos are dropped - so they stay
    visible as a debug line and a count (decisions SS24).
    """

    _AGE_GATE = "confirm your age"

    def __init__(self) -> None:
        self.errors = 0
        self.age_gated = 0

    def debug(self, msg: str) -> None:
        logger.debug("yt-dlp: %s", msg)

    def info(self, msg: str) -> None:
        logger.debug("yt-dlp: %s", msg)

    def warning(self, msg: str) -> None:
        logger.debug("yt-dlp: %s", msg)

    def error(self, msg: str) -> None:
        self.errors += 1
        if self._AGE_GATE in str(msg).lower():
            self.age_gated += 1
        logger.debug("yt-dlp: %s", msg)


def _ytdlp_opts(*, log: _YtdlpLogger | None = None, **extra) -> dict:
    """Shared YoutubeDL options: never print, optionally use browser cookies.

    `YTDLP_COOKIES_FROM_BROWSER` is unset by default and must stay that way -
    reading the operator's cookie jar is a privacy step they opt into, not a
    default. Unset produces byte-identical options to before this existed.
    """
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 15,
        "logger": log or _YtdlpLogger(),
    }
    browser = (os.getenv("YTDLP_COOKIES_FROM_BROWSER") or "").strip()
    if browser:
        opts["cookiesfrombrowser"] = (browser,)
    opts.update(extra)
    return opts


def _flat_search(query: str, n: int, log: _YtdlpLogger | None = None) -> list[dict]:
    from yt_dlp import YoutubeDL

    opts = _ytdlp_opts(log=log, extract_flat="in_playlist")
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
    return [e for e in (info.get("entries") or []) if e and e.get("url")]


def _full_one(url: str, log: _YtdlpLogger | None = None) -> dict | None:
    from yt_dlp import YoutubeDL

    opts = _ytdlp_opts(log=log)
    with YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def fetch_youtube_free(
    query: str, top_n: int | None = None, search_n: int | None = None
) -> list[dict]:
    """Hybrid free YouTube fetch: flat search ranks candidates by view count
    cheaply, then full-extracts only the top N to get upload_date for velocity.

    Returns items in the schema apis.youtube_apify_signal already parses:
    title, viewCount, date, channelName, duration, url. Returns [] on any
    failure (unavailable, network error, empty results) — never raises.
    """
    if not youtube_available():
        return []
    top_n = top_n if top_n is not None else _yt_top_n()
    search_n = search_n if search_n is not None else _yt_search_n()

    ydl_log = _YtdlpLogger()
    try:
        flat = _flat_search(query, search_n, ydl_log)
    except Exception as exc:
        logger.warning("yt-dlp flat search failed for %r: %s", query, exc)
        return []

    flat.sort(key=lambda e: -(e.get("view_count") or 0))

    items: list[dict[str, Any]] = []
    for entry in flat[:top_n]:
        full: dict[str, Any] = {}
        try:
            full = _full_one(entry["url"], ydl_log) or {}
        except Exception as exc:
            logger.debug("yt-dlp full extract failed for %s: %s", entry.get("url"), exc)
        items.append(
            {
                "title": full.get("title") or entry.get("title") or "",
                "viewCount": full.get("view_count") or entry.get("view_count") or 0,
                "date": _iso_date(full.get("upload_date")),
                "channelName": full.get("channel") or entry.get("channel") or "",
                "duration": full.get("duration") or entry.get("duration") or 0,
                "url": full.get("webpage_url") or entry.get("url") or "",
            }
        )
    if ydl_log.age_gated:
        # Debug, not warning: age-gated results are routine, and a warning that
        # fires on most runs trains the operator to ignore warnings. Set
        # YTDLP_COOKIES_FROM_BROWSER to actually read them.
        logger.debug(
            "yt-dlp: %d age-gated video(s) skipped for %r (set "
            "YTDLP_COOKIES_FROM_BROWSER to include them)",
            ydl_log.age_gated,
            query,
        )
    return items


# ---------------------------------------------------------------------------
# Reddit — official OAuth API (free script app, app-only client_credentials)
# ---------------------------------------------------------------------------

_REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_REDDIT_API = "https://oauth.reddit.com"

# App-only bearer token, shared across the thread pool. This is auth plumbing,
# not a result cache — signal results are cached upstream by register_signals.
_reddit_token: str | None = None
_reddit_token_expires: float = 0.0
_REDDIT_TOKEN_LOCK = threading.Lock()


def _reddit_user_agent() -> str:
    return os.getenv("REDDIT_USER_AGENT", "windows:content-machine:v0.1 (signal discovery)")


def reddit_available() -> bool:
    """True iff free Reddit script-app credentials are configured."""
    return bool(
        os.getenv("REDDIT_CLIENT_ID", "").strip() and os.getenv("REDDIT_CLIENT_SECRET", "").strip()
    )


def _reddit_get_token() -> str | None:
    """App-only OAuth token, cached until shortly before expiry. None on failure."""
    global _reddit_token, _reddit_token_expires
    with _REDDIT_TOKEN_LOCK:
        if _reddit_token and time.time() < _reddit_token_expires - 60:
            return _reddit_token
        try:
            resp = requests.post(
                _REDDIT_TOKEN_URL,
                auth=(
                    os.getenv("REDDIT_CLIENT_ID", "").strip(),
                    os.getenv("REDDIT_CLIENT_SECRET", "").strip(),
                ),
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": _reddit_user_agent()},
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning("Reddit OAuth token request failed: HTTP %s", resp.status_code)
                return None
            payload = resp.json()
            token = payload.get("access_token")
            if not token:
                return None
            _reddit_token = token
            _reddit_token_expires = time.time() + float(payload.get("expires_in") or 3600)
            return token
        except Exception as exc:
            logger.warning("Reddit OAuth token request failed: %s", exc)
            return None


def reset_reddit_token() -> None:
    """Drop the cached app-only token (test helper)."""
    global _reddit_token, _reddit_token_expires
    with _REDDIT_TOKEN_LOCK:
        _reddit_token = None
        _reddit_token_expires = 0.0


def fetch_reddit_free(query: str, subreddits: list[str], max_items: int = 20) -> list[dict] | None:
    """Search hot posts across `subreddits` via Reddit's official OAuth API.

    Returns items in the schema apis.reddit_signal already parses from the
    Apify actor: title, ups, numComments, subreddit, url.

    Return values:
      list  -- results (possibly empty: no matches, or auth/network failure).
      None  -- HTTP 429 specifically, so the caller can return
               STATUS_RATE_LIMIT and let the breaker's timed cooldown apply.
    Never raises.
    """
    if not reddit_available():
        return []
    token = _reddit_get_token()
    if not token:
        return []

    multi = "+".join(s.strip() for s in subreddits if s.strip()) or "all"
    try:
        resp = requests.get(
            f"{_REDDIT_API}/r/{multi}/search",
            params={
                "q": query[:100],
                "sort": "hot",
                "restrict_sr": "true",
                "limit": str(max(1, min(max_items, 100))),
                "type": "link",
            },
            headers={"Authorization": f"bearer {token}", "User-Agent": _reddit_user_agent()},
            timeout=20,
        )
    except Exception as exc:
        logger.warning("Reddit free search failed for %r: %s", query, exc)
        return []

    if resp.status_code == 429:
        logger.warning("Reddit free search rate-limited (429) for %r", query)
        return None
    if resp.status_code != 200:
        logger.warning("Reddit free search HTTP %s for %r", resp.status_code, query)
        return []

    try:
        children = (resp.json().get("data") or {}).get("children") or []
    except Exception:
        return []

    items: list[dict[str, Any]] = []
    for child in children:
        data = child.get("data") or {}
        title = data.get("title") or ""
        if not title:
            continue
        permalink = data.get("permalink") or ""
        items.append(
            {
                "title": title,
                "ups": int(data.get("ups") or data.get("score") or 0),
                "numComments": int(data.get("num_comments") or 0),
                "subreddit": data.get("subreddit") or "",
                "url": f"https://www.reddit.com{permalink}" if permalink else "",
            }
        )
    return items
