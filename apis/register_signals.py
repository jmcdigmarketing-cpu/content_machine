import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from apis.cache_manager import build_key, get_cached, set_cache
from apis.live_scores_api import live_scores_cache_ttl
from apis.signal_contract import (
    STATUS_AUTH,
    STATUS_NO_KEY,
    STATUS_QUOTA,
    STATUS_RATE_LIMIT,
    normalize_signal,
)
from apis.signals_bootstrap import get_signal_registry
from apis.youtube_api import start_youtube_warmup_background
from core.logging import get_logger

logger = get_logger("apis.register_signals")

_SKIP = {s.strip().lower() for s in os.getenv("CONTENT_SKIP_SIGNALS", "").split(",") if s.strip()}

# Session circuit breaker
# -----------------------
# A signal that returns a hard, non-recoverable status (quota exhausted, auth/key
# failure) is disabled for the rest of the process: every subsequent build_registry
# call this session skips it instead of paying the failing round-trip again. This
# generalises the per-call Apify 402 handling to ANY signal (the contract already
# classifies these statuses uniformly via signal_contract).
#
# Rate-limits are transient and recover, so they only trip the breaker when
# SIGNAL_BREAKER_INCLUDE_RATE_LIMIT is enabled.
_TRIP_STATUSES = {STATUS_QUOTA, STATUS_AUTH, STATUS_NO_KEY}
_SESSION_DISABLED: set[str] = set()
_BREAKER_LOCK = threading.Lock()


def _breaker_enabled() -> bool:
    return os.getenv("SIGNAL_CIRCUIT_BREAKER", "true").lower() in ("1", "true", "yes")


def _trip_statuses() -> set[str]:
    statuses = set(_TRIP_STATUSES)
    if os.getenv("SIGNAL_BREAKER_INCLUDE_RATE_LIMIT", "").lower() in ("1", "true", "yes"):
        statuses.add(STATUS_RATE_LIMIT)
    return statuses


def _record_signal_health(name: str, result: dict[str, Any]) -> None:
    """Trip the session breaker if a signal returned a hard failure status."""
    if not _breaker_enabled() or not isinstance(result, dict):
        return
    status = result.get("status")
    if status not in _trip_statuses():
        return
    with _BREAKER_LOCK:
        if name in _SESSION_DISABLED:
            return
        _SESSION_DISABLED.add(name)
    logger.warning(
        "Circuit breaker: disabling signal '%s' for this session (status=%s, detail=%s)",
        name,
        status,
        result.get("status_detail") or "",
    )


def _disabled_signals() -> set[str]:
    if not _breaker_enabled():
        return set()
    with _BREAKER_LOCK:
        return set(_SESSION_DISABLED)


def reset_session_breaker() -> None:
    """Clear all session-disabled signals (test/CLI helper)."""
    with _BREAKER_LOCK:
        _SESSION_DISABLED.clear()


def disabled_signals() -> set[str]:
    """Signals disabled this session by the breaker (public view for the dashboard)."""
    return _disabled_signals()


# Signals reused (pinned) from the base-topic fetch during per-variant scoring,
# instead of being re-fetched for each of the 5 variants. The slow/paid Apify
# social actors barely differ across title variants of the same topic — reusing
# them cuts discovery from minutes to seconds and saves Apify credits.
_VARIANT_REUSE = tuple(
    s.strip().lower()
    for s in os.getenv(
        "VARIANT_REUSE_SIGNALS",
        "youtube,reddit,twitter,tiktok_trends,youtube_competitors",
    ).split(",")
    if s.strip()
)

# Domain-aware signal gating
# ---------------------------
# Signals that only make sense for a specific content domain. Anything NOT listed
# here is universal (youtube, trends, news, wikipedia, reddit, etc.) and never gated.
# When a topic confidently belongs to one domain group, we skip domain-specific
# signals from a *different* group — e.g. RAWG/Steam/IGDB never run on a UFC topic
# (which is where they currently match the wrong game), and the sports/odds/UFC
# scrapers never run on a gaming topic.
_DOMAIN_SIGNALS: dict[str, set[str]] = {
    "gaming": {"rawg", "steam", "igdb", "twitch", "trendingnow"},
    "sports": {
        "sports",
        "live_scores",
        "odds",
        "stats_context",
        "api_sports",
        "ufc_context",
        "tapology",
    },
    "finance": {"fred", "sec_edgar", "finnhub", "coingecko"},
    "anime": {"anime"},
    "popculture": {"tmdb", "tvmaze"},
    "music": {"lastfm", "musicbrainz"},
}

# Map an inferred topic domain (from topic_scorer.infer_domain) to a gating group.
_DOMAIN_GROUP: dict[str, str] = {
    "nba": "sports",
    "nfl": "sports",
    "ufc": "sports",
    "gaming": "gaming",
    "finance": "finance",
    "anime": "anime",
    "popculture": "popculture",
    "music": "music",
}

# Reverse index: signal name -> the domain group it belongs to (built once).
_SIGNAL_GROUP: dict[str, str] = {
    name: group for group, names in _DOMAIN_SIGNALS.items() for name in names
}

# Team-sport signals (team databases / team-sport betting / team scoreboards) that
# do NOT cover MMA. They share the "sports" group with ufc_context/tapology, so the
# group-level gating keeps them active on UFC topics — where they return noise (a
# random soccer club, CFL odds). Skip them specifically for UFC/MMA topics; the
# MMA-native signals (ufc_context, tapology, stats_context) stay.
_TEAM_SPORT_SIGNALS = {"sports", "odds", "live_scores", "api_sports"}


def _domain_gating_enabled() -> bool:
    return os.getenv("DOMAIN_SIGNAL_GATING", "true").lower() in ("1", "true", "yes")


def _gated_signal_names(topic: str, channel_id: str | None = None) -> set[str]:
    """
    Names of domain-specific signals to skip for this topic.

    Returns empty when gating is disabled or the topic's domain is unknown/neutral
    (fail-open: when unsure, run everything). Universal signals are never returned.
    """
    if not _domain_gating_enabled():
        return set()

    from apis.topic_scorer import infer_domain

    inferred = infer_domain(topic, channel_id)
    topic_group = _DOMAIN_GROUP.get(inferred)
    if not topic_group:
        return set()

    gated = {name for name, group in _SIGNAL_GROUP.items() if group != topic_group}
    # Within the sports group, team-sport signals don't cover MMA.
    if inferred == "ufc":
        gated |= _TEAM_SPORT_SIGNALS
    return gated


def _youtube_cache_ttl():
    try:
        return int(os.getenv("YOUTUBE_CACHE_TTL_SECONDS", str(6 * 60 * 60)))
    except ValueError:
        return 6 * 60 * 60


def _active_signal_sources(topic: str = "", channel_id: str | None = None):
    registry = get_signal_registry().get_registered_signals()
    pairs = tuple(registry.items())
    skip = set(_SKIP)
    skip |= _disabled_signals()
    if topic:
        skip |= _gated_signal_names(topic, channel_id)
    if not skip:
        return pairs
    return tuple(pair for pair in pairs if pair[0] not in skip)


# Signals whose data comes from a paid Apify actor run.
_APIFY_PAID_SIGNALS = frozenset({"reddit", "twitter", "tiktok_trends", "youtube_competitors"})


def will_use_apify(topic: str = "", channel_id: str | None = None) -> bool:
    """True iff a paid Apify-backed signal survives skip/gating/breaker for this topic.

    Lets the pipeline skip the Apify preflight network call entirely when no
    Apify actor will run (e.g. those signals are in CONTENT_SKIP_SIGNALS or the
    session/persisted breaker already disabled them). Fail-safe: any error → True
    (preflight runs), so we never wrongly skip a needed credit check.
    """
    try:
        active = {name for name, _ in _active_signal_sources(topic, channel_id)}
        return bool(active & _APIFY_PAID_SIGNALS)
    except Exception:
        return True


def _cache_ttl_for(name):
    if name == "live_scores":
        return live_scores_cache_ttl()
    if name == "youtube":
        return _youtube_cache_ttl()
    if name in (
        "stats_context",
        "blog_rss",
        "wikipedia",
        "fred",
        "sec_edgar",
        "anime",
        "tmdb",
        "tvmaze",
        "musicbrainz",
        "igdb",
        "trendingnow",
    ):
        return 6 * 60 * 60
    if name == "twitch":
        return 60 * 60
    if name == "reddit":
        return 4 * 60 * 60  # 4h — Reddit hot posts shift slowly
    if name == "tiktok_trends":
        return 3 * 60 * 60  # 3h — TikTok trends move faster
    if name == "youtube_competitors":
        return 3 * 60 * 60  # 3h — competitor view velocity
    if name == "twitter":
        return 90 * 60  # 1.5h — breaking news moves fastest
    if name == "web_search":
        return 90 * 60  # 1.5h — live facts move fast
    return None


def _fetch_one(name, func, topic, pinned: dict[str, Any] | None = None):
    if pinned and name in pinned and pinned[name]:
        return name, normalize_signal(pinned[name])

    key = build_key(name, topic)
    cached = get_cached(key)
    if cached is not None:
        return name, normalize_signal(cached)

    result = normalize_signal(func(topic))
    _record_signal_health(name, result)
    set_cache(key, result, ttl_seconds=_cache_ttl_for(name))
    return name, result


def _fanout_enabled() -> bool:
    return os.getenv("TOPIC_FANOUT_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def _merge_signal(existing: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    if not existing:
        return new
    if (new.get("score") or 0) > (existing.get("score") or 0):
        return new
    if new.get("active") and not existing.get("active"):
        return new
    return existing


def _apply_topic_fanout(
    topic: str,
    results: dict[str, Any],
    sources: tuple,
) -> dict[str, Any]:
    from apis.topic_fanout import FANOUT_SIGNAL_NAMES, parse_subtopics

    subtopics = parse_subtopics(topic)
    if not subtopics:
        return results

    registry = dict(sources)
    disabled = _disabled_signals()
    for sub in subtopics:
        for name in FANOUT_SIGNAL_NAMES:
            if name not in registry or name in _SKIP or name in disabled:
                continue
            _, sub_sig = _fetch_one(name, registry[name], sub, None)
            results[name] = _merge_signal(results.get(name), sub_sig)

    return results


def build_registry(
    topic,
    max_workers=None,
    *,
    reuse_signals: dict[str, Any] | None = None,
    channel_id: str | None = None,
):
    """
    Fetch all signals in parallel. Results are cached per signal + topic.

    reuse_signals: pin signals from a prior fetch (e.g. base-topic YouTube during
    variant scoring) to avoid duplicate slow API calls.
    channel_id: used as a fallback when inferring the topic's domain for gating.
    """
    start_youtube_warmup_background()

    sources = _active_signal_sources(topic, channel_id)
    workers = max_workers or len(sources)
    pinned = {}
    if reuse_signals:
        for name in _VARIANT_REUSE:
            if reuse_signals.get(name):
                pinned[name] = reuse_signals[name]

    results = {}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_fetch_one, name, func, topic, pinned) for name, func in sources]
        for future in as_completed(futures):
            name, data = future.result()
            results[name] = data

    if _fanout_enabled() and not reuse_signals:
        results = _apply_topic_fanout(topic, results, sources)

    if os.getenv("USE_SIGNAL_SYNTHESIS", "").lower() in ("1", "true", "yes"):
        try:
            from apis.signal_synthesizer import synthesize_signals

            results["_synthesis"] = synthesize_signals(results)
        except Exception:
            pass

    return results
