"""YouTube SEO helpers: tag normalization and merging."""

from __future__ import annotations

import re
from collections.abc import Iterable

# YouTube: max 30 tags; total character limit for all tags combined ~500
MAX_TAGS = 30
MAX_TAG_LEN = 60
MAX_TOTAL_TAG_CHARS = 500


def normalize_youtube_tags(
    tags: Iterable[str] | None,
    *,
    extra: Iterable[str] | None = None,
    max_tags: int = MAX_TAGS,
) -> list[str]:
    """Dedupe, trim, and enforce YouTube tag limits."""
    seen = set()
    out: list[str] = []
    total_chars = 0

    for raw in list(tags or []) + list(extra or []):
        tag = _clean_tag(str(raw))
        if not tag:
            continue
        key = tag.lower()
        if key in seen:
            continue
        add_len = len(tag) + (1 if out else 0)
        if len(out) >= max_tags:
            break
        if total_chars + add_len > MAX_TOTAL_TAG_CHARS:
            break
        seen.add(key)
        out.append(tag)
        total_chars += add_len

    return out


def _clean_tag(tag: str) -> str:
    tag = tag.strip().strip("#").strip()
    tag = re.sub(r"\s+", " ", tag)
    if len(tag) > MAX_TAG_LEN:
        tag = tag[:MAX_TAG_LEN].rstrip()
    # YouTube dislikes commas in tags
    tag = tag.replace(",", "")
    return tag


def tags_from_topic(topic: str, *, limit: int = 6) -> list[str]:
    """Extract simple keyword tags from topic text."""
    words = re.findall(r"[A-Za-z0-9]+", topic)
    tags = []
    for w in words:
        if len(w) < 3:
            continue
        if w.lower() in ("the", "and", "for", "will", "at", "vs"):
            continue
        t = w if w.isupper() and len(w) <= 4 else w.capitalize()
        if t not in tags:
            tags.append(t)
        if len(tags) >= limit:
            break
    return tags
