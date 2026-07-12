import os
import threading
import time
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


def _skip_signals() -> set[str]:
    """Signals to skip entirely (CONTENT_SKIP_SIGNALS), read per-call so a runtime
    toggle applies — e.g. Free mode appends the paid signals after this module is
    already imported (core.pipeline loads eagerly at startup, see main.py)."""
    return {
        s.strip().lower() for s in os.getenv("CONTENT_SKIP_SIGNALS", "").split(",") if s.strip()
    }


# Session circuit breaker
# -----------------------
# A signal that returns a hard, non-recoverable status (quota exhausted, auth/key
# failure) is disabled for the rest of the process: every subsequent build_registry
# call this session skips it instead of paying the failing round-trip again. This
# generalises the per-call Apify 402 handling to ANY signal (the contract already
# classifies these statuses uniformly via signal_contract).
#
# Hard trips also PERSIST across runs (core/quota_governor.py, TTL'd, key-hash
# invalidated — a changed credential clears the record). SIGNAL_BREAKER_PERSIST=false
# turns persistence off.
#
# Rate-limits are transient and recover, so they get a *timed cooldown*
# (disabled-until-T, default 15 min via SIGNAL_RATE_LIMIT_COOLDOWN_SECONDS)
# instead of a session-long trip — unless SIGNAL_BREAKER_INCLUDE_RATE_LIMIT is
# enabled, which promotes 429s to a permanent session trip. Free/keyless
# backends fail by 429 rather than 402, so without the cooldown they'd hammer
# a rate-limiting host on every discovery pass.
_TRIP_STATUSES = {STATUS_QUOTA, STATUS_AUTH, STATUS_NO_KEY}
_SESSION_DISABLED: set[str] = set()
_COOLDOWN_UNTIL: dict[str, float] = {}  # signal name -> unix ts when it may run again
# Hard trips also persist across runs via core/quota_governor.py (scope "signal",
# key-hash invalidated). Loaded once per process into this memo.
_PERSISTED_DISABLED: set[str] = set()
_PERSISTED_SYNCED = False
_BREAKER_LOCK = threading.Lock()


def _breaker_enabled() -> bool:
    return os.getenv("SIGNAL_CIRCUIT_BREAKER", "true").lower() in ("1", "true", "yes")


def _trip_statuses() -> set[str]:
    statuses = set(_TRIP_STATUSES)
    if os.getenv("SIGNAL_BREAKER_INCLUDE_RATE_LIMIT", "").lower() in ("1", "true", "yes"):
        statuses.add(STATUS_RATE_LIMIT)
    return statuses


def _cooldown_seconds() -> int:
    try:
        return int(os.getenv("SIGNAL_RATE_LIMIT_COOLDOWN_SECONDS", "900"))
    except ValueError:
        return 900


def _record_signal_health(name: str, result: dict[str, Any]) -> None:
    """Trip the session breaker (hard failure) or start a cooldown (rate limit)."""
    if not _breaker_enabled() or not isinstance(result, dict):
        return
    status = result.get("status")
    if status == STATUS_RATE_LIMIT and status not in _trip_statuses():
        secs = _cooldown_seconds()
        if secs <= 0:
            return
        until = time.time() + secs
        with _BREAKER_LOCK:
            _COOLDOWN_UNTIL[name] = max(_COOLDOWN_UNTIL.get(name, 0.0), until)
        logger.warning(
            "Circuit breaker: cooling down signal '%s' for %ds after rate limit (detail=%s)",
            name,
            secs,
            result.get("status_detail") or "",
        )
        return
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
    try:
        from core.quota_governor import disable_signal

        detail = result.get("status_detail") or ""
        disable_signal(name, f"{status}: {detail}" if detail else str(status))
    except Exception:
        pass  # persistence is an optimization, never load-bearing


def _persisted_disabled() -> set[str]:
    """Signals disabled by a persisted (cross-run) trip. Read once per process."""
    global _PERSISTED_SYNCED, _PERSISTED_DISABLED
    with _BREAKER_LOCK:
        if _PERSISTED_SYNCED:
            return set(_PERSISTED_DISABLED)
    try:
        from core.quota_governor import persisted_disabled_signals

        names = set(persisted_disabled_signals())
    except Exception:
        names = set()
    with _BREAKER_LOCK:
        _PERSISTED_SYNCED = True
        _PERSISTED_DISABLED = names
    if names:
        logger.info("Signals skipped from persisted state: %s", ", ".join(sorted(names)))
    return set(names)


def _disabled_signals() -> set[str]:
    if not _breaker_enabled():
        return set()
    persisted = _persisted_disabled()
    now = time.time()
    with _BREAKER_LOCK:
        for sig in [n for n, until in _COOLDOWN_UNTIL.items() if until <= now]:
            del _COOLDOWN_UNTIL[sig]
        return set(_SESSION_DISABLED) | set(_COOLDOWN_UNTIL) | persisted


def reset_session_breaker() -> None:
    """Clear session-disabled signals, cooldowns, and persisted signal records
    (test/CLI helper — gives every signal another chance right now)."""
    global _PERSISTED_SYNCED, _PERSISTED_DISABLED
    with _BREAKER_LOCK:
        _SESSION_DISABLED.clear()
        _COOLDOWN_UNTIL.clear()
        _PERSISTED_DISABLED = set()
        _PERSISTED_SYNCED = False
    try:
        from core.quota_governor import clear_all_signals

        clear_all_signals()
    except Exception:
        pass


def disabled_signals() -> set[str]:
    """Signals disabled this session by the breaker (public view for the dashboard)."""
    return _disabled_signals()


def signal_cooldowns() -> dict[str, float]:
    """Active rate-limit cooldowns: signal name -> unix ts when it becomes available.

    Public view for dashboards (ops reliability, signal health) — expired entries
    are purged, so an empty dict means nothing is cooling down.
    """
    if not _breaker_enabled():
        return {}
    now = time.time()
    with _BREAKER_LOCK:
        for sig in [n for n, until in _COOLDOWN_UNTIL.items() if until <= now]:
            del _COOLDOWN_UNTIL[sig]
        return dict(_COOLDOWN_UNTIL)


# Signals reused (pinned) from the base-topic fetch during per-variant scoring,
# instead of being re-fetched for each of the 5 variants. Variants are editorial
# angles on the SAME topic, so signal *data* barely differs between them — and
# composite_score still re-scores each variant's text against the pinned data, so
# per-variant differentiation survives (youtube was always pinned yet scored
# 20-100 across variants). Re-fetching the rest cost 150-185s of variant scoring
# per run, 5x the Tavily/web-search spend, and Wikipedia 429 cooldowns. Default:
# pin everything; env-override to re-fetch specific signals per variant.
_VARIANT_REUSE_DEFAULT = (
    "youtube,reddit,twitter,tiktok_trends,youtube_competitors,"
    "web_search,wikipedia,trends,news,blog_rss,twitch,rawg,steam,igdb,"
    "trendingnow,autocomplete"
)


def _variant_reuse() -> tuple[str, ...]:
    """Signals pinned during variant scoring (read per-call so env/tests apply)."""
    return tuple(
        s.strip().lower()
        for s in os.getenv("VARIANT_REUSE_SIGNALS", _VARIANT_REUSE_DEFAULT).split(",")
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
    "finance": {"fred", "sec_edgar", "finnhub", "coingecko", "earnings"},
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
    skip = _skip_signals()
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
    skip = _skip_signals()
    for sub in subtopics:
        for name in FANOUT_SIGNAL_NAMES:
            if name not in registry or name in skip or name in disabled:
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
        for name in _variant_reuse():
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
