"""Structural feature tags for a video title.

The A/B loop for a single faceless channel can't double-publish, so instead of
testing two titles head-to-head it attributes realized engagement to the
*structural pattern* of the title that shipped (does a number help? a colon? a
"sleeping on" curiosity gap? a callout like "overrated"?). Over many videos this
builds a per-channel "what title pattern wins" signal (`core/title_experiments`).

Pure, dependency-free, and deterministic so it can be unit-tested and reused both
for attribution and for annotating fresh variants at selection time.
"""

from __future__ import annotations

import re

_LIST = re.compile(r"\b\d+\s+[a-z]", re.IGNORECASE)  # "5 reasons", "3 things"
_VERSUS = re.compile(r"\bvs\.?\b", re.IGNORECASE)
_YEAR = re.compile(r"\b(19|20)\d{2}\b")
_SUPERLATIVE = re.compile(
    r"\b(best|worst|biggest|greatest|most|ultimate|insane|crazy|wild|perfect|huge)\b",
    re.IGNORECASE,
)
_CURIOSITY = re.compile(
    r"\b(why|how|secret|nobody|everyone|sleeping on|won'?t believe|actually|real reason|"
    r"hidden|truth)\b",
    re.IGNORECASE,
)
_CALLOUT = re.compile(
    r"\b(fraud|overrated|underrated|snubbed|disrespect\w*|exposed|robbed|washed|cap)\b",
    re.IGNORECASE,
)


def feature_tags(title: str) -> list[str]:
    """Structural pattern tags present in `title` (order-stable, de-duplicated)."""
    t = (title or "").strip()
    if not t:
        return []
    words = t.split()
    tags: list[str] = []

    def add(tag: str, cond: bool) -> None:
        if cond and tag not in tags:
            tags.append(tag)

    add("number", bool(re.search(r"\d", t)))
    add("listicle", bool(_LIST.search(t)))
    add("question", t.endswith("?"))
    add("colon", ":" in t)
    add("versus", bool(_VERSUS.search(t)))
    add("superlative", bool(_SUPERLATIVE.search(t)))
    add("curiosity", bool(_CURIOSITY.search(t)))
    add("callout", bool(_CALLOUT.search(t)))
    add("year", bool(_YEAR.search(t)))
    add("bracket", "[" in t or "(" in t)
    add("short", len(words) <= 6)
    add("long", len(words) >= 12)
    return tags
