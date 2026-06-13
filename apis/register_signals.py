import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from apis.cache_manager import build_key, get_cached, set_cache
from apis.live_scores_api import live_scores_cache_ttl
from apis.signal_contract import normalize_signal
from apis.signals_bootstrap import get_signal_registry
from apis.youtube_api import start_youtube_warmup_background

_SKIP = {s.strip().lower() for s in os.getenv("CONTENT_SKIP_SIGNALS", "").split(",") if s.strip()}

_VARIANT_REUSE = tuple(
    s.strip().lower() for s in os.getenv("VARIANT_REUSE_SIGNALS", "youtube").split(",") if s.strip()
)


def _youtube_cache_ttl():
    try:
        return int(os.getenv("YOUTUBE_CACHE_TTL_SECONDS", str(6 * 60 * 60)))
    except ValueError:
        return 6 * 60 * 60


def _active_signal_sources():
    registry = get_signal_registry().get_registered_signals()
    pairs = tuple(registry.items())
    if not _SKIP:
        return pairs
    return tuple(pair for pair in pairs if pair[0] not in _SKIP)


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
    return None


def _fetch_one(name, func, topic, pinned: dict[str, Any] | None = None):
    if pinned and name in pinned and pinned[name]:
        return name, normalize_signal(pinned[name])

    key = build_key(name, topic)
    cached = get_cached(key)
    if cached is not None:
        return name, normalize_signal(cached)

    result = normalize_signal(func(topic))
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
    for sub in subtopics:
        for name in FANOUT_SIGNAL_NAMES:
            if name not in registry or name in _SKIP:
                continue
            _, sub_sig = _fetch_one(name, registry[name], sub, None)
            results[name] = _merge_signal(results.get(name), sub_sig)

    return results


def build_registry(
    topic,
    max_workers=None,
    *,
    reuse_signals: dict[str, Any] | None = None,
):
    """
    Fetch all signals in parallel. Results are cached per signal + topic.

    reuse_signals: pin signals from a prior fetch (e.g. base-topic YouTube during
    variant scoring) to avoid duplicate slow API calls.
    """
    start_youtube_warmup_background()

    sources = _active_signal_sources()
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
