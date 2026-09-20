# Content OS — Project Brief

> **Class:** charter · **Status:** living · **Reviewed:** 2026-09-20

## Project purpose

Content OS (also referred to as **Content Machine** in code and CLI) is an automated content operating system for short-form vertical video production in sports and gaming niches. It discovers market signals, scores topic variants, generates scripts with a **free-first LLM router**, synthesizes voice audio, renders subtitled MP4s with stock or local backgrounds, publishes to YouTube, and closes a learning loop from real engagement.

The system is designed to evolve from a single-operator CLI into a shared infrastructure that supports multiple brands/channels, asset libraries, analytics, feedback loops, and queued publish workflows. North star: [vision.md](vision.md) — operate media businesses, not just make videos.

## Current capabilities

| Capability | Status | Primary modules |
|------------|--------|-----------------|
| Interactive content pipeline | Operational | `main.py`, `core/pipeline.py` |
| Multi-source signal discovery | Operational | `apis/register_signals.py`, `apis/cache_manager.py` |
| UFC research | Operational | `apis/mma_stats_api.py`, `apis/ufc_context_api.py` (Tapology scrape **retired**, Cloudflare 403) |
| Hybrid local + stock backgrounds | Operational (TapIn default) | `assets/composite.py`, `assets/manager.py` |
| Operator batch CLI | Operational | `scripts/ops.py` (~40 subcommands) |
| Channel config validation | Operational | `py -m config.validate_channels` |
| Normalized signal health reporting | Operational | `apis/signal_contract.py`, `core/ui.py`, `ops feeds` |
| Topic variant generation + scoring | Operational | `apis/topic_variants.py`, `apis/topic_scorer.py` |
| Learning-aware composite scoring | Operational | `apis/topic_scorer.py`, `channel_memory.py`, `performance_memory.py` |
| LLM content package (title/script/description) | Operational | `core/content_engine.py`, `core/script_brief.py`, `core/llm_router.py` |
| TTS audio generation | Operational | `core/tts.py` (ElevenLabs default; Piper/Kokoro/XTTS/Qwen local, $0) |
| Vertical video render (FFmpeg + captions) | Operational | `video/render_video.py`, `video/subtitles.py`, `video/caption_retext.py` |
| Asset provider fallback chain | Operational | `assets/manager.py`, Pexels/Pixabay/local |
| PostgreSQL + JSON dual persistence | Optional | `storage/`, `data/` fallbacks |
| Run ledger + quality + traces | Operational | Pillar 1: `core/run_trace.py`, `core/run_quality.py`, `ops traces` / `dossier` |
| Channel profiles | Operational | `config/channels.json`, `py -m config.validate_channels` |
| Publish log + idempotency | Operational | `youtube/upload.py`, `storage/repositories/publish_log.py` |
| Job queue + worker | Operational | `storage/repositories/jobs.py`, `jobs/worker.py` |
| YouTube upload + scheduling | Operational | `youtube/upload.py`, `publishAt`, upload queue |
| YouTube Analytics → learning | Operational | `analytics/youtube_metrics.py`, `sync_metrics`, best-bet / length / post-time |
| 2026 authenticity / cadence | Operational | `core/authenticity.py` (semantic paraphrase arm), `core/cadence.py` |
| Free ($0) mode | Operational | `core/run_mode.py`, `ops free-doctor` |

**Runtime entry points**

- `py main.py` — interactive CLI (`--channel`, `--queue-upload`)
- `py -m scripts.ops all-setup --channel tapin` — layout, DB, seed, validate, YouTube check
- `py -m scripts.ops reliability` — credit/quota/breaker/cache dashboard
- `py -m scripts.requeue_upload --channel tapin` — list/queue uploads for rendered runs
- `py -m storage.init_db` / `migrate_layout` / `migrate_schema` — DB and file layout
- `py -m jobs.worker` — process pending jobs

**Operations guide:** `docs/debugging.md`

**System dependencies:** Python 3.10+, FFmpeg on `PATH`, API keys in `.env` (see `.env.example`).

## Completed phases

Aligned with the product roadmap source of truth ([docs/roadmap.md](roadmap.md)):

| Phase | Summary |
|-------|---------|
| **Phase 1 — Foundation** | Pipeline orchestration, LLM content generation, TTS, FFmpeg video path, utilities and logging. |
| **Phase 2 — Database Layer** | SQLAlchemy models, Postgres connection, dual JSON/Postgres repositories, Alembic `0001`–`0004`. |
| **Phase 3 — Efficiency & UI** | Parallel signal/variant fetching, signal cache, standardized signal contract, CLI presentation layer. |
| **Phase 4 — Asset Management** | `AssetProvider` interface, Pexels/Pixabay/local chain, JSON catalog, category detection. |
| **D–G** | Upload, OAuth, scheduling, analytics sync, learned weights. |
| **H–K** | Research brief, competitor tracking, `ops status`, Flux thumbnails. |
| **L** | Closed-loop recommenders (best-bet, length, post-time). |
| **Pillars 1–7** | Run ledger, video grading, Fact Engine 2.0, Obsidian vault OS, agent layer, video provider seams, SkillOpt. |

## Current pickup (not a new phase)

**Guiding principle:** *generation before measurement.* Recommenders still sit at ~10 measured run-linked videos vs a 15-sample gate — do not build volume-gated backtests yet. Full plan: **`docs/intelligence_phase.md`** (historical) and **`docs/roadmap.md`** (tactical).

| Item | Focus | Status |
|-------|--------|--------|
| **Recommended next 5** | Pre-run gate, oauth tests + `coverage` extra, pronunciation lexicon, allocated vs marginal cost, numeric/record grounding | Open — [roadmap.md](roadmap.md) |
| **$0 TTS switch** | Piper is technically unblocked (captions retexted); operator voice judgment + duration re-bench | Operator call |
| **Pillar 6 remainder** | CUDA torch on the 4070 Ti; clip-from-source; storyboard | Parked / not started |
| **Deferred** | CTR thumbnail scoring, prompt/asset ranking, full dashboard, Phase M (TikTok/Reels) | Volume-gated / later |

See `docs/roadmap.md` for checkboxes and candidates 56–90 (viability / short-term success / real-world cost).

## Major integrations

| Integration | Role | Module(s) |
|-------------|------|-----------|
| **LLM router (free-first)** | Script/title/description + vision; DeepSeek / OpenRouter / Ollama, OpenAI/Claude opt-in | `core/llm_router.py`, `core/content_engine.py` |
| **ElevenLabs** | Default voice audio (~91% of a rendered run); local Piper/Kokoro/XTTS/Qwen meter $0 | `core/tts.py` |
| **API-SPORTS MMA** | Fighter records/physicals (replaced Tapology) | `apis/mma_stats_api.py` |
| **News API + RSS** | UFC/sports headlines; 37/37 feeds monitored | `apis/ufc_context_api.py`, `apis/rss_feeds.py`, `ops feeds` |
| **YouTube Data + Analytics** | Search, comments, upload, metrics, quota | `apis/youtube_api.py`, `apis/youtube_quota.py`, `youtube/upload.py` |
| **Reddit** | Free OAuth backend; Apify actor retired | `apis/free_backends.py` |
| **Apify (remaining)** | `tiktok_trends` + `youtube_competitors` only | `apis/apify_client.py` |
| **Google Trends** | Trend signal | `apis/trends_api.py` |
| **TheSportsDB / sports APIs** | Sports metadata | `apis/sports_data_api.py` |
| **ESPN (live scores)** | Live/final game signal | `apis/live_scores_api.py` |
| **Odds API** | Betting market signal | `apis/odds_api.py` |
| **RAWG / Steam** | Gaming signals | `apis/rawg_api.py`, `apis/steam_api.py` |
| **Tavily / Brave / DuckDuckGo** | Web search (DuckDuckGo in Free mode) | `apis/web_search_api.py` |
| **Pexels / Pixabay** | Stock portrait video | `assets/pexels_provider.py`, `assets/pixabay_provider.py` |
| **PostgreSQL** | Durable storage | `storage/db.py`, `storage/models.py` |
| **FFmpeg** | Final video mux/subtitles | `video/render_video.py` |

## Long-term vision

Content OS aims to operate as a **multi-tenant content factory**:

1. **Shared core** — one pipeline, signal registry, asset library, and job system.
2. **Many channels** — isolated profiles (niche, weights, credentials, output folders) with per-channel learning.
3. **Closed-loop optimization** — discovery scores → production → publish → platform analytics → adjusted weights and topic memory.
4. **Operational scale** — queued renders/uploads, quota-aware API usage, observability, and automated tests in CI.
5. **Asset intelligence** — centralized catalog (Postgres + object storage), generated thumbnails, and reuse across channels.

The near-term trajectory is **earning measured publishes cheaply** (TTS is ~91% of rendered cost) without violating the 2026 authenticity policy, then MoneyWise as the high-RPM second channel. Pickup order: [docs/roadmap.md](roadmap.md) recommended next 5.

## Documentation vs codebase gaps

The following used to lag the code; living docs were reconciled 2026-08-20:

- H–K and Pillars 1–7 are **shipped**, not planned (this brief and [architecture.md](architecture.md)).
- Tapology is **retired**; fighter facts come from `mma_stats`.
- `content_run_id` FKs shipped in Alembic `0004`.
- Remaining drift lives in dated orphan docs (`next_ideas_2026-07.md`, `code_audit_2026-07.md`, …) which keep supersession headers on purpose.

See `docs/architecture.md` § *Inconsistencies and undocumented systems*, `docs/HANDOFF_SYNOPSIS.md` for session state, and `docs/debugging.md` for operator troubleshooting.
