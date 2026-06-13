# Domain expansion playbook

How new verticals (finance, anime, pop culture, music, gaming depth, sports breadth) slot into Content Machine **without sprawl**. One domain at a time; each source follows the same recipe as gaming/UFC/NBA.

**Do not add all four content niches at once.** Each domain is a maintenance surface — pick by **data quality × audience × your edge**, then keep the load-bearing squares warm.

---

## The recipe (unchanged)

Every new vertical needs five touchpoints:

| Step | Where | What |
|------|--------|------|
| 1 | `apis/{source}_api.py` | Provider(s) returning `make_signal()`; use `apis/signal_chain.py` for fallbacks |
| 2 | `apis/signals_bootstrap.py` | `reg.register("signal_name", fn)` |
| 3 | `apis/topic_scorer.py` | `infer_domain()` keywords + `_LEARNED_PROFILES["domain"]` weights |
| 4 | `apis/learned_weights.py` | `_DOMAIN_PROFILES["domain"]` for performance-derived profiles |
| 5 | `config/data_sources.json` | `domain_rss.{domain}` feeds (community pulse — **not Reddit**) |

Optional: `config/channels.json` channel profile, `config/seo/{channel}.json` vocabulary, `core/script_brief.py` domain matrix.

See [adding-a-data-source.md](adding-a-data-source.md).

---

## Fragility hierarchy (pick load-bearing sources here)

```
bulk dataset / official API  →  REST API (keyed)  →  community wrapper  →  HTML scrape  →  unofficial scrape (yfinance, pytrends-class)
```

**Already in stack (cross-niche spine):**

| Signal | Tier | Notes |
|--------|------|--------|
| `wikipedia` | Official bulk | Leading indicator for any named entity |
| `trends` | Chain: SerpApi → Glimpse → Wikipedia | pytrends removed |
| `blog_rss` | Official RSS | Replaces Reddit for community headlines |
| `youtube` | Official API | Quota-heavy; competitor uploads → `analytics/youtube_rss.py` |
| `stats_context` | BALLDONTLIE → scrapers | Sports stats chain wired |

**High-leverage adds (work for every domain):**

| Source | Tier | Signal idea | Env |
|--------|------|-------------|-----|
| GDELT | Free bulk | News/events/tone at scale | none |
| SerpApi PAA / related | Paid/freemium | Content angles, not just scores | `SERPAPI_KEY` |
| Hacker News API | Free official | Tech/startup demand | none |
| Bluesky API | Free open | Emerging social (cheaper than X) | app password |
| Google News RSS | Free | Per-domain feeds in `data_sources.json` | none |

---

## Finance / stocks

**Your edge:** Bloomberg cert — macro literacy, earnings framing, SEC context.

### Load-bearing (official / free-robust)

| Source | Role | Signal name |
|--------|------|-------------|
| **FRED** | Macro series (rates, CPI, payrolls) | `fred_macro` |
| **SEC EDGAR** | Filings, 8-K, insider context | `sec_filings` |
| **CoinGecko** | Crypto prices + trending | `coingecko` |
| **Wikipedia** | Public interest on tickers/names | `wikipedia` (existing) |
| **Finnhub** (free tier) | News + sentiment + earnings calendar | `finnhub` |

### Keyed market data (verify current free tiers)

Alpha Vantage, Polygon.io, Twelve Data, Financial Modeling Prep — use **one** as primary via `signal_chain`, not all at once.

### Trend / demand for shorts

- Earnings calendar windows (Finnhub / FMP)
- Ticker news spikes + unusual volume (Finnhub)
- `trends` chain on ticker + company name
- `blog_rss`: Bloomberg, Reuters, MarketWatch, CoinDesk RSS

### Traps

| Avoid as spine | Why | Use instead |
|----------------|-----|-------------|
| **yfinance** | Unofficial Yahoo scrape — pytrends-for-stocks | Finnhub / Alpha Vantage / Polygon |
| Reddit WSB | Removed from stack; auth/hostile | Finnhub sentiment, `blog_rss`, Bluesky finance accounts |

### Starter weights sketch (`finance` domain)

High: `finnhub`, `fred_macro`, `news`, `trends`, `wikipedia`  
Mid: `sec_filings`, `blog_rss`, `youtube`  
Low: `coingecko` (unless crypto topic)

---

## Anime

**Your edge:** Authentic interest (Luffy mascot isn't accidental) — seasonal timing, discourse literacy.

### Load-bearing

| Source | Role | Signal name |
|--------|------|-------------|
| **AniList GraphQL** | Trending, scores, airing schedule, season calendar | `anilist` |
| **Wikipedia** | Spike detection on titles/characters | `wikipedia` (existing) |
| **blog_rss** | ANN, Crunchyroll news, r/anime **headlines via RSS mirrors** if needed | `blog_rss` |

### Secondary

| Source | Role | Trap level |
|--------|------|------------|
| Kitsu | Metadata backup | Low |
| MyAnimeList official API | Alt metadata | Medium (auth) |
| **Jikan** | MAL wrapper | **Unofficial** — fallback only, not spine |

### Trend / demand for shorts

- AniList trending + **airing this season** (content timing gold)
- Seasonal premiere calendar → `opportunity_window` inputs
- `trends` + Wikipedia on title/character names
- YouTube (reaction/clip demand)

### Traps

Prefer **AniList** over Jikan for anything load-bearing. Do not scrape MAL HTML.

### Starter weights sketch (`anime` domain)

High: `anilist`, `youtube`, `blog_rss`, `wikipedia`  
Mid: `trends`, `news`  
Low: `autocomplete`

---

## Pop culture (movies / TV / celebrity)

Large audience; less differentiated unless you pick a lane (box office vs streaming vs celebrity drama).

### Load-bearing

| Source | Role | Signal name |
|--------|------|-------------|
| **TMDB** | Trending, popularity, releases — crown jewel | `tmdb` |
| **Wikipedia** | Who/what is spiking | `wikipedia` (existing) |
| **TVmaze** | TV schedules | `tvmaze` |

### Secondary

Trakt (watch activity), Watchmode/JustWatch (streaming availability) — nice for brief facts, not required day one.

### Traps

| Avoid | Why | Use instead |
|-------|-----|-------------|
| Box Office Mojo scrape | Fragile HTML | TMDB + news RSS |
| IMDb scrape | No clean free API | TMDB; OMDb only as thin wrapper |
| Reddit r/movies | Removed | `blog_rss` + TMDB trending |

### Starter weights sketch (`popculture` domain)

High: `tmdb`, `youtube`, `wikipedia`, `blog_rss`  
Mid: `trends`, `tvmaze`  
Low: `news`

---

## Music

Read carefully — **Spotify API locked down (Feb 2026)** for new apps (audio features / analysis behind ~250k MAU gate). Treat Spotify as closed for a new indie tool.

### Load-bearing

| Source | Role | Signal name |
|--------|------|-------------|
| **MusicBrainz** | Open metadata, MBIDs | `musicbrainz` |
| **Last.fm** | Charts, tags, similar artists (genre workaround) | `lastfm` |
| **YouTube** | Where music virality shows up for shorts | `youtube` (existing) |
| **Wikipedia** | Artist/album interest spikes | `wikipedia` (existing) |

### Virality / charts (2026 reality)

- TikTok sound trends (Creative Center — manual or scrape; no stable free API)
- Shazam via RapidAPI (paid)
- Last.fm / Apple Music charts RSS
- Genius / Musixmatch for lyrics context (brief-only, not scorer)

### Traps

| Avoid as spine | Why |
|----------------|-----|
| Spotify Web API | Closed for new entrants |
| Chartmetric / Songstats | Paid; legacy Spotify access — rent, don't own |

### Starter weights sketch (`music` domain)

High: `lastfm`, `youtube`, `wikipedia`, `blog_rss`  
Mid: `trends`, `musicbrainz`  
Low: `news`

---

## Gaming (deepening existing domain)

You already have `rawg`, `steam`, `blog_rss`. Highest-ROI adds:

| Source | Tier | Signal idea |
|--------|------|-------------|
| **Twitch API** | Official OAuth | Live viewership by game — best real-time demand signal |
| **IGDB** + PopScore | Official (Twitch OAuth) | 24h popularity primitives |
| **TrendingNow.games** | Free JSON/RSS hourly | Cheap no-auth Steam trend feed |
| OpenCritic | Scrape/API | Review aggregate for brief |

Trap: SteamDB / SteamSpy — stats-derived, no official API; use as enrichment, not spine.

Esports: PandaScore / balldontlie esports tier when you add an `esports` sub-domain.

---

## Sports (deepening)

| Already wired | Next |
|---------------|------|
| `balldontlie` → scrapers chain | API-SPORTS (MMA + soccer + WebSocket) |
| `odds`, `live_scores` | Line movement as leading indicator |
| ESPN/SportsDB | **nflverse** / **pybaseball** for robust NFL/MLB stats |

**Biggest gap:** soccer — Football-Data.org / API-Football (largest global sports audience).

F1: Jolpica-F1 (Ergast successor). Cricket: Sportmonks free tier.

---

## Recommended order

| Priority | Domain | Why |
|----------|--------|-----|
| 1 | **Anime** or **Finance** | Anime = authentic grind; Finance = Bloomberg cert moat |
| 2 | Gaming depth (Twitch + IGDB) | Extends TapIn without new channel identity |
| 3 | Pop culture | Large but undifferentiated — needs a lane |
| 4 | Music | Spotify closure makes sourcing harder; YouTube + Last.fm first |

**Rule:** Ship one domain end-to-end (signals + weights + RSS + one channel in `channels.json`) before starting the next.

---

## First-domain checklist (copy per vertical)

- [ ] `infer_domain()` keywords + tests
- [ ] 2–4 load-bearing signals with `signal_chain` fallbacks
- [ ] `_LEARNED_PROFILES` + `_DOMAIN_PROFILES` weights (sum ≈ 1.0)
- [ ] `domain_rss` feeds in `data_sources.json`
- [ ] `.env.example` keys documented
- [ ] `CONTENT_SKIP_SIGNALS` doc for optional heavies
- [ ] One intelligence report smoke test with real topic string

---

## Related docs

- [data-sources.md](data-sources.md) — current signal map
- [adding-a-data-source.md](adding-a-data-source.md) — implementation steps
- [signals-and-sources.md](signals-and-sources.md) — zeros, quotas, env
- [roadmap.md](roadmap.md) — phase tracking
