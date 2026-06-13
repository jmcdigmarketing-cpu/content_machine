import os

from apis.learned_weights import compute_profile_from_performance
from config.channels import get_channel_profile, resolve_channel_id
from storage.repositories.channel_memory import get_channel_memory_repository
from storage.repositories.performance_memory import get_performance_memory_repository

# Blend heuristic profiles with engagement-derived templates when outcome data exists
_LEARNED_BLEND = float(os.getenv("LEARNED_WEIGHT_BLEND", "0.85"))

# TapIn-aligned templates (engagement-first, suppress sports rankings)
_LEARNED_PROFILES = {
    "gaming": {
        "youtube": 0.22,
        "twitch": 0.14,
        "igdb": 0.1,
        "trendingnow": 0.08,
        "trends": 0.06,
        "news": 0.04,
        "wikipedia": 0.06,
        "blog_rss": 0.14,
        "sports": 0.0,
        "live_scores": 0.0,
        "odds": 0.04,
        "stats_context": 0.0,
        "rawg": 0.14,
        "steam": 0.08,
        "autocomplete": 0.04,
    },
    "finance": {
        "youtube": 0.18,
        "finnhub": 0.22,
        "fred": 0.12,
        "sec_edgar": 0.08,
        "coingecko": 0.08,
        "trends": 0.1,
        "wikipedia": 0.08,
        "blog_rss": 0.1,
        "news": 0.04,
    },
    "anime": {
        "youtube": 0.22,
        "anime": 0.28,
        "blog_rss": 0.18,
        "wikipedia": 0.12,
        "trends": 0.08,
        "news": 0.04,
        "autocomplete": 0.04,
    },
    "popculture": {
        "youtube": 0.22,
        "tmdb": 0.28,
        "blog_rss": 0.14,
        "wikipedia": 0.12,
        "tvmaze": 0.1,
        "trends": 0.08,
        "news": 0.04,
    },
    "music": {
        "youtube": 0.28,
        "lastfm": 0.22,
        "musicbrainz": 0.12,
        "blog_rss": 0.12,
        "wikipedia": 0.1,
        "trends": 0.08,
        "autocomplete": 0.04,
    },
    "ufc": {
        "youtube": 0.22,
        "tapology": 0.18,
        "ufc_context": 0.12,
        "blog_rss": 0.16,
        "trends": 0.06,
        "news": 0.09,
        "wikipedia": 0.05,
        "sports": 0.02,
        "live_scores": 0.0,
        "odds": 0.1,
        "stats_context": 0.0,
        "rawg": 0.0,
        "steam": 0.0,
        "autocomplete": 0.08,
    },
    "neutral": {
        "youtube": 0.33,
        "trends": 0.1,
        "news": 0.1,
        "wikipedia": 0.1,
        "blog_rss": 0.12,
        "sports": 0.05,
        "live_scores": 0.0,
        "odds": 0.05,
        "rawg": 0.1,
        "steam": 0.05,
        "autocomplete": 0.05,
    },
    "nba": {
        "youtube": 0.26,
        "trends": 0.08,
        "news": 0.09,
        "wikipedia": 0.06,
        "blog_rss": 0.08,
        "stats_context": 0.14,
        "api_sports": 0.04,
        "sports": 0.04,
        "live_scores": 0.08,
        "odds": 0.05,
        "rawg": 0.0,
        "steam": 0.0,
        "autocomplete": 0.08,
    },
    "nfl": {
        "youtube": 0.28,
        "trends": 0.08,
        "news": 0.1,
        "wikipedia": 0.06,
        "blog_rss": 0.08,
        "stats_context": 0.16,
        "api_sports": 0.04,
        "sports": 0.04,
        "live_scores": 0.05,
        "odds": 0.05,
        "rawg": 0.0,
        "steam": 0.0,
        "autocomplete": 0.08,
    },
}


def infer_domain(topic, channel_id=None):
    topic_lower = (topic or "").lower()

    if any(
        word in topic_lower for word in ["nba", "draft", "wembanyama", "finals", "knicks", "spurs"]
    ):
        return "nba"

    if any(
        word in topic_lower
        for word in [
            "nfl",
            "super bowl",
            "quarterback",
            "herbert",
            "chargers",
            "mahomes",
            "chiefs",
        ]
    ):
        return "nfl"

    if any(word in topic_lower for word in ["ufc", "fight", "boxing", "mma"]):
        return "ufc"

    if any(
        word in topic_lower
        for word in [
            "stock",
            "stocks",
            "earnings",
            "fed ",
            "fomc",
            "cpi",
            "inflation",
            "bitcoin",
            "btc",
            "crypto",
            "nasdaq",
            "s&p",
            "dividend",
            "portfolio",
            "ticker",
            "sec filing",
            "treasury",
        ]
    ):
        return "finance"

    if any(
        word in topic_lower
        for word in [
            "anime",
            "manga",
            "crunchyroll",
            "one piece",
            "naruto",
            "demon slayer",
            "studio ghibli",
            "anilist",
            "shonen",
            "isekai",
        ]
    ):
        return "anime"

    if any(
        word in topic_lower
        for word in [
            "album",
            "song",
            "rapper",
            "grammy",
            "billboard",
            "lyrics",
            "soundtrack",
            "music video",
            "tour dates",
        ]
    ):
        return "music"

    if (
        any(
            word in topic_lower
            for word in [
                "movie",
                "film",
                "trailer",
                "netflix",
                "disney+",
                "celebrity",
                "oscar",
                "box office",
                "tv show",
                "star wars",
                "marvel movie",
                "dc universe",
            ]
        )
        and "marvel rivals" not in topic_lower
    ):
        return "popculture"

    if any(
        word in topic_lower
        for word in [
            "gta",
            "gaming",
            "game",
            "steam",
            "roblox",
            "marvel rivals",
            "esports",
        ]
    ):
        return "gaming"

    profile = get_channel_profile(channel_id)
    if profile.domain and profile.domain != "neutral":
        return profile.domain

    return "neutral"


def get_default_weights(domain):
    if domain in _LEARNED_PROFILES:
        return dict(_LEARNED_PROFILES[domain])
    return dict(_LEARNED_PROFILES["neutral"])


def _normalize_weights(weights: dict) -> dict:
    total = sum(weights.values())
    if total > 0 and abs(total - 1.0) > 0.01:
        return {k: v / total for k, v in weights.items()}
    return weights


def _blend_weights(heuristic: dict, learned: dict) -> dict:
    keys = set(heuristic) | set(learned)
    blended = {
        k: _LEARNED_BLEND * learned.get(k, 0) + (1 - _LEARNED_BLEND) * heuristic.get(k, 0)
        for k in keys
    }
    return _normalize_weights(blended)


def _engagement_adjusted_profile(domain: str, channel_id: str) -> dict[str, float] | None:
    learned = compute_profile_from_performance(channel_id)
    if learned:
        factor = get_performance_memory_repository().get_domain_average(domain, channel_id)
        if factor > 1.1 and domain in ("gaming", "ufc"):
            learned["rawg"] = min(learned.get("rawg", 0) + 0.03, 0.28)
            learned["twitch"] = min(learned.get("twitch", 0) + 0.03, 0.2)
            learned["blog_rss"] = min(learned.get("blog_rss", 0) + 0.03, 0.22)
        if factor > 1.1 and domain == "anime":
            learned["anime"] = min(learned.get("anime", 0) + 0.04, 0.35)
        return learned

    perf = get_performance_memory_repository()
    if not perf.has_outcome_data(channel_id):
        return None

    domains = list(_LEARNED_PROFILES.keys())
    engagement = {d: perf.get_domain_engagement_average(d, channel_id) for d in domains}
    if not any(engagement.values()):
        return None

    best_domain = max(engagement, key=engagement.get)
    base = dict(_LEARNED_PROFILES.get(best_domain, _LEARNED_PROFILES["neutral"]))

    factor = perf.get_domain_average(domain, channel_id)
    if factor < 0.75 and domain in ("nba", "nfl"):
        base["sports"] = 0.0
        base["live_scores"] = 0.0
    if factor > 1.1 and domain in ("gaming", "ufc"):
        base["rawg"] = min(base.get("rawg", 0) + 0.05, 0.25)
        base["twitch"] = min(base.get("twitch", 0) + 0.04, 0.18)
        base["blog_rss"] = min(base.get("blog_rss", 0) + 0.05, 0.22)
    if factor > 1.1 and domain == "anime":
        base["anime"] = min(base.get("anime", 0) + 0.05, 0.32)

    return _normalize_weights(base)


def get_weights(domain, channel_id=None):
    channel_id = resolve_channel_id(channel_id)
    perf = get_performance_memory_repository()
    heuristic = dict(get_default_weights(domain))
    learned = _engagement_adjusted_profile(domain, channel_id)
    weights = _blend_weights(heuristic, learned) if learned else heuristic

    # Static channels.json overrides apply only until real outcome data exists
    use_static_overrides = os.getenv("LEARNED_USE_CHANNEL_OVERRIDES", "").lower() in (
        "1",
        "true",
        "yes",
    )
    if not perf.has_outcome_data(channel_id) or use_static_overrides:
        overrides = get_channel_profile(channel_id).weight_overrides
        for key, value in overrides.items():
            if key in weights:
                weights[key] = float(value)
    return _normalize_weights(weights)


def composite_score(signals, topic, channel_id=None):
    from apis.signal_corroboration import assess_corroboration, corroboration_score_adjustment

    channel_id = resolve_channel_id(channel_id)
    domain = infer_domain(topic, channel_id)
    weights = get_weights(domain, channel_id)

    weighted_total = 0
    total_weight = 0
    active_signals = 0

    for key, weight in weights.items():
        signal = signals.get(key)

        if not signal:
            continue

        if not signal.get("connected"):
            continue

        if not signal.get("active"):
            continue

        score = max(0, min(signal.get("score", 0), 100))

        weighted_total += score * weight
        total_weight += weight
        active_signals += 1

    if total_weight == 0:
        return 0

    final_score = weighted_total / total_weight

    if active_signals == 1:
        final_score *= 0.75

    memory = get_channel_memory_repository()
    boost = memory.get_historical_boost(topic, channel_id)
    perf = get_performance_memory_repository()
    domain_factor = perf.get_domain_average(domain, channel_id)
    final_score = final_score * (0.7 + 0.3 * domain_factor) + boost
    final_score = corroboration_score_adjustment(final_score, assess_corroboration(signals))

    return round(min(final_score, 100), 2)
