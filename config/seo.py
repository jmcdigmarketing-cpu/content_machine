"""Per-channel YouTube SEO profiles (tags, title/description rules, RSS feeds)."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from config.paths import ROOT_DIR

SEO_DIR = os.path.join(ROOT_DIR, "config", "seo")
HINTS_DIR = os.path.join(ROOT_DIR, "data")


def _seo_path(channel_id: str) -> str:
    return os.path.join(SEO_DIR, f"{channel_id}.json")


def hints_path(channel_id: str) -> str:
    return os.path.join(HINTS_DIR, f"seo_hints_{channel_id}.json")


@lru_cache(maxsize=16)
def get_seo_profile(channel_id: str) -> dict[str, Any]:
    path = _seo_path(channel_id)
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def load_seo_hints(channel_id: str) -> dict[str, Any]:
    path = hints_path(channel_id)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def build_seo_prompt_block(channel_id: str) -> str:
    profile = get_seo_profile(channel_id)
    if not profile:
        return ""

    hints = load_seo_hints(channel_id)
    lines = ["SEO GUIDELINES (channel profile):"]

    for key, label in (
        ("title_rules", "Title"),
        ("description_rules", "Description"),
        ("tag_rules", "Tags"),
    ):
        rules = profile.get(key) or []
        if rules:
            lines.append(f"{label}:")
            for rule in rules:
                lines.append(f"  - {rule}")

    defaults = profile.get("default_tags") or []
    if defaults:
        lines.append(
            f"Default tags to consider (merge with topic-specific): {', '.join(defaults[:12])}"
        )

    trending = hints.get("trending_tags") or []
    if trending:
        lines.append(
            "Trending niche tags (from recent refresh — use if relevant): "
            + ", ".join(trending[:15])
        )

    return "\n".join(lines)


def default_tags_for_channel(channel_id: str, topic: str | None = None) -> list[str]:
    """
    Curated brand/default tags that are always safe to attach for this channel.

    Deliberately does NOT force-inject the auto-refreshed `trending_tags`: those
    are a flat, domain-mixed list (e.g. a gaming+UFC channel's hints carry fighter
    names like "Gaethje"/"Strickland"), so force-adding them bleeds UFC names onto
    gaming videos and vice-versa. Trending tags are still offered to the model via
    build_seo_prompt_block ("use if relevant"), so on-topic ones surface through the
    LLM's own tags — relevance-gated instead of unconditional.
    """
    profile = get_seo_profile(channel_id)
    defaults = profile.get("default_tags") or []
    merged: list[str] = []
    for tag in defaults:
        if tag and str(tag) not in merged:
            merged.append(str(tag))

    if topic:
        try:
            from apis.topic_scorer import infer_domain

            domain = infer_domain(topic, channel_id)
            if domain not in ("ufc", "mma"):
                drop = {"ufc", "mma", "featherweight", "lightweight"}
                merged = [t for t in merged if t.lower() not in drop]
        except Exception:
            pass

    return merged


def rss_feeds_for_channel(channel_id: str) -> list[dict[str, str]]:
    profile = get_seo_profile(channel_id)
    feeds = profile.get("rss_feeds") or []
    out = []
    for item in feeds:
        if isinstance(item, dict) and item.get("url"):
            out.append({"name": str(item.get("name", "feed")), "url": str(item["url"])})
    return out
