"""Load extra RSS / domain feeds from config/data_sources.json."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from config.paths import ROOT_DIR
from config.seo import rss_feeds_for_channel

_DATA_PATH = os.path.join(ROOT_DIR, "config", "data_sources.json")


@lru_cache(maxsize=1)
def _load_data_sources() -> dict[str, Any]:
    if not os.path.isfile(_DATA_PATH):
        return {}
    with open(_DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _dedupe_feeds(feeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    out: list[dict[str, Any]] = []
    for item in feeds:
        url = (item.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        feed: dict[str, Any] = {"name": str(item.get("name", "feed")), "url": url}
        if item.get("domains"):
            feed["domains"] = [str(d).lower() for d in item["domains"]]
        out.append(feed)
    return out


def _feed_matches_domain(feed: dict[str, Any], domain: str) -> bool:
    """Untagged feeds are universal; tagged feeds run only for matching domains.

    Treats ufc/mma as equivalent so an MMA feed serves UFC topics and vice-versa.
    """
    domains = feed.get("domains")
    if not domains:
        return True
    domains = {str(d).lower() for d in domains}
    if domain in domains:
        return True
    # ufc/mma are interchangeable for feed routing.
    return domain in ("ufc", "mma") and bool({"ufc", "mma"} & domains)


def domain_rss_feeds(domain: str) -> list[dict[str, str]]:
    cfg = _load_data_sources()
    by_domain = cfg.get("domain_rss") or {}
    feeds = list(cfg.get("global_rss") or [])
    if domain in by_domain:
        feeds.extend(by_domain[domain])
    elif domain == "ufc" and "mma" in by_domain:
        feeds.extend(by_domain["mma"])
    return _dedupe_feeds(feeds)


def rss_feeds_for_topic(topic: str, channel_id: str) -> list[dict[str, Any]]:
    """Channel SEO feeds + domain-specific + global extras, routed by topic domain.

    Feeds tagged with `domains` are dropped when they don't match the topic's
    domain, so a gaming topic no longer pulls MMA/soccer feeds (and vice-versa).
    Untagged feeds remain universal.
    """
    from apis.topic_scorer import infer_domain

    feeds = list(rss_feeds_for_channel(channel_id))
    domain = infer_domain(topic, channel_id)
    feeds.extend(domain_rss_feeds(domain))
    deduped = _dedupe_feeds(feeds)
    return [f for f in deduped if _feed_matches_domain(f, domain)]
