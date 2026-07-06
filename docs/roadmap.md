# Content OS — Roadmap

> **North star:** [vision.md](vision.md) — the v3 intelligence-systems vision
> ("operate media businesses," not "make videos"), a senior-level critique of it,
> and the revised 12-month architecture plan prioritized for defensibility,
> revenue, and learning advantage.
> **Operating plan:** [operating_plan.md](operating_plan.md) — pace/cost projections
> (2wk/1mo/3mo/6mo/1yr), the new-channel playbook, AI cost-per-run + reduction
> roadmap, side-income territories, ops/process hygiene, and competitive analysis.
> This roadmap is the tactical layer beneath both.

Product phase names are the source of truth. **Phases H–K** (intelligence) are specified in **[intelligence_phase.md](intelligence_phase.md)**.

Last updated: 2026-07-02 — **2026-07 focus wave shipped** on `fix/credit-efficiency-review` (PR #24); 613 tests green. Adds O10 reset-window auto-re-enable, opt-in semantic trade validation, the Phase S creator coach (`ops coach`) + weekly-digest next actions, and headless key facts for `auto_generate` — on top of the fact-first pipeline (angles at discovery, title after facts + script).

**New verticals:** [domain-expansion.md](domain-expansion.md) — finance, anime, pop culture, music, gaming/sports depth. One domain at a time; official APIs first.

**Where we are:** the discovery → script → render → publish pipeline is complete and the **learning loop is closed** — real YouTube engagement now feeds topic, length, and post-time recommendations. Current focus is widening data intake (Apify), tightening automation, and engineering hygiene. See "Next — current focus" below.

---

## Completed

### Phase 1 — Foundation

- [x] Discovery → content → optional render pipeline
- [x] OpenAI, TTS, FFmpeg vertical video, CLI

### Phase 2 — Database Layer

- [x] PostgreSQL + dual JSON repositories
- [x] `init_db`, `migrate_json`, `migrate_schema`

### Phase 3 — Efficiency & UI

- [x] Parallel signals/variants, cache, signal contract, health UI

### Phase 4 — Asset Management

- [x] Provider chain (local, Pexels, Pixabay), catalog, category detection
- [x] Postgres `assets` table + post-render recording
- [x] Pillow thumbnails per channel (`output/{channel}/thumbnails/`)

### Phases D–G (infrastructure)

- [x] **Upload:** OAuth, resumable `videos.insert`, idempotent `publish_log`, quota guard, job worker
- [x] **Signals:** `SignalRegistry` bootstrap, optional `USE_SIGNAL_SYNTHESIS`
- [x] **Scaling:** CI workflow, stuck-job reclaim, structured render logging
- [x] **Render:** Loop stock video to audio length, mute stock audio, 9:16 scale/crop

### Channel profiles

- [x] `channels.json`, weight overrides, asset order, OAuth token path, output subdirs
- [x] Interactive channel + upload prompts
- [x] TapIn profile with gaming weights + `output/tapin/`
- [x] Hybrid backgrounds (`background_mode`, `hybrid_local_ratio`, `assets/composite.py`)
- [x] Channel validation CLI + root-level asset/background fields

### Upload, scheduling, analytics (D–G continuation)

- [x] `py -m youtube.check_setup --channel tapin`
- [x] Optimal post scheduling, upload queue, YouTube `publishAt`
- [x] Publish idempotency hardening
- [x] Learn post slots from analytics (`learn_slots_from_analytics`)
- [x] Scheduled upload jobs: `scheduled_at` gate on worker claim
- [x] YouTube Analytics API + `py -m analytics.sync_metrics`
- [x] Learned weights (`apis/learned_weights.py`, `LEARNED_WEIGHT_BLEND`)

### Operator & research (pre–Phase H)

- [x] Operator batch CLI (`scripts/ops.py`)
- [x] Re-queue uploads (`scripts/requeue_upload.py`)
- [x] `ufc_context` + `tapology` signals; UFC `script_brief` + `content_engine` prompts
- [x] Docs: architecture, debugging, changelog

---

## Intelligence phase (H → K) — complete

*Principle: **generation before measurement**. Full spec: [intelligence_phase.md](intelligence_phase.md).*

### Prerequisites (before / with Phase H)

- [ ] Alembic baseline + FKs (`content_run_id` on `publish_log`, `jobs`, `assets`)
- [x] Provenance columns on `content_runs`: `brief_version`, `prompt_version`
- [ ] Reddit OAuth + rate-limit-aware caching for agent workload *(the OAuth signal backend half shipped 2026-07-06 — `apis/free_backends.py` `fetch_reddit_free` behind `SIGNAL_BACKEND`; agent-workload caching still open)*
- [ ] RSS feeds to reduce Tapology scrape dependency

### Phase H — Research Brief Engine (+ Reddit Agent + RSS) — **priority**

- [x] `core/research_brief.py` — typed `ResearchBrief`, built **once** after variant selection
- [x] `core/pipeline.py` hook; `content_engine` brief-first with signal-facts fallback
- [x] Reddit intelligence (`apis/reddit_intelligence.py`) — brief-only, cached
- [x] RSS headlines (`apis/rss_feeds.py`) — from `config/seo/{channel}.json`, brief-only
- [x] Brief/agent caching (topic + channel)
- [x] YouTube SEO: tags in content package + upload; `config/seo/`, `py -m analytics.seo_refresh`
- [x] Alembic baseline (`0001`–`0002`); provenance on `content_runs` via models + `migrate_schema`
- [x] Stats scrapers + `blog_rss` signal + `config/data_sources.json` — see [data-sources.md](data-sources.md)
- [x] Research brief v3 includes reference stat lines

### Phase I — Competitor Tracking

- [x] Config `config/competitors/{channel}.json` + `py -m analytics.competitor_sync`
- [x] Snapshot cache `data/competitors_{channel}.json` (quota-aware)
- [x] Daily sync: `py -m scripts.daily_sync` / `py -m scripts.ops daily-sync`
- [x] Auto-refresh on discovery if snapshot >24h (`COMPETITOR_SYNC_ON_DISCOVERY=auto`)
- [x] Feed discovery / brief / variants (`analytics/competitor_context.py`)

### Phase J — Minimal status view

- [x] `py -m scripts.ops status` / `py -m scripts.status`
- [x] Queue manager CLI + `py main.py` startup option 2 + upload option 5

### Queue operations

- [x] Re-queue after YouTube delete (`scripts.queue_manage`, `analytics.queue_manager`)
- [x] `publish_log` status `cancelled` + idempotency release for re-upload

### Phase K — Thumbnail generation (opportunistic)

- [x] Flux thumbnails in `assets/flux_thumbnail.py` + pipeline hook (`THUMBNAIL_MODE=auto|off`, `BFL_API_KEY`)
- [x] Live render progress (`core/render_progress.py`, `CONTENT_RENDER_PROGRESS=1`)
- [x] YouTube `thumbnails.set` after `videos.insert` (`youtube/thumbnails.py`, `YOUTUBE_THUMBNAIL_UPLOAD=auto|off`)
- [ ] Pillow remains fallback

### Phase L — Closed-loop recommenders (2026-06)

*All three share one pattern: `analytics` source when enough engagement history exists, sensible default otherwise, each with a rationale string.*

- [x] **Best Bet (topic)** — `core/best_bet.py`; `source="analytics"` path live once metrics sync working (engaged-rate by domain). **Confidence-weighted + diversified** (2026-06): empirical-Bayes domain shrinkage + adequately-sampled-domains-first ranking (`_adjusted_domain_rates`/`_domain_priority`), ≤1 pick per domain so thin 1-sample domains can't fill every slot, and measured-history domains count as on-brand (`_effective_allowed` — surfaces e.g. NBA on a gaming/UFC channel).
- [x] **Recommended post time** — `analytics/post_timing.py` (`get_recommended_time`); engagement bucketed by weekday/hour, domain-aware; surfaced in `main.py`, `auto_generate`, ops `recommend-time`
- [x] **Recommended length** — `core/length_recommender.py`; engaged-rate by length preset (uses `timings_json.length_preset`); `auto_generate --length auto`; ops `recommend-length`
- [x] YouTube Analytics sync hardened — validating probe query, clear "enable API"/scope guidance (`analytics/sync_metrics.py`)
- [ ] Backtest recommender accuracy vs. realised engagement once volume grows
- [x] Confidence thresholds / minimum-sample surfacing in the UI (`core/recommender_confidence.py`; low/moderate caveats on best-bet/post-time/length)

### Phase L2 — Apify data layer (2026-06)

*Catalog-driven external signals. Single source of truth: `config/apify_sources.json` (`apis/apify_catalog.py`).*

- [x] Apify client with key routing + local cache (`apis/apify_client.py`); `~`-form actor ids
- [x] `youtube_competitors` — top videos by **view velocity** (`apis/youtube_apify_signal.py`)
- [x] `twitter` — breaking news weighted by domain authority accounts (`apis/twitter_signal.py`)
- [x] `reddit`, `tiktok_trends` — community sentiment + viral angles
- [x] Per-domain targeting (`domain_targets`); fact formatting keeps competitor titles as context, not verified facts
- [x] Docs: [apify-data-sources.md](apify-data-sources.md)
- [ ] `youtube_comments` / `instagram_figures` — templated in catalog, not yet wired as signals
- [ ] Live-run tuning of actor inputs once observed against real topics

### Phase L3 — Idea intake (2026-06)

- [x] `py main.py` menu **option 5** — generate from a user idea or a **YouTube link** (`watch`/`shorts`/`youtu.be`)
- [x] `apis/youtube_api.extract_youtube_video_id` + `fetch_video_metadata` (title/channel for the seed)
- [x] Shared `_run_new_video_flow(seed_topic=...)`; best-bet skipped when idea supplied
- [x] Tests: `tests/test_youtube_idea_intake.py`

### Engineering quality baseline (2026-06)

- [x] `pyproject.toml` — canonical deps + tool config; `[dev]` and `[sports]` extras
- [x] `ruff` lint + format across the tree (clean); `python-dotenv` replaces hand-rolled `.env` parser
- [x] CI: lint + format-check + type baseline + tests on Python 3.10/3.11/3.12
- [x] `.pre-commit-config.yaml`; `.gitignore` covers tool caches
- [x] `youtube.readonly` scope added for publisher dup-check / OAuth reads
- [ ] **git remote** — repo initialised locally; create **private** GitHub remote and push
- [x] **`CLAUDE.md`** — project guide for AI coding agents (pipeline overview, `ops`/`main.py` entry points, signal architecture, LLM router tiers, test/lint commands, hard rules). Companion: [docs/claude_code_usage.md](claude_code_usage.md) (Claude Code modes/features specific to this repo).
- [ ] Tighten the mypy baseline (~94 errors → fix the real ones, e.g. `timings` value type)
- [ ] Annotate/retire the remaining best-effort broad `except Exception` handlers
- [ ] Raise test coverage on render + publish paths

---

## Recently shipped (2026-06)

All on branch `youtube-readonly-scope-and-roadmap` (PR #1), CI green:

- **Recommenders + analytics loop live** — best-bet (now **3 rotating options**), recommended length, recommended post-time; analytics sync (most-recent-3 with titles).
- **Phase O — authenticity/compliance**: pre-upload self-check, AI disclosure, cadence guardrail, competitor-outlier surface, monetisation CTAs.
- **Phase P — hook intelligence**: 0–100 hook scorer + opt-in regeneration.
- **Phase Q — captions**: proportional, sentence-aware timing.
- **Idea intake (option 5)** with cross-genre creative-brief threading.
- **MoneyWise finance channel** (2nd channel) + `infer_domain` word-boundary fix.
- **Apify hardening**: `set_cache` credit-burn fix, 201 handling, circuit breaker + preflight on/off check, per-variant signal reuse (discovery minutes → seconds).
- **Script prompt refinement**: recap-first VOICE block, filler ban-list, anti-padding Extended format.
- **Engineering baseline**: pyproject/ruff/mypy/pre-commit, CI on 3.11, 220 tests.
- **Brand kit** for MoneyWise (`assets/branding/moneywise/`).
- **Assessment**: `docs/assessment.md` (strengths/weaknesses/fixes).

---

## Next — current focus

*Prioritised fix queue, top first. `[S]`/`[M]`/`[L]` = effort.*

**Immediate (from live runs):** *(mostly shipped — see recency cycle + script-accuracy PR)*
1. ~~Manual fact feeding~~ — key facts + vault + `paste` block + char budget (`core/operator_facts.py`)
2. ~~Domain-aware signal gating~~ — shipped
3. ~~Auto-disable on credit/quota~~ — shipped (+ persisted Apify, LLM router)
4. ~~Live discovery feedback~~ — shipped

**Current focus (2026-07):** *(wave shipped 2026-07-02 — see below)*
1. ~~Fact-first generation pipeline~~ — shipped (angles at discovery, title after facts + script)
2. ~~O10 reset-window auto-re-enable~~ — shipped (`core/reset_window.py`; [credit_efficiency.md](credit_efficiency.md) O10)
3. ~~Semantic trade validation~~ — shipped opt-in (`core/trade_validation.py`, `SEMANTIC_TRADE_VALIDATION`)
4. ~~Creator coach surface (Phase S)~~ — shipped (`core/creator_coach.py`, `ops coach`; weekly digest gained "Next actions")

**Up next:** thumbnail A/B (Phase S remainder — the experiment harness now exists; needs a thumbnail lever + upload variation) · O11 remainder (migrate Apify + LLM router behind `core/quota_governor.py`). *(Shipped 2026-07-06: signal-breaker persistence + key-hash invalidation as the O11 governor seed — see [credit_efficiency.md](credit_efficiency.md) O11 — batch generation `ops batch-drafts`, and script-lever A/B experiments `ops experiment`.)*

➡ One-time: re-auth `youtube.readonly` (`py -m youtube.oauth_setup --channel tapin`) to activate the dup-upload check. MoneyWise needs its own `oauth_setup`.

---

## Market positioning (2026)

*From a scan of the short-form / creator-tooling market (OpusClip, AutoShorts, Revid, Higgsfield, vidIQ, TubeBuddy) and YouTube policy.*

**The defining shift — authenticity enforcement.** YouTube's "inauthentic content" policy (Jul 2025) plus the **Jan 2026 mass-termination wave** demonetised templated, synthetic-voiceover, volume-over-substance faceless channels. *Faceless is still fine — synthetic-and-shallow is not.* What survives: **original insight, real variation between videos, human context, substance over volume.** That is an existential constraint for a generation-first pipeline and reorders our priorities (Phase O).

**Where rivals are strong (our gaps):**

| Capability | Who has it | Us today |
|---|---|---|
| Virality / hook score 0–100, hold-rate prediction | OpusClip, Higgsfield | composite topic score only — no hook/retention predictor |
| Hook-first generation (first 3 s / 60 frames) | most 2026 tools | generic hook rule in the prompt |
| Burned animated captions, speaker reframe | effectively all | not burning captions (table stakes) |
| A/B testing title/thumb/desc → CTR/watch-time | TubeBuddy | generate variants, but no post-publish A/B loop |
| "Daily ideas" coach | vidIQ | best-bet (close — expand into a coach) |
| Clip-from-long-form (VOD / podcast → shorts) | OpusClip core | generation-only; idea-intake already accepts YT links |

**Our moat (lean in):** no competitor runs the **full closed loop** — decide → *research with verified facts* → generate → publish → learn — self-hosted, on an anti-hallucination / intelligence-report spine. vidIQ decides, TubeBuddy optimises, OpusClip clips; we do all three plus a sourcing layer they lack. Double down on **verifiable substance + the analytics learning loop**.

---

## Candidate phases — 2026 roadmap expansion (proposed)

*Brainstorm, market-grounded. Ordering reflects risk/impact, not commitment.*

### Phase O — Authenticity & monetisation safety  *(highest priority — existential)*
Turn the research spine into a compliance moat.
- [x] **Pre-upload authenticity self-check** — `core/authenticity.py`: variation / original-insight / substance score + checklist; `AUTHENTICITY_GATE=block` to enforce.
- [x] **Per-video variation guard** — shipped as the authenticity "variation" check (difflib vs recent uploads' script_preview).
- [x] **AI-content disclosure** — `core/description_extras.py`: in-description disclosure on every upload (YouTube's #1 compliance "do"); `AI_DISCLOSURE_ENABLED`, per-channel `ai_disclosure`.
- [x] **Cadence guardrail** — `core/cadence.py`: caps videos/rolling-week (recent + scheduled); `MAX_VIDEOS_PER_WEEK` (default 5); gates `auto_generate` (`--force` to override). Pairs with the variation check (variety + volume).
- [x] **Original-insight injection** — when a script reads as a neutral recap, inject one opinion/prediction/"why it matters" beat grounded only in verified facts (`content_engine._maybe_inject_insight`, `core/authenticity.has_insight`, `INSIGHT_INJECTION_ENABLED`). Runs before the grounding regen; default-on; no-op when a take already exists. Prompt also gained a detector-aligned STANCE bullet.
- [x] **Human-context layer** — per-channel persona (voice/tone/audience/recurring-segment/sign-off via `channels.json` "persona") + data-driven continuity callbacks to recent coverage, injected into the script prompt (`core/channel_persona.human_context_block`). Bounded so it can't override grounding; "" when unconfigured + thin history.
- [ ] **Voice variety** — vary TTS delivery; optional real-voice clone slot.

**From 2026 market research (shipped 2026-06):**
- [x] **Competitor "outlier" surface** — `core/outlier.py`: top view-velocity competitor video shown as a content prompt (every guide says "study over-performing competitors first").
- [x] **Alt-monetisation CTAs** — per-channel `monetization_cta` lines appended to descriptions (gaming/UFC is low-CPM; ad revenue alone underperforms).
- [ ] **Multi-language** — single script → translated script + localized TTS → per-language uploads. Real growth lever, **low priority** for the gaming/UFC niche; pairs with Phase Q captions. *(deferred — see Later horizons.)*

### Phase P — Hook & retention intelligence
- [x] **Hook-score 0–100** — `core/hook_score.py`: heuristic scorer (brevity, specificity, curiosity/contradiction, stakes; penalises weak openers) surfaced in the pipeline + auto_generate.
- [x] **Hook-first regeneration** — opt-in `HOOK_REGEN_ENABLED`: rewrites a weak opening line via the LLM, only swapping it in if it scores higher.
- [x] **Retention-curve modelling** — syncs the per-position audience-retention curve (`audienceWatchRatio` by `elapsedVideoTimeRatio`, stored on publish_log metrics) and aggregates it into a channel drop-off point (`core/retention.py`), confidence-gated (≥`RETENTION_MIN_VIDEOS`). Feeds the script prompt's pacing pivot (front-load before the measured cliff) + `ops retention` view. Activates as curves accrue.
- [x] **A/B variant loop** (single-channel attribution form) — a faceless channel can't double-publish without cannibalizing, so instead of head-to-head it attributes realized engagement to the published title's **structural pattern** (`core/title_features`), builds a per-channel pattern leaderboard (`core/title_experiments`, `scripts.ops title-patterns`), and surfaces "▲ proven pattern" on matching variants at selection time. Thumbnail A/B (true two-up) still open.
- [x] **Script-lever A/B experiments** — *shipped 2026-07-06:* controlled one-lever-at-a-time experiments (`core/experiments.py` lifecycle + `core/experiment_levers.py` arms: `hook_style`, `cta_style` + `core/experiment_stats.py` low-n-safe Bayesian winner detection). `py -m core.experiments start hook_style` → every batch draft gets the least-used arm's prompt directive, assignments persist in `data/experiments.json`, and `ops experiment` joins them to realized engaged-rates: "collecting" until ≥6 measured per arm, winner only at P(best) ≥ 95%. Fed by `ops batch-drafts` (volume-with-variation). Tests: `tests/test_experiments.py`.

### Phase Q — Captions & visual polish  *(table stakes)*
- [x] **Burned captions, properly timed** — `video/subtitles.py`: sentence-aware, tighter chunks (`CAPTION_WORDS_PER_LINE`, default 5), durations **proportional to word count** (was uniform 8-word lines). Already burned in the render command.
- [x] **Word-level animated captions** — real per-word timing from ElevenLabs `convert_with_timestamps` (no Whisper); `video/caption_timing.py` builds accurate SRT + karaoke-highlight ASS. `CAPTION_STYLE=word` (default, accurate SRT) / `karaoke` (animated, opt-in — verify with a render) / `plain`. Burned via the existing `subtitles` filter.
- [x] **Scene-matched b-roll** — `video/scene_plan.py` splits the script into timed beats (real word timings when available), one stock clip per beat concatenated (`assets/composite.build_multi_concat_command`). Opt-in `SCENE_MATCHED_BROLL`, fails safe to the normal background.
- [x] **Dynamic emphasis** — keyword pop (karaoke caption highlight) + beat-synced cuts (scene-matched b-roll) shipped; hook zoom-in remains an optional flourish.

### Phase R — Clip-from-source mode  *(market hedge)*
*The market's "real content" pivot; pairs with idea-intake, which already accepts YouTube links.*
- [ ] Ingest a long video / VOD / podcast (file or URL) → transcribe → find strong moments → cut vertical shorts with captions.
- [ ] Reuse the scoring / hook / caption stack from Phases P–Q.

### Phase S — Creator coach surface
- [x] Expand best-bet into a **"daily ideas + why"** coach view (vidIQ-style, but with our sourcing) — `core/creator_coach.py`, `py -m scripts.ops coach`: ranked ideas each with a *why*, plus recommended length/post-time, winning title patterns, retention pacing, and cadence headroom. Read-only + fail-open. *(2026-07-02)*
- [ ] **Thumbnail A/B** + CTR optimisation (Flux thumbnails already exist).
- [x] Weekly performance digest with concrete next actions — `analytics/weekly_report.build_next_actions`: the winners/losers per dimension become numbered operator instructions ("Lead with the 'fraud' angle again", "Retire the 'recap' angle"), noise-gated at ±3pp vs baseline. *(2026-07-02)*

### UI / experience — themeable skins  *(fun, on-brand)* — **shipped 2026-07-02**
*Builds on the existing braille ASCII art, `DiscoverySpinner`, and `print_domain_art`.*
- [x] **`CONTENT_UI_THEME=onepiece|zelda|pokemon|dbz|jjba|plain|default`** (`core/themes.py`) — each skin swaps the ANSI palette (16-color + auto-detected 256-color via `CONTENT_UI_COLOR_DEPTH`), spinner frames + themed loading copy, section glyphs, meter characters, startup tagline + inline mascot panel, publish celebration art, and a ≥90-score hype tag.
  - **Zelda** — ▲ spinner + glyphs, **heart-container meters** (❤❤♡♡♡ cadence/quota), "YOU GOT THE RENDERED VIDEO" item-get celebration, *SECRET FOUND* score tag.
  - **Pokémon** — Pokéball spinner (◓◑◒◐), "type advantage" loading copy, level-up celebration, *SUPER EFFECTIVE* score tag.
  - **DBZ** — ki-charge spinner, Scouter loading copy, **"IT'S OVER 9000!"** on composite ≥ 90, over-9000 celebration.
  - **JJBA** — ゴゴゴ menacing spinner + mascot, "ORA ORA scoring variants", **"TO BE CONTINUED ➡"** publish celebration, *MUDA MUDA* score tag.
- [x] Theme registry with per-channel skin via `"ui_theme"` in `channels.json` (env overrides); `plain` keeps logs/CI color- and art-free. Meters + milestones (`maybe_print_milestone`) + themed celebrations wired into main flow, cadence, `ops reliability`, and `ops coach`. Sections/banners now span the full terminal width (capped at 100 cols). Tests: `tests/test_themes.py`.

### Efficiency & integrations
> **Credit/quota/spend optimization backlog:** [credit_efficiency.md](credit_efficiency.md) — Apify preflight skip, cross-run breaker persistence, operator budgets, LLM provider failover, reliability dashboard, unified quota governor (O1–O11).
- [ ] **Whisper** locally for caption timing + clip transcription (enables Phases Q & R).
- [ ] **Cost / quota dashboard** — per-run API spend (OpenAI / Apify / YouTube units) in status. *(spec'd as O9 in [credit_efficiency.md](credit_efficiency.md); LLM half now ledger-priced.)*
- [x] **Multi-provider LLM router** (`core/llm_router.py`) — task-tier routing (cheap/extract/premium) across **DeepSeek, OpenRouter, Ollama (local), OpenAI, Anthropic** (Groq wired but not default — signup gated; Doubao wired but skipped — China-region-locked, ~$0 savings); OpenAI-compatible client shape + native Claude. Free-first defaults (**OpenRouter** free `:free` models anchor cheap, Ollama local fallback; **DeepSeek-V3** anchors extract+premium ≈ gpt-4o quality, ~10× cheaper), env-overridable per tier + per-provider `{PROVIDER}_MODEL_<TIER>`, graceful degradation, loads `.env` standalone. Consolidated the 3 ad-hoc Claude call sites + migrated content_engine / research_brief / fact_enrichment / topic_variants / background_query / local_provider. Real **per-provider token ledger** prices `cost_meter` (free `:free`/Ollama = $0). (`DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_MODEL`.)
- [x] **Local-LLM option (Ollama)** — folded into the router as the `ollama` provider (OpenAI-compatible, `OLLAMA_MODEL` + optional `OLLAMA_BASE_URL`); zero marginal cost in the ledger.
- [ ] **Router follow-ups** — route thumbnail vision scorer once multimodal is added to the router; add a provider failover (premium→cheaper on auth/quota error); surface per-provider spend in the cost line.
- [x] **Free in-process signal backends (Option 3)** — *spike done 2026-06-29; YouTube backend shipped 2026-07-01:* `apis/free_backends.py` (hybrid `yt-dlp` flat-rank → full-extract top-N) behind `SIGNAL_BACKEND=apify|free|auto` (default `apify` — unchanged behavior; `free` = keyless/zero-cost; `auto` = free-first with Apify fallback). Cost meter no longer bills a free-served `youtube_competitors` as an Apify run. *Reddit OAuth free backend shipped 2026-07-06* (`fetch_reddit_free`, official API via free script app — Reddit keyless *scraping* is 403-blocked; 429s feed the rate-limit cooldown). Twitter/TikTok stay Apify. Tests: `tests/test_free_backends.py`. Full write-up: [agent_reach_evaluation.md](agent_reach_evaluation.md).
- [x] **Per-platform rate-limit cooldown** — *shipped 2026-07-01:* free backends fail by 429 (rate-limit), not 402 (credit). Session breaker (`apis/register_signals.py`) now gives transient 429s a *disabled-until-T* cooldown (`SIGNAL_RATE_LIMIT_COOLDOWN_SECONDS`, default 15 min, 0 = off) instead of ignoring them; hard statuses still trip permanently, and `SIGNAL_BREAKER_INCLUDE_RATE_LIMIT=true` still promotes 429s to a full-session trip. "Next available" surfaces in `ops reliability` and the post-discovery signal-health panel (`youtube_competitors → 14:32`). Tests in `tests/test_circuit_breaker.py`.
- [x] **Script-accuracy follow-ups (2026-07-01)** — Apify 403 vs 402 messaging + shorter auth-failure TTL; `MAX_OPERATOR_KEY_FACTS` env cap; pipeline-end `finalize_run_observability()` for cache stats; `auto_generate` mirrors fact-grounding gate.
- [x] **Fact-first pipeline (2026-07-02)** — `core/operator_facts.py` (paste block, vault save-all, char budget); discovery → **angles** not titles; `core/title_generator.py` runs after facts + script; anti-slop title rules.
- [x] **O10 reset-window auto-re-enable (2026-07-02)** — `core/reset_window.py` encodes real reset cadences (YouTube daily 00:00 PT, Apify monthly `APIFY_RESET_DAY`, Odds monthly). Apify 402/monthly-limit exhaustion persists until the cycle reset (auth keeps 30m TTL, budget keeps flat TTL); quota-blocked YouTube uploads retry just after the real reset; reset times in `ops reliability`. `RESET_WINDOW_AUTO_ENABLE` master switch. Tests: `tests/test_reset_window.py`.
- [x] **Semantic trade validation (2026-07-02, opt-in)** — `core/trade_validation.py`: extracts `player → team` trade claims from the script and warns when the pair never co-occurs on a single fact line (catches fused trades token grounding passes, e.g. real Giannis→Heat + invented Butler→Celtics). `SEMANTIC_TRADE_VALIDATION` (default **off** — higher false-positive risk); warns after the Fact-grounding section in `main.py`/`auto_generate`, never blocks. Tests: `tests/test_trade_validation.py`.
- [x] **Headless key facts for `auto_generate` (2026-07-02)** — `--facts-file` (same parser as interactive `paste` mode — trade blocks work) + repeatable `--fact` lines; deduped/tip-filtered, saved in full to the vault, injected as ground truth, and echoed in the grounding report. Tests: `tests/test_auto_generate_facts.py`.
- [ ] **Webhook / n8n / Zapier out** — emit run + publish events for external automation.
- [x] **Batch generation** — *shipped 2026-07-06:* `py -m scripts.ops batch-drafts --channel tapin --count 3` (or `py -m core.batch_generation` with explicit topics / `--file ideas.txt`). N ideas → N draft scripts unattended: discovery → best variant → recommended length → script/title/description saved to `output/<ch>/drafts/<ts>-<slug>/` (`draft.md` + `meta.json` with hook score, authenticity verdict, grounding flags, cost). Render-free by design — no TTS spend, no cadence impact; feeds A/B + volume-with-variation. Tests: `tests/test_batch_generation.py`.
- [ ] **Observability** — structured run traces + timing dashboard (timings already captured).

---

## Later horizons

*Valuable, but intentionally pushed out.*

### Phase M — Multi-platform distribution  *(pushed back — far later)*
*Repurpose one rendered vertical to several surfaces. Publisher contract already exists (`publishing/`). Deferred behind authenticity (O), hook/retention (P), and captions (Q) — distribution multiplies whatever quality we ship, so it waits until the content itself is policy-safe and sharper.*
- [ ] **TikTok publisher** — `TIKTOK_CLIENT_KEY`/`SECRET` present; `TikTokPublisher` still unimplemented (in `DEFERRED_PLATFORMS`)
- [ ] Instagram Reels / Meta — `META_APP_ID`/`SECRET`, `INSTAGRAM_*` (keys still empty)
- [ ] Per-platform caption/hashtag shaping from existing SEO + TikTok-trend signal
- [ ] Cross-platform performance back into the learning loop (unify with YouTube engaged-rate)

---

## Recently shipped — recency & robustness cycle (2026-06)

*Focus: get current facts into scripts (events past the LLM cutoff) and stop wasted/wrong signal calls.*

- [x] **Manual key facts** — operator pastes verified facts injected as top-priority `OPERATOR KEY FACTS` ground truth (`core/content_engine.py`, `main.py`)
- [x] **Domain-aware signal gating** — UFC/sports topics skip gaming signals (rawg/steam/igdb) & vice-versa (`apis/register_signals.py`, `DOMAIN_SIGNAL_GATING`)
- [x] **Generalized circuit breaker** — any signal returning quota/auth/no-key auto-skips for the session (`apis/register_signals.py`, `SIGNAL_CIRCUIT_BREAKER`)
- [x] **Live discovery feedback** — spinner shows real phases + per-variant `Scoring variants N/M` (`core/ui.py` `DiscoverySpinner.report`, `core/pipeline.py` `run_discovery(progress=…)`)
- [x] **Tapology enabled** — `TAPOLOGY_SCRAPE_ENABLED=true` for live UFC fight data
- [x] **Live web search signal** — universal, never-gated; Tavily preferred + Brave fallback; feeds VERIFIED FACTS (`apis/web_search_api.py`, `TAVILY_API_KEY`/`BRAVE_SEARCH_API_KEY`)
- [x] **Obsidian vault connector** — auto-pulls topic-relevant fact bullets to pre-fill the key-facts prompt; diversified, open-ended capture (`core/obsidian_facts.py`, `OBSIDIAN_VAULT_PATH`)
- [x] **Apify out-of-credits guard** — first 402 marks the key exhausted; later actor calls on it short-circuit (no repeated failing round-trips that dragged discovery to 200-300s+) (`apis/apify_client.py`)
- [x] **Tag-pollution fix** — stop force-injecting domain-mixed `trending_tags` (fighter names bled onto gaming videos); trending tags stay offered to the LLM relevance-gated (`config/seo.py`)
- [x] **Filler-phrase fix** — script prompt no longer coaches the "but here's the thing" crutch; stock transitions banned verbatim (`core/content_engine.py`)
- [x] **Recommender confidence surfacing** — best-bet/post-time/length annotate thin sample bases (low/moderate confidence + sample count); raised length `min_total` so 4 samples no longer reads as authoritative (`core/recommender_confidence.py`, `core/length_recommender.py`, `analytics/post_timing.py`, `core/best_bet.py`)
- [x] **Per-run cost surfaced** — run summary shows estimated fully-loaded cost (llm/tts/apify/web breakdown) + an Apify out-of-credits warning when a key was exhausted this session (`core/cost_meter.py` `format_cost_line`, `apis/apify_client.py` `apify_credit_exhausted`, `core/ui.py`)
- [x] **Fact-grounding post-check** — flags script specifics (heroes/products/patch-versions) not backed by VERIFIED FACTS/key facts before publish; conservative multi-word + version detector (`core/fact_grounding.py`, surfaced in `main.py`). **Now regenerate-then-warn** (`content_engine._maybe_reground_script`, `GROUNDING_REGEN_ENABLED`): regenerates once to strip the unsupported specifics, then warns on the remainder. Pasted-link facts are junk-filtered first (`core/link_facts._is_junk_line`).
- [x] **RAWG relevance gate** — filters fuzzy RAWG matches ("Need for Speed Rivals" for *Marvel Rivals*) by topic token overlap + acronym (keeps GTA→Grand Theft Auto) so only the real game is injected as facts (`apis/rawg_api.py`)
- [x] **Domain-routed RSS** — feeds carry optional `domains` tags; gaming topics no longer pull MMA/soccer feeds (BBC Sport) and vice-versa; untagged feeds stay universal (`config/data_sources.py`, `config/seo.py`, `config/data_sources.json`, `config/seo/tapin.json`)
- [x] **Obsidian source capture** — links pasted in the key-facts prompt are appended to `<vault>/<channel>/_sources.md` (de-duped, channel-scoped, `[sources, research]`) and read back by `obsidian_facts.load_facts` on related topics — research brought in once is reusable, not discarded (`core/source_capture.py`, wired in `prompt_key_facts`). *Follow-up: also capture `web_search` result URLs.*
- [x] **Repo hygiene** — `.gitattributes` (LF/binary), ignore local background media, `.env.example` web-search keys surfaced, leaked-file-handle test fix; merged branches pruned (single-branch repo)

---

## Deferred (volume-gated)

*Do not build until publish volume supports meaningful correlations.*

- [ ] Thumbnail scoring → CTR
- [ ] Prompt performance analysis (after provenance shipped)
- [ ] Asset effectiveness ranking from `assets` history
- [ ] Full operator dashboard + Channel Command Center
- [ ] Tavily / broad web research
- [ ] Bluesky direction signal
- [x] Retire unused research stubs in `legacy/` (removed 2026-06)

### Asset intelligence (non-urgent)

- [ ] Reuse scoring from `assets` history for background selection

---

## Operator checklist

**Fast path:** `py -m scripts.ops all-setup --channel tapin` then `py main.py`

1. `py -m storage.migrate_layout`
2. `py -m storage.migrate_schema` (until Alembic baseline replaces ad-hoc DDL)
3. `py -m analytics.seed_tapin --channel tapin`
4. `py -m config.validate_channels --channel tapin`
5. `py -m youtube.check_setup --channel tapin`
6. Add clips to `video/backgrounds/` for hybrid mode
7. `YOUTUBE_UPLOAD_ENABLED=true` + `py -m jobs.worker --loop 30`

**`py main.py` menu:** 1) new video · 2) queue manager · 3) intelligence report · 4) sync analytics · 5) make a video from your own idea / a YouTube link

**Recommendation helpers:** `py -m scripts.ops recommend-time --channel tapin` · `recommend-length` · best-bet shown at startup

**Developer setup:** `pip install -e ".[dev]"` then `pre-commit install`; `ruff check .` · `ruff format .` · `mypy analytics apis core config storage`. Tooling config lives in `pyproject.toml`.

**Troubleshooting:** [debugging.md](debugging.md)

---

*Never commit `.env`, OAuth tokens, or `client_secrets.json`.*
