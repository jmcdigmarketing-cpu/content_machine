"""
Best-bet topic selection: find the most likely to succeed topic seed
based on historical ContentRun + PublishLog performance data.

Uses input_topic (user seed), not LLM variant titles. Respects channel
franchise continuity (e.g. Marvel Rivals on TapIn).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from config.channels import get_channel_profile
from core.channel_context import (
    dominant_anchor,
    normalize_seed_topic,
    on_brand_domains,
    recent_input_topics,
)
from core.logging import get_logger

logger = get_logger("core.best_bet")

_TOP_N = 30  # recent runs to analyse


@dataclass
class BestBetResult:
    topic: str
    domain: str
    avg_engaged_rate: float
    source: str  # "analytics" | "score" | "continuity"
    supporting_runs: int
    rationale: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _engaged_rate(metrics_json: str) -> float | None:
    try:
        m = json.loads(metrics_json or "{}")
        if "engaged_rate" in m:
            return float(m["engaged_rate"])
        views = float(m.get("views", 0))
        likes = float(m.get("likes", 0))
        if views > 0:
            return likes / views
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    return None


def _infer_domain(topic: str, channel_id: str) -> str:
    try:
        from apis.topic_scorer import infer_domain

        return infer_domain(topic, channel_id)
    except Exception:
        return "neutral"


def _build_entries(channel_id: str) -> list[dict]:
    from storage.repositories.content_runs import get_content_run_repository
    from storage.repositories.publish_log import get_publish_log_repository

    run_repo = get_content_run_repository()
    log_repo = get_publish_log_repository()

    runs = run_repo.list_for_channel(channel_id)[:_TOP_N]
    if not runs:
        return []

    log_by_run = {log.content_run_id: log for log in log_repo.list_timed_outcomes(channel_id)}

    entries = []
    for run in runs:
        seed = normalize_seed_topic(run.input_topic or run.selected_topic or "")
        if not seed:
            continue
        log = log_by_run.get(run.id)
        engaged_rate = _engaged_rate(log.metrics_json) if log else None
        entries.append(
            {
                "run_id": run.id,
                "topic": seed,
                "input_topic": normalize_seed_topic(run.input_topic or ""),
                "selected_topic": run.selected_topic or "",
                "engaged_rate": engaged_rate,
                "composite_score": float(run.composite_score or 0),
                "domain": _infer_domain(seed, channel_id),
            }
        )
    return entries


def _filter_on_brand(entries: list[dict], channel_id: str) -> list[dict]:
    allowed = on_brand_domains(channel_id)
    on_brand = [e for e in entries if e["domain"] in allowed]
    return on_brand or entries


def _pick_score_seed(entries: list[dict], channel_id: str) -> dict:
    """Highest-scoring on-brand run; tie-break toward franchise continuity."""
    allowed = on_brand_domains(channel_id)
    candidates = [e for e in entries if e["domain"] in allowed] or entries
    anchor = dominant_anchor(e["topic"] for e in candidates)

    def sort_key(e: dict) -> tuple:
        score = e["composite_score"]
        anchor_match = 0
        if anchor and anchor.lower() in e["topic"].lower():
            anchor_match = 1
        return (score, anchor_match, e["run_id"])

    return max(candidates, key=sort_key)


_CONTINUITY_THRESHOLD = 3  # same as variant generator's _ESTABLISHED_THRESHOLD

# Angle templates keyed by content-keyword — matched against weighted history keywords.
# If a keyword from history maps to a template key, that angle gets boosted.
_KEYWORD_ANGLE_MAP: dict[str, str] = {
    "meta": "{anchor} meta evolution",
    "patch": "{anchor} patch wishlist",
    "balance": "what's broken in {anchor} balance",
    "fix": "what {anchor} needs to fix next patch",
    "future": "{anchor} upcoming content predictions",
    "season": "{anchor} season roadmap predictions",
    "hero": "best heroes in {anchor} right now",
    "character": "best heroes in {anchor} right now",
    "community": "{anchor} community concerns",
    "update": "{anchor} upcoming content predictions",
    "buff": "{anchor} balance issues — who needs buffs",
    "nerf": "{anchor} balance issues — who needs nerfs",
    "broken": "what's broken in {anchor} right now",
    "tier": "{anchor} tier list — current meta breakdown",
    "rank": "{anchor} ranked mode breakdown",
    "new": "{anchor} upcoming content predictions",
    "coming": "{anchor} upcoming content predictions",
}

# Fallback rotation when no keyword match is found
_FALLBACK_ANGLES = [
    "{anchor} community concerns",
    "{anchor} player count declining or growing",
    "{anchor} balance issues",
    "{anchor} season roadmap",
    "what's broken in {anchor}",
    "{anchor} tier list",
]

_STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "update",
    "latest",
    "new",
    "in",
    "a",
    "an",
    "is",
    "to",
    "of",
    "on",
    "at",
    "by",
    "as",
    "or",
    "be",
    "this",
    "that",
    "how",
    "what",
    "why",
    "are",
    "was",
    "has",
    "have",
}


def _weighted_keywords(entries: list[dict], anchor: str) -> list[str]:
    """
    Extract topic keywords weighted by historical engagement/score.

    Words appearing in high-performing topics are ranked above words from
    low-performing ones. The anchor name itself is excluded.
    """
    import re
    from collections import defaultdict

    anchor_words = set(anchor.lower().split())
    word_score_sum: dict[str, float] = defaultdict(float)
    word_count: dict[str, int] = defaultdict(int)

    for entry in entries:
        topic = entry.get("topic", "")
        if not topic:
            continue
        # Prefer real engagement; fall back to normalised composite score
        perf = entry.get("engaged_rate")
        if perf is None:
            perf = entry.get("composite_score", 0) / 100.0

        words = re.findall(r"[a-z]{3,}", topic.lower())
        for word in words:
            if word in _STOP_WORDS or word in anchor_words:
                continue
            word_score_sum[word] += perf
            word_count[word] += 1

    # Normalise by frequency so a word repeated 10× doesn't dominate
    scored = [(w, word_score_sum[w] / word_count[w]) for w in word_score_sum if word_count[w] >= 1]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [w for w, _ in scored[:8]]


def _continuity_seed(channel_id: str, entries: list[dict]) -> BestBetResult | None:
    """
    Suggest a fresh seed from the channel's dominant franchise.

    - Below threshold: replay the most recent topic mentioning the anchor.
    - At/above threshold: use keyword-weighted history to pick an angle that
      biases toward what has worked before, with a fallback rotation.
    """
    recent = recent_input_topics(channel_id, limit=_TOP_N)
    anchor = dominant_anchor(recent)
    if not anchor:
        return None

    anchor_runs = [t for t in recent if anchor.lower() in t.lower()]
    repeat_count = len(anchor_runs)

    if repeat_count >= _CONTINUITY_THRESHOLD:
        # Build performance-weighted keyword list from all anchor-related entries
        anchor_entries = [e for e in entries if anchor.lower() in e.get("topic", "").lower()]
        top_kws = _weighted_keywords(anchor_entries or entries, anchor)

        # Find the first keyword that maps to a known angle template
        seed = None
        matched_kw = None
        for kw in top_kws:
            for template_key, template in _KEYWORD_ANGLE_MAP.items():
                if template_key in kw or kw in template_key:
                    seed = template.format(anchor=anchor)
                    matched_kw = kw
                    break
            if seed:
                break

        if not seed:
            # No keyword match — use fallback rotation
            idx = (repeat_count - _CONTINUITY_THRESHOLD) % len(_FALLBACK_ANGLES)
            seed = _FALLBACK_ANGLES[idx].format(anchor=anchor)

        domain = _infer_domain(seed, channel_id)
        kw_note = f" (keyword bias: '{matched_kw}')" if matched_kw else " (rotation fallback)"
        return BestBetResult(
            topic=seed,
            domain=domain,
            avg_engaged_rate=0.0,
            source="continuity",
            supporting_runs=repeat_count,
            rationale=(f"covered {anchor} {repeat_count}× — pivoting to '{seed}'" f"{kw_note}"),
        )

    # Not yet saturated — replay the most recent anchor topic
    for topic in anchor_runs:
        domain = _infer_domain(topic, channel_id)
        return BestBetResult(
            topic=topic,
            domain=domain,
            avg_engaged_rate=0.0,
            source="continuity",
            supporting_runs=repeat_count,
            rationale=f"channel focus: {anchor} — continuing recent {anchor} coverage",
        )
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_best_bet(channel_id: str) -> BestBetResult | None:
    """
    Return the winning topic seed for channel_id.

    Priority:
    1. Best-performing domain by avg engaged_rate (requires analytics data).
    2. Franchise continuity seed when channel has a clear anchor (e.g. Marvel Rivals).
    3. Highest composite_score input_topic on-brand run (no analytics yet).

    Returns None when there are no prior runs at all.
    """
    entries = _build_entries(channel_id)
    if not entries:
        return None

    profile = get_channel_profile(channel_id)
    with_analytics = [e for e in entries if e["engaged_rate"] is not None]

    if with_analytics:
        domain_rates: dict[str, list[float]] = {}
        domain_topics: dict[str, list[str]] = {}
        for e in with_analytics:
            d = e["domain"]
            domain_rates.setdefault(d, []).append(e["engaged_rate"])
            domain_topics.setdefault(d, []).append(e["topic"])

        best_domain = max(
            domain_rates,
            key=lambda d: sum(domain_rates[d]) / len(domain_rates[d]),
        )
        rates = domain_rates[best_domain]
        avg_rate = sum(rates) / len(rates)
        best_topic = domain_topics[best_domain][0]

        return BestBetResult(
            topic=best_topic,
            domain=best_domain,
            avg_engaged_rate=avg_rate,
            source="analytics",
            supporting_runs=len(rates),
            rationale=(
                f"{best_domain} averages {avg_rate:.1%} engagement " f"across {len(rates)} video(s)"
            ),
        )

    continuity = _continuity_seed(channel_id, entries)
    if continuity:
        return continuity

    best = _pick_score_seed(entries, channel_id)
    return BestBetResult(
        topic=best["topic"],
        domain=best["domain"],
        avg_engaged_rate=0.0,
        source="score",
        supporting_runs=1,
        rationale=(
            f"highest on-brand signal score ({best['composite_score']:.0f}) "
            f"for {profile.name} — no engagement analytics yet"
        ),
    )


def display_best_bet(result: BestBetResult) -> None:
    """Print a summary of the best-bet recommendation to stdout."""
    tag = {
        "analytics": "analytics",
        "continuity": "channel history",
        "score": "score-based",
    }.get(result.source, result.source)
    print(f"\n  Best Bet ({tag}): {result.topic}")
    print(f"  Domain : {result.domain}")
    print(f"  Reason : {result.rationale}")
