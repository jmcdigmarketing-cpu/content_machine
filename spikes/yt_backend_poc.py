"""THROWAWAY SPIKE POC — in-process free YouTube backend → real signal parity.

Proves Option 3 for `youtube_competitors`: a keyless yt-dlp fetcher whose output,
fed through the SAME scoring helpers the Apify signal uses, yields a valid
make_signal(). Hybrid for speed: flat search ranks candidates by view_count fast,
then full-extract only the top N to get upload_date for view-velocity.

Run: python -m spikes.yt_backend_poc "Marvel Rivals new season"
"""

from __future__ import annotations

import sys
import warnings

warnings.filterwarnings("ignore")

from yt_dlp import YoutubeDL  # noqa: E402

# Reuse the REAL scoring helpers from the production signal — this is the parity proof.
from apis.signal_contract import STATUS_INACTIVE, STATUS_OK, make_signal  # noqa: E402
from apis.youtube_apify_signal import (  # noqa: E402
    _days_since,
    _duration_secs,
    _normalise_score,
    _parse_int,
)


def _flat_search(query: str, n: int) -> list[dict]:
    opts = {"quiet": True, "skip_download": True, "noplaylist": True, "extract_flat": "in_playlist"}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
    return [e for e in (info.get("entries") or []) if e and e.get("url")]


def _full_one(url: str) -> dict | None:
    opts = {"quiet": True, "skip_download": True, "noplaylist": True}
    try:
        with YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception:
        return None


def _iso_date(upload_date: str | None) -> str | None:
    # yt-dlp gives 'YYYYMMDD'. NOTE: the signal's _days_since only parses dates with a
    # 'T' time component (latent bug — see spawned task), so emit full ISO datetime.
    if upload_date and len(upload_date) == 8 and upload_date.isdigit():
        return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}T12:00:00"
    return None


def fetch_youtube_free(query: str, top_n: int = 5, search_n: int = 15) -> list[dict]:
    """Return items in the schema get_youtube_apify_signal already parses."""
    flat = _flat_search(query, search_n)
    flat.sort(key=lambda e: -(e.get("view_count") or 0))  # cheap rank by views
    items: list[dict] = []
    for e in flat[:top_n]:
        full = _full_one(e["url"]) or {}
        items.append(
            {
                "title": full.get("title") or e.get("title") or "",
                "viewCount": full.get("view_count") or e.get("view_count") or 0,
                "date": _iso_date(full.get("upload_date")),  # → velocity
                "channelName": full.get("channel") or e.get("channel") or "",
                "duration": full.get("duration") or e.get("duration") or 0,
                "url": full.get("webpage_url") or e.get("url") or "",
            }
        )
    return items


def score_like_signal(items: list[dict]) -> dict:
    """Mirror of get_youtube_apify_signal's enrichment, using the real helpers."""
    enriched = []
    for it in items:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        views = _parse_int(it.get("viewCount") or it.get("views"))
        age_days = _days_since(it.get("date"))
        velocity = round(views / age_days, 1) if views else 0.0
        enriched.append(
            {
                "title": title[:140],
                "channel": (it.get("channelName") or "")[:60],
                "views": views,
                "age_days": round(age_days, 1),
                "velocity": velocity,
                "duration_secs": _duration_secs(it.get("duration")),
                "url": it.get("url") or "",
            }
        )
    if not enriched:
        return make_signal(connected=True, active=False, score=0, status=STATUS_INACTIVE)
    enriched.sort(key=lambda v: -v["velocity"])
    top_velocity = enriched[0]["velocity"]
    durations = sorted(v["duration_secs"] for v in enriched if v["duration_secs"] > 0)
    return make_signal(
        connected=True,
        active=True,
        score=_normalise_score(top_velocity),
        data={
            "videos": enriched,
            "top_velocity": top_velocity,
            "median_duration_secs": durations[len(durations) // 2] if durations else 0,
            "hot_titles": [v["title"] for v in enriched[:8]],
        },
        status=STATUS_OK,
    )


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "Marvel Rivals new season"
    import time

    t = time.time()
    items = fetch_youtube_free(query)
    sig = score_like_signal(items)
    dt = time.time() - t
    print(f"\nquery={query!r}  fetch+score={dt:.1f}s")
    print(f"signal: active={sig['active']} score={sig['score']} status={sig['status']}")
    d = sig.get("data") or {}
    print(f"top_velocity={d.get('top_velocity')}  median_dur={d.get('median_duration_secs')}s")
    print("hot videos (by velocity):")
    for v in (d.get("videos") or [])[:5]:
        safe_title = v["title"][:50].encode("ascii", "replace").decode("ascii")
        print(
            f"  vel={v['velocity']:>10}/day  views={v['views']:>9}  age={v['age_days']:>5}d  "
            f"{safe_title!r}"
        )
