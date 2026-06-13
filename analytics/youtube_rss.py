"""
Free YouTube channel upload feed — no Data API quota.

https://www.youtube.com/feeds/videos.xml?channel_id=UC...
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

import requests

from core.logging import get_logger

logger = get_logger("analytics.youtube_rss")

ATOM = "http://www.w3.org/2005/Atom"
YT = "http://www.youtube.com/xml/schemas/2015"
FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


def fetch_channel_uploads_rss(
    youtube_channel_id: str,
    *,
    max_results: int = 8,
    timeout: int = 12,
) -> list[dict[str, Any]]:
    """Recent uploads from the public Atom feed (unquota'd)."""
    url = FEED_URL.format(channel_id=youtube_channel_id)
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "ContentMachine/1.0 (competitor-rss)"},
        )
        if response.status_code != 200:
            logger.warning("YouTube RSS %s returned %s", youtube_channel_id, response.status_code)
            return []
        root = ET.fromstring(response.content)
    except Exception as exc:
        logger.warning("YouTube RSS parse failed for %s: %s", youtube_channel_id, exc)
        return []

    videos: list[dict[str, Any]] = []
    for entry in root.findall(f"{{{ATOM}}}entry"):
        title_el = entry.find(f"{{{ATOM}}}title")
        published_el = entry.find(f"{{{ATOM}}}published")
        vid_el = entry.find(f"{{{YT}}}videoId")
        title = (title_el.text or "").strip() if title_el is not None else ""
        published = (published_el.text or "").strip() if published_el is not None else ""
        video_id = (vid_el.text or "").strip() if vid_el is not None else ""
        if not title:
            continue
        videos.append(
            {
                "video_id": video_id,
                "title": title,
                "published_at": published,
                "source": "youtube_rss",
            }
        )
        if len(videos) >= max_results:
            break
    return videos
