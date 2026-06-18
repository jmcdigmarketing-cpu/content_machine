# Content OS — Roadmap

Product phase names are the source of truth. **Phases H–K** (intelligence) are specified in **[intelligence_phase.md](intelligence_phase.md)**.

Last updated: Domain expansion playbook (2026-06).

**New verticals:** [domain-expansion.md](domain-expansion.md) — finance, anime, pop culture, music, gaming/sports depth. One domain at a time; official APIs first.

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

## Next — Intelligence phase (H → K)

*Principle: **generation before measurement**. Full spec: [intelligence_phase.md](intelligence_phase.md).*

### Prerequisites (before / with Phase H)

- [ ] Alembic baseline + FKs (`content_run_id` on `publish_log`, `jobs`, `assets`)
- [x] Provenance columns on `content_runs`: `brief_version`, `prompt_version`
- [ ] Reddit OAuth + rate-limit-aware caching for agent workload
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

**Troubleshooting:** [debugging.md](debugging.md)

---

*Never commit `.env`, OAuth tokens, or `client_secrets.json`.*
