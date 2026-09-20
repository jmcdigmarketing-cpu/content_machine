# Apify data layer — highest-value content & data

> **Class:** reference · **Status:** living · **Reviewed:** 2026-09-20

The Content Machine uses Apify to pull data that no free API exposes well:
real-time social signal, competitor performance, and breaking news. With the
upgraded plan, these run on every discovery pass for gaming/UFC topics.

**Catalog (single source of truth):** [`config/apify_sources.json`](../config/apify_sources.json)
Edit targets there — subreddits, Twitter authority accounts, actor input — with
no code changes. Loader: [`apis/apify_catalog.py`](../apis/apify_catalog.py).

**Credentials:**
- `APIFY_CONTENT_MACHINE_KEY` → all general actors (`key: "main"`)
- `APIFY_BENABLE_BOT` → TikTok actor (`key: "tiktok"`)

---

## What each source retrieves, ranked by value

### 1. YouTube competitor performance — `youtube_competitors`  ⭐ highest value
**Signal:** `youtube_competitors` · [`apis/youtube_apify_signal.py`](../apis/youtube_apify_signal.py)
**Actor:** `streamers/youtube-scraper`

Pulls the videos actually ranking for a topic this month, then computes
**view velocity (views/day)** — so you see what has momentum *now*, not what
accumulated views over years. Output feeds:
- **Topic discovery** — which angle is surging
- **Title patterns** — proven hooks ranking today (used as context, never copied as fact)
- **Optimal duration** — median length of the winners (`median_duration_secs`)
- **Anti-hallucination** — real titles reference real, current events

Treated as **context, not verified facts** in the script prompt.

### 2. Twitter/X breaking news — `twitter_breaking`  ⭐
**Signal:** `twitter` · [`apis/twitter_signal.py`](../apis/twitter_signal.py)
**Actor:** `apidojo/tweet-scraper`

Highest-timeliness source. UFC breaks on Twitter (bookings, results, injuries,
beef); gaming patch drama spreads there first. For each topic it searches recent
top tweets and recognises **domain authority accounts** (Ariel Helwani, Schefter,
Dexerto…) — authority hits raise the score and are tagged `[authority]` in facts.
Shortest cache (1.5h) so "just happened" topics stay fresh.

### 3. Reddit community — `reddit_community`
**Signal:** `reddit` · [`apis/reddit_signal.py`](../apis/reddit_signal.py)
**Actor:** `trudax/reddit-scraper-lite`

Hot posts + engagement from domain subreddits. Community sentiment, the debates
fans care about, and the exact language they use. 4h cache.

### 4. TikTok trends — `tiktok_trends`
**Signal:** `tiktok_trends` · [`apis/tiktok_signal.py`](../apis/tiktok_signal.py)
**Actor:** `clockworks/tiktok-scraper` (via `APIFY_BENABLE_BOT`)

Viral angles, hooks, and hashtag patterns — which framings already win attention
in short-form. 3h cache.

### 5. YouTube comments → audience questions — `youtube_comments`  (catalog-ready)
**Actor:** `streamers/youtube-comments-scraper`

Top comments on the best videos for a topic = the questions and disagreements
competitors are **not** answering. The richest source of fresh angles. Templated
in the catalog; wire a signal when you want to mine content gaps.

### 6. Instagram figures — `instagram_figures`  (optional, `enabled: false`)
**Actor:** `apify/instagram-scraper`

UFC fighters announce fights/injuries on IG first; creators tease drops. Flip
`enabled: true` in the catalog to chase athlete/creator-driven stories.

---

## Domain targeting

`domain_targets` in the catalog maps each domain to its best sources:

| Domain | Subreddits | Twitter authorities | IG hashtags |
|--------|-----------|--------------------|-------------|
| gaming | marvelrivals, pcgaming, FortNiteBR, CallOfDuty, valorant… | Dexerto, IGN, PlayStation, Xbox | marvelrivals, callofduty, fortnite |
| ufc | ufc, MMA, mmafighting, Boxing | ufc, espnmma, arielhelwani, danawhite | ufc, mma, ufcfightnight |
| nba | nba, basketball | wojespn, ShamsCharania, NBA | nba |
| nfl | nfl, fantasyfootball | AdamSchefter, RapSheet, NFL | nfl |

Tune these freely — they drive Reddit subreddit selection and Twitter authority
weighting.

---

## Caching & cost control

Every actor run is cached locally by (actor, input) for its catalog `ttl_seconds`
(see [`apis/apify_client.py`](../apis/apify_client.py)), so repeated discovery on
the same topic within the TTL window costs nothing. TTLs: Twitter 1.5h, TikTok/YT
3h, Reddit 4h, comments/IG 6h.

To temporarily disable any Apify signal without removing keys:
```env
CONTENT_SKIP_SIGNALS=twitter,youtube_competitors
```
