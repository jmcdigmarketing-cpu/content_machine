"""
Refresh trending SEO tag hints from YouTube search + RSS headlines.

Run periodically (weekly) — not on every pipeline run:

    py -m analytics.seo_refresh --channel tapin
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone

from apis.rss_feeds import fetch_rss_context
from apis.youtube_api import search_youtube
from config.paths import ensure_data_dir
from config.seo import get_seo_profile, hints_path


def _tokens_from_titles(titles: list[str]) -> list[str]:
    counter: Counter = Counter()
    for title in titles:
        for word in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", title):
            w = word.lower()
            if w in ("the", "and", "for", "with", "from", "this", "that", "news"):
                continue
            if len(w) > 24:
                continue
            counter[w] += 1
    return [w.capitalize() if len(w) > 3 else w.upper() for w, _ in counter.most_common(20)]


def refresh_seo_hints(channel_id: str) -> dict:
    profile = get_seo_profile(channel_id)
    queries = profile.get("seo_refresh_queries") or ["gaming", "UFC"]
    titles: list[str] = []

    for q in queries[:6]:
        signal = search_youtube(q)
        data = signal.get("data") if isinstance(signal, dict) else None
        if isinstance(data, dict):
            for t in data.get("titles") or []:
                if isinstance(t, str):
                    titles.append(t)

    rss = fetch_rss_context("UFC gaming MMA esports", channel_id, max_headlines=20)
    for h in rss.get("headlines") or []:
        if isinstance(h, dict) and h.get("title"):
            titles.append(h["title"])

    trending = _tokens_from_titles(titles)
    defaults = profile.get("default_tags") or []
    merged = []
    for tag in list(defaults) + trending:
        if tag and tag not in merged:
            merged.append(tag)

    payload = {
        "channel_id": channel_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "trending_tags": merged[:25],
        "sample_titles": titles[:15],
    }

    ensure_data_dir()
    path = hints_path(channel_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh SEO tag hints for a channel")
    parser.add_argument("--channel", default="tapin")
    args = parser.parse_args()
    payload = refresh_seo_hints(args.channel)
    print(
        f"Wrote {len(payload.get('trending_tags', []))} trending tags to {hints_path(args.channel)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
