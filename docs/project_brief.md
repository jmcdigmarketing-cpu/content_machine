# Content OS — Project Brief

## Project purpose

Content OS (also referred to as **Content Machine** in code and CLI) is an automated content operating system for short-form vertical video production in sports and gaming niches. It discovers market signals, scores topic variants, generates scripts with an LLM, synthesizes voice audio, renders subtitled MP4s with stock or local backgrounds, and persists runs for learning and multi-channel operations.

The system is designed to evolve from a single-operator CLI into a shared infrastructure that supports multiple brands/channels, asset libraries, analytics, feedback loops, and queued publish workflows.

## Current capabilities

| Capability | Status | Primary modules |
|------------|--------|-----------------|
| Interactive content pipeline | Operational | `main.py`, `core/pipeline.py` |
| Multi-source signal discovery (12+ APIs) | Operational | `apis/register_signals.py`, `apis/cache_manager.py` |
| UFC research (Tapology + ufc_context) | Operational (scrape may 403) | `apis/tapology_api.py`, `apis/ufc_context_api.py` |
| Hybrid local + stock backgrounds | Operational (TapIn default) | `assets/composite.py`, `assets/manager.py` |
| Operator batch CLI | Operational | `scripts/ops.py`, `scripts/requeue_upload.py` |
| Channel config validation | Operational | `py -m config.validate_channels` |
| Normalized signal health reporting | Operational | `apis/signal_contract.py`, `core/ui.py` |
| Topic variant generation + scoring | Operational | `apis/topic_variants.py`, `apis/topic_scorer.py` |
| Learning-aware composite scoring | Operational | `apis/topic_scorer.py`, `channel_memory.py`, `performance_memory.py` |
| LLM content package (title/script/description) | Operational | `core/content_engine.py`, `core/script_brief.py` |
| TTS audio generation | Operational | `core/tts.py` |
| Vertical video render (FFmpeg + subtitles) | Operational | `video/render_video.py`, `video/subtitles.py` |
| Asset provider fallback chain | Operational | `assets/manager.py`, Pexels/Pixabay/local |
| PostgreSQL + JSON dual persistence | Optional | `storage/`, `data/` fallbacks |
| Content run ledger | Operational | `core/run_recorder.py`, `storage/repositories/content_runs.py` |
| Channel profiles | Operational | `config/channels.json`, `py -m config.validate_channels` |
| Publish log + idempotency | Operational | `youtube/upload.py`, `storage/repositories/publish_log.py` |
| Job queue + worker | Operational | `storage/repositories/jobs.py`, `jobs/worker.py` |
| YouTube upload + scheduling | Operational | `youtube/upload.py`, `publishAt`, upload queue |
| YouTube Analytics → learning | Operational | `analytics/youtube_metrics.py`, `sync_metrics`, `learned_weights` |
| Learned post slots | Operational | `learn_slots_from_analytics`, `USE_LEARNED_POST_SLOTS=auto` |

**Runtime entry points**

- `py main.py` — interactive CLI (`--channel`, `--queue-upload`)
- `py -m scripts.ops all-setup --channel tapin` — layout, DB, seed, validate, YouTube check
- `py -m scripts.requeue_upload --channel tapin` — list/queue uploads for rendered runs
- `py -m storage.init_db` / `migrate_layout` / `migrate_schema` — DB and file layout
- `py -m jobs.worker` — process pending jobs

**Operations guide:** `docs/debugging.md`

**System dependencies:** Python 3.10+, FFmpeg on `PATH`, API keys in `.env` (see `.env.example`).

## Completed phases

Aligned with the product roadmap source of truth:

| Phase | Summary |
|-------|---------|
| **Phase 1 — Foundation** | Pipeline orchestration, OpenAI content generation, ElevenLabs TTS, MoviePy/FFmpeg video path, utilities and logging. |
| **Phase 2 — Database Layer** | SQLAlchemy models, Postgres connection, dual JSON/Postgres repositories for topic and performance memory, migration helper. |
| **Phase 3 — Efficiency & UI** | Parallel signal/variant fetching, signal cache (3h TTL), standardized signal contract, CLI presentation layer. |
| **Phase 4 — Asset Management** | `AssetProvider` interface, Pexels/Pixabay/local chain, JSON catalog dedupe, category detection, env-driven provider order. |

## Planned phases (Intelligence — post D–G)

**Guiding principle:** *generation before measurement.* TapIn is data-starved (~42 videos, low median views); invest in better artifacts and external direction, not outcome-ML on noise. Full plan: **`docs/intelligence_phase.md`**.

| Phase | Focus | Status |
|-------|--------|--------|
| **H** | Research Brief Engine + Reddit agent + RSS | Planned (flagship) |
| **I** | YouTube competitor tracking (daily batch) | Planned |
| **J** | Minimal CLI status view | Planned |
| **K** | Flux thumbnail generation | Opportunistic |
| **Deferred** | CTR thumbnail scoring, prompt analysis, asset ranking, full dashboard, Tavily, Bluesky | Volume-gated |

**Prerequisites:** Alembic + FKs; `brief_version` / `prompt_version` on `content_runs`; Reddit OAuth/cache; RSS to offset Tapology 403.

**Already shipped (feeds Phase H):** `ufc_context`, `tapology`, `core/script_brief.py` (UFC rules matrix), `core/content_engine.py`.

See `docs/roadmap.md` for checkboxes.

## Major integrations

| Integration | Role | Module(s) |
|-------------|------|-----------|
| **OpenAI** | Script/title/description generation | `core/content_engine.py`, `core/llm_client.py` |
| **ElevenLabs** | Voice audio | `core/tts.py` |
| **Tapology (scrape)** | UFC event/bout context | `apis/tapology_api.py` |
| **News API + Reddit** | UFC/sports headlines | `apis/ufc_context_api.py`, `apis/news_api.py` |
| **YouTube Data API** | Search signal + (planned) upload/analytics | `apis/youtube_api.py`, `apis/youtube_quota.py`, `youtube/upload.py` |
| **Reddit (PRAW)** | Community signal | `apis/reddit_api.py` |
| **Google Trends** | Trend signal | `apis/trends_api.py` |
| **News API** | News signal | `apis/news_api.py` |
| **TheSportsDB / sports APIs** | Sports metadata | `apis/sports_data_api.py` |
| **ESPN (live scores)** | Live/final game signal | `apis/live_scores_api.py` |
| **Odds API** | Betting market signal | `apis/odds_api.py` |
| **RAWG / Steam** | Gaming signals | `apis/rawg_api.py`, `apis/steam_api.py` |
| **Autocomplete** | Query expansion signal | `apis/autocomplete_api.py` |
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

The near-term trajectory is completing the feedback loop (real uploads + analytics) while hardening channel profiles and the job queue, without rewriting the existing pipeline-centric architecture.

## Documentation vs codebase gaps

The following are implemented in code but **not** reflected in the root `ROADMAP.md` phase numbering the product brief uses above:

- Content run ledger, publish log, and job queue (partial Phases 6–7 in `ROADMAP.md`)
- Channel profiles and learning loop in `composite_score` (partial Phases 6 and 9 in `ROADMAP.md`)

See `docs/architecture.md` § *Inconsistencies and undocumented systems* and `docs/debugging.md` for operator troubleshooting.
