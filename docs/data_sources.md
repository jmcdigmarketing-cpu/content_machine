# Data sources — stats, blogs, APIs

> **Class:** reference · **Status:** living · **Reviewed:** 2026-09-20

Content Machine pulls research from **API signals** (variant scoring), **reference scrapers** (stats lines), **RSS/blog feeds** (headlines), and the **research brief** (LLM synthesis after variant pick).

---

## API key status

Last verified: 2026-06-10

### ✅ Configured

| Key | Service | Notes |
|-----|---------|-------|
| `OPENAI_API_KEY` | OpenAI GPT-4o | Script gen, research briefs, fact extraction |
| `ELEVEN_API_KEY` | ElevenLabs | TTS audio |
| `YOUTUBE_API_KEY` | YouTube Data API v3 | Signal discovery, competitor titles, video descriptions |
| `YOUTUBE_CLIENT_ID` | YouTube OAuth | Upload-side identity (token file separate — see OAuth section) |
| `FLUX_API_KEY` | Black Forest Labs | AI thumbnail generation |
| `ANTHROPIC_API_KEY` | Claude API | Alternative LLM for fact enrichment (`RESEARCH_ENRICH_PROVIDER=anthropic`) |
| `NEWS_API_KEY` | NewsAPI.org | News headlines signal |
| `STEAM_API_KEY` | Steam Web API | Steam game signals |
| `RAWG_API_KEY` | RAWG.io | Game database facts, ratings, tags |
| `ODDS_API_KEY` | The Odds API | Betting odds signal |
| `SPORTSDB_API_KEY` | TheSportsDB | Sports teams (`123` = free tier) |
| `BALLDONTLIE_API_KEY` | BallDontLie | NBA/NFL stats (preferred over scrapers) |
| `API_SPORTS_KEY` | API-Sports.io | Multi-sport stats — NFL, soccer, etc. |
| `SERPAPI_KEY` | SerpApi | Google Trends data (best trends provider) |
| `FINNHUB_API_KEY` | Finnhub | Stock market signal |
| `FRED_API_KEY` | FRED (St. Louis Fed) | Economic data signal |
| `LASTFM_API_KEY` | Last.fm | Music trending signal |
| `LASTFM_SHARED_SECRET` | Last.fm | Paired with API key |
| `TMDB_API_KEY` | TMDB | Movie/TV metadata |
| `TMDB_API_TOKEN` | TMDB Bearer token | Read-access JWT (alternative to key) |
| `TWITCH_CLIENT_ID` | Twitch Dev | Live stream counts |
| `TWITCH_CLIENT_SECRET` | Twitch Dev | Paired with Client ID |
| `IGDB_CLIENT_ID` | IGDB (via Twitch) | Game database — **same value as TWITCH_CLIENT_ID** |
| `IGDB_CLIENT_SECRET` | IGDB (via Twitch) | **Same value as TWITCH_CLIENT_SECRET** |
| `PEXELS_API_KEY` | Pexels | Stock video backgrounds |
| `PIXABAY_API_KEY` | Pixabay | Stock video backgrounds (fallback) |
| `DATABASE_URL` | PostgreSQL | All persistence (content runs, publish log, jobs) |
| `TIKTOK_CLIENT_KEY` | TikTok | Platform keys present — publish flow not yet shipped |
| `TIKTOK_CLIENT_SECRET` | TikTok | Paired with Client Key |

### ❌ Still empty

| Key | Service | Priority for TapIn | Get it at |
|-----|---------|-------------------|-----------|
| `GLIMPSE_API_KEY` | Glimpse | Low (SerpApi already active) | [meetglimpse.com/api](https://meetglimpse.com/api/) |
| `META_APP_ID` | Meta / Instagram | Deferred — platform not shipped | Meta Developer Portal |
| `META_APP_SECRET` | Meta / Instagram | Deferred | Meta Developer Portal |
| `INSTAGRAM_ACCOUNT_ID` | Instagram | Deferred | Meta Developer Portal |
| `INSTAGRAM_OAUTH_TOKEN_FILE` | Instagram OAuth | Deferred | — |

---

## Signal map

| Signal | Type | When active | Config |
|--------|------|-------------|--------|
| `youtube` | YouTube Data API v3 | Always (key set) — titles + descriptions now fetched | `YOUTUBE_API_KEY` |
| `stats_context` | BallDontLie → scrapers | NBA/NFL/MMA topic with player/team names | `BALLDONTLIE_API_KEY`, `STATS_PROVIDER_ORDER` |
| `trends` | SerpApi → Glimpse → Wikipedia | Interest / trajectory proxy | `TRENDS_PROVIDER_ORDER=serpapi,glimpse,wikipedia` |
| `blog_rss` | RSS | Headlines from merged feeds | `config/data_sources.json` + `config/seo/{channel}.json` |
| `news` | NewsAPI | Key set | `NEWS_API_KEY` |
| `rawg` | RAWG.io | Gaming topics | `RAWG_API_KEY` |
| `steam` | Steam Web API | Gaming topics | `STEAM_API_KEY` |
| `igdb` | IGDB via Twitch OAuth | Gaming topics — game metadata, genres | `IGDB_CLIENT_ID`, `IGDB_CLIENT_SECRET` |
| `twitch` | Twitch API | Gaming topics — live viewer counts | `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET` |
| `tmdb` | TMDB | Movie/TV topics | `TMDB_API_KEY` |
| `lastfm` | Last.fm | Music topics | `LASTFM_API_KEY` |
| `finnhub` | Finnhub | Finance/stock topics | `FINNHUB_API_KEY` |
| `fred` | FRED | Economic/finance topics | `FRED_API_KEY` |
| `live_scores` | ESPN API | NBA topics with scoreboard match | — (no key needed) |
| `tapology` | HTML scrape (**retired**) | — | Cloudflare 403 since ~2026-07; leave off. Fighter facts come from API-SPORTS MMA via `ufc_context` |
| `wikipedia` | Wikimedia pageviews REST | Free trends fallback | No key — always on |
| `odds` | The Odds API | Sports betting angle | `ODDS_API_KEY` |
| `youtube_competitors` | Apify YouTube scraper | Competitor performance — top videos by view velocity (views/day) | `APIFY_CONTENT_MACHINE_KEY` |
| `twitter` | Apify tweet scraper (**retired**) | — | Retired 2026-08-14: `inactive` on 19/19 run traces, never produced a fact, while being the slowest signal (~32s) and billing an actor run each time. The actor returns `{"noResults": true}` sentinels — X search needs auth now |
| `reddit` | Apify reddit scraper (**retired**) | — | Retired 2026-08-14: actor failed on every live run while still billing; the free OAuth backend needs `REDDIT_CLIENT_ID`/`SECRET`, unset |
| `tiktok_trends` | Apify TikTok scraper | Viral content discovery — trending angles + hashtags | `APIFY_BENABLE_BOT` (primary), `APIFY_CONTENT_MACHINE_KEY` (fallback) |
| `youtube_comments` | **YouTube Data API** (not Apify) | Unanswered audience questions on a topic's top videos — the content gaps competitors left, plus audience vocabulary | `YOUTUBE_API_KEY` (~103 units/topic; the catalog's Apify actor is deliberately unused) |
| `mma_stats` | API-SPORTS MMA host | Fighter records + physicals (replaced the Tapology scrape) | `API_SPORTS_KEY` — free tier 10 req/min, 100/day; `/fights` gated to 2022–2024, so **no upcoming cards** |

Apify data layer detail: [apify_data_sources.md](apify_data_sources.md) · catalog: `config/apify_sources.json`

Scoring weights per domain: `apis/topic_scorer.py` (`nba`, `nfl`, `ufc`, `gaming`).

**Add a source:** [adding_a_data_source.md](adding_a_data_source.md)

---

## Gaming RSS feeds (domain_rss.gaming)

All active in `config/data_sources.json`:

| Feed | URL |
|------|-----|
| Kotaku | https://kotaku.com/rss |
| PC Gamer | https://www.pcgamer.com/rss/ |
| Rock Paper Shotgun | https://www.rockpapershotgun.com/feed |
| Dot Esports | https://dotesports.com/feed |
| IGN Games | https://feeds.ign.com/ign/games |
| Game Rant | https://gamerant.com/feed/ |

---

## YouTube OAuth (upload)

OAuth token is **separate** from the API key. The `YOUTUBE_CLIENT_ID` in `.env` is the Data API identity — upload requires a full OAuth token file.

```powershell
# Generate / refresh token
py -m youtube.oauth_setup --channel tapin

# Verify upload is configured
py -m youtube.check_setup --channel tapin
```

Token lands at: `config/secrets/youtube_token_tapin.json`

Required scopes: `youtube.upload` + `youtube.readonly` (for analytics sync).

---

## Stats context (API first, scrapers fallback)

| Source | Module | Data |
|--------|--------|------|
| **BallDontLie** (preferred) | `apis/balldontlie_api.py` | Official NBA/NFL stats API |
| **Basketball Reference** | `apis/scrapers/basketball_reference.py` | Player/team search → per-game line |
| **Pro-Football-Reference** | `apis/scrapers/football_reference.py` | Same for NFL |
| **ESPN** | `apis/scrapers/espn_stats.py` | Public `site.api.espn.com` search |

Unified signal: `apis/stats_context_api.py` → `gather_stats_context(topic)`.

Cache: `data/scraper_cache/` (6h TTL).

**Topic tip:** Include player or team names (`Jokic triple-double`, `Myles Garrett Rams`). Vague topics stay inactive.

---

## Trends provider chain

```
SerpApi (active) → Glimpse (key empty, skipped) → Wikipedia pageviews (free fallback)
```

`TRENDS_PROVIDER_ORDER=serpapi,glimpse,wikipedia` is set. SerpApi is active — trends signal should now show real Google search interest rather than "stable pageview level".

---

## Blogs & niche RSS

Feeds merged in order:

1. `config/seo/{channel_id}.json` → `rss_feeds`
2. `config/data_sources.json` → `global_rss` + `domain_rss.{domain}`

Signal: `blog_rss` — scored by topic-matched headline count.
Brief path: `fetch_rss_context()` (same merged feed list, broader match).

---

## Gaming channel — recommended skip list

Finance, anime, and music signals add latency with zero value for TapIn:

```env
CONTENT_SKIP_SIGNALS=fred,sec_edgar,finnhub,coingecko,anime,tvmaze,lastfm,musicbrainz
```

Keep: `youtube`, `rawg`, `steam`, `igdb`, `twitch`, `blog_rss`, `news`, `trends`, `odds`, `ufc_context` (UFC), `sports`, `live_scores`.

> **Feed rot is silent.** Sources die without telling you — an audit on 2026-08-14 found
> 11 of ~37 configured feeds dead and one live feed lost to a parser bug, none of it
> reported. Run `py -m scripts.ops feeds` periodically (it's in `all-checks`); dead and
> stale feeds also surface in `ops reliability`.

---

## Operator checklist

1. **YouTube OAuth** — run `py -m youtube.oauth_setup --channel tapin` if not done yet
2. **IGDB/Twitch** — keys now filled; restart app to activate gaming signals
3. **SerpApi** — key filled; trends should now show real Google data
4. **TMDB + Last.fm** — keys filled; pop culture and music signals now active
5. Customize `config/data_sources.json` for new RSS outlets without code changes
6. For UFC: enable `TAPOLOGY_SCRAPE_ENABLED=true` for fight card data

See also: [signals_and_sources.md](signals_and_sources.md), [architecture.md](architecture.md).
