# Signals, zeros, and how to expand sources

> **Class:** reference · **Status:** living · **Reviewed:** 2026-09-26

## What "(zero)" means in the CLI

The **Signal breakdown** line lists APIs whose **score is 0** for that variant. It is not the same as "API broken."

| Health line | Score in breakdown | Counts in composite score? |
|-------------|-------------------|----------------------------|
| `ON` + score 50+ | Shown as `Sports: 50` | Yes |
| `ON (not active)` | Listed under `(zero)` | No — `active=false` |
| `QUOTA EXCEEDED` | Usually `(zero)` | No |
| `OFF (no API key)` | `(zero)` | No |
| `AUTH FAILED` | `(zero)` | No |

Composite score only uses signals that are **`connected` + `active`** with a positive weight for your channel domain (gaming, UFC, etc.).

A signal that is wired but returns nothing on every run is a cost, not a zero: across the
38 recorded runs to 2026-09-20, `trendingnow`, `igdb`, `steam`, `tapology`, `stats_context`,
`tvmaze` and `tmdb` returned nothing inside a 58.7 s median discovery
([engine_upgrades.md](engine_upgrades.md); #810/#811 stopped spending threads on them).

---

## Stats & blogs

| Signal | What it does |
|--------|----------------|
| **stats_context** | BALLDONTLIE API (preferred) → Basketball Reference + PFR + ESPN JSON for NBA/NFL topics |
| **blog_rss** | Extra niche RSS from `config/data_sources.json` + channel SEO feeds |

Full guide: **[data_sources.md](data_sources.md)**.

---

## Expand data sources (`.env`)

```env
# Gaming discovery (high value for TapIn)
RAWG_API_KEY=
NEWS_API_KEY=
STEAM_API_KEY=          # optional; Steam store search works without key

# Trends (provider chain — Wikipedia works without keys)
# TRENDS_PROVIDER_ORDER=serpapi,glimpse,wikipedia
SERPAPI_KEY=
BALLDONTLIE_API_KEY=

# YouTube signal search (not upload OAuth)
YOUTUBE_API_KEY=
YOUTUBE_LIGHTWEIGHT=true
YOUTUBE_MAX_RESULTS=5

# Sports (only for team/league topics — skip for pure gaming)
# SPORTSDB_API_KEY=
# CONTENT_SKIP_SIGNALS=sports,odds,live_scores

# Speed: skip slow sources
# CONTENT_SKIP_SIGNALS=trends,tapology

# Competitor uploads: free RSS (no quota)
# COMPETITOR_SYNC_RSS=true
```

Run `py -m scripts.ops daily-sync --channel tapin` for competitor + SEO hints.

---

## Multi-game topics (fanout)

For topics like:

`State of Gaming 2026. Marvel Rivals, terraria, cod, subnautica 2`

the pipeline now **splits on commas / "and"** and re-queries **Steam, RAWG, autocomplete, and trends** per game name, keeping the **best** score per signal.

Stock/local background search uses the **first game name** (e.g. `Marvel Rivals`) instead of the full paragraph.

Disable fanout:

```env
TOPIC_FANOUT_ENABLED=false
```

---

## Expand clip / background sources

| Source | Config | Action |
|--------|--------|--------|
| **Local gameplay** | `video/backgrounds/gaming/` | Add more vertical `.mp4` clips (best for TapIn hybrid) |
| **Pexels** | `PEXELS_API_KEY` | Stock B-roll |
| **Pixabay** | `PIXABAY_API_KEY` | Stock fallback |
| **Hybrid ratio** | `channels.json` → `hybrid_local_ratio` | More local vs stock (TapIn 0.70, MoneyWise 0.45 — decisions §26: more unrelated stock is not a quality lever) |
| **Order** | `asset_provider_order` | e.g. `["local","pexels","pixabay"]` |

Use a **specific game name** in the topic for better Pexels/Pixabay matches.

---
