"""
Blog / niche RSS as a scored signal (headline match count).

Feeds: channel SEO profile + config/data_sources.json (global + per-domain).
"""

from __future__ import annotations

from apis.rss_feeds import _anchor_phrases, _fetch_feed, _matches_topic, _topic_tokens
from apis.signal_contract import STATUS_INACTIVE, STATUS_NO_KEY, STATUS_OK, make_signal
from config.channels import resolve_channel_id
from config.data_sources import rss_feeds_for_topic
from config.settings import get_settings


def get_blog_rss_signal(topic: str):
    channel_id = resolve_channel_id(get_settings().content_channel_id)
    feeds = rss_feeds_for_topic(topic, channel_id)

    if not feeds:
        return make_signal(
            connected=False,
            active=False,
            status=STATUS_NO_KEY,
            status_detail="No RSS feeds in config/seo or config/data_sources.json",
        )

    tokens = _topic_tokens(topic)
    phrases = _anchor_phrases(topic)
    headlines: list[dict] = []
    errors = []

    for feed in feeds[:10]:
        url = feed["url"]
        try:
            for row in _fetch_feed(url):
                title = row.get("title", "")
                if _matches_topic(title, tokens, phrases=phrases):
                    headlines.append(
                        {
                            "title": title,
                            "source": feed.get("name", "blog"),
                            "link": row.get("link", ""),
                        }
                    )
                if len(headlines) >= 10:
                    break
        except Exception as exc:
            errors.append(str(exc)[:80])
        if len(headlines) >= 10:
            break

    matched = len(headlines)

    if not headlines:
        return make_signal(
            connected=True,
            active=False,
            score=0,
            data={"feeds_checked": len(feeds), "errors": errors[:3]},
            status=STATUS_INACTIVE,
            status_detail=f"0 topic-matched headlines from {len(feeds)} feeds",
        )

    score = min(100.0, 20.0 + matched * 15.0)

    return make_signal(
        connected=True,
        active=matched > 0,
        score=score,
        confidence=0.75,
        data={
            "headlines": headlines[:8],
            "matched": matched,
            "feeds_checked": len(feeds),
        },
        status=STATUS_OK,
        status_detail=f"{matched} topic-matched headlines from {len(feeds)} feeds",
    )
