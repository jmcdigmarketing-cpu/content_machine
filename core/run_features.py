"""Normalize a content run into queryable features (the feature-store substrate).

These structured features are what the Analytics Intelligence layer correlates with
outcomes (CTR, retention, engagement) to learn *why* videos win. Stored as
content_runs.features_json. Keep raw text alongside labels so labels can be
recomputed if a classifier improves.
"""

from __future__ import annotations

import re
from typing import Any

from core.logging import get_logger
from core.script_length import get_length_preset

logger = get_logger("core.run_features")

FEATURE_VERSION = "v2"  # v2: angle_intent from detect_angle_intent (#661)

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
    """Analytics label for a topic.

    Generation (`detect_angle_intent`) is the source of truth when it names a
    real frame. The older keyword list (fraud / recap / …) only fires when
    intent is `default`, so `"GTA 6 looks amazing!!!"` is `reaction` here too
    (#661) rather than `general`.
    """
    from core.angle_intent import ANGLE_DEFAULT, detect_angle_intent

    intent = detect_angle_intent(topic)
    if intent != ANGLE_DEFAULT:
        return intent
    text = f"{topic} {recommended_format}".lower()
    for label, words in _ANGLE_KEYWORDS:
        if any(w in text for w in words):
            return label
    if recommended_format:
        return recommended_format.lower()
    return "general"


def _angle_intent(topic: str) -> str:
    from core.angle_intent import detect_angle_intent

    return detect_angle_intent(topic)


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
    vault_relevance_audit: list[dict[str, Any]] | None = None,
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

    features = {
        "domain": infer_domain(topic, channel_id),
        "format": preset.label,
        "length_preset": preset.choice,
        "angle": classify_angle(topic, recommended_format),
        "angle_intent": _angle_intent(topic),
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
        "feature_version": FEATURE_VERSION,
    }
    if vault_relevance_audit is not None:
        features["vault_relevance"] = list(vault_relevance_audit)
    return features


def load_features(run_id: int | None) -> dict[str, Any]:
    """Read a run's persisted features dict ({} when absent/undecodable)."""
    if not run_id:
        return {}
    try:
        import json

        from storage.repositories.content_runs import get_content_run_repository

        record = get_content_run_repository().get(run_id)
        if record is None:
            return {}
        loaded = json.loads(record.features_json or "{}")
        return loaded if isinstance(loaded, dict) else {}
    except Exception as exc:
        logger.debug("features read skipped for run %s: %s", run_id, exc)
        return {}


def merge_features(run_id: int | None, updates: dict[str, Any]) -> None:
    """Merge keys into an existing features_json (e.g. the post-render cost lines).

    Mirrors `core.run_quality.merge_quality`. Needed because both operator render paths
    finalize the run *before* rendering, so the stored cost never gained its TTS line.
    """
    if not run_id or not updates:
        return
    try:
        import json

        from storage.repositories.content_runs import get_content_run_repository

        repo = get_content_run_repository()
        current = load_features(run_id)
        current.update(updates)
        repo.update(run_id, {"features_json": json.dumps(current)})
    except Exception as exc:
        logger.debug("features merge skipped for run %s: %s", run_id, exc)
