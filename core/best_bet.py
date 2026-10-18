"""
Best-bet topic selection: find the most likely to succeed topic seed
based on historical ContentRun + PublishLog performance data.

Uses input_topic (user seed), not LLM variant titles. Respects channel
franchise continuity (e.g. Marvel Rivals on TapIn).
"""

from __future__ import annotations

import os
import random
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from apis.topic_tokens import FUNCTION_WORDS
from config.channels import get_channel_profile
from core.channel_context import (
    dominant_anchor,
    normalize_seed_topic,
    on_brand_domains,
    recent_input_topics,
)
from core.engagement import safe_infer_domain as _infer_domain
from core.engagement import subscribers_gained as _subscribers_gained
from core.logging import get_logger
from core.recommender_confidence import MODERATE_SAMPLES, confidence_note
from core.success import target as _target

logger = get_logger("core.best_bet")

_TOP_N = 30  # recent runs to analyse


def _published_age_days(log: Any) -> float | None:
    """Days since the video went out. None when the log has no usable timestamp -
    `recency_weight` then falls back to 1.0, which is the old unweighted mean."""
    raw = getattr(log, "published_at", None) if log is not None else None
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            raw = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(raw, datetime):
        return None
    when = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - when).total_seconds() / 86400.0)


def recency_weight(age_days: float | None) -> float:
    if age_days is None:
        return 1.0
    return 0.5 ** (max(0.0, float(age_days)) / 90.0)


def weighted_engaged_mean(pairs: list[tuple[float, float | None]]) -> float:
    num = 0.0
    den = 0.0
    for rate, age in pairs:
        weight = recency_weight(age)
        num += float(rate) * weight
        den += weight
    return num / den if den else 0.0


@dataclass
class BestBetResult:
    topic: str
    domain: str
    avg_engaged_rate: float
    source: str  # "analytics" | "score" | "continuity" | "arc" | "calendar" | "trending"
    supporting_runs: int
    rationale: str
    call: str = ""  # #1301: a preview's prediction, "Packers win - Dallas allows deep balls"
    facts: list[str] = field(default_factory=list)  # #991: the lines a series idea is written from


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_entries(channel_id: str) -> list[dict]:
    from storage.repositories.content_runs import get_content_run_repository
    from storage.repositories.publish_log import get_publish_log_repository

    run_repo = get_content_run_repository()
    log_repo = get_publish_log_repository()

    all_runs = run_repo.list_for_channel(channel_id)
    if not all_runs:
        return []

    log_by_run = {log.content_run_id: log for log in log_repo.list_timed_outcomes(channel_id)}
    # #929: every measured run counts, as it does for post time, the predictor and the
    # ledger; the 30-run window only bounds runs with no outcome yet.
    runs = [r for i, r in enumerate(all_runs) if i < _TOP_N or r.id in log_by_run]

    entries = []
    for run in runs:
        seed = normalize_seed_topic(run.input_topic or run.selected_topic or "")
        if not seed:
            continue
        log = log_by_run.get(run.id)
        # #938: the recommenders' target - 7-day views (log scale) or the engaged rate. The
        # key keeps its old name; every reader below formats it through `_target`.
        engaged_rate = (
            _target.outcome(log.metrics_json, getattr(log, "published_at", None)) if log else None
        )
        subs = _subscribers_gained(log.metrics_json) if log else 0
        entries.append(
            {
                "run_id": run.id,
                "topic": seed,
                "input_topic": normalize_seed_topic(run.input_topic or ""),
                "selected_topic": run.selected_topic or "",
                "engaged_rate": engaged_rate,
                "subscribers_gained": subs,
                "composite_score": float(run.composite_score or 0),
                "domain": _infer_domain(seed, channel_id),
                # #365: the weighting in get_best_bet reads this. Without it every
                # weight is 1.0 and the "decayed" mean is the arithmetic one.
                "age_days": _published_age_days(log),
                "views": _views_of(log),  # #1024
            }
        )
    return entries


def _views_of(log: Any) -> int | None:
    """View count on a publish-log row, or None when the row has no views field."""
    if log is None:
        return None
    import json

    try:
        data = json.loads(getattr(log, "metrics_json", None) or "{}")
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("views") is None:
        return None
    try:
        return int(data["views"])
    except (TypeError, ValueError):
        return None


def _today() -> date:
    return date.today()


_SLASH_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")


def pooled_drop_reason(topic: str, views: int | None, *, today: date | None = None) -> str:
    """Why a history-pool topic must not be offered again (#1024), or ""."""
    if views == 0:
        return "0 views"
    day = today or _today()
    from core.facts.event_dates import past_numbered_event

    numbered = past_numbered_event(topic, day)
    if numbered:
        return numbered
    match = _SLASH_DATE.search(topic or "")
    if match:
        month, dom = int(match.group(1)), int(match.group(2))
        year = int(match.group(3)) if match.group(3) else day.year
        if year < 100:
            year += 2000
        try:
            when = date(year, month, dom)
        except ValueError:
            when = None
        if when is not None and when < day:
            return f"event date {when.isoformat()} has passed"
    try:
        from core.batch_review import freshness_window_days
        from core.facts.event_dates import _SUPER_BOWL_ARABIC, _UFC_EVENT, _WRESTLEMANIA

        names_event = any(p.search(topic or "") for p in (_UFC_EVENT, _WRESTLEMANIA,
                                                          _SUPER_BOWL_ARABIC))  # fmt: skip
        if not names_event and freshness_window_days({"topic": topic, "title": topic}) < 7:
            # #1246: the menu replayed "Messi World Cup Hat Trick" months after the final. A
            # numbered event still ahead ("UFC 325 main event") is dated above, not here.
            return "a news story is not replayed"
    except Exception as exc:
        logger.debug("replay window unread: %s", exc)
    return ""


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

_STOP_WORDS = set(FUNCTION_WORDS) | {
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
            rationale=(f"covered {anchor} {repeat_count}× — pivoting to '{seed}'{kw_note}"),
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


def _angle_options(
    channel_id: str,
    entries: list[dict],
    *,
    exclude: set[str],
    limit: int,
) -> list[BestBetResult]:
    """Distinct content angles on the channel's dominant franchise anchor — to fill
    best-bet slots when live headlines + history run out.

    A single-franchise channel (all its coverage is one game) can't be given more *distinct
    headlines*, but it can be given more *distinct angles* on that franchise (tier list vs.
    what's broken vs. meta evolution). $0 — reuses the angle templates already used by
    _continuity_seed. Returns [] when there's no clear anchor (e.g. finance channels).
    """
    if limit <= 0 or not entries:
        return []
    anchor = dominant_anchor(e["topic"] for e in entries)
    if not anchor:
        return []

    anchor_entries = [e for e in entries if anchor.lower() in e.get("topic", "").lower()]
    top_kws = _weighted_keywords(anchor_entries or entries, anchor)

    ordered: list[str] = []
    seen_local: set[str] = set()

    def _add(text: str) -> None:
        key = normalize_seed_topic(text).lower()
        if key and key not in exclude and key not in seen_local:
            seen_local.add(key)
            ordered.append(text)

    # Keyword-matched angles first (biased toward what has worked), then the fallback
    # rotation for variety — same ordering _continuity_seed uses, but keep them all.
    for kw in top_kws:
        for template_key, template in _KEYWORD_ANGLE_MAP.items():
            if template_key in kw or kw in template_key:
                _add(template.format(anchor=anchor))
    for tmpl in _FALLBACK_ANGLES:
        _add(tmpl.format(anchor=anchor))

    return [
        BestBetResult(
            topic=text,
            domain=_infer_domain(text, channel_id),
            avg_engaged_rate=0.0,
            source="angle",
            supporting_runs=0,
            rationale=f"a fresh angle on {anchor} to vary your coverage",
        )
        for text in ordered[:limit]
    ]


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
        ages = [e.get("age_days") for e in with_analytics if e["domain"] == best_domain]
        avg_rate = weighted_engaged_mean(list(zip(rates, ages, strict=True)))
        best_topic = domain_topics[best_domain][0]
        subs_total = sum(
            int(e.get("subscribers_gained") or 0)
            for e in with_analytics
            if e["domain"] == best_domain
        )
        subs_note = f" · gained {subs_total} subscriber(s)" if subs_total else ""

        return BestBetResult(
            topic=best_topic,
            domain=best_domain,
            avg_engaged_rate=avg_rate,
            source="analytics",
            supporting_runs=len(rates),
            rationale=(
                f"{best_domain} averages {_target.show(avg_rate)} "
                f"across {len(rates)} video(s)"
                f"{_target.interval_note(rates)}"
                f"{_ranked_on_note(avg_rate, adjusted.get(best_domain))}"
                f"{confidence_note(len(rates))}"
                f"{subs_note}"
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
    from core.recommender_confidence import shrunk_mean

    all_rates = [r for v in by_domain.values() for r in v]
    prior = sum(all_rates) / len(all_rates)
    return {d: shrunk_mean(v, prior, MODERATE_SAMPLES) for d, v in by_domain.items()}


def _ranked_on_note(raw_rate: float, adjusted_rate: float | None, *, places: int = 1) -> str:
    """`recommender_confidence.ranked_on_note` - shared with length and post-time (#352).

    `_domain_priority` sorts on the empirical-Bayes-shrunk rate; the rationale prints
    the raw mean, whose #351 interval would otherwise disagree in public.
    """
    return _target.ranked_on_note(raw_rate, adjusted_rate, places=places)  # #938


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


def best_bet_preview_count() -> int:
    """How many previews/predictions the menu shows beside the ideas (decision 66)."""
    try:
        return max(0, min(8, int(os.getenv("BEST_BET_PREVIEWS", "5"))))
    except ValueError:
        return 5


def best_bet_option_count() -> int:
    """How many best-bet options to surface at startup (BEST_BET_OPTIONS, default 5)."""

    try:
        return max(1, min(8, int(os.getenv("BEST_BET_OPTIONS", "5"))))
    except ValueError:
        return 5


def _best_bet_signal_sources() -> set[str]:
    """Which candidate sources feed best-bet (BEST_BET_SIGNALS csv, default just 'rss').

    Opt-in extras are the KEYLESS ($0) backends 'reddit' and 'youtube' — never paid Apify.
    They add current Reddit-hot / YouTube-velocity titles at the cost of startup latency,
    so they stay off by default.
    """

    raw = os.getenv("BEST_BET_SIGNALS", "rss")
    return {s.strip().lower() for s in raw.split(",") if s.strip()} or {"rss"}


def _fresh_enabled() -> bool:

    return os.getenv("BEST_BET_FRESH", "true").lower() in ("1", "true", "yes")


def _fresh_days() -> int:

    try:
        return max(1, int(os.getenv("BEST_BET_FRESH_DAYS", "5")))
    except ValueError:
        return 5


def _parse_pubdate(raw: str | None) -> datetime | None:
    """Parse an RSS pubDate (RFC822) or Atom published/updated (ISO8601). None if unknown."""
    if not raw:
        return None
    from email.utils import parsedate_to_datetime

    s = raw.strip()
    dt: datetime | None = None
    try:
        dt = parsedate_to_datetime(s)  # RFC822, e.g. "Tue, 08 Jul 2026 14:03:00 GMT"
    except (TypeError, ValueError, IndexError):
        dt = None
    if dt is None:
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))  # ISO8601 (Atom)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _first_anchor(topic: str) -> str | None:
    """Franchise anchor for a title (e.g. 'gta'), or None — used for per-anchor diversity.

    Returns the most-GENERAL match (shortest) so 'GTA VI' and 'GTA 6' collapse to one
    franchise ('gta') and don't both fill best-bet slots.
    """
    try:
        from core.channel_context import extract_anchors

        anchors = extract_anchors(topic)
        return min(anchors, key=len).lower() if anchors else None
    except Exception:
        return None


# Product/deal/affiliate headlines that pass the domain gate (a gaming site's feed is
# full of "RTX 5080 Prebuilt Drops to $2,350") but are commerce, not video topics. These
# make terrible best bets — the recurring "best bet is always products" complaint.
_COMMERCE_MARKERS = (
    "drops to",
    "on sale",
    "for sale",
    "% off",
    "percent off",
    "discount",
    " deal",
    "deals",
    "coupon",
    "promo code",
    "price cut",
    "save $",
    "save up to",
    "restock",
    "clearance",
    "bundle",
    "cheapest",
    "lowest price",
    "best price",
    "prebuilt",
    "pre-built",
    "gaming pc",
    "gaming laptop",
    "gaming monitor",
    "gaming chair",
    "gaming desk",
    "gaming headset",
    "gaming keyboard",
    "gaming mouse",
    "graphics card",
    "nvme",
    "alienware",
    "geforce rtx",
    "radeon rx",
    "best buy",
    "newegg",
    "dell outlet",
    "microcenter",
    "amazon prime day",
)
_PRICE_RE = re.compile(r"\$\s?\d")


def _commerce_filter_enabled() -> bool:

    return os.getenv("BEST_BET_FILTER_COMMERCE", "true").lower() not in ("0", "false", "no")


def _is_commerce_headline(title: str) -> bool:
    """True for shopping/deal/hardware-listing headlines (not a real content topic)."""
    t = (title or "").lower()
    if _PRICE_RE.search(t):
        return True
    return any(m in t for m in _COMMERCE_MARKERS)


# Wave 112: live 2026-10-18 an idea was "NFL Week 6 odds, predictions, expert picks: Cowboys roll
# into Lambeau Field..." - another outlet's betting roundup, not a story. The channel makes its own
# calls (#1301).
_ROUNDUP_MARKERS = (
    "expert picks",
    "odds, predictions",
    "odds and predictions",
    "picks and predictions",
    "predictions and picks",
    "picks against the spread",
    "best bets",
    "betting odds",
    "betting picks",
    "player props",
    "parlay",
    "fantasy rankings",
    "start 'em",
    "start em, sit em",
    "dfs picks",
)


def _is_roundup_headline(title: str) -> bool:
    """True for a betting or fantasy roundup headline (another outlet's picks, not a story)."""
    t = (title or "").lower()
    return any(m in t for m in _ROUNDUP_MARKERS)


def _domain_for_feed(word_domain: str, feed_domains: list[str] | None) -> str:
    """A single-domain feed wins when the headline's words name something else.

    `mma` and `ufc` are one domain. An untagged source, or a feed tagged with
    more than one domain, keeps the word domain. A headline with no domain
    words stays neutral (#1221): the feed does not assign one.
    """
    tags = {str(d).strip().lower() for d in (feed_domains or []) if str(d).strip()}
    if not tags:
        return word_domain
    folded = {"ufc" if tag == "mma" else tag for tag in tags}
    if word_domain in tags or word_domain in folded:
        return word_domain
    # #1221: "Dr Food walks free..." is neutral. A gaming feed made it a gaming bet.
    if not word_domain or word_domain == "neutral":
        return word_domain or "neutral"
    # #1258: an MMA feed covers boxing and UFC. A weigh-in the words call boxing
    # stays boxing; one domain on the feed does not rename it.
    if word_domain == "boxing" and folded <= {"ufc"}:
        return "boxing"
    if len(folded) == 1:
        return next(iter(folded))
    return word_domain


def _consider_candidate(
    title: str,
    source: str,
    *,
    allowed: set[str],
    exclude: set[str],
    seen_local: set[str],
    published: datetime | None = None,
    feed_domains: list[str] | None = None,
) -> dict | None:
    """Vet a headline into a candidate dict, or None when it's empty, a duplicate, off-brand,
    or a commerce/deal headline. Shared by the RSS and keyless-signal candidate loops."""
    from apis.topic_scorer import infer_topic_domain

    t = (title or "").strip()
    if not t:
        return None
    if not isinstance(seen_local, set):
        seen_local = set(seen_local)
    key = normalize_seed_topic(t).lower()
    if key in exclude or key in seen_local:
        return None
    # #851: the headline's own domain. `infer_domain(t)` looked channel-free but resolved
    # the missing channel through CONTENT_CHANNEL_ID, so on a PC pinned to tapin every
    # keyword-less headline read "gaming" and passed.
    domain = _domain_for_feed(infer_topic_domain(t), feed_domains)
    if domain not in allowed:
        return None
    # Drop product/deal/affiliate headlines — commerce, not video topics.
    if _commerce_filter_enabled() and _is_commerce_headline(t):
        return None
    if _is_roundup_headline(t):  # wave 112: another outlet's picks
        return None
    seen_local.add(key)
    return {"topic": t, "domain": domain, "source": source, "published": published}


def _keyless_query_seed(channel_id: str, entries: list[dict]) -> str:
    """Search seed for the keyless backends: the channel's dominant franchise anchor if it
    has one, else its configured domain/name."""
    anchor = dominant_anchor(e["topic"] for e in entries) if entries else None
    if anchor:
        return anchor
    try:
        prof = get_channel_profile(channel_id)
        return (prof.domain or prof.name or "").strip()
    except Exception:
        return ""


def _keyless_candidates(
    channel_id: str,
    *,
    entries: list[dict],
    allowed: set[str],
    exclude: set[str],
    seen_local: set[str],
) -> list[dict]:
    """Fresh candidates from KEYLESS backends (reddit-free hot, youtube-free velocity), gated
    by BEST_BET_SIGNALS. Never touches paid Apify; fail-open per source. Trending/hot items
    are current by nature, so they're stamped 'now' for the recency preference."""
    sources = _best_bet_signal_sources()
    if not (sources & {"reddit", "youtube"}):
        return []
    seed = _keyless_query_seed(channel_id, entries)
    if not seed:
        return []

    now = datetime.now(timezone.utc)
    out: list[dict] = []

    def _absorb(items, source_label: str) -> None:
        for it in items or []:
            cand = _consider_candidate(
                it.get("title", ""),
                source_label,
                allowed=allowed,
                exclude=exclude,
                seen_local=seen_local,
                published=now,
            )
            if cand:
                out.append(cand)

    if "reddit" in sources:
        try:
            from apis.free_backends import fetch_reddit_free
            from apis.reddit_signal import _pick_subreddits

            _absorb(fetch_reddit_free(seed, _pick_subreddits(seed, channel_id)[:6]), "Reddit")
        except Exception as exc:
            logger.debug("fetch_reddit_free skipped: %s", exc)

    if "youtube" in sources:
        try:
            from apis.free_backends import fetch_youtube_free

            _absorb(fetch_youtube_free(seed), "YouTube")
        except Exception as exc:
            logger.debug("fetch_youtube_free skipped: %s", exc)

    return out


def _competitor_outlier_candidates(
    channel_id: str, *, allowed: set[str], exclude: set[str], seen_local: set[str], limit: int = 3
) -> list[dict]:
    """#1063: a watched channel's breakout video as a topic candidate, labelled with the
    channel and how far ahead of its median it is. Reads the stored snapshot - no network.
    Vetted like every other headline (on-brand domain, not a repeat, not a deal)."""
    try:
        from analytics.competitor_context import load_competitor_snapshot, outliers

        rows = outliers(load_competitor_snapshot(channel_id))[:limit]
    except Exception as exc:
        logger.debug("competitor outliers skipped: %s", exc)
        return []
    out: list[dict] = []
    for row in rows:
        cand = _consider_candidate(
            row["title"],
            f"{row['label']} breakout, {row['ratio']:.1f}x their median",
            allowed=allowed,
            exclude=exclude,
            seen_local=seen_local,
            published=_parse_pubdate(row.get("published_at")),
        )
        if cand:
            out.append(cand)
    return out


def _fresh_candidates(
    channel_id: str,
    *,
    allowed: set[str],
    exclude: set[str],
    limit: int = 12,
    entries: list[dict] | None = None,
) -> list[dict]:
    """Current headlines as fresh topic candidates — RSS by default, plus opt-in keyless
    signals (BEST_BET_SIGNALS).

    Returns [{topic, domain, source, published}] deduped against `exclude` (recently
    covered). Only titles that *confidently* map to an on-brand domain are kept (inferred
    without channel fallback) — filtering mixed-feed noise. Never raises — [] on any problem.

    Freshness: gathers a wide pool, prefers items published within BEST_BET_FRESH_DAYS,
    then applies a **date-seeded shuffle** so the surfaced set rotates day-to-day (stable
    within a session) instead of always returning the same top-of-feed headlines.
    """
    sources = _best_bet_signal_sources()
    pool: list[dict] = []
    seen_local: set[str] = set()

    if "rss" in sources:
        try:
            feeds = idea_feeds(channel_id, allowed)
            for feed, rows in zip(feeds, _fetch_feeds(feeds), strict=True):
                for row in rows[:20]:
                    cand = _consider_candidate(
                        row.get("title", ""),
                        feed.get("name", "RSS"),
                        allowed=allowed,
                        exclude=exclude,
                        seen_local=seen_local,
                        published=_parse_pubdate(row.get("published")),
                        feed_domains=list(feed.get("domains") or []),
                    )
                    if cand:
                        pool.append(cand)
        except Exception as exc:
            logger.debug("_fetch_feed skipped: %s", exc)

    pool.extend(
        _competitor_outlier_candidates(
            channel_id, allowed=allowed, exclude=exclude, seen_local=seen_local
        )
    )

    # Opt-in keyless signal breadth (reddit-free / youtube-free), $0, fail-open.
    pool.extend(
        _keyless_candidates(
            channel_id,
            entries=entries or [],
            allowed=allowed,
            exclude=exclude,
            seen_local=seen_local,
        )
    )

    if not pool:
        return []

    # Prefer recent items; keep older ones only if too few recent exist. Undated items
    # count as "unknown" and stay in the full pool (ranked no worse than old-but-dated).
    horizon = datetime.now(timezone.utc) - timedelta(days=_fresh_days())
    recent = [c for c in pool if c["published"] and c["published"] >= horizon]
    base = recent if len(recent) >= limit else pool

    # Daily rotation breaks ties only (#1300): the story on the most outlets leads.
    random.Random(datetime.now(timezone.utc).strftime("%Y-%m-%d")).shuffle(base)
    return rank_by_coverage(base)[:limit]


_IDEA_FEED_CAP = 24
_COVERAGE_HOURS = 48


def idea_feeds(channel_id: str, allowed: set[str] | None) -> list[dict]:
    """#1300: the feeds the idea pool reads - the channel's own and every configured feed for
    its on-brand domains. It read the channel's first 8, which for TapIn were four (MMA
    Fighting, Dexerto, IGN, Polygon), so no story could be seen on more than one outlet."""
    from config.data_sources import _dedupe_feeds, domain_rss_feeds, rss_feeds_for_channel

    feeds: list[dict[str, Any]] = list(rss_feeds_for_channel(channel_id))
    for domain in sorted(d for d in (allowed or ()) if d and d != "neutral"):
        for feed in domain_rss_feeds(domain):
            entry: dict[str, Any] = dict(feed)
            if not entry.get("domains"):
                entry["domains"] = [domain]
            feeds.append(entry)
    return _dedupe_feeds(feeds)[:_IDEA_FEED_CAP]


def _fetch_feeds(feeds: list[dict]) -> list[list[dict]]:
    """Each feed's rows, fetched side by side; [] for one that fails."""
    from concurrent.futures import ThreadPoolExecutor

    from apis.rss_feeds import _fetch_feed

    def one(feed: dict) -> list[dict]:
        try:
            return list(_fetch_feed(feed["url"]) or [])
        except Exception as exc:
            logger.debug("_fetch_feed skipped: %s", exc)
            return []

    if not feeds:
        return []
    with ThreadPoolExecutor(max_workers=min(8, len(feeds))) as pool:
        return list(pool.map(one, feeds))


def rank_by_coverage(pool: list[dict], *, now: datetime | None = None) -> list[dict]:
    """#1300 (the operator, 2026-10-18: "ideas are small small boring stories/news"): each
    candidate gets `outlets` - the distinct sources carrying the same story in the last 48 h,
    by `same_story`'s rule (two of its subjects named, or its only one) - and the pool is
    ordered by that count, then recency. The other headlines of a story leave the pool, so
    one story is one idea. The incoming order breaks ties (the daily rotation)."""
    from apis.topic_tokens import content_tokens, names_any, subject_markers, subject_terms

    moment = now or datetime.now(timezone.utc)
    horizon = moment - timedelta(hours=_COVERAGE_HOURS)

    def groups_of(topic: str) -> list[list[str]]:
        terms = subject_terms(topic, limit=6)
        # A headline with one subject matches on its whole name, and so does a "name" longer
        # than three words: a Title Case headline reads as one long name, and its single
        # words ("Fight", "Press", "Week") named every UFC story.
        if len(terms) == 1:
            return [[terms[0]]]
        return [[term] if len(term.split()) > 3 else subject_markers([term]) for term in terms]

    marks = [groups_of(str(c.get("topic") or "")) for c in pool]
    words = [set(content_tokens(str(c.get("topic") or ""))) for c in pool]

    def recent(c: dict) -> bool:
        published = c.get("published")
        return not isinstance(published, datetime) or published >= horizon

    def covers(i: int, j: int) -> bool:
        shared = len(words[i] & words[j])
        # The same words: "Call Of Duty: MW4's Campaign Launches Today" and "Call Of Duty: MW4
        # Is Not On Xbox Game Pass" name no subject the same way.
        if shared >= 3 and shared >= 0.4 * (min(len(words[i]), len(words[j])) or 1):
            return True
        groups = marks[i]
        if not groups or shared < min(2, len(words[i])):
            return False
        need = min(2, len(groups))
        topic = str(pool[j].get("topic") or "")
        return sum(1 for group in groups if names_any(topic, group)) >= need

    members: list[set[int]] = []
    for i, cand in enumerate(pool):
        story = {j for j in range(len(pool)) if j != i and recent(pool[j]) and covers(i, j)}
        members.append(story)
        outlets = {str(pool[j].get("source") or "") for j in story} | {
            str(cand.get("source") or "")
        }
        cand["outlets"] = sorted(o for o in outlets if o)

    def stamp(c: dict) -> float:
        published = c.get("published")
        return published.timestamp() if isinstance(published, datetime) else 0.0

    order = sorted(range(len(pool)), key=lambda i: (-len(pool[i]["outlets"]), -stamp(pool[i])))
    kept: list[dict] = []
    gone: set[int] = set()
    for i in order:
        if i in gone:
            continue
        kept.append(pool[i])
        gone |= members[i]
    return kept


def coverage_note(cand: dict) -> str:
    """ "on 3 outlets (BBC Sport, MMA Fighting, MMA Weekly)", or the one source (#1300)."""
    outlets = [o for o in cand.get("outlets") or [] if o]
    if len(outlets) < 2:
        return f"trending on {cand.get('source')} now"
    shown = ", ".join(outlets[:3]) + (", ..." if len(outlets) > 3 else "")
    return f"on {len(outlets)} outlets ({shown})"


def pick_record(options: list[Any], picked: int | None, *, by: str = "operator") -> dict[str, Any]:
    """#909: what the best-bet card offered and which rank was taken (None = typed own).

    Kept as `features["best_bet"]` so the prediction ledger can score the card. `by` says
    who took it (#913): "operator" at the card in main.py, "batch" for the overnight
    batch, "auto" for auto_generate.
    """
    offered = [
        {
            "topic": str(getattr(o, "topic", "") or ""),
            "domain": str(getattr(o, "domain", "") or ""),
            "expected": float(getattr(o, "avg_engaged_rate", 0.0) or 0.0),
            "source": str(getattr(o, "source", "") or ""),
            # #1301: the call a preview made, so the result can score it.
            **({"call": str(o.call)} if getattr(o, "call", "") else {}),
        }
        for o in options or []
    ]
    rank = picked if isinstance(picked, int) and 1 <= picked <= len(offered) else None
    # #938: what "expected" is measured in, so the ledger scores it on the same scale.
    record: dict[str, Any] = {
        "offered": offered,
        "picked": rank,
        "by": str(by or "operator"),
        "target": _target.target(),
    }
    chosen = list(options or [])[rank - 1] if rank else None
    facts = [str(f) for f in (getattr(chosen, "facts", None) or []) if str(f).strip()]
    if facts:  # #991: a series pick carries the lines it is written from
        record["facts"] = facts
    return record


# #1242 (the operator, 2026-10-16: "NFL + NBA, marquee games only"). A game becomes an idea
# when the league's national window carries it, the league marks it (London, a holiday game),
# or it is a team the channel has made videos about.
_NATIONAL_TV = {
    "nfl": frozenset({"NBC", "ESPN", "ABC", "ESPN2", "Prime Video", "Netflix", "NFL Net",
                      "NFL Network"}),
    "nba": frozenset({"ESPN", "ABC", "TNT", "NBC", "Prime Video", "Peacock", "NBA TV"}),
}  # fmt: skip


def _covered_teams(topics: list[str]) -> set[str]:
    from apis.nba_teams import team_names_in as nba_teams
    from apis.nfl_entities import team_names_in as nfl_teams

    out: set[str] = set()
    for topic in topics:
        teams = set(nfl_teams(topic)) | set(nba_teams(topic))
        if len(teams) >= 2 and " at " in f" {topic.lower()} ":
            # A bare game name was the old board's draft, not a team the operator chose.
            continue
        out.update(teams)
    return out


def marquee_note(topic: str, detail: dict[str, Any], covered: set[str] | list[str]) -> str:
    """Why this game is worth a video ("NBC", "NFL London Games", "Chargers, a team you made
    videos about"), or "" - then it is not offered."""
    from apis.nba_teams import team_names_in as nba_teams
    from apis.nfl_entities import team_names_in as nfl_teams

    league = str(detail.get("league") or "")
    national = _NATIONAL_TV.get(league)
    if not national:
        return ""
    on_tv = [name for name in detail.get("broadcasts") or [] if name in national]
    if on_tv:
        return on_tv[0]
    notes = detail.get("notes") or []
    if notes:
        return str(notes[0])
    mine = sorted((set(nfl_teams(topic)) | set(nba_teams(topic))) & set(covered))
    if mine:
        return f"{mine[0].split()[-1]}, a team you made videos about"
    return ""


def _kickoff(raw: str) -> str:
    """ "Sat Oct 24 9:00 PM EDT" - in the channel's zone, labelled, like the post-time line.
    Wave 105: the machine's zone gave CI (UTC) "Sun Oct 25 1:00 AM" and the PC (CDT) 8 PM."""
    try:
        from zoneinfo import ZoneInfo

        from analytics.post_timing import _load_static_post_schedule
        from config.channels import resolve_channel_id

        zone: Any = ZoneInfo(_load_static_post_schedule(resolve_channel_id(None)).timezone)
    except Exception:
        zone = timezone.utc
    try:
        when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        when = when.astimezone(zone)
    except ValueError:
        return ""
    hour = when.strftime("%I").lstrip("0") or "12"
    return f"{when:%a %b} {when.day} {hour}:{when:%M %p} {when.tzname() or ''}".rstrip()


def game_line(detail: dict[str, Any], note: str) -> str:
    """#1243: "Sun Oct 18 7:20 PM · NBC · Cowboys 3-3 at Packers 4-1" - not "on the board"."""
    parts = [part for part in (_kickoff(str(detail.get("date") or "")), note) if part]
    away, home = detail.get("away") or {}, detail.get("home") or {}
    if away.get("name") and home.get("name"):
        left = f"{away['name']} {away.get('record') or ''}".strip()
        right = f"{home['name']} {home.get('record') or ''}".strip()
        parts.append(f"{left} at {right}")
    return " · ".join(parts) or "on the board this week"


def _started(raw: str, now: datetime) -> bool:
    try:
        when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return False
    if when.tzinfo is None:
        return False
    return when <= now


def suggested_games(
    scheduled: list[tuple[str, str]],
    *,
    covered_topics: list[str],
    now: datetime | None = None,
) -> list[BestBetResult]:
    """The week's games worth an idea, each with its reason (#1242, #1243). An award date
    carries no game detail and stays as it was; a game that has started is not an idea."""
    from core.seasonal_calendar import game_details

    covered = _covered_teams(covered_topics)
    moment = now or datetime.now(timezone.utc)
    out: list[BestBetResult] = []
    for topic, domain in scheduled:
        detail = game_details(topic)
        if detail and _started(str(detail.get("date") or ""), moment):
            # The board is dated in UTC and cached: a 9:30 PM CDT tip-off is still "Oct 17".
            continue
        if detail:
            note = marquee_note(topic, detail, covered)
            if not note:
                continue
            rationale = game_line(detail, note)
        else:
            from core.seasonal_calendar import award_line

            rationale = award_line(topic) or "on the board this week"
        out.append(
            BestBetResult(
                topic=topic,
                domain=domain,
                avg_engaged_rate=0.0,
                source="schedule",
                supporting_runs=0,
                rationale=rationale,
            )
        )
    return out


def get_best_bets(
    channel_id: str,
    n: int = 5,
    *,
    games: bool = True,
    scheduled: list[tuple[str, str]] | None = None,
) -> list[BestBetResult]:
    """
    Up to `n` DISTINCT topic options, best first.

    Forward-looking: the channel's analytics pick the winning *domain* (what works),
    while live RSS headlines supply the *current* topic (what's relevant now), so the
    suggestions are fresh and stop repeating the same historical seeds. Falls back to
    the historical engagement ranking when no fresh headlines are available.

    ``games=False`` (decision 66): the ideas half of the menu - the coming games, cards and
    awards are `preview_options`'s.
    """
    entries = _build_entries(channel_id)
    if scheduled is None:
        scheduled = []
        try:
            from core.seasonal_calendar import fetch_week_topics

            scheduled = fetch_week_topics()
        except Exception as exc:
            logger.debug("week topics skipped: %s", exc)
    if not games:
        scheduled = []
    try:
        recent_topics = list(recent_input_topics(channel_id, limit=60))
    except Exception:
        recent_topics = []
    marquee = suggested_games(
        scheduled, covered_topics=recent_topics + [str(e.get("topic") or "") for e in entries]
    )
    if not entries:
        if marquee:
            return marquee[:n]
        single = get_best_bet(channel_id)
        return [single] if single else []

    allowed = _effective_allowed(channel_id, entries)
    domain_rates = _domain_avg_rates(entries)
    domain_counts = _domain_sample_counts(entries)
    adjusted = _adjusted_domain_rates(entries)
    # Don't re-suggest anything covered recently (kills the repeat problem) — nor
    # any topic in the Graveyard (proven flops; avoid-list from core/topic_db).
    recent = {normalize_seed_topic(t).lower() for t in recent_input_topics(channel_id, limit=30)}
    try:
        from core.topic_db import graveyard_topics

        recent |= {normalize_seed_topic(t).lower() for t in graveyard_topics(channel_id)}
    except Exception as exc:
        logger.debug("graveyard_topics skipped: %s", exc)

    options: list[BestBetResult] = []
    seen: set[str] = set(recent)
    # #1244 (the operator, 2026-10-16: "compete like any idea"): a game is a candidate in its
    # league's slot - after a fresh headline there, before a replay - never a reserved place.
    games_by_domain: dict[str, list[BestBetResult]] = {}
    for game in marquee:
        key = normalize_seed_topic(game.topic).lower()
        if key and key not in seen:
            games_by_domain.setdefault(game.domain, []).append(game)
    used_domains: set[str] = set()
    used_anchors: set[str] = set()  # per-franchise cap so gaming isn't all one game (e.g. GTA)

    try:
        from core.topic_graph import follow_up_seed

        arc = follow_up_seed(channel_id)
        if arc:
            key = normalize_seed_topic(arc.topic).lower()
            if key and key not in seen:
                options.append(arc)
                seen.add(key)
                used_domains.add(arc.domain)
                anchor = _first_anchor(arc.topic)
                if anchor:
                    used_anchors.add(anchor)
    except Exception as exc:
        logger.debug("topic graph skipped: %s", exc)

    try:
        from core.seasonal_calendar import due_topics

        for item in due_topics(channel_id):
            topic = str(item.get("topic") or "").strip()
            key = normalize_seed_topic(topic).lower()
            if not key or key in seen:
                continue
            domain = str(item.get("domain") or "").strip() or _infer_domain(topic, channel_id)
            cal = BestBetResult(
                topic=topic,
                domain=domain,
                avg_engaged_rate=0.0,
                source="calendar",
                supporting_runs=0,
                rationale=f"seasonal calendar ({item.get('date')})",
            )
            options.append(cal)
            seen.add(key)
            used_domains.add(domain)
            anchor = _first_anchor(topic)
            if anchor:
                used_anchors.add(anchor)
            if len(options) >= n:
                return options[:n]
    except Exception as exc:
        logger.debug("seasonal calendar skipped: %s", exc)

    # #114: what the channel's own viewers asked, two or more of them.
    try:
        from analytics.mailbag import top_question

        asked = top_question(channel_id, exclude=seen)
        if asked and len(options) < n:
            topic = str(asked["question"])
            domain = _infer_domain(topic, channel_id)
            count, videos = int(asked.get("count") or 0), len(asked.get("videos") or [])
            options.append(
                BestBetResult(
                    topic=topic,
                    domain=domain,
                    avg_engaged_rate=0.0,
                    source="mailbag",
                    supporting_runs=0,
                    rationale=f"viewers asked: {count} viewers on {videos} video"
                    + ("s" if videos != 1 else ""),
                )
            )
            seen.add(normalize_seed_topic(topic).lower())
            used_domains.add(domain)
    except Exception as exc:
        logger.debug("mailbag candidate skipped: %s", exc)

    def _domain_key(d: str) -> tuple:
        return _domain_priority(d, adjusted, domain_counts)

    # Fresh RSS headlines, grouped by domain (relevant "what's hot now").
    by_domain: dict[str, list[dict]] = {}
    ordered_fresh_domains: list[str] = []
    if _fresh_enabled():
        fresh = _fresh_candidates(channel_id, allowed=allowed, exclude=recent, entries=entries)
        on_brand_fresh = [c for c in fresh if c["domain"] in allowed] or fresh
        for c in on_brand_fresh:
            by_domain.setdefault(c["domain"], []).append(c)
        ordered_fresh_domains = sorted(by_domain, key=_domain_key, reverse=True)

    def _emit_fresh(c: dict) -> bool:
        key = normalize_seed_topic(c["topic"]).lower()
        if not key or key in seen:
            return False
        anchor = _first_anchor(c["topic"])
        if anchor and anchor in used_anchors:
            return False  # already have a pick for this franchise
        seen.add(key)
        used_domains.add(c["domain"])
        if anchor:
            used_anchors.add(anchor)
        rate = domain_rates.get(c["domain"])
        rationale = coverage_note(c)
        if rate is not None:
            rationale += f" · {c['domain']} averages {_target.show(rate, places=0)}"
            rationale += _ranked_on_note(rate, adjusted.get(c["domain"]), places=0)
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

    def _emit_game(game: BestBetResult) -> bool:
        key = normalize_seed_topic(game.topic).lower()
        if not key or key in seen:
            return False
        seen.add(key)
        used_domains.add(game.domain)
        options.append(game)
        return True

    def _emit_hist(e: dict) -> bool:
        key = normalize_seed_topic(e["topic"]).lower()
        if not key or key in seen:
            return False
        if pooled_drop_reason(e["topic"], e.get("views"), today=_today()):
            return False
        anchor = _first_anchor(e["topic"])
        if anchor and anchor in used_anchors:
            return False  # already have a pick for this franchise
        seen.add(key)
        used_domains.add(e["domain"])
        if anchor:
            used_anchors.add(anchor)
        if e["engaged_rate"] is not None:
            source = "analytics"
            # No `_ranked_on_note` here, deliberately: this is one run's own rate,
            # labelled as such, not a domain aggregate. Appending a shrunk *domain*
            # figure would compare two different quantities (#654).
            rationale = f"{_target.show(e['engaged_rate'], places=0)} on a past {e['domain']} video"
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
        set(ordered_fresh_domains) | set(hist_domains) | set(games_by_domain),
        key=_domain_key,
        reverse=True,
    )
    for d in all_domains:
        if len(options) >= n:
            break
        if d in used_domains:
            continue
        if any(_emit_fresh(c) for c in by_domain.get(d, [])):
            continue
        if any(_emit_game(game) for game in games_by_domain.get(d, [])[:1]):
            continue  # one game a league, and only where no headline answered
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

    # Phase 3 — angle multiplexing: fill remaining slots with DISTINCT angles on the
    # dominant franchise (e.g. "GTA tier list", "what's broken in GTA"). This is what a
    # single-franchise channel needs instead of near-duplicate headlines — and it's $0.
    if len(options) < n:
        for opt in _angle_options(channel_id, entries, exclude=seen, limit=n - len(options)):
            seen.add(normalize_seed_topic(opt.topic).lower())
            options.append(opt)
            if len(options) >= n:
                break

    # Last resort: the continuity seed (below-threshold franchise replay) if still short.
    if len(options) < n:
        cont = _continuity_seed(channel_id, entries)
        if cont and normalize_seed_topic(cont.topic).lower() not in seen:
            options.append(cont)

    return options[:n]  # #1244: a thin day shows fewer ideas, never more games


_OTHER_LEAGUES = ("nfl", "nba")


def _event_when(topic: str) -> str:
    """ "Sat Oct 24 9:00 PM" for a card or game read this run, else ""."""
    try:
        from core.seasonal_calendar import event_start

        return _kickoff(str(event_start(topic) or ""))
    except Exception:
        return ""


def same_story(preview: str, ideas: list[str]) -> bool:
    """An idea already covers this event: it names two of the preview's subjects, or its only
    one (2026-10-17: "LIVE! UFC Edmonton Results: Buckley vs. Malott" beside the preview "UFC
    Fight Night: Buckley vs. Malott"). One shared team is another story ("Packers sign a new
    kicker" is not the Cowboys-Packers game)."""
    from apis.topic_tokens import names_any, subject_markers, subject_terms

    terms = subject_terms(preview, limit=6)
    if not terms:
        return False
    need = min(2, len(terms))
    for idea in ideas:
        named = sum(1 for term in terms if names_any(idea, subject_markers([term])))
        if named >= need:
            return True
    return False


def preview_options(
    scheduled: list[tuple[str, str]],
    *,
    covered_topics: list[str],
    exclude: list[str] | tuple[str, ...] = (),
    ideas: list[str] | tuple[str, ...] = (),
    n: int = 5,
    now: datetime | None = None,
) -> list[BestBetResult]:
    """The coming events worth a preview or a prediction (decision 66): marquee NFL/NBA games,
    UFC cards, awards, then the other NFL and NBA games - one of each kind in turn, each kind
    soonest first. Nothing started, nothing already covered."""
    from dataclasses import replace

    from core.seasonal_calendar import game_details

    moment = now or datetime.now(timezone.utc)
    skip = {normalize_seed_topic(t).lower() for t in exclude if t}
    kinds: dict[str, list[tuple[str, BestBetResult]]] = {
        "marquee": [], "ufc": [], "award": [], "other": [],
    }  # fmt: skip
    offered: set[str] = set()
    shown = list(ideas)
    for bet in suggested_games(scheduled, covered_topics=covered_topics, now=moment):
        key = normalize_seed_topic(bet.topic).lower()
        if not key or key in skip or same_story(bet.topic, shown):
            continue
        detail = game_details(bet.topic)
        offered.add(bet.topic)
        if detail:
            kinds["marquee"].append((str(detail.get("date") or ""), bet))
        elif bet.domain == "ufc":
            when = _event_when(bet.topic)
            card = replace(bet, rationale=f"{when} · UFC card" if when else "UFC card")
            kinds["ufc"].append((str(when), card))
        else:
            kinds["award"].append(("", bet))
    for topic, domain in scheduled:
        key = normalize_seed_topic(topic).lower()
        if topic in offered or not key or key in skip or same_story(topic, shown):
            continue
        detail = game_details(topic)
        if not detail or str(detail.get("league") or "") not in _OTHER_LEAGUES:
            continue
        if _started(str(detail.get("date") or ""), moment):
            continue
        offered.add(topic)
        kinds["other"].append(
            (
                str(detail.get("date") or ""),
                BestBetResult(
                    topic=topic,
                    domain=domain,
                    avg_engaged_rate=0.0,
                    source="schedule",
                    supporting_runs=0,
                    rationale=game_line(detail, ""),
                ),
            )
        )
    queues = [[bet for _when, bet in sorted(rows, key=lambda r: r[0])] for rows in kinds.values()]
    out: list[BestBetResult] = []
    while len(out) < n and any(queues):
        for queue in queues:
            if queue and len(out) < n:
                out.append(queue.pop(0))
    return out


def get_idea_menu(
    channel_id: str,
    *,
    ideas: int | None = None,
    previews: int | None = None,
    now: datetime | None = None,
) -> tuple[list[BestBetResult], list[BestBetResult]]:
    """(ideas, previews): five of each by default (the operator, 2026-10-17, decision 66 -
    "5 ideas 5 previews/predictions")."""
    scheduled: list[tuple[str, str]] = []
    try:
        from core.seasonal_calendar import fetch_week_topics

        scheduled = fetch_week_topics()
    except Exception as exc:
        logger.debug("week topics skipped: %s", exc)
    idea_list = get_best_bets(
        channel_id, ideas or best_bet_option_count(), games=False, scheduled=scheduled
    )
    try:  # #991: "Picks, graded" leads the week it is due, in place of the last idea
        series = _series_idea(channel_id)
        if series is not None:
            idea_list = [series, *idea_list][: max(len(idea_list), 1)]
    except Exception as exc:
        logger.debug("series idea skipped: %s", exc)
    want = best_bet_preview_count() if previews is None else previews
    if want <= 0:
        return idea_list, []
    try:
        recent = list(recent_input_topics(channel_id, limit=30))
        covered = list(recent_input_topics(channel_id, limit=60))
        covered += [str(e.get("topic") or "") for e in _build_entries(channel_id)]
    except Exception:
        recent, covered = [], []
    preview_list = preview_options(
        scheduled,
        covered_topics=covered,
        exclude=[*recent, *(b.topic for b in idea_list)],
        ideas=[b.topic for b in idea_list],
        n=want,
        now=now,
    )
    try:  # #1301: each preview with its call - fail-open
        from core.predictions import calls

        if preview_list and calls.enabled():
            previews_now = list(preview_list)
            made = calls.preview_calls(
                previews_now, headlines=lambda: calls.headlines_for(previews_now)
            )
            preview_list = with_calls(preview_list, made)
    except Exception as exc:
        logger.debug("preview calls skipped: %s", exc)
    return idea_list, preview_list


def _series_idea(channel_id: str) -> BestBetResult | None:
    """This week's "Picks, graded", once its calls are scored and it is not drafted yet (#991)."""
    from core.batch_generation import series_drafted
    from core.predictions.calls import picks_graded

    series = picks_graded()
    if series is None:
        return None
    topic, facts, rationale = series
    if series_drafted(channel_id, topic):
        return None
    return BestBetResult(
        topic=topic,
        domain="nfl",
        avg_engaged_rate=0.0,
        source="series",
        supporting_runs=0,
        rationale=rationale,
        facts=list(facts),
    )


def with_calls(previews: list[BestBetResult], made: dict[str, dict]) -> list[BestBetResult]:
    """The previews with their calls in the menu line and on the result (#1301)."""
    from dataclasses import replace

    from core.predictions.calls import call_line, call_text

    out: list[BestBetResult] = []
    for bet in previews:
        call = made.get(bet.topic)
        if not call:
            out.append(bet)
            continue
        rationale = f"{bet.rationale} · {call_line(call)}" if bet.rationale else call_line(call)
        out.append(replace(bet, rationale=rationale, call=call_text(call)))
    return out


def display_idea_menu(
    ideas: list[BestBetResult], previews: list[BestBetResult], *, print_fn=print
) -> None:
    """Two groups, numbered on: the ideas, then the previews and predictions (decision 66)."""
    print_fn("\n  Ideas (pick one, or type your own):")
    for number, opt in enumerate(ideas, 1):
        print_fn(f"   {number:>2}. [{opt.domain}] {opt.topic}")
        print_fn(f"       {opt.rationale}")
    if previews:
        print_fn("\n  Previews and predictions:")
        for number, opt in enumerate(previews, len(ideas) + 1):
            print_fn(f"   {number:>2}. [{opt.domain}] {opt.topic}")
            print_fn(f"       {opt.rationale}")


def display_best_bet(result: BestBetResult) -> None:
    """Print a summary of the best-bet recommendation to stdout."""
    tag = {
        "analytics": "analytics",
        "continuity": "channel history",
        "score": "score-based",
        "arc": "franchise arc",
        "calendar": "seasonal calendar",
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
