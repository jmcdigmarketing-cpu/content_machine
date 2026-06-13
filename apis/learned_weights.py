"""
Build signal weight profiles from real channel performance (TapIn seed + analytics).
"""

from __future__ import annotations

from collections import defaultdict

from storage.repositories.performance_memory import get_performance_memory_repository

# Same keys as register_signals / topic_scorer
SIGNAL_KEYS = (
    "youtube",
    "trends",
    "news",
    "wikipedia",
    "blog_rss",
    "sports",
    "live_scores",
    "odds",
    "rawg",
    "steam",
    "autocomplete",
    "ufc_context",
    "tapology",
    "stats_context",
    "api_sports",
    "twitch",
    "igdb",
    "trendingnow",
    "fred",
    "sec_edgar",
    "finnhub",
    "coingecko",
    "anime",
    "tmdb",
    "tvmaze",
    "lastfm",
    "musicbrainz",
)

_DOMAIN_PROFILES = {
    "gaming": {
        "youtube": 0.24,
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
        "youtube": 0.3,
        "trends": 0.08,
        "news": 0.1,
        "blog_rss": 0.18,
        "sports": 0.02,
        "live_scores": 0.0,
        "odds": 0.18,
        "ufc_context": 0.12,
        "tapology": 0.04,
        "rawg": 0.0,
        "steam": 0.0,
        "autocomplete": 0.1,
    },
    "nba": {
        "youtube": 0.35,
        "trends": 0.1,
        "news": 0.15,
        "wikipedia": 0.06,
        "blog_rss": 0.08,
        "stats_context": 0.12,
        "sports": 0.05,
        "live_scores": 0.05,
        "odds": 0.05,
        "rawg": 0.0,
        "steam": 0.0,
        "autocomplete": 0.1,
    },
    "nfl": {
        "youtube": 0.4,
        "trends": 0.1,
        "news": 0.15,
        "wikipedia": 0.06,
        "blog_rss": 0.08,
        "stats_context": 0.12,
        "sports": 0.05,
        "live_scores": 0.05,
        "odds": 0.05,
        "rawg": 0.0,
        "steam": 0.0,
        "autocomplete": 0.1,
    },
    "neutral": {
        "youtube": 0.35,
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
}


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total > 0 and abs(total - 1.0) > 0.01:
        return {k: v / total for k, v in weights.items()}
    return dict(weights)


def _is_outcome_entry(entry: dict) -> bool:
    if entry.get("source") == "proxy":
        return False
    if "engaged_rate" in entry:
        return True
    if entry.get("source") in ("tapin_seed", "youtube_analytics"):
        return entry.get("alignment_score") is not None
    return False


def compute_profile_from_performance(
    channel_id: str,
    min_entries: int = 8,
) -> dict[str, float] | None:
    """
    Derive a signal weight profile from performance memory when enough outcome
    data exists. Returns None when entries are below min_entries.
    """
    repo = get_performance_memory_repository()
    entries = [e for e in repo.load_all(channel_id) if _is_outcome_entry(e)]
    if len(entries) < min_entries:
        return None

    domain_counts: dict[str, int] = defaultdict(int)
    for entry in entries:
        domain = str(entry.get("domain") or "neutral").strip().lower()
        domain_counts[domain] += 1

    best_domain = max(domain_counts, key=domain_counts.get)
    profile = dict(_DOMAIN_PROFILES.get(best_domain, _DOMAIN_PROFILES["neutral"]))
    return _normalize_weights(profile)
