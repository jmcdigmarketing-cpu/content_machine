# Agent-Reach — evaluation & integration spike

**Status:** proposed (not started). **Effort:** `[M]`. **Owner:** TBD.
**Source:** https://github.com/Panniantong/Agent-Reach

## What it is

An open-source CLI that gives an agent free, unified read/search access to 15+
platforms (Twitter/X, Reddit, YouTube, GitHub, Bilibili, XiaoHongShu, Facebook,
Instagram, LinkedIn, RSS, generic web). Each platform uses a **"first choice +
backup backends"** pattern with automatic failover, wraps existing OSS tools
(`yt-dlp`, `twitter-cli`, `bili-cli`, …) instead of reimplementing them, and ships
an `agent-reach doctor` health command. Credentials live locally in
`~/.agent-reach/`. "All tools open-source, all APIs free" except an optional ~$1/mo
proxy.

## Why it's relevant to us

It maps almost 1:1 onto our **most fragile, most expensive layer** — the external
signal providers (`docs/assessment.md` weakness #2: "external-API fragility — the
#1 ops cost"). Its design philosophy (free-first, failover backends, a `doctor`
diagnostic) mirrors patterns we already have: the LLM router
(`core/llm_router.py`), the session circuit breaker (`apis/register_signals.py`),
and `ops reliability`.

### The four signals where it could pay off

Only **four** signals are Apify-paid today (`_APIFY_PAID_SIGNALS` in
`apis/register_signals.py`):

| Signal | File | Apify actor | Agent-Reach equivalent |
|---|---|---|---|
| `twitter` | `apis/twitter_signal.py` | `apidojo/tweet-scraper` | Twitter/X read+search |
| `reddit` | `apis/reddit_signal.py` | reddit actor | Reddit read+search |
| `tiktok_trends` | `apis/tiktok_signal.py` | tiktok actor | (no direct TikTok — gap) |
| `youtube_competitors` | `apis/youtube_apify_signal.py` | youtube actor | YouTube (via yt-dlp) |

`web_search` (Tavily/Brave) and `blog_rss` are **already free** — no change there.
So Agent-Reach's cost win is specifically the Twitter/Reddit/YouTube social layer.

## The key technical risk — engagement metrics, not just text

Our signals don't just fetch posts; they **score reach from engagement counts**:

- `twitter_signal._engagement()` reads `likeCount` / `retweetCount` / `replyCount`
  / `quoteCount`; `_normalise_score()` buckets top engagement into 0–100.
- `youtube_apify_signal` ranks by **view velocity**.

If Agent-Reach returns post text/metadata but **not** the numeric engagement
fields, we keep the recency/fact value but **lose the scoring quality**. This must
be the first thing the spike verifies, per platform. (Mitigation: where metrics are
missing, the signal can still be `active` with a flat/confidence-reduced score and
contribute facts only.)

## Recommended posture: validate via CLI → own it in-process

Two phases. **Agent-Reach is the fast way to validate the data; it is not the
intended production dependency.**

- **Phase 1 (spike):** install the Agent-Reach CLI locally, call it via subprocess,
  use it to answer the one question that decides everything — *do the free backends
  return the engagement counts we score on?* (likes/RTs, view velocity).
- **Phase 2 (end-state, Option 3):** re-implement the winning backends **in-process**
  against the free OSS tools directly (`yt-dlp`, Reddit JSON, snscrape/nitter). The
  pipeline owns its free data layer — no external CLI, no subprocess parsing, no
  supply-chain surface, still $0. **This is the recommended end-state.**

Either way: **lean, don't rip out Apify.** Apify stays as the fallback for any
signal whose metrics the free backend can't carry.

```
First choice (free, owned)      Fallback (paid, maintained)
──────────────────────────      ───────────────────────────
in-process free backend      →  Apify actor — used when the free
(yt-dlp / Reddit JSON / ...)     backend is rate-limited (429),
                                 blocked, or via SIGNAL_BACKEND=apify
```

The signal contract already gives us the seam: every signal is a
`func(topic) -> make_signal(...)` that does **build query → fetch items → score
items**. Only the *middle* step is Apify today, so we swap just the fetcher and the
~50 lines of scoring below it stay untouched. The existing circuit breaker
(`_record_signal_health`) remains the safety net.

### Why Option 3 over depending on the CLI

Agent-Reach is mostly a convenience wrapper around free tools we can call ourselves.
Calling them in-process removes the whole external-CLI tax (install/version drift on
the host, subprocess spawn + stdout parsing as a new failure surface, a
single-maintainer repo that runs shell and stores creds). We keep the *idea*
(free-first + failover backends + a `doctor`-style health view) and drop the
dependency.

### Phase 2 — Option 3 in-process backends (recommended end-state)

Per-platform free tool, each normalised at the fetcher boundary to **the exact item
schema the signal already parses** (so `_engagement` / `_normalise_score` /
view-velocity ranking need zero changes):

| Signal | Free tool | Key fields to emit (match Apify) | Metrics present? |
|---|---|---|---|
| `reddit` | Reddit public `.json` (no key) | `title`, `score`/`ups`, `num_comments`, `url` | ✅ yes |
| `youtube_competitors` | `yt-dlp --dump-json` | `viewCount`, `uploadDate`, `title`, `url` | ✅ yes (→ view velocity) |
| `twitter` | snscrape / nitter | `text`, `likeCount`, `retweetCount`, `replyCount`, `quoteCount`, `url`, `authorUsername` | ⚠️ verify in spike |
| `tiktok_trends` | (no clean free tool) | — | ❌ keep on Apify |

**1. `apis/free_backends.py`** — one fetcher per platform, each returning
`list[dict] | None` in the Apify item shape:
```python
def fetch_reddit(query) -> list[dict] | None: ...   # public .json
def fetch_youtube(query) -> list[dict] | None: ...   # yt-dlp --dump-json
def fetch_twitter(query) -> list[dict] | None: ...   # snscrape / nitter
```
The fetcher's only job is **schema-matching at the boundary** — emit the same field
names Apify did and everything downstream is unchanged.

**2. Backend selection** — env `SIGNAL_BACKEND=free|apify|auto` (default `apify`
during the spike, flip to `auto`/`free` once validated). In each paid signal, one
line changes:
```python
# was: items = run_actor(actor, actor_input, purpose="main", timeout_secs=120, ttl=ttl)
items = fetch_items(_SOURCE, query, ttl=ttl)   # picks free / apify / auto internally
```
`auto` = try free first, fall back to Apify on empty / 429 / block.

**3. Everything else is reused as-is:**
- **Cache** — already keyed per signal+topic (`register_signals._fetch_one`,
  `_cache_ttl_for`); free results cache identically.
- **Circuit breaker** — a free fetcher returning `STATUS_RATE_LIMIT` flows through
  `_record_signal_health` already; add a *cooldown-until* variant for transient 429s
  (see the rate-limit-cooldown task in the roadmap).
- **Cost meter** — free backends priced at `$0` in `core/cost_meter.py` (same as
  Ollama / `:free` LLM routes), so the run-cost line shows the saving.
- **Gating / fanout / variant-reuse** — operate on signal *names*; untouched.

Net change: **one fetcher module + a 3-way backend flag + one swapped line per
signal.** Only the 4 `_APIFY_PAID_SIGNALS` are touched; the engagement-scoring logic
stays exactly as written.

### Phase 1 — spike acceptance criteria

- [ ] Install Agent-Reach on the dev host; `agent-reach doctor` green for
      Twitter/Reddit/YouTube.
- [ ] For 5 real topics per channel, capture output and confirm whether **engagement
      counts** are present per platform (the scoring question above) — this decides
      free-primary vs Apify-fallback per signal.
- [ ] Measure: cost delta (Apify credits saved), latency delta, failure/rate-limit
      rate over ~20 runs.

### Phase 2 — in-process backends (Option 3) acceptance criteria

- [ ] `apis/free_backends.py` with `fetch_reddit` + `fetch_youtube` (the two with
      confirmed metrics), each emitting the Apify item schema.
- [ ] `SIGNAL_BACKEND=free|apify|auto` flag; swap the one fetch line in `reddit` +
      `youtube_competitors`; their `make_signal` output diffs clean vs the Apify path.
- [ ] `auto` falls back to Apify on empty/429/block; breaker + cooldown verified.
- [ ] Decision per signal: free-primary / Apify-fallback / Apify-only
      (`tiktok_trends` stays Apify; `twitter` per spike result).

## Risks / open questions

- **Trading one fragility for another.** Apify's paid value is that *they* keep the
  scraper working when a platform changes. Self-maintained/community scrapers break
  silently — the very failure mode we're trying to reduce. Failover (keep Apify as
  backup) is what makes this net-positive instead of lateral.
- **ToS / legal.** Scraping X / Instagram / LinkedIn against their terms; today we
  partly pay Apify to carry that risk. Relevant to our compliance posture
  (Phase O). Prefer it for low-risk reads (Reddit, RSS, YouTube metadata) first.
- **Supply chain.** Single-maintainer repo that runs shell and stores credentials.
  Vet the source before wiring into an unattended pipeline; pin a version.
- **Operational weight.** New external dependency (Python + shell + `yt-dlp` +
  sub-CLIs) to install and keep current on the host; subprocess parsing is a new
  failure surface vs in-process HTTP.
- **No TikTok backend** — `tiktok_trends` would stay on Apify regardless.

## Spike results (Phase 1) — 2026-06-29

Validated the in-process free backends directly (faster path to the decisive
question than the CLI). Probe: `spikes/free_backends_probe.py` (throwaway).

| Backend | Result | Evidence |
|---|---|---|
| **Reddit** keyless `.json` | ❌ **FAIL** | HTTP **403** on `www`+`old`, search+hot, browser UA — blocked at IP level from this host |
| **YouTube** `yt-dlp` flat (`extract_flat=in_playlist`) | ⚠️ **PARTIAL** | **5.7s** / 8 videos; `view_count` ✅ `duration` ✅ `channel` ✅ `url` ✅ — but `upload_date` **None** |
| **YouTube** `yt-dlp` full (`extract_flat=False`) | ✅ **PASS** | **60s** / 8 videos; **all** fields incl. `upload_date` → view-velocity works; real, current 2026 data |

**POC — end-to-end parity proven** (`spikes/yt_backend_poc.py`): the hybrid
`yt-dlp` fetcher, fed through the **real** scoring helpers from
`apis/youtube_apify_signal` (`_parse_int`, `_days_since`, `_duration_secs`,
`_normalise_score`), produces a valid `make_signal` identical in shape to the Apify
path — `active=True`, correct `score`, `top_velocity`, `median_duration_secs`,
`hot_titles`. On "UFC 320 Pereira": score 90, top velocity ~89k/day, and the
ranking correctly surfaces the **freshest** high-velocity clip (89k/day, 14.6d old)
above an older higher-view one. **~23–36s** for top-5 full extraction.

> **Production bug surfaced by the POC:** `youtube_apify_signal._days_since`
> truncates a plain `YYYY-MM-DD` to 8 chars (`"2026-06-"`) and fails, silently
> defaulting to 30 days — it only parses dates containing a `T`. Any Apify result
> with a plain date currently gets a wrong velocity → wrong ranking/score. Flagged
> as a separate fix (spawned task). The POC works around it by emitting full ISO
> datetimes.

**Findings:**

1. **YouTube is a clean free win — the biggest single saving.** `yt-dlp` returns
   every field `youtube_apify_signal` scores on. Latency is the only tuning knob:
   flat is 10× faster (5.7s/8) but lacks the upload date (→ rank by raw views, no
   velocity); full has the date (→ velocity) but is ~7s/video. **Recommended:
   hybrid** — flat search to rank candidates by `view_count` fast, then
   full-extract only the top ~5 to get dates for velocity (~23–36s measured).
   Replaces the `youtube_competitors` Apify actor (a heavy one). *POC parity proven
   (above).*
2. **Reddit keyless scraping is dead** (403). The free-but-legit path is a **Reddit
   OAuth script app** (free, ~100 req/min) — which is *already* a roadmap
   prerequisite ("Reddit OAuth + rate-limit-aware caching"). So Reddit should move
   to OAuth, **not** keyless scraping; until then it stays on Apify.
3. **`yt-dlp` deprecation watch:** warns "no JS runtime" — metadata extraction still
   works today, but yt-dlp is steering toward needing a JS runtime (deno). Pin the
   version and track this; it's the kind of quiet breakage Apify otherwise absorbs.
4. **Not yet tested:** `twitter` (keyless X is locked down harder than Reddit —
   expect FAIL without snscrape+proxies) and `tiktok_trends` (no clean free tool).
   Both likely stay on Apify.

**Revised per-signal verdict:**

| Signal | Decision | Backend |
|---|---|---|
| `youtube_competitors` | **Go free** | `yt-dlp` hybrid, in-process |
| `reddit` | **Go free via OAuth** (not scraping); Apify until OAuth lands | Reddit OAuth app |
| `twitter` | Likely **Apify-only** (verify in a follow-up) | Apify |
| `tiktok_trends` | **Apify-only** | Apify |

**Net:** Apify spend drops substantially (YouTube is a heavy actor and goes to $0)
but not to zero — Twitter/TikTok stay paid, Reddit converts to a free *API* rather
than a free scrape. The "all free" ideal is real for the biggest signal; the rest is
a mix.

## Bottom line

Spike done (see results above). **YouTube is the win:** `yt-dlp` carries every
metric we score on, so `youtube_competitors` — a heavy Apify actor — can go free
in-process via a flat-rank → full-extract-top-N hybrid. **Reddit keyless scraping is
blocked (403)**; the free path is the Reddit OAuth app already on the roadmap, not a
scrape. **Twitter/TikTok stay on Apify** for now. So Phase 2 ships the `yt-dlp`
backend first (biggest saving, lowest risk), keeps Apify as the `auto` fallback, and
folds Reddit into the existing Reddit-OAuth prerequisite rather than scraping it.

## Shipped (Phase 2) — 2026-07-01

The YouTube backend is live: [`apis/free_backends.py`](../apis/free_backends.py)
(`fetch_youtube_free`, hybrid flat-rank → full-extract top-N, `YT_FREE_TOP_N` /
`YT_FREE_SEARCH_N` overrides) selected via `SIGNAL_BACKEND=apify|free|auto` in
[`apis/youtube_apify_signal.py`](../apis/youtube_apify_signal.py). Default stays
`apify` (byte-identical to pre-change behavior); `free` runs keyless with no
Apify fallback; `auto` tries free first and falls back to Apify. The active
signal's `data.backend` records which backend served it, and
[`core/cost_meter.py`](../core/cost_meter.py) skips free-served runs when
counting Apify cost. Free-path failures return `STATUS_INACTIVE` (never
`no_key`), so they can't trip the session circuit breaker. Mocked tests:
[`tests/test_free_backends.py`](../tests/test_free_backends.py). Live smoke
2026-07-01 ("UFC 320 Pereira"): active, score 90, correct varying ages and
velocity ranking, $0.

## Shipped (Reddit OAuth backend) — 2026-07-06

The Reddit free path is live, exactly as recommended above: **official OAuth
API, not a scrape** (the 403 finding only ever applied to keyless
www.reddit.com JSON). `fetch_reddit_free` in
[`apis/free_backends.py`](../apis/free_backends.py) does an app-only
client-credentials grant (free script app, `REDDIT_CLIENT_ID` /
`REDDIT_CLIENT_SECRET`, token cached in-process) and searches hot posts across
the domain subreddits, emitting the same item schema the Apify actor returns.
Selected by the same `SIGNAL_BACKEND` flag in
[`apis/reddit_signal.py`](../apis/reddit_signal.py); default `apify` unchanged.
A Reddit 429 returns `STATUS_RATE_LIMIT`, which the breaker's timed cooldown
absorbs (`SIGNAL_RATE_LIMIT_COOLDOWN_SECONDS`). With this, two of the four paid
signals have free backends; Twitter/TikTok remain Apify-only per the verdict
table above.

## Wave C — public-apis shortlist (2026-08-26)

Research only. Remaining paid Apify actors are **`tiktok_trends`** and
**`youtube_competitors`**. Anything that cannot answer *key vs keyless* and
*survives discovery-load rate limits* is not a candidate. No new dependency.

Checked against [public-apis](https://github.com/public-apis/public-apis)
(Video / Social) plus each API's current published docs.

| Candidate | `apis/` signal it would serve | Paid call it displaces | Key vs keyless | Discovery-load rate limits |
|---|---|---|---|---|
| **YouTube Data API `search.list` / channel RSS** (`https://www.youtube.com/feeds/videos.xml?channel_id=`) | `youtube_competitors` | Apify youtube actor | Official Data API needs a key we already hold; channel RSS is **keyless** | RSS: one GET per competitor per run, well under typical feed limits. Data API: 100 units/search against 10k/day — already budgeted. **Already shipped** as `fetch_youtube_free` / competitor snapshot. Not a new candidate. |
| **Twitch Helix `Get Top Games` / `Get Streams`** | new gaming-trend helper (does **not** replace TikTok) | none of the remaining Apify actors (different platform) | **Key** (app client-credentials) | 800 points/minute documented. One or two calls per discovery run survives. Honest boundary: it is a *supplement* for TapIn gaming, not a `tiktok_trends` replacement. |
| **TikTok unofficial / RapidAPI scrapers listed on public-apis** | `tiktok_trends` | Apify tiktok actor | Usually a vendor key; some "keyless" HTML scrapes | No published SLA that survives concurrent discovery (one run × variants). Historical 403/ban pattern matches retired `twitter`/`tapology`. **Not a candidate.** |
| **Reddit JSON / OAuth** | `reddit` (retired) | already displaced | OAuth key (free script app) | 429 handled as `STATUS_RATE_LIMIT`. **Already shipped** as `fetch_reddit_free`. |

**Verdict:** there is **no licence-clear, documented-limit, keyless public-apis
entry that displaces `tiktok_trends`**. `youtube_competitors` already has a
free backend. Twitch Helix is the only remaining shortlist item with a
published rate limit that would survive a real discovery load, and it does
not replace either remaining Apify actor. Do not add a dependency until that
changes.
