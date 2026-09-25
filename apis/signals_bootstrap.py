"""Register all signal providers on SignalRegistry (single source of truth)."""

from apis.anime_api import get_anime_signal
from apis.api_registry import SignalRegistry
from apis.api_sports_api import get_api_sports_signal
from apis.autocomplete_api import get_autocomplete_data
from apis.blog_rss_api import get_blog_rss_signal
from apis.coingecko_api import get_coingecko_signal
from apis.earnings_signal import get_earnings_signal
from apis.finnhub_api import get_finnhub_signal
from apis.fred_api import get_fred_signal
from apis.igdb_api import get_igdb_signal
from apis.lastfm_api import get_lastfm_signal
from apis.live_scores_api import get_live_scores_signal
from apis.musicbrainz_api import get_musicbrainz_signal
from apis.news_api import get_news_score
from apis.odds_api import get_odds_data
from apis.rawg_api import get_rawg_signal
from apis.reddit_signal import get_reddit_signal
from apis.sec_edgar_api import get_sec_edgar_signal
from apis.sports_data_api import get_sports_data
from apis.stats_context_api import get_stats_context_signal
from apis.steam_api import get_steam_signal
from apis.tapology_api import get_tapology
from apis.tiktok_signal import get_tiktok_signal
from apis.tmdb_api import get_tmdb_signal
from apis.trendingnow_api import get_trendingnow_signal
from apis.trends_api import get_trend_score
from apis.tvmaze_api import get_tvmaze_signal
from apis.twitch_api import get_twitch_signal
from apis.twitter_signal import get_twitter_signal
from apis.ufc_context_api import get_ufc_context
from apis.web_search_api import get_web_search_signal
from apis.wikipedia_pageviews_api import get_wikipedia_pageviews_signal
from apis.youtube_api import search_youtube
from apis.youtube_apify_signal import get_youtube_apify_signal
from apis.youtube_comments_signal import get_youtube_comments_signal
from core.logging import get_logger

logger = get_logger("apis.signals_bootstrap")

_registry: SignalRegistry | None = None


# Retired signals — decisions §19: a source that produces nothing is switched off
# with the reason recorded here, and its module is kept for revival rather than
# deleted. §19's kill switch is `config/apify_sources.json`, which only covers paid
# actors; this is the same rule for a free signal, applied where free signals are
# registered. Deleting the entry below is all a revival needs.
RETIRED_SIGNALS: dict[str, str] = {
    "trendingnow": (
        "2026-08-29: trendingnow.games has failed to resolve on every run for weeks "
        "(run 74: HTTPSConnectionPool 'Max retries exceeded'). It contributed zero "
        "facts and cost a connection timeout per run. Module kept at "
        "apis/trendingnow_api.py."
    ),
    "tapology": (
        "2026-09-20: zero facts across every recorded run that called it (wave 25 "
        "measurement). Cloudflare 403 for 33 days in 2026-08 already documented in "
        "decisions.md §19; the scrape stays default-off. Module kept at "
        "apis/tapology_api.py."
    ),
    "stats_context": (
        "2026-09-20: zero facts across every recorded run that called it. Module "
        "kept at apis/stats_context_api.py."
    ),
    "tvmaze": (
        "2026-09-20: zero facts across every recorded run that called it. Module "
        "kept at apis/tvmaze_api.py."
    ),
    "tmdb": (
        "2026-09-20: zero facts across every recorded run that called it. Module "
        "kept at apis/tmdb_api.py."
    ),
}


def get_signal_registry() -> SignalRegistry:
    global _registry
    if _registry is not None:
        return _registry

    reg = SignalRegistry()
    # Core
    reg.register("youtube", search_youtube)
    reg.register("youtube_comments", get_youtube_comments_signal)
    reg.register("trends", get_trend_score)
    reg.register("news", get_news_score)
    reg.register("wikipedia", get_wikipedia_pageviews_signal)
    reg.register("blog_rss", get_blog_rss_signal)
    reg.register("web_search", get_web_search_signal)
    reg.register("autocomplete", get_autocomplete_data)
    # Sports
    reg.register("sports", get_sports_data)
    reg.register("live_scores", get_live_scores_signal)
    reg.register("odds", get_odds_data)
    reg.register("stats_context", get_stats_context_signal)
    reg.register("api_sports", get_api_sports_signal)
    reg.register("ufc_context", get_ufc_context)
    reg.register("tapology", get_tapology)
    # Gaming
    reg.register("rawg", get_rawg_signal)
    reg.register("steam", get_steam_signal)
    reg.register("twitch", get_twitch_signal)
    reg.register("igdb", get_igdb_signal)
    reg.register("trendingnow", get_trendingnow_signal)
    # Finance
    reg.register("fred", get_fred_signal)
    reg.register("sec_edgar", get_sec_edgar_signal)
    reg.register("finnhub", get_finnhub_signal)
    reg.register("coingecko", get_coingecko_signal)
    reg.register("earnings", get_earnings_signal)
    # Anime
    reg.register("anime", get_anime_signal)
    # Pop culture
    reg.register("tmdb", get_tmdb_signal)
    reg.register("tvmaze", get_tvmaze_signal)
    # Music
    reg.register("lastfm", get_lastfm_signal)
    reg.register("musicbrainz", get_musicbrainz_signal)
    # Social / community (Apify)
    reg.register("reddit", get_reddit_signal)
    reg.register("tiktok_trends", get_tiktok_signal)
    reg.register("twitter", get_twitter_signal)
    reg.register("youtube_competitors", get_youtube_apify_signal)

    for name, note in RETIRED_SIGNALS.items():
        if reg.unregister(name):
            logger.debug("signal %s is retired: %s", name, note)

    _registry = reg
    return _registry
