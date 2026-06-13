"""
Saturation / opportunity-window scoring.

High demand + low competitor coverage = open window.
High demand + saturated coverage = closing or closed.
"""

from __future__ import annotations

import re
from typing import Any

WINDOW_OPEN = "open"
WINDOW_CLOSING = "closing"
WINDOW_CLOSED = "closed"
WINDOW_MODERATE = "moderate"


def _topic_tokens(topic: str) -> list[str]:
    words = re.findall(r"[a-z0-9]{3,}", topic.lower())
    stop = {
        "the",
        "and",
        "for",
        "will",
        "that",
        "this",
        "with",
        "from",
        "about",
        "how",
        "why",
        "what",
    }
    return [w for w in words if w not in stop]


def assess_opportunity_window(
    topic: str,
    *,
    composite_score: float,
    competitor_titles: list[dict[str, str]],
    corroboration_confidence: float = 0.5,
) -> dict[str, Any]:
    """
    Combine demand (score + corroboration) with competitor title overlap.
    """
    tokens = _topic_tokens(topic)
    overlap = 0
    for row in competitor_titles:
        title = str(row.get("title", "")).lower()
        if not title:
            continue
        if tokens:
            if sum(1 for t in tokens if t in title) >= max(1, len(tokens) // 3):
                overlap += 1
        else:
            overlap += 1

    demand = min(1.0, (composite_score / 100.0) * (0.7 + 0.3 * corroboration_confidence))
    coverage = min(1.0, overlap / 6.0)  # 6+ similar competitor titles ≈ saturated
    gap_score = round(demand * (1.0 - coverage), 3)

    if demand >= 0.5 and coverage < 0.25:
        status = WINDOW_OPEN
        summary = "High demand, low competitor coverage — differentiated angle still viable."
    elif coverage >= 0.65:
        status = WINDOW_CLOSED
        summary = "Competitors already saturated this angle — need a contrarian hook or skip."
    elif demand >= 0.55 and coverage >= 0.35:
        status = WINDOW_CLOSING
        summary = "Demand is real but coverage is building — move soon or narrow the take."
    else:
        status = WINDOW_MODERATE
        summary = "Moderate demand/coverage balance — win on execution and specificity."

    return {
        "window_status": status,
        "demand_index": round(demand, 3),
        "competitor_overlap": overlap,
        "coverage_index": round(coverage, 3),
        "gap_score": gap_score,
        "summary": summary,
    }
