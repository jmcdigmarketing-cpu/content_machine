import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from typing import Any

from apis.cache_manager import build_key, get_cached, get_expired, record_stale_served, set_cache
from apis.live_scores_api import live_scores_cache_ttl
from apis.signal_contract import (
    STATUS_AUTH,
    STATUS_ERROR,
    STATUS_HTTP,
    STATUS_INACTIVE,
    STATUS_NO_KEY,
    STATUS_OK,
    STATUS_QUOTA,
    STATUS_RATE_LIMIT,
    STATUS_SKIPPED,
    STATUS_UNAVAILABLE,
    STATUS_UPSTREAM,
    make_signal,
    normalize_signal,
)
from apis.signals_bootstrap import get_signal_registry
from apis.youtube_api import start_youtube_warmup_background
from core.logging import get_logger

logger = get_logger("apis.register_signals")

# Franchise-anchor batch: reuse build_key/get_cached/set_cache (no second cache).
# Module-level so ThreadPoolExecutor workers in the same run_batch see it.
_franchise_batch_anchor: str | None = None
_franchise_batch_lock = threading.Lock()


@contextmanager
def franchise_batch_cache(topics: list[str], channel_id: str = "tapin"):
    """Share discovery cache keys across topics with the same dominant franchise."""
    del channel_id  # reserved: cache key is franchise-only, not channel-prefixed
    global _franchise_batch_anchor
    anchor = None
    try:
        from core.channel_context import dominant_anchor

        raw = dominant_anchor(topics or [])
        if raw:
            from core.channel_context import anchor_families

            fams = anchor_families(raw)
            anchor = sorted(fams)[0] if fams else str(raw).lower()
    except Exception as exc:
        logger.debug("franchise batch anchor skipped: %s", exc)
        anchor = None
    with _franchise_batch_lock:
        prev = _franchise_batch_anchor
        _franchise_batch_anchor = anchor
    try:
        yield
    finally:
        with _franchise_batch_lock:
            _franchise_batch_anchor = prev


def _cache_topic(name: str, topic: str) -> str:
    """Same signal + overlapping franchise inside run_batch → one paid fetch."""
    del name
    anchor = _franchise_batch_anchor
    if not anchor or not topic:
        return topic
    try:
        from core.channel_context import anchor_families

        fams = anchor_families(topic)
        if anchor in fams:
            return f"franchise:{anchor}"
    except Exception as exc:
        logger.debug("franchise cache topic skipped: %s", exc)
    return topic


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
_EMPTY_STREAK: dict[str, int] = {}  # consecutive empty-200 per signal (#394)
_EMPTY_QUARANTINE_N = 3
# Scraper-class signals only. An empty HTTP 200 is ambiguous -- it means "dead
# scraper" for a source that scrapes a page, and "no entity for this topic" for a
# lookup API. This is an ALLOWLIST, not a denylist, because the safe default is to
# never quarantine: rawg (apis/rawg_api.py:166), odds (odds_api.py:61) and sports
# (sports_data_api.py:76) all return connected+INACTIVE with NO status_detail when
# a topic is outside their domain, and a denylist disabled them after three
# off-domain topics in one batch -- costing the NEXT topic data they could answer.
_EMPTY_QUARANTINE_SIGNALS = frozenset({"tapology"})
# Domain-skip / kill-switch details — not an empty HTTP 200.
_EMPTY_SKIP_DETAIL = re.compile(
    r"disabled|not an |gated|skipped|no page",
    re.IGNORECASE,
)
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


def _is_empty_200_inactive(name: str, result: dict[str, Any]) -> bool:
    """Tapology-class 200+nothing, not a healthy topic-miss INACTIVE.

    ``STATUS_INACTIVE`` is the contract for a live source with no match (Wikipedia
    has no page; RAWG has no game for a UFC topic). Those must not session-disable.
    Empty-200 is: a scraper-class signal, connected, inactive, and no skip-detail.
    """
    if result.get("status") != STATUS_INACTIVE:
        return False
    if name not in _EMPTY_QUARANTINE_SIGNALS:
        return False
    if result.get("connected") is False:
        return False
    detail = str(result.get("status_detail") or "")
    return _EMPTY_SKIP_DETAIL.search(detail) is None


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
    if status == STATUS_OK:
        with _BREAKER_LOCK:
            _EMPTY_STREAK.pop(name, None)
    elif _is_empty_200_inactive(name, result):
        trip = False
        with _BREAKER_LOCK:
            n = _EMPTY_STREAK.get(name, 0) + 1
            _EMPTY_STREAK[name] = n
            if n >= _EMPTY_QUARANTINE_N and name not in _SESSION_DISABLED:
                _SESSION_DISABLED.add(name)
                trip = True
        if trip:
            logger.warning(
                "Circuit breaker: disabling signal '%s' for this session after "
                "%d empty/inactive responses (status=%s, detail=%s)",
                name,
                _EMPTY_QUARANTINE_N,
                status,
                result.get("status_detail") or "",
            )
        return
    elif status == STATUS_INACTIVE:
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
        from core.win_notify import notify_breaker

        notify_breaker(
            f"signal {name}",
            f"{status}: {result.get('status_detail') or ''}".strip(),
        )
    except Exception as exc:
        logger.debug("breaker toast skipped: %s", exc)
    try:
        from core.quota_governor import disable_signal

        detail = result.get("status_detail") or ""
        disable_signal(name, f"{status}: {detail}" if detail else str(status))
    except Exception as exc:
        # Persistence is an optimization, never load-bearing: the session breaker above
        # already disabled the signal. Losing this only costs a repeat probe next run.
        logger.debug("Cross-run persistence skipped for signal '%s': %s", name, exc)


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
        _EMPTY_STREAK.clear()
        _PERSISTED_DISABLED = set()
        _PERSISTED_SYNCED = False
    try:
        from core.quota_governor import clear_all_signals

        clear_all_signals()
    except Exception as exc:
        logger.debug("clear_all_signals skipped: %s", exc)


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
    "youtube,youtube_comments,reddit,twitter,tiktok_trends,youtube_competitors,"
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


# Signal name -> Apify catalog key, for signals whose data comes from a catalog actor.
# Lets `enabled: false` in config/apify_sources.json actually switch a signal off:
# apify_catalog.source_enabled() existed but had no callers, so the catalog's own
# kill-switch was dead config.
_CATALOG_KEY_FOR_SIGNAL = {
    "reddit": "reddit_community",
    "twitter": "twitter_breaking",
    "tiktok_trends": "tiktok_trends",
    "youtube_competitors": "youtube_competitors",
}


def _catalog_disabled_signals() -> set[str]:
    """Signals switched off via `enabled: false` in the Apify catalog. Fail-open."""
    try:
        from apis.apify_catalog import source_enabled

        return {name for name, key in _CATALOG_KEY_FOR_SIGNAL.items() if not source_enabled(key)}
    except Exception:
        return set()


def _active_signal_sources(topic: str = "", channel_id: str | None = None):
    registry = get_signal_registry().get_registered_signals()
    pairs = tuple(registry.items())
    skip = _skip_signals()
    skip |= _disabled_signals()
    skip |= _catalog_disabled_signals()
    if topic:
        skip |= _gated_signal_names(topic, channel_id)
        try:
            from core.vault_relevance import relevance_mode

            # Scored/shadow skip after non-web fetch (build_registry two-stage).
            if relevance_mode() not in ("shadow", "scored"):
                from core.web_search_skip import should_skip_web_search

                if should_skip_web_search(topic, channel_id):
                    skip.add("web_search")
        except Exception as exc:
            logger.debug("web_search density skip skipped: %s", exc)
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
    if name == "youtube_comments":
        # 6h — comment threads move slowly, and each miss costs ~103 YouTube units
        # (one search + one read per video) against the 10k/day budget.
        return 6 * 60 * 60
    if name == "twitter":
        return 90 * 60  # 1.5h — breaking news moves fastest
    if name == "web_search":
        return 90 * 60  # 1.5h — live facts move fast
    return None


_LIVE_FAILURE_STATUSES = frozenset(
    {
        STATUS_UNAVAILABLE,
        STATUS_ERROR,
        STATUS_AUTH,
        STATUS_RATE_LIMIT,
        STATUS_HTTP,
        STATUS_UPSTREAM,
        STATUS_QUOTA,
    }
)


def stale_cache_max_age_seconds() -> float | None:
    """48h default. 0/off restores pre-#389 (never serve expired)."""
    raw = (os.getenv("STALE_CACHE_MAX_AGE_HOURS", "48") or "48").strip().lower()
    if raw in ("", "0", "off", "false", "no"):
        return None
    try:
        hours = float(raw)
    except ValueError:
        return None
    if hours <= 0:
        return None
    return hours * 3600


def _is_live_failure(signal: dict[str, Any]) -> bool:
    return str(signal.get("status") or "") in _LIVE_FAILURE_STATUSES


def _stamp_stale(payload: dict[str, Any], age_seconds: float) -> dict[str, Any]:
    """Keep the facts; mark worse than fresh so the UI cannot treat it as a hit."""
    out = normalize_signal(payload)
    hours = age_seconds / 3600.0
    flag = f"STALE cache, age {hours:.1f}h"
    detail = str(out.get("status_detail") or "").strip()
    if detail.lower() in ("", "ok"):
        out["status_detail"] = flag
    else:
        out["status_detail"] = f"{detail}; {flag}"
    out["stale"] = True
    out["stale_age_hours"] = round(hours, 2)
    try:
        out["score"] = min(float(out.get("score") or 0), 0.0)
    except (TypeError, ValueError):
        out["score"] = 0.0
    return out


def _maybe_serve_stale(key: str) -> dict[str, Any] | None:
    ceiling = stale_cache_max_age_seconds()
    if ceiling is None:
        return None
    got = get_expired(key)
    if not got:
        return None
    data, age = got
    if age > ceiling:
        return None
    return _stamp_stale(data, age)


def _fetch_one(name, func, topic, pinned: dict[str, Any] | None = None):
    if pinned and name in pinned and pinned[name]:
        return name, normalize_signal(pinned[name])

    key = build_key(name, _cache_topic(name, topic))
    cached = get_cached(key)
    if cached is not None:
        return name, normalize_signal(cached)

    result = normalize_signal(func(topic))
    _record_signal_health(name, result)
    if _is_live_failure(result):
        stale = _maybe_serve_stale(key)
        if stale is not None:
            record_stale_served(key)
            logger.warning(
                "%s live fetch failed (%s); serving %s",
                name,
                result.get("status_detail") or result.get("status"),
                stale.get("status_detail"),
            )
            return name, stale
        set_cache(key, result, ttl_seconds=_cache_ttl_for(name))
        return name, result

    set_cache(key, result, ttl_seconds=_cache_ttl_for(name))
    return name, result


def _two_stage_web() -> bool:
    try:
        from core.vault_relevance import relevance_mode

        return relevance_mode() in ("shadow", "scored")
    except Exception:
        return False


def _maybe_fetch_web_search(
    topic: str,
    channel_id: str | None,
    func,
    non_web: dict[str, Any],
    pinned: dict[str, Any],
) -> dict[str, Any]:
    """Fetch web_search once, or emit STATUS_SKIPPED when vault coverage is enough."""
    if pinned.get("web_search"):
        return normalize_signal(pinned["web_search"])
    key = build_key("web_search", _cache_topic("web_search", topic))
    cached = get_cached(key)
    if cached is not None:
        return normalize_signal(cached)
    skip = False
    try:
        from core.web_search_skip import should_skip_web_search

        skip = should_skip_web_search(topic, channel_id, signals=non_web)
    except Exception as exc:
        logger.warning("web-search skip scoring failed; fetching web: %s", exc)
    if skip:
        skipped = make_signal(
            connected=True,
            active=False,
            status=STATUS_SKIPPED,
            status_detail="vault coverage sufficient; web_search not called",
        )
        set_cache(key, skipped, ttl_seconds=_cache_ttl_for("web_search"))
        return skipped
    _, result = _fetch_one("web_search", func, topic, pinned)
    return result


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


def _discovery_worker_cap(n_sources: int) -> int:
    """Cap concurrent signal fetches (candidate 41). 0/off = one worker per source."""
    if n_sources <= 0:
        return 1
    raw = os.getenv("DISCOVERY_MAX_WORKERS", "8").strip().lower()
    if raw in ("", "0", "off", "false", "no"):
        return n_sources
    try:
        cap = int(float(raw))
    except ValueError:
        return n_sources
    if cap <= 0:
        return n_sources
    return max(1, min(cap, n_sources))


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
    web_source = None
    if _two_stage_web():
        web_source = next(((name, func) for name, func in sources if name == "web_search"), None)
        sources = tuple((name, func) for name, func in sources if name != "web_search")
    workers = max_workers or _discovery_worker_cap(len(sources) + (1 if web_source else 0))
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

    if web_source is not None:
        results["web_search"] = _maybe_fetch_web_search(
            topic, channel_id, web_source[1], results, pinned
        )

    if _fanout_enabled() and not reuse_signals:
        results = _apply_topic_fanout(topic, results, sources)

    if os.getenv("USE_SIGNAL_SYNTHESIS", "").lower() in ("1", "true", "yes"):
        try:
            from apis.signal_synthesizer import synthesize_signals

            results["_synthesis"] = synthesize_signals(results)
        except Exception as exc:
            logger.debug("synthesize_signals skipped: %s", exc)

    return results
