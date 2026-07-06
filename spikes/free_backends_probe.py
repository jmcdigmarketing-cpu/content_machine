"""THROWAWAY SPIKE — validate free signal backends return the fields we score on.

Not wired into the pipeline. Answers the one decisive question from
docs/agent_reach_evaluation.md: do free, keyless backends carry the engagement
metrics the Apify-paid signals score on?

Reddit signal reads:  title, ups/score, numComments/num_comments, subreddit, url
YouTube signal reads: title, viewCount/views, date/publishedAt (→velocity),
                      channelName, duration, url

Run: python -m spikes.free_backends_probe
"""

from __future__ import annotations

import sys

import requests

UA = "content-machine-spike/0.1 (research; contact: local)"


def probe_reddit(subreddit: str, query: str, limit: int = 10) -> None:
    print(f"\n=== REDDIT  r/{subreddit}  q='{query}' ===")
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q": query,
        "restrict_sr": "on",
        "sort": "hot",
        "limit": limit,
        "raw_json": 1,
    }
    try:
        resp = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=15)
    except Exception as exc:
        print(f"  REQUEST FAILED: {exc}")
        return
    print(f"  HTTP {resp.status_code}")
    if resp.status_code != 200:
        print(f"  body[:200]: {resp.text[:200]!r}")
        return
    children = resp.json().get("data", {}).get("children", [])
    print(f"  posts returned: {len(children)}")
    for ch in children[:5]:
        d = ch.get("data", {})
        print(
            f"    ups={d.get('ups'):>6}  comments={d.get('num_comments'):>4}  "
            f"sub={d.get('subreddit'):<14}  title={d.get('title', '')[:60]!r}"
        )
    # Field-presence verdict
    if children:
        d0 = children[0]["data"]
        have = {
            "title": "title" in d0,
            "ups/score": ("ups" in d0) or ("score" in d0),
            "num_comments": "num_comments" in d0,
            "subreddit": "subreddit" in d0,
            "url/permalink": ("url" in d0) or ("permalink" in d0),
        }
        print(f"  FIELD PRESENCE: {have}")
        print(f"  VERDICT: {'PASS' if all(have.values()) else 'PARTIAL'}")


def probe_youtube(query: str, limit: int = 8) -> None:
    print(f"\n=== YOUTUBE  ytsearch q='{query}' ===")
    try:
        import yt_dlp  # noqa: F401
    except ModuleNotFoundError:
        print("  yt-dlp NOT INSTALLED — skipping. (pip install yt-dlp to test)")
        return
    from yt_dlp import YoutubeDL

    opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": False,  # need view_count/upload_date → not flat
        "noplaylist": True,
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    except Exception as exc:
        print(f"  yt-dlp FAILED: {exc}")
        return
    entries = info.get("entries", []) if info else []
    print(f"  videos returned: {len(entries)}")
    for e in entries[:5]:
        print(
            f"    views={e.get('view_count')!s:>10}  upload={e.get('upload_date')}  "
            f"dur={e.get('duration')}  chan={(e.get('channel') or '')[:20]:<20}  "
            f"title={(e.get('title') or '')[:50]!r}"
        )
    if entries:
        e0 = entries[0]
        have = {
            "title": e0.get("title") is not None,
            "view_count": e0.get("view_count") is not None,
            "upload_date": e0.get("upload_date") is not None,
            "channel": e0.get("channel") is not None,
            "duration": e0.get("duration") is not None,
            "url/webpage_url": (e0.get("webpage_url") or e0.get("url")) is not None,
        }
        print(f"  FIELD PRESENCE: {have}")
        print(f"  VERDICT: {'PASS' if all(have.values()) else 'PARTIAL'}")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "reddit"):
        probe_reddit("MMA", "Topuria")
        probe_reddit("marvelrivals", "new season")
    if which in ("all", "youtube"):
        probe_youtube("Marvel Rivals new season")
