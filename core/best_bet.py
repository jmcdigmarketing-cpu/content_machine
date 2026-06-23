"""
Best-bet topic selection: find the most likely to succeed topic seed
based on historical ContentRun + PublishLog performance data.

Uses input_topic (user seed), not LLM variant titles. Respects channel
franchise continuity (e.g. Marvel Rivals on TapIn).
"""

from __future__ import annotations

from dataclasses import dataclass

from config.channels import get_channel_profile
from core.channel_context import (
    dominant_anchor,
    normalize_seed_topic,
    on_brand_domains,
    recent_input_topics,
)
from core.engagement import engaged_rate as _engaged_rate
from core.engagement import safe_infer_domain as _infer_domain
from core.logging import get_logger
from core.recommender_confidence import MODERATE_SAMPLES, confidence_note

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

        # Confidence-first: a well-sampled domain beats a thin high-rate one (don't
        # crown a 1-video 39% domain over a 6-video 11% domain).
        adjusted = _adjusted_domain_rates(entries)
        counts = _domain_sample_counts(entries)
        best_domain = max(
            domain_rates,
            key=lambda d: _domain_priority(d, adjusted, counts),
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
                f"{best_domain} averages {avg_rate:.1%} engagement "
                f"across {len(rates)} video(s)"
                f"{confidence_note(len(rates))}"
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


def _domain_avg_rates(entries: list[dict]) -> dict[str, float]:
    """Per-domain average engaged_rate (only domains with engagement data)."""
    by_domain: dict[str, list[float]] = {}
    for e in entries:
        rate = e.get("engaged_rate")
        if rate is not None:
            by_domain.setdefault(e["domain"], []).append(float(rate))
    return {d: sum(v) / len(v) for d, v in by_domain.items() if v}


def _domain_sample_counts(entries: list[dict]) -> dict[str, int]:
    """Per-domain count of videos with engagement data (confidence basis)."""
    counts: dict[str, int] = {}
    for e in entries:
        if e.get("engaged_rate") is not None:
            counts[e["domain"]] = counts.get(e["domain"], 0) + 1
    return counts


def _adjusted_domain_rates(entries: list[dict]) -> dict[str, float]:
    """Empirical-Bayes-shrunk per-domain engaged_rate.

    Thin domains regress toward the global mean so a single 39%-from-1-video domain
    can't outrank a well-sampled 11%-from-6 domain. Prior strength = MODERATE_SAMPLES.
    """
    by_domain: dict[str, list[float]] = {}
    for e in entries:
        r = e.get("engaged_rate")
        if r is not None:
            by_domain.setdefault(e["domain"], []).append(float(r))
    if not by_domain:
        return {}
    all_rates = [r for v in by_domain.values() for r in v]
    prior = sum(all_rates) / len(all_rates)
    k = MODERATE_SAMPLES
    return {d: (sum(v) + k * prior) / (len(v) + k) for d, v in by_domain.items()}


def _domain_priority(domain: str, adjusted: dict[str, float], counts: dict[str, int]) -> tuple:
    """Sort key (descending): adequately-sampled domains first, then shrunk rate.

    This is the fix for "all 3 picks are a stale 1-sample domain": a domain with
    < MODERATE_SAMPLES videos of engagement data is ranked *below* any domain that
    clears the bar, regardless of how high its thin average looks.
    """
    n = counts.get(domain, 0)
    return (1 if n >= MODERATE_SAMPLES else 0, adjusted.get(domain, 0.0))


def _effective_allowed(channel_id: str, entries: list[dict]) -> set[str]:
    """On-brand domains PLUS domains the channel has actually published & measured.

    Fixes the case where a channel makes content in a domain that isn't in its
    configured on-brand set (e.g. NBA on a gaming/UFC channel): if it has measured
    engagement there, it's de-facto on-brand, so best-bet reflects the *real* topic
    mix instead of silently dropping it.
    """
    allowed = set(on_brand_domains(channel_id))
    allowed |= {e["domain"] for e in entries if e.get("engaged_rate") is not None}
    return allowed


def _fresh_enabled() -> bool:
    import os

    return os.getenv("BEST_BET_FRESH", "true").lower() in ("1", "true", "yes")


def _fresh_candidates(
    channel_id: str, *, allowed: set[str], exclude: set[str], limit: int = 12
) -> list[dict]:
    """Current headlines from the channel's RSS feeds as fresh topic candidates.

    Returns [{topic, domain, source}] deduped against `exclude` (recently covered).
    Only headlines whose title *confidently* maps to an on-brand domain are kept
    (inferred without channel fallback) — this filters mixed-feed noise like a
    gaming site's general-news items. Never raises — returns [] on any problem.
    """
    try:
        from apis.rss_feeds import _fetch_feed
        from apis.topic_scorer import infer_domain
        from config.data_sources import rss_feeds_for_channel
    except Exception:
        return []

    candidates: list[dict] = []
    seen_local: set[str] = set()
    for feed in list(rss_feeds_for_channel(channel_id))[:6]:
        try:
            rows = _fetch_feed(feed["url"])
        except Exception:
            continue
        for row in rows[:8]:
            title = (row.get("title") or "").strip()
            key = normalize_seed_topic(title).lower()
            if not title or key in exclude or key in seen_local:
                continue
            # Infer WITHOUT channel fallback so neutral/off-brand titles are dropped.
            domain = infer_domain(title)
            if domain not in allowed:
                continue
            seen_local.add(key)
            candidates.append({"topic": title, "domain": domain, "source": feed.get("name", "RSS")})
            if len(candidates) >= limit:
                return candidates
    return candidates


def get_best_bets(channel_id: str, n: int = 3) -> list[BestBetResult]:
    """
    Up to `n` DISTINCT topic options, best first.

    Forward-looking: the channel's analytics pick the winning *domain* (what works),
    while live RSS headlines supply the *current* topic (what's relevant now), so the
    suggestions are fresh and stop repeating the same historical seeds. Falls back to
    the historical engagement ranking when no fresh headlines are available.
    """
    entries = _build_entries(channel_id)
    if not entries:
        single = get_best_bet(channel_id)
        return [single] if single else []

    allowed = _effective_allowed(channel_id, entries)
    domain_rates = _domain_avg_rates(entries)
    domain_counts = _domain_sample_counts(entries)
    adjusted = _adjusted_domain_rates(entries)
    # Don't re-suggest anything covered recently (kills the repeat problem).
    recent = {normalize_seed_topic(t).lower() for t in recent_input_topics(channel_id, limit=30)}

    options: list[BestBetResult] = []
    seen: set[str] = set(recent)
    used_domains: set[str] = set()

    def _domain_key(d: str) -> tuple:
        return _domain_priority(d, adjusted, domain_counts)

    # Fresh RSS headlines, grouped by domain (relevant "what's hot now").
    by_domain: dict[str, list[dict]] = {}
    ordered_fresh_domains: list[str] = []
    if _fresh_enabled():
        fresh = _fresh_candidates(channel_id, allowed=allowed, exclude=recent)
        on_brand_fresh = [c for c in fresh if c["domain"] in allowed] or fresh
        for c in on_brand_fresh:
            by_domain.setdefault(c["domain"], []).append(c)
        ordered_fresh_domains = sorted(by_domain, key=_domain_key, reverse=True)

    def _emit_fresh(c: dict) -> bool:
        key = normalize_seed_topic(c["topic"]).lower()
        if not key or key in seen:
            return False
        seen.add(key)
        used_domains.add(c["domain"])
        rate = domain_rates.get(c["domain"])
        rationale = f"trending on {c['source']} now"
        if rate is not None:
            rationale += f" · {c['domain']} averages {rate:.0%} engagement"
            rationale += confidence_note(domain_counts.get(c["domain"], 0))
        options.append(
            BestBetResult(
                topic=c["topic"],
                domain=c["domain"],
                avg_engaged_rate=rate or 0.0,
                source="trending",
                supporting_runs=0,
                rationale=rationale,
            )
        )
        return True

    # Historical pool, ranked confidence-first.
    pool = [e for e in entries if e["domain"] in allowed] or entries
    ranked = sorted(
        pool,
        key=lambda e: (_domain_key(e["domain"]), e["engaged_rate"] or 0.0, e["composite_score"]),
        reverse=True,
    )

    def _emit_hist(e: dict) -> bool:
        key = normalize_seed_topic(e["topic"]).lower()
        if not key or key in seen:
            return False
        seen.add(key)
        used_domains.add(e["domain"])
        if e["engaged_rate"] is not None:
            source = "analytics"
            rationale = f"{e['engaged_rate']:.0%} engagement on a past {e['domain']} video"
            rationale += confidence_note(domain_counts.get(e["domain"], 0))
        else:
            source = "score"
            rationale = f"high signal score ({e['composite_score']:.0f}) for {e['domain']}"
        options.append(
            BestBetResult(
                topic=e["topic"],
                domain=e["domain"],
                avg_engaged_rate=e["engaged_rate"] or 0.0,
                source=source,
                supporting_runs=1,
                rationale=rationale,
            )
        )
        return True

    # Phase 1 — DIVERSITY: at most one pick per domain, confidence-first order,
    # preferring a fresh headline for the domain, else its best historical run. This
    # is what stops three stale 1-sample picks from one domain filling every slot.
    hist_domains: list[str] = []
    for e in ranked:
        if e["domain"] not in hist_domains:
            hist_domains.append(e["domain"])
    all_domains = sorted(
        set(ordered_fresh_domains) | set(hist_domains), key=_domain_key, reverse=True
    )
    for d in all_domains:
        if len(options) >= n:
            break
        if d in used_domains:
            continue
        if not any(_emit_fresh(c) for c in by_domain.get(d, [])):
            for e in ranked:
                if e["domain"] == d and _emit_hist(e):
                    break

    # Phase 2 — fill remaining slots: more fresh (priority order), then historical.
    if len(options) < n:
        for d in ordered_fresh_domains:
            for c in by_domain.get(d, []):
                if len(options) >= n:
                    break
                _emit_fresh(c)
            if len(options) >= n:
                break
    if len(options) < n:
        for e in ranked:
            if len(options) >= n:
                break
            _emit_hist(e)

    if len(options) < n:
        cont = _continuity_seed(channel_id, entries)
        if cont and normalize_seed_topic(cont.topic).lower() not in seen:
            options.append(cont)

    return options[:n]


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


def display_best_bets(options: list[BestBetResult], *, print_fn=print) -> None:
    """Print a numbered list of best-bet options to pick from."""
    print_fn("\n  Best bets (pick one, or type your own):")
    for i, opt in enumerate(options, 1):
        print_fn(f"    {i}. [{opt.domain}] {opt.topic}")
        print_fn(f"       {opt.rationale}")
