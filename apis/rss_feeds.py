"""
RSS headline fetch for research brief (not registered in variant scoring).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlparse

import requests

from apis.cache_manager import build_key, get_cached, set_cache
from config.data_sources import rss_feeds_for_topic
from core.logging import get_logger

logger = get_logger("apis.rss_feeds")

_CACHE_TTL = 60 * 60 * 2  # 2 hours
_TIMEOUT = 12


def _topic_tokens(topic: str) -> list[str]:
    words = re.findall(r"[a-z0-9]{3,}", topic.lower())
    stop = {"the", "and", "for", "will", "that", "this", "with", "from", "about"}
    return [w for w in words if w not in stop][:12]


def _anchor_phrases(topic: str) -> list[str]:
    try:
        from core.channel_context import extract_anchors

        return [a.lower() for a in extract_anchors(topic)]
    except Exception:
        return []


def _matches_topic(text: str, tokens: list[str], *, phrases: list[str] | None = None) -> bool:
    if not tokens and not phrases:
        return True
    lower = text.lower()
    if phrases and any(p in lower for p in phrases):
        return True
    return any(t in lower for t in tokens)


def _parse_feed_xml(xml_text: str, *, limit: int = 25) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    # RSS 2.0: channel/item; Atom: entry
    for item in root.iter():
        tag = item.tag.split("}")[-1] if "}" in item.tag else item.tag
        if tag not in ("item", "entry"):
            continue
        title_el = None
        link_el = None
        date_el = ""
        for child in item:
            ctag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if ctag == "title" and child.text:
                title_el = child.text.strip()
            elif ctag == "link":
                if child.text:
                    link_el = child.text.strip()
                elif child.get("href"):
                    link_el = child.get("href", "").strip()
            elif ctag in ("pubDate", "published", "updated", "date") and child.text and not date_el:
                # RSS pubDate (RFC822) or Atom published/updated (ISO8601)
                date_el = child.text.strip()
        if title_el:
            items.append({"title": title_el, "link": link_el or "", "published": date_el})
        if len(items) >= limit:
            break
    return items


def _fetch_feed(url: str) -> list[dict[str, str]]:
    headers = {
        "User-Agent": "ContentMachine/1.0 (+https://localhost; research/rss)",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    resp = requests.get(url, headers=headers, timeout=_TIMEOUT)
    resp.raise_for_status()
    return _parse_feed_xml(resp.text)


def fetch_rss_context(
    topic: str,
    channel_id: str,
    *,
    max_headlines: int = 12,
    search_query: str | None = None,
) -> dict[str, Any]:
    """
    Headlines from channel-configured RSS feeds, filtered loosely by topic.
    Cached per channel+topic.
    """
    feeds = rss_feeds_for_topic(topic, channel_id)
    if not feeds:
        return {"connected": False, "headlines": [], "feeds_checked": 0}

    cache_key = build_key("rss", f"{channel_id}::{search_query or topic}")
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    tokens = _topic_tokens(search_query or topic)
    phrases = _anchor_phrases(search_query or topic)
    headlines: list[dict[str, str]] = []
    errors = []

    for feed in feeds:
        url = feed["url"]
        try:
            for row in _fetch_feed(url):
                title = row.get("title", "")
                if _matches_topic(title, tokens, phrases=phrases):
                    headlines.append(
                        {
                            "title": title,
                            "source": feed.get("name", urlparse(url).netloc),
                            "link": row.get("link", ""),
                        }
                    )
                if len(headlines) >= max_headlines:
                    break
        except Exception as exc:
            errors.append(f"{feed.get('name')}: {exc}")
            logger.debug("RSS feed failed %s: %s", url, exc)
        if len(headlines) >= max_headlines:
            break

    payload = {
        "connected": True,
        "headlines": headlines[:max_headlines],
        "feeds_checked": len(feeds),
        "errors": errors[:3],
    }
    set_cache(cache_key, payload, ttl_seconds=_CACHE_TTL)
    return payload
