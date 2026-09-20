# Content Machine — Operating Plan (pace, cost, channels, ops)

> **Class:** plan · **Status:** living · **Reviewed:** 2026-09-20

Companion to [vision.md](vision.md) (the north-star architecture & 12-month plan).
This doc is the **operational** layer: what to build next at the **real** pace and
cost, how to stand up new channels, where the money and the risks are, and the
boring top-down hygiene that compounds. Grounded in the actual codebase and git
history as of **2026-06-23** (main `f500efa`, 58 commits since 2026-06-13).

> This file is written to be loaded as context for future sessions. Where a claim
> depends on live data (RPM, real API bills, view counts), it's marked *assumption*
> — verify before betting on it.

---

## 0. Where this project actually is

The repo has crossed from "YouTube automation script" into a **small media
operating system**: discovery → research brief → score → script → TTS → render →
publish, wrapped in a closed learning loop (feature store + recommenders + weekly
report + vault writeback) and a 2026-policy compliance gate (Phase O). Generation
is now a *minority* of the value; the intelligence + data layer is the asset.

Honest position vs. the field:
- **Ahead of** the average automation builder (GPT + ElevenLabs + a stock-clip glue script).
- **At/above** the "advanced" tier (multi-channel config, analytics, scheduling, competitor pulse, circuit breakers).
- **Entering** the "small media OS" tier (research/intelligence/analytics/asset/monetization subsystems exist in v0–v1).
- **Not** a SaaS platform (no multi-user/UI/billing) — and per vision.md, **don't go there yet**; it's premature until the data moat is real.

---

## 1. Can we move past Phase O? Yes — and here's the next axis

Phase O (authenticity/cadence/outlier + AI-disclosure + monetization-CTA) is
**shipped and load-bearing** (`core/authenticity.py`, gate in `main.py`). It's not
"done forever" — it's a guardrail that stays on — but it no longer needs net-new
build. **Moving past it is correct.**

"Aside from multi-platform, what's next?" — ranked by ROI and grounded in what the
code is ready for. The honest answer from vision.md stands: **the next axis is not
a feature, it's trustworthy, causal data.** Concretely, in order:

1. **Reliability & observability (data you can trust).** *This is the real "Phase
   next."* A data-quality monitor + a reliability/cost dashboard (API success
   rate, quota usage, cache hits, per-run cost). Everything downstream
   ("intelligence") is worthless on untrusted data, and API fragility (the Apify
   402 saga) is today's #1 operational risk. Cheap to build, protects everything.
2. **Cost-meter expansion + RPM/margin** (see §4) — turn "views" into "business."
3. **Experimentation harness** (vision.md's moat) — causal learning, not correlation.
4. **Channel Health Agent + Topic Graveyard/Winners** (see §2 month view).
5. *Then* the bigger swings: MoneyWise depth, Benable/affiliate, competitor genome.

**App building / UI overhaul:** defer. A local FastAPI control panel reusing
`core/` is the eventual move (keep `core/` UI-agnostic — it already is), but the
terminal UI is not the bottleneck; data trust and monetization are. Build the UI
when there's a second operator or a customer, not before.

---

## 2. Projected roadmap at current pace

**Pace reality:** 58 commits in 10 days, but that's a *burst* (this session alone
landed PRs #1–7). A sustainable solo pace is ~**3–6 meaningful changes/week**
shipping with tests. Projections below assume that sustainable pace, not the burst.
Dates anchored to **2026-06-23**.

### Next 2 weeks — to ~2026-07-07 — *Stabilize the foundation*
- **Reliability dashboard** (`scripts/ops reliability` or a status panel): API
  success rate, quota usage, cache-hit rate, per-run cost — surfaced from data
  that mostly already exists (cost_meter, cache_manager, signal health).
- **Cost-meter expansion** (§4): add Flux thumbnail (currently *missing*), split
  LLM by model (OpenAI vs Claude), make per-run cost trustworthy.
- **Feature-store completeness pass**: confirm every run persists hook/title/
  thumbnail/assets-used/publish-time alongside the engagement join (most exist;
  audit the gaps). This is the fuel for everything later.
- Carry-over polish: web-search source auto-capture (extend the just-shipped
  pasted-link capture to also log web_search result URLs).

### Next month — to ~2026-07-23 — *Decisions from data*
- **Channel Health Agent** (nightly Green/Yellow/Red on CTR/views/retention/cadence
  trends) — reuses `analytics/weekly_report.py` machinery.
- **Topic Graveyard** (avoid-list of failed topics wired into discovery) +
  **Winners DB** (ranked top-decile view + "clone a winner" path) — the data is
  already in `content_runs`/`publish_log`; this is mostly query + UI.
- **Prompt evolution v1**: a frozen eval set + `prompt_version`↔outcome tracking
  (the field already persists) so prompt changes are measured, not vibes.

### Next 3 months — to ~2026-09-23 — *Channel 2 becomes real (MoneyWise)*
- MoneyWise from "domain adaptation" to a real engine: **earnings calendar**
  (CPI/FOMC/jobs/earnings → predictable content cadence), **ticker tracking**
  (SPY/QQQ/NVDA/TSLA/BTC/ETH), **conviction/sentiment scores** per ticker, a
  separate **finance asset library**. Most inputs are free APIs (the expensive
  part is sentiment quality).
- Requires the channel-build work in §3 (oauth, branding, SEO, feeds, slots).

### Next 6 months — to ~2026-12-23 — *Changes category: portfolio*
- **Portfolio dashboard** (channels × revenue × views × growth × **margin**, not
  just a per-channel view) — aggregation over existing per-channel data.
- **Opportunity scanner** (score niches by demand/competition/monetization/trend).
- **Competitor genome** (hook/title/upload-time/frequency/length per competitor —
  cost-gated, hard-cached) + **emerging-trend detection**.
- **Asset intelligence**: from "find an asset" to "find the highest-*retaining*
  asset" (needs retention attribution per clip).

### Next year — to ~2027-06-23 — *Research + Analytics + Media + Monetization layers*
- Generation becomes ~15–20% of the codebase; the rest is intelligence and
  monetization. Realistic end-of-year state: 2–4 channels live, a portfolio view,
  a working experimentation loop, and at least one non-ad revenue stream
  (affiliate/Benable) measured per topic. **Full autonomy is deliberately *not*
  a 12-month goal** (vision.md §6) — it's the output of trustworthy data + causal
  learning + spend governance + policy safety.

---

## 3. Standing up a new channel in a different genre

The architecture is **config-first** (Decision §8) — a channel is data, not code.
Concrete checklist to launch a genre (e.g. AI Tools, NBA, Tech):

**Required (config + auth):**
1. `config/channels.json` — channel entry: name, `domain`, `post_schedule`
   (timezone + slots + per-domain slots).
2. `config/seo/<id>.json` — `default_tags` (curated brand tags only — keep them
   clean per the tag-pollution fix), `title_rules`, `seo_refresh_queries`, and
   domain-tagged `rss_feeds` (use the `domains` tag so feeds route correctly).
3. `config/data_sources.json` — add the genre to `domain_rss` if not present.
4. `apis/topic_scorer.py` `infer_domain` — keyword list for the new domain (so
   gating + recommenders route correctly); add it to the gating groups in
   `apis/register_signals.py` if it needs domain-specific signals.
5. Brand kit: `assets/branding/<id>/` (intro, fonts, colors) + a background-clip
   folder under `video/backgrounds/<genre>/` (media auto-ignored by git).
6. `py -m youtube.oauth_setup --channel <id>` (+ the `youtube.readonly` scope) and
   a `config/secrets/youtube_token_<id>.json`.
7. `py -m config.validate_channels --channel <id>` to confirm.

**What's genuinely new per genre (the real work):** domain-specific *signals*
(finance has FRED/SEC/Finnhub/CoinGecko; sports has odds/stats/scores; gaming has
RAWG/Steam/IGDB) and a domain-specific *asset library*. Everything else (pipeline,
recommenders, compliance, cost meter, vault) is shared and free.

**Genre ROI ratings** (*assumption — validate against real RPM*):

| Genre | Why | Effort to add | Rating |
|---|---|---|---|
| **Finance (MoneyWise)** | infra exists, operator domain expertise, high RPM, free data APIs | low (already scaffolded) | **9.5** |
| **AI Tools / Tech** | easy affiliate, Benable-friendly, high search demand | medium (new signals/assets) | **9** |
| **Gaming (TapIn)** | already built | live | **8.5** |
| **Consumer tech / products** | affiliate-friendly, evergreen | medium | **8** |
| **Anime** | infra exists (anime signals), but weak monetization | low | **6.5** |

The platform's defensibility is *repeatability*: each new channel reuses the same
intelligence backend, so the marginal cost of a channel trends toward "config +
assets + an OAuth token."

---

## 4. AI cost per run + cost-reduction roadmap

**Per-run cost (grounded in `core/cost_meter.py` defaults):** a rendered ~180-word
short estimates ≈ **$0.30** — and **TTS dominates** (ElevenLabs: `chars/1000 × $0.30`
≈ $0.27 of it). LLM is modeled at `max(words×8,1500)/1000 × $0.005` ≈ $0.0075
(*almost certainly an undercount* — it only counts final-script tokens, not the
many discovery/variant/brief/expansion calls). Apify is `$0.02 × active social
signals`; web search `$0.008`; render $0 (local FFmpeg).

**Known cost-meter gaps to fix (cheap, high-value):**
- **Flux thumbnail is not metered at all** (`BFL_API_KEY`, ~$0.04–0.05/image) —
  add it; it's a real per-run cost.
- ~~LLM is one blended line — split OpenAI vs Claude and count discovery calls.~~
  ✅ **Done** — the `llm_router` token ledger now records every call's provider +
  model + in/out tokens, and `cost_meter.llm_cost_from_usage` prices them per
  provider (free `:free`/Ollama = $0). The old word-count heuristic is the fallback
  only when a run recorded no usage.

**Two different cost problems:**
- **Per-run variable cost** → dominated by **TTS** (and Flux thumbnails).
- **Fixed monthly cost** → dominated by **Apify** (~$40–200/mo per memory) — the
  402 saga showed it's the real budget ceiling.

**Cost-reduction roadmap (ordered by leverage):**
1. **Tiered models** — ✅ **SHIPPED (2026-06-23)** via `core/llm_router.py`: every
   LLM call picks a tier (`cheap`/`extract`/`premium`) routed across DeepSeek /
   OpenRouter / Ollama / OpenAI / Claude. Cheap+extract run on free providers
   (DeepSeek/OpenRouter free models) → per-run LLM cost ≈ $0; premium stays free on
   DeepSeek-V3 by default, one env flip to upgrade to gpt-4o/Claude. A real
   per-provider token ledger now prices this section. See [credit_efficiency.md](credit_efficiency.md)
   for the remaining quota/spend optimizations (failover, persistence, budgets).
2. **Apify discipline** — already helped by the 402 guard + preflight + domain
   gating + variant-reuse pinning. Next: use the feature store to *measure* whether
   each paid social signal actually moves the composite score; drop the dead weight.
3. **TTS spend** — cache aggressively (never re-render the same script); consider a
   cheaper voice tier for non-final passes; keep scripts tight (shorter = cheaper).
4. **Flux gating** — `THUMBNAIL_FLUX_FIRST`/score-gate so Flux only runs on
   high-score topics; Pillow fallback is free.
5. **Signal gating by score threshold** — only fire the expensive APIs when a
   topic clears a bar (partially there via gating; extend to a cost-aware gate).
6. **Margin, not cost** — pair cost_meter with realized RPM (vision.md) so the
   optimization target is *profit per video*, not raw spend.

---

## 5. Cross-project tools worth having

Reusable beyond this repo (and worth extracting cleanly):
- **The signal contract + registry** (`apis/signal_contract.py`, `signals_bootstrap`)
  — a generic "fan out across N heterogeneous sources, degrade gracefully" pattern.
- **The cost meter + reliability layer** — applicable to any multi-API pipeline.
- **The Obsidian read/writeback pattern** (`obsidian_facts` + `vault_writeback` +
  the new `source_capture`) — a human↔machine knowledge layer usable by any agent.
- **The recommender + confidence pattern** (`recommender_confidence`) — honest
  "don't present 3 samples as fact" surfacing, reusable anywhere analytics drive UI.
- A **provider/quota governor** (to build) — one budget layer over OpenAI/Claude/
  ElevenLabs/Apify/Tavily with per-day ceilings — useful across every AI project.

---

## 6. Side-income / monetization territories

Beyond YouTube ad revenue (low RPM on shorts):
1. **Affiliate / Benable** (highest-leverage, in vision.md Phase G): topic →
   product match → link → **revenue-per-topic** attribution. AI Tools & consumer
   tech are the best-fit genres. Treat video→click→sale tracking as a spike with a
   kill criterion (it's the hardest data plumbing).
2. **Productize the intelligence layer itself** — the repo already separates
   intelligence from production (`docs/positioning.md`, `intelligence_report`). A
   **"Content Intelligence Report"** (research brief + opportunity score +
   competitor pulse for a topic/niche) is a freelancer/consulting deliverable that
   **requires generating zero videos**. Fastest path to first external dollar.
3. **Finance channel RPM** — finance shorts carry far higher RPM than gaming;
   MoneyWise is the highest-ROI channel expansion (§3).
4. **Sponsorships / channel memberships** — downstream of audience; not a system to
   build now, but the analytics layer makes the pitch deck.

---

## 7. Top-down / process improvements (boring, compounding)

- **Google account structure** — separate identities: a personal account, a
  "Content Machine admin" (owns API projects/billing), and per-brand accounts
  (TapIn, MoneyWise). Don't run everything from one login — it entangles billing,
  OAuth scopes, and risk. Use a password manager + 2FA on each.
- **Backups (weekly)** — PostgreSQL dump, the Obsidian vault, `config/` (esp.
  `config/secrets/` — *encrypted, off the synced OneDrive folder*), and the asset
  catalog. The DB *is* the moat; losing it loses the learning advantage.
- **Get the repo off OneDrive** — the OneDrive `.git` hazard ([[onedrive-git-hazard]]
  in memory) already rewound a commit mid-session and spawned conflict-copy
  branches. Move to `C:\dev\content_machine` (or exclude from OneDrive sync). This
  is the single highest-value ops fix; it threatens git integrity weekly.
- **Branch discipline** — already enforced (PR-only to main, ADR §12; direct pushes
  are blocked). Keep feature branches short-lived; the two-PR consolidation mess is
  the cautionary tale.
- **Secrets hygiene** — `.env`/`config/secrets/*` are gitignored; keep them out of
  any backup that syncs to a third party in plaintext. Rotate keys periodically.
- **Domains** — secure brand/domain variants (contentmachine / contentos /
  contentintelligence) before they're needed, even if parked.

---

## 8. Industry & competitive comparison

> **Override (2026-07-07, decisions §17):** the "keep generation boring… if a
> change only adds generation volume it's probably not [worth building]" clause
> below is **retired**. Generation *quality* is now a competitive lever — see
> [video_creation_stack.md](video_creation_stack.md) for the full tool list to
> add (free/local-first, cost-metered provider slots). The moat thesis in this
> section still holds; the video layer is additive, not a substitute for the loop.


| Tool | Stronger than us | We're stronger on |
|---|---|---|
| **TubeBuddy** | polished UI, install base | intelligence depth, closed learning loop |
| **vidIQ** | UI, keyword tooling | per-channel performance data scale, custom analytics |
| **OpusClip** | clip repurposing UX | different category (we generate + learn, not just clip) |
| **Generic YT-automation kits** | none meaningfully | far more sophisticated (research, compliance, analytics, multi-channel) |

**The real competitive threat is not other builders — it's the platforms.** If
OpenAI / Google / YouTube ship one-click research→script→thumbnail→video→upload,
GPT-wrapper tools die. The defense is the one thing they can't replicate: **your
specific, historical, causally-validated performance data and the channel
intelligence trained on it.** Every priority in vision.md and this plan is chosen
to widen that moat. The grand-strategy question to keep asking:

> *How does Content Machine evolve from a content generator into a media
> holding-company operating system?*

Once a feature clearly answers that, it's worth building. If it only adds
generation volume, it's probably not.

---

## 9. The one-paragraph "what to do Monday"

The reliability + cost dashboard (`ops reliability`, O11–O12) **shipped**. The
cost meter now sees TTS (~91% of a rendered run, ~$0.31 metered / ~$1 allocated).
Channel Health, graveyard, and winners exist. **Monday pickup** is
[roadmap.md](roadmap.md) **recommended next 5**: pre-run completion gate, oauth
tests + `coverage` extra, pronunciation lexicon (what actually unblocks the $0
TTS flip), allocated vs marginal economics, numeric/record grounding. Do not
start clip-from-source, avatar, or Phase M. MoneyWise still needs `oauth_setup`
before a depth wave. CUDA torch (`2.8.0+cpu` on a 4070 Ti) is the GPU gate, not
hardware.
