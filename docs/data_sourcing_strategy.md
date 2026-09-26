# Data-Sourcing Strategy & Plan — 2026-06-25

> **Class:** reference · **Status:** living · **Reviewed:** 2026-09-25

**Planning + documentation only.** Prompted by the "Virgin API Consumer vs Chad
Third-Party Scraper" meme, this doc (a) makes the project's sourcing *policy*
explicit in one place — today it's scattered across
[domain_expansion.md](domain_expansion.md), [data_sources.md](data_sources.md),
[credit_efficiency.md](credit_efficiency.md), [decisions.md](decisions.md) — and
(b) lists only the **genuinely useful** changes that fall out of it, with an explicit
**do-not-change** list so the meme's temptations don't turn into busywork.

---

## 1. The policy (canonical)

Content Machine is deliberately **neither** the chained API purist **nor** the
rule-breaking scraper. It runs a **risk-managed hybrid** governed by one ladder
(from [domain_expansion.md](domain_expansion.md)):

```
bulk dataset / official API → keyed REST API → community wrapper → HTML scrape → unofficial scrape
```

**Decision rule for a new source:** take the **highest rung that covers the fact**.
Drop to scraping only when every higher rung is missing or inadequate — and never
onto the deny list (§4). Every rung sits behind the same **resilience contract**:
per-signal cache TTL, session circuit breaker (quota/auth/no-key → skip), spend
budgets, and graceful degradation (a dead source never crashes discovery).

**Compliance guardrail (non-negotiable):** this is a *monetized* channel business
under the 2026 authenticity regime (Phase O). Sourcing must stay **defensible** —
no proxy-rotation/CAPTCHA-solving/aggressive evasion, no ToS-hostile scraping of
targets that forbid it. Reliability and reputation outrank raw data access.

## 2. How today's system embodies it (grounded)

- **API rungs:** RAWG, Steam, Odds, SEC EDGAR, FRED, TMDB, Jikan, CoinGecko,
  BallDontLie, api-sports, MusicBrainz, YouTube Data (OAuth + 10k units/day).
- **Scrape rungs:** `apis/scrapers/` (ESPN, Basketball-/Football-Reference via
  BeautifulSoup), `apis/tapology_api.py` (opt-in), and **Apify** actors
  (`apis/apify_client.py`) as *managed* scrapers for reddit/twitter/tiktok/youtube.
- **Licensed middle path:** `apis/web_search_api.py` (Tavily/Brave) — a third lane
  the meme ignores: paid, ToS-clean access to fresh facts.
- **The resilience contract in code:** `apis/register_signals.py` breakers, Apify
  402/429 handling + budgets (`credit_efficiency.md` O1–O11), 6h caches. *These
  breakers are the machine refusing both extremes — it routes around dead endpoints
  (not a pure Virgin) while respecting budgets and failing safe (not a reckless
  Chad).*

## 3. Strategic assessment (pros / cons)

**API-first core — pros:** dependability, structured contracts, reproducibility,
and — decisively — **compliance/reputation fit** for a monetized channel.
**Cons:** quota walls, OAuth friction, and *gaps* (events past the LLM cutoff — the
recency Achilles heel).

**Scraper/Apify supplements — pros:** fill exactly the recency/competitor gaps APIs
can't; this layer is *why the recency cycle improved*.
**Cons the meme hides but the codebase proves:** not free (Apify **402
out-of-credits**; you pay the proxy/CAPTCHA bill); **fragile** — the #1 recurring
ops cost in [assessment.md](assessment.md) is scrapers/actors *breaking* (bebity
404, `sortVideosBy` 400, RSS 404…); and it demands the whole breaker/governor
apparatus — the "millions of engineer hours" punchline, inverted.

**Verdict:** the current hybrid is the *mature* answer. The real strategic dial is
recency (which pulls toward more Chad) vs. fragility + compliance (which pull toward
less) — and the machine correctly buys recency the **least-Chad** way (web search +
operator key-facts + tighter grounding), not by scraping harder.

## 4. Planned implementations (only the useful ones)

Ranked by usefulness ÷ effort. All opt-in, fail-safe, unit-tested per
[decisions.md](decisions.md) §11. Flags: **Type · Effort · Value**.

| ID | Change | Type | Effort | Value | Grounding |
|---|---|---|---|---|---|
| **S1** | *This doc* — canonical sourcing policy (the ladder + decision rule + resilience contract + compliance guardrail) as one governing artifact | Docs | `[S]` | High | consolidates scattered guidance |
| **S2** | **Scraper politeness** in `apis/scrapers/base.py`: per-domain min-interval throttle + exponential backoff on failure + optional `robots.txt` respect | Code | `[S–M]` | **High** | base.py has a spoofed UA and **no delay/backoff/robots** (`time` used only for cache) — the real gap |
| **S3** | **Scrape deny-guard**: encode the prose "do not scrape" rules (MAL HTML, Box Office Mojo — `domain_expansion.md:124,154`) as a config denylist that refuses to register/enable a listed scraper | Code | `[S]` | Med–High | prevents a future contributor silently wiring a fragile/ToS-hot scraper |
| **S4** | **Source-tier tagging**: add a `tier` (official_api\|keyed_rest\|wrapper\|scrape\|unofficial_scrape) to the signal/source registry — makes the ladder **machine-readable** | Code | `[M]` | Med (enabler) | no tier concept exists in code today (grep-confirmed); enables S3 preference + S5 |
| **S5** | **Sourcing surfacing** in `core/reliability.py`: a session summary of facts-by-tier ("how much of this run leaned on scraping") as a fragility early-warning | Code | `[S–M]` | Med | extends the O9 dashboard; needs S4 |

**Do-first:** **S1 (done here)** + **S2**. S2 is the standout — it directly cuts the
#1 ops cost (getting blocked / breaking), makes the scrape rungs *defensible*, and is
low-risk. S3 is a cheap governance win. S4→S5 only if the tier-reporting is wanted.

### S2 detail (the one worth doing now)
`apis/scrapers/base.py` `fetch_html` currently fires immediately with a browser UA.
Plan:
- a module-level `_last_hit: dict[domain, ts]` + `_throttle(url, min_interval)` that
  sleeps to honor a per-domain minimum gap (`SCRAPER_MIN_INTERVAL_SECONDS`, default
  ~2s);
- exponential backoff + one retry on transient failure (mirrors the git-push policy);
- optional `urllib.robotparser` check gated by `SCRAPER_RESPECT_ROBOTS` (default on
  for reference sites);
- keep the realistic UA but pair it with politeness so the posture is *defensible,
  not evasive*. Also apply the throttle in `apis/tapology_api.py`. (Apify is managed
  — it handles its own concurrency; no change there.)
- Tests: throttle enforces the gap between two calls; robots-disallow short-circuits;
  backoff retries once then gives up; caching still bypasses the network (unchanged).

## 5. Explicitly out of scope — do **not** change (honoring "if actually useful")

The analysis *validates* the status quo here; changing these would be a regression:
- **Do not "go full Chad"** — proxy networks, CAPTCHA-solving, evasion, or
  scrape-everything to chase recency. Reputational/legal risk kills the Phase O
  compliance moat; recency is already handled the least-Chad way.
- **Do not "go full Virgin"** — ripping out scrapers/Apify reopens the recency gap
  that the whole recency cycle closed.
- **Do not collapse the layered breakers** — per `decisions.md` §13 they're
  intentionally separate; keep the API-first default and the hybrid as-is.

The only net-new work worth doing is making the *scrape rungs we already have*
**politer and more governed** (S2/S3) and, optionally, **legible** (S4/S5).

---

## Cross-references
- Ladder & per-domain sources: [domain_expansion.md](domain_expansion.md),
  [data_sources.md](data_sources.md).
- Resilience contract: [credit_efficiency.md](credit_efficiency.md) (O1–O11),
  `apis/register_signals.py`, `apis/apify_client.py`.
- Fragility evidence: [assessment.md](assessment.md) (weakness #2).
- Scraper code: `apis/scrapers/base.py`, `apis/tapology_api.py`.
- Reliability dashboard: `core/reliability.py`.
