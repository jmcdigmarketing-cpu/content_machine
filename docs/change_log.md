# Content OS — Changelog

Initial changelog summarizing major modifications present in the codebase as of documentation generation. Versions are grouped by theme rather than release tags (the project does not yet use semantic versioning or tagged releases).

---

## [Unreleased] — Content OS evolution (2026)

### 2026-07 focus wave: O10 + trade validation + creator coach + headless facts — 2026-07-02

*Closes the four "Current focus (2026-07)" roadmap items that remained after the
fact-first pipeline. Suite 613 green.*

- **O10 reset-window auto-re-enable** — `core/reset_window.py`: encodes real quota
  reset cadences (YouTube Data API daily 00:00 Pacific; Apify monthly cycle via
  `APIFY_RESET_DAY`; Odds monthly). A hard Apify **402/monthly-limit** exhaustion
  now persists until the actual cycle reset instead of re-checking every 6h
  (401/403 keeps the 30m TTL; the operator-budget trip keeps the flat TTL so a
  raised budget recovers fast). Quota-blocked YouTube uploads retry 5 min after
  the real reset. Reset times surface in `ops reliability`. Master switch
  `RESET_WINDOW_AUTO_ENABLE` (default on). Tests: `tests/test_reset_window.py`.
- **Semantic trade validation (opt-in)** — `core/trade_validation.py`: extracts
  `player → team` claims from the script and warns when the pair never co-occurs
  on a single fact line — the fused-trade failure token grounding passes (real
  Giannis→Heat fused with invented Butler→Celtics). `SEMANTIC_TRADE_VALIDATION`
  default **off** (higher false-positive rate); shown after Fact grounding in
  `main.py` + `auto_generate`; warns, never blocks. Tests:
  `tests/test_trade_validation.py`.
- **Creator coach (Phase S)** — `core/creator_coach.py` + `py -m scripts.ops coach`:
  daily "ideas + why" view — ranked best-bets each with a rationale, recommended
  length + post time, winning title patterns, retention pacing hint, cadence
  headroom. Read-only, fail-open per section. Tests: `tests/test_creator_coach.py`.
- **Weekly digest next actions (Phase S)** — `analytics/weekly_report.py` now
  derives numbered operator instructions from the per-dimension winners/losers
  ("Lead with the 'fraud' angle again (45% vs 25% baseline, n=3)"), noise-gated
  at ±3pp vs baseline; rendered under "Next actions:" with a pointer to `ops coach`.
- **Headless key facts for `auto_generate`** — `--facts-file` (parsed with the same
  paste-block parser as the interactive prompt; trade trackers work) + repeatable
  `--fact` lines. Deduped/tip-filtered, saved in full to the vault, injected as
  highest-priority ground truth, echoed in the grounding report. Tests:
  `tests/test_auto_generate_facts.py`.

### Scene-matched B-roll (Phase Q) — 2026-06-23

*The render looped one background clip; this cuts between several, one per script
beat (visual changes as the topic does — a retention lever).*

- **`video/scene_plan.py`** (pure, tested): `plan_scenes(script, topic, duration,
  words=…)` splits the script into ≤N timed beats, each with a `topic + beat-keyword`
  B-roll query. Uses real word timings for accurate beat boundaries when available,
  else proportional.
- **`assets/composite.build_multi_concat_command`**: generalises the 2-input hybrid
  concat to N normalised scene clips; `compose_scene_matched_background` runs it.
- **`assets/manager.get_scene_matched_background`** + render wiring: fetches a stock
  clip per beat and composes. **Default OFF** (`SCENE_MATCHED_BROLL`) — a render-path
  feature; **returns None → falls back** to the normal single/hybrid background on
  any missing clip or compose error, so it only ever upgrades, never breaks a render.
- **Tests:** `tests/test_scene_plan.py` (planning, contiguous windows, word-timed
  boundaries, N-input concat builder, missing-clip fallback). Suite 521 green.

*With this, Phase Q is functionally complete: timed + word-level animated captions
(keyword pop) and scene-matched cuts (beat-synced) cover the "dynamic emphasis"
checklist; a hook zoom-in remains an optional flourish.*

### Word-level captions from real TTS timing (Phase Q) — 2026-06-23

*Captions were timed by word-count estimate; the TTS step now gets real per-word
timing from ElevenLabs (free, same call) — no Whisper dependency.*

- **`video/caption_timing.py`** (pure, tested): `words_from_alignment` (char
  alignment → word timings), `build_srt_from_words` (accurately-timed,
  sentence/length-aware SRT), `build_ass_karaoke` (per-word `\k` highlight ASS —
  the animated-caption upgrade).
- **`core/tts.py`**: `convert_with_timestamps` captures alignment and writes a
  `<mp3>.words.json` sidecar (best-effort, `TTS_WORD_TIMESTAMPS`; any failure
  falls back to the plain stream).
- **`video/subtitles.generate_subtitle_file`**: prefers the sidecar — `CAPTION_STYLE`
  `word` (accurate SRT, **default**, safe strict upgrade) / `karaoke` (animated ASS,
  opt-in — verify with a render) / `plain` (old proportional). The existing
  `subtitles` ffmpeg filter burns both `.srt` and `.ass`, so no render-filter change.
- **Tests:** `tests/test_caption_timing.py` (word grouping, SRT/ASS, TTS sidecar +
  fallback) + word-timed branch in `tests/test_subtitles.py`. Suite 511 green.

### Retention-curve modelling → data-driven pacing (Phase P) — 2026-06-23

*Closes the Phase P retention item. We synced `averageViewPercentage` but never the
per-position curve; this adds it and the model that consumes it.*

- **Curve sync** (`analytics/youtube_metrics._fetch_retention_curve`): a second
  Analytics report (`audienceWatchRatio` by `elapsedVideoTimeRatio`) stored as
  `retention_curve` on the publish_log metrics blob. Best-effort
  (`RETENTION_CURVE_SYNC`, default on) — empty for low-watch videos, never breaks
  the main sync.
- **`core/retention.py`**: aggregates per-video curves into a channel-average
  curve and a **drop-off point** (first position below `RETENTION_DROPOFF_FLOOR`,
  default 50%). Strictly confidence-gated — no model until ≥ `RETENTION_MIN_VIDEOS`
  (default 3) curves exist, so it can't overfit a handful of videos.
- **Data-driven pacing**: `pacing_hint()` replaces the script prompt's static
  "~30-second mark" retention pivot with the channel's *measured* drop-off once
  data accrues (no-op until then).
- **`scripts.ops retention`** renders the average curve + drop-off.
- **Tests:** `tests/test_retention.py` (min-videos gate, average curve, drop-off
  detection, pacing-hint text, no-channel/no-data). Suite 500 green.

### A/B title-pattern loop (2026-06-23)

*Phase P "A/B variant loop", in the single-channel form: a faceless channel can't
double-publish without cannibalizing, so instead of head-to-head it **attributes**
realized engagement to the published title's structural pattern and biases future
picks.*

- **`core/title_features.py`** — `feature_tags(title)`: structural pattern tags
  (number / listicle / question / colon / versus / superlative / curiosity /
  callout / year / bracket / short / long). Pure + deterministic.
- **`core/title_experiments.py`** — joins each published title to its engagement
  (`content_runs.title` ↔ `publish_log`), aggregates by pattern into a
  `pattern_leaderboard()` ("colon titles average 18%"), and exposes `winning_tags()`
  (patterns above the channel's overall engaged-rate, cached per run,
  `TITLE_PATTERN_MIN_SAMPLES`).
- **Loop closes at selection**: `core/ui.display_variants(channel_id=…)` annotates
  any variant matching a winning pattern with "▲ <pattern>", so the analytics loop
  biases the operator's pick. Wired at both `main.py` variant prompts.
- **`scripts.ops title-patterns`** prints the leaderboard.
- **Tests:** `tests/test_title_experiments.py` (feature extraction, leaderboard
  ranking, winning-tags threshold, empty/min-samples). Suite 494 green.

### Topic Winners + Graveyard (2026-06-23)

*The data was already in `content_runs`↔`publish_log`; this surfaces it by topic.*

- **`core/topic_db.py`** — aggregates run history per topic into `TopicRecord`
  (runs, measured count, avg/best engaged-rate, last status). `winners()` ranks
  topics that engaged ("clone these"); `graveyard()` flags topics that measurably
  flopped (avg engaged-rate < `GRAVEYARD_RATE_FLOOR`, default 4%). Read-only,
  confidence-aware (`min_measured`), best-effort (empty on any storage error).
- **Avoid-list wired into discovery**: `graveyard_topics()` is folded into
  best-bet's exclude set (`GRAVEYARD_AVOID`, default on), so discovery stops
  re-pitching proven losers.
- **`scripts.ops topic-db --channel <id>`** prints Winners + Graveyard; also
  `py -m core.topic_db`.
- **Tests:** `tests/test_topic_db.py` (ranking, min-measured, floor, avoid-set,
  disabled, empty display). Suite 486 green.

### Human-context layer (Phase O) — persona + continuity (2026-06-23)

*The last open Phase O item. YouTube's 2026 policy rewards a consistent human voice
and continuity (a creator following a story), not fresh templated uploads.*

- **`core/channel_persona.py`** — `human_context_block(channel_id)` builds a prompt
  block from (1) an optional per-channel **persona** (`channels.json` "persona":
  perspective / tone / audience / recurring_segment / signoff) and (2) a
  data-driven **continuity** hint from real run history (`recent_input_topics` +
  `dominant_anchor`): "this channel has been covering X — acknowledge the ongoing
  storyline if it fits, never invent a prior video." Returns "" when there's
  nothing to add; bounded so it can't override anti-hallucination/grounding.
- **`config/channels.py`**: optional `persona` dict on `ChannelProfile`; a working
  persona added to the `tapin` channel.
- **`content_engine`**: the block is injected into the script prompt (after TOPIC).
- **Tests:** `tests/test_channel_persona.py` (persona rendering/order, arbitrary
  keys, anchor + theme continuity, thin-history no-op). Suite 480 green.

### Subject anchoring + future-dated-fact filter (2026-06-23)

*Live run: operator picked a "Kape" best-bet and pasted Kape facts, but the video
came out about a different fighter (Du Plessis) — variant generation generalised
the subject away ("the one fighter everyone is sleeping on") and the script then
followed a web-search tangent, silently abandoning the operator's key facts. The
same script also grounded on a web line claiming an event was "lost on July 18" (a
future date relative to the run).*

- **Subject preservation in variants** (`apis/topic_variants._subject_terms`):
  single-word proper-noun subjects (e.g. "Kape") that `extract_anchors`
  (franchise-only) misses are now pinned into the title rules — "keep the seed's
  subject, do not generalise to 'one fighter'".
- **Key-fact recenter** (`content_engine._maybe_recenter_on_key_facts`): if the
  finished script mentions *none* of the proper-noun subjects in the operator's
  pasted key facts, regenerate once to center it on them (accepted only if the
  rewrite covers a key-fact subject without gutting the script). Runs first, before
  insight/grounding. Default-on (`KEY_FACT_ANCHOR_ENABLED`).
- **Future-dated junk-fact filter** (`core/fact_recency.drop_future_dated`): drops
  corpus lines asserting a *completed* action on a date after today
  (`FACT_FUTURE_DATE_FILTER`, default on). High-precision — only fires when a
  future date co-occurs with a past-action verb, so legit previews survive.
- **`core/fact_grounding`**: public `specific_entities()` + `mentions()` helpers.
- **Tests:** `tests/test_fact_recency.py`, `tests/test_key_fact_anchor.py`
  (subject terms + recenter accept/noop/reject/disabled). Suite 474 green.

### Best-bet: confidence-weighted + diversified (2026-06-23)

*Same live run: for an NBA session, best-bet offered 3 stale UFC picks, all "low
confidence (1 sample)". Two root causes — fresh headlines were ranked by raw domain
rate (a 1-video 39% UFC domain outranked a 6-video 11% NBA domain), and NBA was
filtered out entirely because it isn't in the channel's configured on-brand set.*

- **Confidence-adjusted domain ranking** (`_adjusted_domain_rates`,
  `_domain_priority`): empirical-Bayes shrinkage toward the global mean, and
  adequately-sampled domains (≥ `MODERATE_SAMPLES`) rank above thin ones regardless
  of how high the thin average looks. Applied to both `get_best_bets` and the
  singular `get_best_bet` domain pick.
- **De-facto on-brand domains** (`_effective_allowed`): a domain the channel has
  actually published *with measured engagement* counts as on-brand even if it's not
  in the configured set — so NBA on a gaming/UFC channel is surfaced, not dropped.
- **Domain diversity** (`get_best_bets`): Phase-1 picks at most one per domain in
  confidence-first order (fresh headline preferred, else best historical run), so
  three 1-sample picks from one domain can't fill every slot; Phase 2 fills the rest.
  Historical rationales now carry the confidence note too.
- **Tests:** `tests/test_best_bet.py` — adjusted-rate shrink, domain-priority,
  well-sampled-leads-over-thin, no-single-domain-stacking. Suite 458 green.

### Original-insight injection (Phase O) — 2026-06-23

*Same live run flagged Authenticity 65/100: "no opinion/prediction/analysis beat —
reads as a neutral recap." The base prompt asked for opinion but a recap still
slipped past the gate's marker-based detector.*

- **`core/authenticity.has_insight()`** — public wrapper over the insight detector
  so generation can use the exact signal the gate scores on.
- **`content_engine._maybe_inject_insight`** — when a script has no take, inject one
  opinion/prediction/"why it matters" beat grounded **only** in the verified facts.
  Default-on (`INSIGHT_INJECTION_ENABLED`), premium tier; no-op when the script
  already has a take (most runs pay nothing); accepted only if it now reads as
  having a take and didn't shrink the script (≥90% word count). Runs **before** the
  grounding regen, so any specifics it introduces are still caught/cleaned.
- **Prompt**: added a detector-aligned STANCE bullet to the script prompt
  ("expect…", "here's why…", "my prediction…", grounded in the facts).
  `PROMPT_VERSION` → `content_engine_v7`.
- **Tests:** `tests/test_insight_injection.py` (inject / no-op-when-has-take /
  reject-no-take / reject-gutted / disabled) + `has_insight`. Suite 454 green.

### Anti-hallucination wave — regenerate-then-warn grounding + link cleanup (2026-06-23)

*From a live run where a script fused a real trade (Giannis→Heat, from pasted
links) with an invented one (Butler→Celtics): the grounding check flagged it but
the script shipped anyway, and link extraction had fed the model promo/teaser junk.*

- **Regenerate-then-warn grounding** (`core/content_engine._maybe_reground_script`):
  when the post-gen check flags specifics not in VERIFIED FACTS, regenerate **once**
  to strip/generalize the unsupported names/trades/numbers, accept the rewrite only
  if it reduces the unsupported count and keeps ≥60% of the word count, then warn on
  whatever remains. Default-on (`GROUNDING_REGEN_ENABLED`, `GROUNDING_REGEN_MIN`);
  premium tier; triggered only when something was flagged (most runs pay nothing).
- **Link-fact cleanup** (`core/link_facts._is_junk_line`): drop promo/nav
  boilerplate ("has the latest", "subscribe", "all rights reserved", …) and teaser
  questions ("Will the Bucks move Giannis?") from extracted article facts — index
  pages were poisoning the fact corpus, which is what the model then hallucinated
  around.
- **Tests:** `tests/test_grounding_regen.py` + link junk-filter cases in
  `tests/test_link_facts.py`. Suite 447 green.

### Credit-efficiency wave 3 — observability (2026-06-23)

*Third wave from [credit_efficiency.md](credit_efficiency.md) (O8 + O9): make the
credit layer visible.*

- **Cache-hit instrumentation (O8):** `apis/cache_manager.py` counts hits/misses
  per key-prefix (signal/source name); `flush_cache_stats()` merges in-process
  counters into `data/cache_stats.json` once per run (in `run_discovery`), so no
  per-lookup write. `get_cache_stats()` / `reset_cache_stats()` added; `get_cached`
  refactored to record each access.
- **Reliability dashboard (O9):** `core/reliability.py` (`gather`/`render`) +
  `py -m scripts.ops reliability` — Apify breaker/budget + persisted exhaustion,
  LLM disabled providers + daily spend vs budget, session-disabled signals, cache
  hit-rate by prefix, YouTube units. Read-only, fail-open. New public accessors:
  `llm_router.disabled_providers()`, `register_signals.disabled_signals()`.
- **Tests:** `tests/test_observability.py` (cache stats record/flush/persist/reset +
  reliability gather/render). Suite 433 green.

### Credit-efficiency wave 2 — operator spend ceilings (2026-06-23)

*Second wave from [credit_efficiency.md](credit_efficiency.md) (O4 + O7): graceful
degradation before the hard credit walls.*

- **Apify budget (O4):** `APIFY_MONTHLY_BUDGET_USD` — `apify_client._evaluate_apify_usage`
  trips (and persists) the breaker when monthly usage hits the operator's budget,
  before Apify's hard limit. Enforced on both the fresh and cached preflight paths;
  the status line shows the budget.
- **LLM daily budget (O7):** `LLM_DAILY_BUDGET_USD` — `core/llm_router` accumulates
  today's cross-run spend in `quota_state` (only when a budget is set), and once
  exceeded a `premium`/`extract` call downgrades to the free-first `cheap` chain.
  Pricing reuses `cost_meter.llm_cost_from_usage`; `reset_llm_spend()` test helper.
- **Tests:** Apify budget (trip-before-limit, persistence) in
  `tests/test_credit_efficiency.py`; LLM budget (spend tracking, downgrade,
  under-budget keeps premium) in `tests/test_llm_router.py`. Suite 425 green.

### Credit-efficiency wave 1 — persistence + LLM failover (2026-06-23)

*First implementation wave from [credit_efficiency.md](credit_efficiency.md) (O1/O2/O3/O5/O6).*

- **`core/quota_state.py`** (new): cross-run, TTL'd, fail-open store at
  `data/quota_state.json` — exhaustion records (`mark_exhausted`/`is_exhausted`) +
  a small TTL key/value cache (`set_value`/`get_value`). Seed of the eventual
  unified quota governor (O11). `config/paths.py` adds `QUOTA_STATE_FILE`.
- **Apify persistence (O2/O3):** `apis/apify_client.py` now seeds its breaker from
  persisted state (`_sync_persistent`), persists hard 401/402/403/limit failures
  (`_persist_exhausted`, `QUOTA_STATE_TTL_SECONDS`, default 6h), and caches the
  `/users/me` usage reading (`APIFY_USAGE_CACHE_TTL_SECONDS`, default 20m) so a
  fresh process skips the network preflight. A prior run's out-of-credits is
  remembered — no re-paid failing call next run.
- **Preflight skip (O1):** `apis/register_signals.will_use_apify(topic, channel_id)`;
  `core/pipeline.run_discovery` only preflights when a paid Apify signal actually
  survives skip/gating/breaker.
- **LLM failover + breaker (O5/O6):** `core/llm_router.complete` resolves a tier to
  a provider *chain* (`_resolve_chain`) and fails over on retryable errors
  (429/402/401/403/5xx/timeout); hard auth/quota disables that provider for the
  session (`_disable_llm`/`reset_llm_breaker`). Non-retryable errors propagate;
  explicit `provider=` pins one (no failover). Makes the free OpenRouter tier
  resilient (rate-limit → fall to DeepSeek).
- **Tests:** `tests/test_quota_state.py`, `tests/test_credit_efficiency.py`
  (Apify persistence + `will_use_apify`), router failover/breaker tests, and
  `tests/test_apify_client.py` isolated to a temp quota-state file. Suite 417 green.

### Multi-provider LLM router + credit-efficiency docs (2026-06-23)

- **`core/llm_router.py`:** unified router for every runtime LLM call. Task tiers
  — `cheap` / `extract` / `premium` — routed across **DeepSeek, OpenRouter, Ollama
  (local), OpenAI, Anthropic** (Groq wired but not default — signup gated; Doubao
  wired but skipped — China-region-locked). Free-first defaults: OpenRouter `:free`
  models anchor `cheap` (Ollama local fallback), DeepSeek-V3 anchors `extract` +
  `premium`. OpenAI-compatible providers share one client shape (different
  `base_url`); Claude uses the native messages API. Per-tier overrides
  `LLM_<TIER>_PROVIDER`/`_MODEL` and per-provider `{PROVIDER}_MODEL_<TIER>`; loads
  `.env` standalone; degrades gracefully (OpenAI-only behaves like the old code).
- **Call sites migrated** off the hardcoded OpenAI client: `core/content_engine.py`
  (final script/expand → premium; hook regen → cheap), `core/research_brief.py`
  (premium), `core/fact_enrichment.py` (extract — consolidated the duplicated raw
  Claude branch), `apis/topic_variants.py` (cheap), `assets/background_query.py`
  (cheap — merged the openai+anthropic duplicates), `assets/local_provider.py`
  (cheap). Only the multimodal thumbnail vision scorer stays on `core/llm_client.py`.
- **Cost meter:** real **per-provider token ledger** (`llm_router` records usage;
  `cost_meter.llm_cost_from_usage` prices it) replaces the word-count heuristic for
  LLM cost; free `:free`/Ollama calls priced at $0. `reset_usage()` per run in
  `run_discovery`. Pricing table for DeepSeek/OpenRouter/Llama/Ollama/OpenAI/Claude.
- **Config:** `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_MODEL`/`OLLAMA_BASE_URL`
  added to `settings` + `.env.example` (with the free-setup guidance).
- **Docs:** new [credit_efficiency.md](credit_efficiency.md) — credit/quota/spend
  optimization backlog (O1–O11); architecture, decisions (§14), debugging, roadmap,
  operating_plan updated.
- **Tests:** `tests/test_llm_router.py` (tier resolution, overrides, failover-ready
  routing, usage ledger, completion mocking) + `tests/test_cost_meter.py` ledger
  pricing. Suite green at 397.

### Multi-domain signal expansion (2026-06)

- **Finance:** `fred`, `sec_edgar`, `finnhub`, `coingecko` APIs.
- **Anime:** `anime` signal (AniList → Jikan chain).
- **Pop culture:** `tmdb`, `tvmaze`.
- **Music:** `lastfm`, `musicbrainz`.
- **Gaming+:** `twitch`, `igdb`, `trendingnow`.
- **Sports+:** `api_sports`; `stats_context` chain extended with nflverse/pybaseball.
- **Domains:** `finance`, `anime`, `popculture`, `music` in `infer_domain` + weight profiles; RSS in `data_sources.json`.

### Data reliability upgrade (2026-06)

- **Trends:** Removed archived **pytrends**; provider chain in `apis/trends_api.py` + `apis/signal_chain.py` (SerpApi → Glimpse → Wikipedia pageviews).
- **Stats:** `apis/balldontlie_api.py` + `STATS_PROVIDER_ORDER=balldontlie,scrapers` in `apis/stats_context_api.py`.
- **Competitors:** `analytics/youtube_rss.py` + RSS-first sync in `analytics/competitor_sync.py` (`COMPETITOR_SYNC_RSS=true`).
- **Reddit removed:** `apis/reddit_api.py`, `apis/reddit_intelligence.py` deleted; community context via `blog_rss` + `community_summary` in research brief.
- **Tapology:** scrape off by default (`TAPOLOGY_SCRAPE_ENABLED=false`).
- **Deps:** dropped `pytrends`, `praw`, `pandas` from `requirements.txt`.

### Analyst intelligence v2 (2026-06)

- **Trajectory:** `core/topic_trajectory.py` — snapshots in `data/topic_trajectory.json`, rising/peaking/decaying phases.
- **Corroboration:** `apis/signal_corroboration.py` — multi-source confidence; optional score adjustment in `composite_score`.
- **Opportunity window:** `core/opportunity_window.py` — demand vs competitor saturation (open/closing/closed).
- **Explainability:** `core/analyst_explain.py` — why now / why this / contrarian in reports.
- **Self-measurement:** `core/analyst_accuracy.py` — volume-gated hit-rate backtest.
- **New signal:** `wikipedia` pageviews (`apis/wikipedia_pageviews_api.py`).
- **Docs:** [analyst-intelligence.md](analyst-intelligence.md), [adding-a-data-source.md](adding-a-data-source.md).

### Intelligence layer & positioning (2026-06)

- **`core/intelligence_report.py`:** Markdown/JSON report from discovery + research brief + competitor pulse; CLI and `scripts.ops intelligence-report`.
- **`main.py`:** Menu option 3 (intelligence report only); `CONTENT_MODE=intelligence` skips production-tail warmup.
- **Docs:** [positioning.md](positioning.md), [case_study.md](case_study.md), [samples/intelligence_report_example.md](samples/intelligence_report_example.md).

### Codebase cleanup (2026-06)

- **Removed dead modules:** `legacy/` package, `core/signal_health.py` (duplicate of `core/ui.py`), orphaned `apis/community_analyzer.py` and `apis/query_optimizer.py`, unused `sports/router.py` + BallDontLie/SportsData helpers, broken `scripts/extract_luffy_art.py`, pre-Luffy `core/art/*.txt`, root `prospect_cache.json`, typo `sports/_init_.py`.
- **Trimmed:** `apis/api_registry.py` dead `execute_all`, `sports/espn.py` unused standings helpers.
- **Kept:** ASCII/Luffy startup UI (`core/ascii_art.py`, `core/data/luffy_ascii.txt`), `scripts/update_luffy_art.py` for refreshing bundled mascot art.

### Data sources expansion + brief v3 (2026-06)

- **Stats scrapers:** `apis/scrapers/` (Basketball Reference, Pro-Football-Reference, ESPN JSON) → signal `stats_context`.
- **Blog RSS signal:** `blog_rss` merges `config/seo/{channel}.json` + `config/data_sources.json` domain feeds.
- **Research brief:** `research_brief_v3` injects reference stat lines; RSS brief path uses expanded feeds.
- **Docs:** [data-sources.md](data-sources.md); architecture + roadmap updated.

### Phase K — YouTube thumbnail API (2026-06)

- **`youtube/thumbnails.py`:** Resolves thumbnail from `assets` row or `output/{channel}/thumbnails/`; calls `thumbnails.set` after successful upload (~50 quota units).
- **`YOUTUBE_THUMBNAIL_UPLOAD`:** `auto` (default) or `off`; ineligible channels log `ineligible` without failing the video upload.
- **Tests:** `tests/test_youtube_thumbnails.py`.

### Phase H + YouTube SEO tags (2026-06)

- **Research brief:** `core/research_brief.py` runs once after variant selection; RSS + Reddit intel; cached.
- **SEO:** `config/seo/tapin.json`, LLM `tags` in content package, upload via `enqueue_upload_job` / worker.
- **Refresh:** `py -m analytics.seo_refresh` → `data/seo_hints_{channel}.json`.
- **Provenance:** `tags_json`, `brief_version`, `prompt_version` on `content_runs` (`py -m storage.migrate_schema`).
- **Modules:** `apis/rss_feeds.py`, `apis/reddit_intelligence.py`, `core/signal_facts.py`, `core/seo.py`.

### Intelligence phase roadmap adopted (2026-06)

- **`docs/intelligence_phase.md`:** Post D–G plan — generation before measurement; Phases H–K; feature triage; architectural prerequisites (brief after variant selection, caching, provenance).
- **`docs/roadmap.md`:** Restructured — completed D–G; next H→K with prerequisites; volume-gated deferrals.
- **Prerequisites (since shipped):** research brief, RSS, Reddit intel, competitor sync, and Alembic baseline were documented here before implementation; see Phase H and Alembic entries above.

### Operator tooling, UFC research, and stability (2026-06)

- **`scripts/ops.py`:** Batch and individual operator commands (`all-setup`, `all-checks`, `all-analytics`, validate, seed, worker, tests).
- **`scripts/requeue_upload.py`:** List rendered-but-not-uploaded `content_runs`; queue upload jobs by `--run-id`.
- **Hybrid backgrounds (TapIn default):** `background_mode: hybrid`, `hybrid_local_ratio`, FFmpeg concat in `assets/composite.py`; local gameplay from `video/backgrounds/` plus stock B-roll.
- **UFC script accuracy:** `apis/ufc_context_api.py` (news + Reddit MMA), `apis/tapology_api.py` (event scrape + `data/tapology_cache.json`), `core/script_brief.py` (UFC matrix), stricter prompts in `core/content_engine.py` with JSON mode and signal facts injection.
- **Signals:** `tapology` and `ufc_context` registered in `apis/signals_bootstrap.py`; weights in `apis/topic_scorer.py` and `apis/learned_weights.py`.
- **`config.validate_channels`:** Validates root-level `background_mode`, `hybrid_local_ratio`, `asset_provider_order`; numeric-only `weight_overrides`.
- **Bug fixes:** `apis/register_signals.py` import path (`apis.cache_manager`); `youtube/upload.py` secrets under `config/secrets/`; truncated `content_engine.py` restored; signal cache atomic writes + retries + non-fatal failures (`apis/cache_manager.py`).
- **Docs:** `docs/debugging.md` — operator debugging guide; README and architecture updated for layout and new modules.

### Project root cleanup (2026-06)

- **Layout:** `config/channels.json`, `config/secrets/`, `data/` for runtime JSON; `core/content_engine.py`, `core/tts.py`, `apis/cache_manager.py`.
- **Removed from root:** duplicate facades, unused scripts → `legacy/`.
- **Migration:** `py -m storage.migrate_layout` moves legacy root files into `data/` and `config/secrets/` on first run.
- **README.md** at repo root; `ROADMAP.md` points to `docs/roadmap.md`.

### Analytics learning sprint (2026-06)

- **`learn_slots_from_analytics`:** Engagement-weighted weekday/hour slots from `publish_log` timed outcomes; `USE_LEARNED_POST_SLOTS=auto` in `get_post_schedule`.
- **`py -m analytics.learn_schedule`:** Compare static vs learned post schedules.
- **`py -m config.validate_channels`:** Validate `channels.json` (TTS, weights, post_schedule, OAuth paths).
- **Seed:** TapIn seed staggers `published_at` across slot windows for timing learning.
- **Tests:** Learned post timing, job `scheduled_at` claim gate, learned weight profile, channel validation.
- **`tzdata`:** Windows dependency for `zoneinfo` (America/New_York).

### Publish path hardening (2026-06)

- **Idempotency:** Unique `idempotency_key`; reuse single `publish_log` row per run; heal `pending` via YouTube uploads playlist title match before `videos.insert` (crash-window safe).
- **Quota:** `record_upload_usage()` on upload attempt, not only success.
- **Metrics:** Removed immediate post-upload `refresh_publish_metrics` from upload path and worker (use delayed `py -m analytics.sync_metrics`).
- **Migration:** `migrate_schema` dedupes duplicate keys and adds partial unique index on `idempotency_key`.

### Upload queue & slot reservation (2026-06)

- **`analytics/upload_queue.py`:** Reserved `youtube_publish_at` times from jobs + `publish_log`; CLI **Publish queue** in `main.py` and before upload prompts.
- **`next_optimal_post_time`:** Skips slots already in the queue; video 2+ get the next optimal time after prior reservations.
- **YouTube `publishAt`:** Option 4 uploads once; YouTube publishes at the reserved slot (PC off after upload).
- Docs: **`docs/post_scheduling.md`**

### Roadmap 1–2–3 — Upload, worker, analytics (2026-06)

- **`py -m youtube.check_setup`:** Validates TapIn OAuth, env, token scopes.
- **`youtube/oauth_setup`:** Requests `youtube.upload` + `yt-analytics.readonly` by default.
- **`analytics/youtube_metrics.py`:** YouTube Analytics API v2 `fetch_video_metrics`; worker + upload hook sync.
- **`py -m analytics.sync_metrics`:** Batch refresh for uploaded `publish_log` rows.

### Render + channel outputs (2026-06)

- **`video/render_video.py`:** `filter_complex` uses **`[0:v]` only** (stock audio stripped); **`-stream_loop -1`** + **`-t` audio duration**; vertical 1080×1920. Tested via **`tests/test_render_video.py`**.
- **`core/output_paths.py`:** Per-channel dirs `output/{channel}/audio|video|thumbnails`.
- **`analytics/youtube_metrics.py`:** Stub for post-upload metrics sync (`YOUTUBE_ANALYTICS_SYNC`).
- **`channels.json`:** TapIn `output_subdir`, OAuth token path, default privacy.

### Phase D–G — Upload, assets, signals, scaling (2026-06)

- **YouTube upload (Phase D):** OAuth flow (`youtube/oauth.py`, `py -m youtube.oauth_setup`), resumable `videos.insert` in **`youtube/upload.py`**, quota guard via **`apis/youtube_quota.py`**, idempotent **`publish_log`** rows (`idempotency_key`). Upload jobs complete only on `uploaded`; terminal failures mark **`jobs`** as failed.
- **Asset intelligence (Phase E):** **`Asset`** model, **`storage/repositories/assets.py`**, **`core/asset_recorder.py`** hooks after render; Pillow title-card thumbnails in **`assets/flux_thumbnail.py`**. **`storage/migrate_schema.py`** adds `idempotency_key` and `assets` on existing Postgres DBs. Asset DB writes log warnings and no longer fail the render path after successful ffmpeg output.
- **Research intelligence (Phase F):** **`apis/signals_bootstrap.py`** registers all providers on **`SignalRegistry`**; **`register_signals.py`** reads from registry. Optional **`USE_SIGNAL_SYNTHESIS`** adds `_synthesis` metadata. Removed unused **`draft_aggregator.py`**, **`prospect_scraper.py`**, **`video/background_selector.py`**.
- **Scaling (Phase G):** **`reclaim_stuck_running()`** on job repo + worker (`JOB_STUCK_MINUTES`). GitHub Actions **`.github/workflows/ci.yml`** runs `unittest discover`. Render path uses structured logging in **`video/render_video.py`**.

### Pipeline architecture

- Introduced **`core/pipeline.py`** as the single orchestration layer decoupled from CLI I/O.
- Added **`run_discovery()`** to fetch signals and score variants in parallel without generating content.
- Added **`PipelineResult`** / **`DiscoveryResult`** dataclasses with timings, variants, abort reasons, `channel_id`, and `run_id`.
- Split interactive flow in **`main.py`**: discovery → user variant choice → content preview → optional render via **`run_media_only()`**.
- Integrated **`core/run_recorder.py`** to persist every pipeline completion to **`content_runs`** and trigger learning updates.

### Signal scoring and learning loop

- Standardized signal shape in **`apis/signal_contract.py`** (`connected`, `active`, `score`, `status`, `status_detail`).
- Implemented domain-aware static weights in **`apis/topic_scorer.py`** (`infer_domain`, `get_default_weights`).
- **Wired learning into scoring:** `composite_score()` now applies:
  - Per-channel weight overrides from **`channels.json`**
  - Historical topic boost via **`channel_memory`** / `topic_scores`
  - Domain performance multiplier via **`performance_memory`** / `performance_entries`
- **Wired learning into pipeline:** `record_learning_outcome()` on successful runs (drafted/rendered).
- Single-active-signal penalty (0.75×) retained when only one signal is active.

### Database integration

- Added SQLAlchemy models: **`TopicScore`**, **`PerformanceEntry`**, **`ContentRun`**, **`PublishLog`**, **`Job`** (`storage/models.py`).
- Dual-write repository pattern: PostgreSQL when `DATABASE_URL` set, else JSON under **`data/`**.
- **`storage/init_db.py`** creates all tables via `create_all` (no migration history).
- **`storage/migrate_json.py`** for one-time import from legacy JSON memory files.
- Per-channel topic memory: Postgres filters by `channel_id`; JSON uses **`data/channel_memory/{channel_id}.json`** (default channel keeps **`channel_memory.json`**).

### Channel profiles and multi-channel

- Added **`channels.json`** and **`config/channels.py`** (`ChannelProfile`, `resolve_channel_id`).
- **`CONTENT_CHANNEL_ID`** env and **`main.py --channel`** flag.
- Pipeline and asset manager accept **`channel_id`**; per-channel asset provider order supported.

### Asset management (Phase 4)

- **`AssetProvider`** ABC and **`AssetResult`** type (`assets/base.py`, `assets/types.py`).
- Providers: **local** (`video/backgrounds/`), **Pexels**, **Pixabay** with download cache (`assets/cache/`).
- **`assets/manager.py`**: ordered fallback chain from env or channel profile.
- **`assets/catalog.json`**: deduplication metadata for stock downloads.
- **`assets/category.py`**: topic → search category for stock APIs.
- **`video/background_selector.py`**: removed; use **`assets/manager.py`** directly.
- **`assets/flux_thumbnail.py`**: Pillow title cards after render (Flux API optional).

### Performance optimizations

- **Parallel signal fetch** in `build_registry()` (`ThreadPoolExecutor`, one future per source).
- **Parallel variant scoring** in `run_discovery()` (up to 5 workers).
- **Parallel discovery bootstrap**: signals + variant generation concurrently (2 workers).
- **Signal cache** (`cache_manager.py`): 3-hour TTL in `signal_cache.json`, thread-locked read/write.
- **`CONTENT_SKIP_SIGNALS`**: omit slow sources (e.g. `trends`) without code changes.
- **YouTube quota tracking** (`apis/youtube_quota.py`, `youtube_quota.json`) to surface search quota usage.

### API integrations

- Central registry in **`apis/register_signals.py`** for signals including: youtube, reddit, trends, news, sports, live_scores, odds, rawg, steam, autocomplete, **tapology**, **ufc_context**.
- **YouTube search** signal with normalized errors and quota classification (`apis/youtube_api.py`).
- **Live scores** signal with ESPN-oriented game matching (`apis/live_scores_api.py`).
- **Draft-aware variants** (`apis/draft_policy.py`, `apis/entity_extractor.py`, `apis/topic_variants.py`).
- **OpenAI** content package with JSON mode, signal facts injection, anti-hallucination prompts (`core/content_engine.py`).
- **YouTube upload** (`youtube/upload.py`): OAuth, resumable `videos.insert`, `publishAt`, idempotent `publish_log`.
- **Job worker** (`jobs/worker.py`): processes upload/render jobs from DB/JSON queue.

### UI and developer experience

- **`core/ui.py`**: sectioned CLI, signal health legend, variant list, DB status line.
- **`core/logging.py`**: configurable quiet mode via `CONTENT_QUIET_LOGS` / `CONTENT_LOG_LEVEL`.
- **`config/settings.py`**: `.env` loader, centralized settings dataclass.
- **`.env.example`** expanded for DB, assets, channel, upload, and worker hints.
- **`requirements.txt`** pinned dependencies (OpenAI, Google API client, MoviePy, SQLAlchemy, PRAW, etc.).

### Documentation and housekeeping

- Added **`docs/`** package: `project_brief.md`, `architecture.md`, `roadmap.md`, `change_log.md`, `debugging.md`, `post_scheduling.md`.
- **`.gitignore`**: `data/` directory for local JSON fallbacks.

---

## Historical / pre-pipeline (inferred from structure)

The following components predate or sit beside the current pipeline and may reflect earlier experiments:

- **`draft_aggregator.py`**, **`prospect_scraper.py`**, **`video/background_selector.py`** — removed (unused).
- **`topic_strategist.py`** + **`apis/signal_synthesizer.py`** — alternate angle generation from title synthesis (not imported by pipeline).
- **`apis/api_registry.py`** + **`apis/signals_bootstrap.py`** — class-based registry now wired via `register_signals.build_registry()`.
- **`sports/`** package — standalone topic router for playoffs/player/standings (not wired to `core/pipeline.py`).
- Root **`channel_memory.json`** / **`performance_memory.json`** — legacy flat files still supported for default channel.

---

## Known issues / open items

- **Operator setup:** OAuth (`YOUTUBE_UPLOAD_ENABLED`, `py -m youtube.oauth_setup --channel tapin`) required before unattended publish.
- **Tapology scrape:** May return 403/blocked; use `ufc_context` + news; see **`docs/debugging.md`**.
- **OneDrive / signal cache:** Heavy parallel discovery can contend on `data/signal_cache.json`; cache failures are non-fatal but may disable caching for that run.
- **Alembic + FKs:** Use **`storage/migrate_schema.py`** today; full revisions should add FKs (`content_run_id` → `content_runs`) and formalize schema.
- **Metrics delay:** Run `py -m analytics.sync_metrics` after publish, not seconds after upload.
- **Dual JSON/Postgres** for default-channel memory: read prefers Postgres when `DATABASE_URL` is set.

See **`docs/debugging.md`** for symptom → fix tables.

---

## How to update this changelog

When shipping meaningful changes:

1. Add a dated section under `[Unreleased]` or a new version heading.
2. Reference modules and tables affected.
3. Note breaking changes to env vars, CLI flags, or DB schema.
4. Reconcile **`docs/roadmap.md`** checkboxes when a planned phase item is fully delivered.
5. Add symptom/fix notes to **`docs/debugging.md`** when operators hit new failure modes.
