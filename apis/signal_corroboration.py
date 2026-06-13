"""
Cross-source corroboration — how many independent signals confirm a topic.

Separates analyst-grade confidence from a single-source spike.
"""

from __future__ import annotations

import os
from typing import Any

# Independent signal families (not double-counting synthesis metadata)
CORROBORATION_SOURCES: tuple[str, ...] = (
    "youtube",
    "trends",
    "news",
    "blog_rss",
    "wikipedia",
    "autocomplete",
    "rawg",
    "steam",
    "twitch",
    "igdb",
    "trendingnow",
    "tapology",
    "ufc_context",
    "stats_context",
    "api_sports",
    "live_scores",
    "odds",
    "fred",
    "finnhub",
    "sec_edgar",
    "coingecko",
    "anime",
    "tmdb",
    "tvmaze",
    "lastfm",
    "musicbrainz",
)

_MIN_SCORE = float(os.getenv("CORROBORATION_MIN_SCORE", "12"))


def _active_corroborators(
    signals: dict[str, Any],
    *,
    min_score: float = _MIN_SCORE,
) -> list[str]:
    found: list[str] = []
    for name in CORROBORATION_SOURCES:
        sig = signals.get(name)
        if not sig or not sig.get("connected") or not sig.get("active"):
            continue
        if float(sig.get("score", 0) or 0) >= min_score:
            found.append(name)
    return found


def assess_corroboration(signals: dict[str, Any]) -> dict[str, Any]:
    """
    Return confidence 0–1 and corroborating source list.

    1 source ≈ 0.40, 2 ≈ 0.58, 3 ≈ 0.72, 4+ caps near 0.90.
    """
    sources = _active_corroborators(signals)
    count = len(sources)
    if count == 0:
        confidence = 0.15
    elif count == 1:
        confidence = 0.40
    elif count == 2:
        confidence = 0.58
    elif count == 3:
        confidence = 0.72
    else:
        confidence = min(0.92, 0.72 + (count - 3) * 0.06)

    label = _confidence_label(confidence, count)
    return {
        "confidence": round(confidence, 3),
        "source_count": count,
        "corroborating_sources": sources,
        "label": label,
    }


def _confidence_label(confidence: float, count: int) -> str:
    if count >= 4:
        return "high — multiple independent sources agree"
    if count == 3:
        return "moderate-high — triangulated"
    if count == 2:
        return "moderate — two sources; verify before acting"
    if count == 1:
        return "low — single-source spike; treat as hypothesis"
    return "insufficient — no corroborating demand signals"


def corroboration_score_adjustment(
    base_score: float,
    corroboration: dict[str, Any],
) -> float:
    """
    Optional small boost/penalty (max ±5 pts) when CORROBORATION_BOOST is on.
    """
    if os.getenv("CORROBORATION_BOOST", "true").lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return base_score

    conf = float(corroboration.get("confidence", 0.5))
    # Map 0.15–0.92 → roughly -2.5 to +3.5
    delta = (conf - 0.5) * 8.0
    return round(min(100.0, max(0.0, base_score + delta)), 2)
