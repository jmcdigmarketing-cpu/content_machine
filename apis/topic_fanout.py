"""
Split multi-game / multi-entity topics so per-game APIs (Steam, RAWG, etc.) get useful queries.

Example:
  "State of Gaming 2026. Marvel Rivals, terraria, cod, subnautica 2"
  → ["Marvel Rivals", "terraria", "cod", "subnautica 2"]
"""

from __future__ import annotations

import re

# Signals refetched per subtopic (short queries work better than full paragraph topics)
FANOUT_SIGNAL_NAMES = ("steam", "rawg", "autocomplete", "trends")

_LEAD_IN_RE = re.compile(
    r"^(?:state of gaming(?:\s+\d{4})?|gaming in \d{4}|state of .+?\d{4})\s*[.:]?\s*",
    re.I,
)


def parse_subtopics(topic: str, *, max_parts: int = 6) -> list[str]:
    """Return subtopic strings when the input lists multiple games or angles."""
    if not topic or not topic.strip():
        return []

    text = _LEAD_IN_RE.sub("", topic.strip())
    text = re.sub(r"\band more\b", "", text, flags=re.I).strip()

    parts = re.split(r"[,;]+|\s+\band\s+", text, flags=re.I)
    cleaned: list[str] = []
    for part in parts:
        part = part.strip().strip(".- ")
        if len(part) < 2:
            continue
        if part.lower() in ("gaming", "games", "video games"):
            continue
        if part not in cleaned:
            cleaned.append(part)

    if len(cleaned) >= 2:
        return cleaned[:max_parts]

    return []


def primary_search_query(topic: str) -> str:
    """Best short string for stock/local background search (Pexels/Pixabay)."""
    subs = parse_subtopics(topic)
    if subs:
        return subs[0]
    return topic.strip()
