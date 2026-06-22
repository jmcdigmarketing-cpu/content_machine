"""Normalize a content run into queryable features (the feature-store substrate).

These structured features are what the Analytics Intelligence layer correlates with
outcomes (CTR, retention, engagement) to learn *why* videos win. Stored as
content_runs.features_json. Keep raw text alongside labels so labels can be
recomputed if a classifier improves.
"""

from __future__ import annotations

import re
from typing import Any

from core.script_length import get_length_preset

_QUESTION_RE = re.compile(r"\?\s*$")
_NUMBER_RE = re.compile(r"\b\d+\b")
_LISTICLE_RE = re.compile(r"^\s*(top|best|worst)\s+\d+\b", re.I)

# angle keyword -> label (first match wins; order matters)
_ANGLE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("fraud", ("fraud", "overrated", "exposed", "fake", "scam", "washed")),
    ("ranking", ("ranking", "tier list", "tier-list", "ranked", "top ", "best ", "worst ")),
    ("prediction", ("predict", "will ", "vs.", " vs ", "odds", "who wins")),
    ("reaction", ("reacts", "reaction", "responds", "fires back")),
    ("recap", ("recap", "results", "highlights", "recapped", "full card")),
]


def classify_title_structure(title: str) -> str:
    t = (title or "").strip()
    if not t:
        return "unknown"
    if _LISTICLE_RE.search(t):
        return "listicle"
    if _QUESTION_RE.search(t):
        return "question"
    if _NUMBER_RE.search(t):
        return "number"
    if ":" in t or "—" in t or " - " in t:
        return "callout"
    return "statement"


def classify_angle(topic: str, recommended_format: str = "") -> str:
    text = f"{topic} {recommended_format}".lower()
    for label, words in _ANGLE_KEYWORDS:
        if any(w in text for w in words):
            return label
    if recommended_format:
        return recommended_format.lower()
    return "general"


def extract_hook(script: str) -> str:
    """First sentence of the script (the spoken hook)."""
    s = (script or "").strip()
    if not s:
        return ""
    m = re.search(r"^(.*?[.!?])(\s|$)", s, re.S)
    hook = (m.group(1) if m else s).strip()
    return hook[:200]


def _word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def build_features(
    *,
    topic: str,
    channel_id: str,
    content_package: dict[str, Any] | None,
    research_brief: Any = None,
    length_choice: str = "2",
    key_facts: list[str] | None = None,
    fact_source: str = "",
) -> dict[str, Any]:
    """Assemble the normalized feature dict for a content run."""
    pkg = content_package or {}
    title = str(pkg.get("title") or "")
    script = str(pkg.get("script") or "")
    hook = extract_hook(script)

    recommended_format = ""
    controversy = None
    sentiment = ""
    title_direction = ""
    suggested_hook = ""
    if research_brief is not None:
        recommended_format = str(getattr(research_brief, "recommended_format", "") or "")
        controversy = getattr(research_brief, "controversy_score", None)
        sentiment = str(getattr(research_brief, "audience_sentiment", "") or "")
        title_direction = str(getattr(research_brief, "title_direction", "") or "")
        suggested_hook = str(getattr(research_brief, "suggested_hook", "") or "")

    from apis.topic_scorer import infer_domain

    preset = get_length_preset(length_choice)

    return {
        "domain": infer_domain(topic, channel_id),
        "format": preset.label,
        "length_preset": preset.choice,
        "angle": classify_angle(topic, recommended_format),
        "title_structure": classify_title_structure(title),
        "title": title,
        "title_direction": title_direction,
        "hook_text": hook,
        "hook_words": _word_count(hook),
        "suggested_hook": suggested_hook,
        "recommended_format": recommended_format,
        "controversy_score": controversy,
        "audience_sentiment": sentiment,
        "word_count": int(pkg.get("word_count") or _word_count(script)),
        "fact_source": fact_source or ("manual" if key_facts else "signals"),
        "key_facts_count": len(key_facts or []),
        "feature_version": "v1",
    }
