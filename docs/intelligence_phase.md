# Content OS — Intelligence Phase Roadmap (Post D–G)

Principal-architect recommendation for the transition from **infrastructure** to **intelligence**. Grounded in reconciled project docs and TapIn’s early performance profile (~42 videos, median ~70 views, minimal subscriber base — **data-starved** for outcome-driven ML).

**Related:** [roadmap.md](roadmap.md) (phase checklist), [architecture.md](architecture.md), [debugging.md](debugging.md).

---

## Guiding principle: generation before measurement

Phases D–G delivered upload, signals, assets, and learning *plumbing*. Closed-loop features that correlate thumbnails, prompts, or assets to CTR **need volume**; at current scale they mostly learn from noise.

Leverage **now** lives in:

1. **Generation** — better hooks, angles, and packaging per video.
2. **Direction** — what to make next from **external** signal (competitors, RSS, community), not internal outcomes.

**Measurement** (thumbnail→CTR models, prompt-performance analysis, asset effectiveness ranking, analytics dashboards) is **deferred** until publish volume justifies correlations.

**Exception:** cheap **provenance instrumentation** ships early so future measurement is attributable (`brief_version`, `prompt_version` on `content_runs`).

---

## TapIn context (why this order)

| Observation | Implication |
|-------------|-------------|
| Low view median, near-zero subs/shares | Don’t optimize on internal CTR curves yet |
| Debate/drama formats perform relatively better | Brief should surface controversy, angles, sentiment |
| Tapology scrape often 403 | RSS + Reddit + news are more reliable brief inputs |
| Infrastructure ready | Next dollar is quality of **one** artifact + **topic choice** |

---

## Feature triage

| Feature | Class | Verdict |
|---------|-------|---------|
| Research Brief Engine | Generation | **Build first** — flagship |
| Reddit Intelligence Agent | Generation (brief input) | **Build with brief** |
| RSS (MMA Fighting, Dexerto, IGN, Polygon, ESPN, …) | Generation (brief input) | **Build with brief** — cheap, reliable; reduces Tapology scrape dependency |
| YouTube Competitor Tracking | Direction | **Second** — useful at any volume |
| Minimal status view (CLI) | Ops | **Third** — 80/20 of dashboard/command-center |
| Flux thumbnail *generation* | Generation | Opportunistic (Phase K) |
| Thumbnail *scoring → CTR* | Measurement | **Defer** (volume-gated) |
| Prompt performance *analysis* | Measurement | **Defer** (instrument now, analyze later) |
| Asset effectiveness ranking | Measurement | **Defer** (volume-gated) |
| Operator dashboard + Channel Command Center | Ops + Measurement | **Defer** |
| Tavily (broad web) | Generation | **Defer** — RSS/Reddit/news cover niches cheaper |
| Bluesky | Direction | **Defer** — thin niche signal today |

---

## Architectural prerequisites

### Brief placement in the pipeline

```
run_discovery()     → signals + variants + scores (unchanged)
       ↓
user selects variant
       ↓
run_pipeline()      → build_research_brief() ONCE for selected topic
       ↓
generate_content_package(brief=…)  → primary LLM input
```

- **Do not** run the brief inside per-variant discovery scoring (5× cost/latency).
- **Do** run after variant selection, before `generate_content_package`.
- **Fallback:** if brief LLM fails, use today’s per-signal facts (`_format_signal_facts`) — never block render.

### Distinction from `core/script_brief.py`

| Module | Role today / planned |
|--------|----------------------|
| `core/script_brief.py` | Static UFC/script **rules matrix** (weight class, event accuracy) |
| `core/research_brief.py` (new) | Dynamic **ResearchBrief** from signals + Reddit agent + RSS (narrative, sentiment, controversy, angles, evidence, format) |

Both may feed `content_engine`; research brief is the flagship generation input.

### Provider integration

- Reddit agent + RSS as **registered providers** via `apis/signals_bootstrap.py` / `SignalRegistry`.
- Outputs feed the **brief builder**, not raw scorer weights (unless explicitly designed later).
- **Caching:** brief + agent outputs keyed by `topic + channel_id` (extend `apis/cache_manager.py` and/or snapshot on `content_runs`).
- Reddit summarization is expensive — no recompute on retry.

### Competitor tracking

- **Scheduled daily ingestion** — not per pipeline run.
- Own table (`competitors` / `competitor_snapshots`); shares `apis/youtube_quota.py` budget.
- Feeds discovery / `topic_variants` and optionally the research brief.

### Provenance (ship with Phase H)

Add to `content_runs` (Alembic, not ad-hoc `migrate_schema` only):

- `brief_version` — e.g. `research_brief_v1`
- `prompt_version` — e.g. `content_engine_v2`

Enables future prompt-performance analysis without retrofitting history.

---

## Tech debt to clear first

| # | Item | Why before H |
|---|------|----------------|
| 1 | **Alembic baseline + FKs** | Brief/competitor tables + provenance columns; add `content_run_id` FKs on `publish_log`, `jobs`, `assets` |
| 2 | **Reddit OAuth + rate-limit cache** | Agent summarization exceeds scalar PRAW signal load |
| 3 | **Tapology fragility** | RSS augments/replaces 403-prone scrape |
| 4 | **Brief on critical path** | Singleton LLM client, timeout/retry, graceful degradation |

Stop extending schema-only via `storage/migrate_schema.py` once Alembic baseline lands.

---

## Phase H — Research Brief Engine (+ Reddit Agent + RSS)

**Purpose:** Convert disconnected signals into one structured **ResearchBrief** as the primary LLM input: narrative, audience sentiment, controversy score, debate angles, supporting evidence, recommended format.

**Inputs:** existing signals, Reddit intelligence agent, niche RSS feeds.

| Area | Files / modules |
|------|-----------------|
| Brief core | `core/research_brief.py` — typed `ResearchBrief`, `build_research_brief()` |
| LLM consumer | `core/content_engine.py` — brief-first prompts; fallback to signal facts |
| Pipeline hook | `core/pipeline.py` — call brief once after variant selection |
| Reddit | `apis/reddit_api.py` → agent path; PRAW auth + cache |
| RSS | new `apis/rss_feeds.py` (or `apis/rss_*.py`); channel-configurable feed list |
| Registry | `apis/signals_bootstrap.py`, `apis/register_signals.py` |
| Cache | `apis/cache_manager.py` |
| Schema | `alembic/` baseline; `storage/models.py` — provenance columns |
| Config | `config/channels.json` — per-channel RSS list, brief toggles |

**Risk:** Medium — extra LLM call on critical path. **Mitigate:** cache + fallback.

**Benefit:** Improves every video immediately; no outcome data required; aligns with TapIn debate/drama winners.

**Checklist:**

- [ ] Alembic env + initial revision (FKs + provenance)
- [ ] `ResearchBrief` schema + builder
- [ ] RSS provider(s) registered
- [ ] Reddit agent (summarize, not scalar score only)
- [ ] Pipeline: brief after variant pick
- [ ] `content_engine` consumes brief
- [ ] Cache brief by topic+channel
- [ ] Tests: brief fallback, RSS parse, pipeline smoke with mocked brief

---

## Phase I — Competitor Tracking

**Purpose:** Track selected channels’ titles, upload times, view velocity, topic patterns; inform **what to make** and enrich brief/discovery.

| Area | Files / modules |
|------|-----------------|
| Ingestion | new `jobs/competitor_sync.py` or `analytics/competitor_sync.py` (daily) |
| Storage | `competitors`, `competitor_videos` (or snapshots) tables |
| Quota | `apis/youtube_quota.py` — shared daily budget |
| Discovery | `apis/topic_variants.py`, optional brief injection |
| Config | `config/channels.json` — `competitor_channel_ids` |

**Risk:** Medium — YouTube Data API quota. **Mitigate:** daily batch, strict cap, no per-run calls.

**Benefit:** External direction signal that works at **any** audience size.

**Checklist:**

- [ ] Schema + repository
- [ ] Daily job + ops CLI hook
- [ ] Quota governor integration
- [ ] CLI/doc: how to add competitor channels for TapIn

---

## Phase J — Minimal status view

**Purpose:** One read-only surface: publish queue, upload status, API/quota health, recent runs, per-channel summary.

| Area | Files / modules |
|------|-----------------|
| CLI | `py -m scripts.ops status` or `py -m core.status` |
| Data | reuse `publish_log`, `jobs`, `content_runs`, signal health helpers |
| Optional later | thin FastAPI page over same queries |

**Risk:** Low.

**Benefit:** ~80% of dashboard/command-center value for daily ops.

**Checklist:**

- [ ] `status` command in `scripts/ops.py`
- [ ] Channel filter `--channel tapin`
- [ ] Quota + OAuth summary lines

---

## Phase K — Thumbnail generation upgrade (opportunistic)

**Purpose:** Flux-generated thumbnails vs Pillow title cards for clickability.

| Area | Files / modules |
|------|-----------------|
| Generation | `assets/flux_thumbnail.py` |
| Pipeline | `core/pipeline.run_media_only` hook after render |
| YouTube API | `youtube/thumbnails.py` — `thumbnails.set` after upload (`YOUTUBE_THUMBNAIL_UPLOAD=auto`) |

**Risk:** Low–medium (provider cost).

**Benefit:** Better packaging now; **scoring vs CTR deferred**.

---

## Deferred (volume-gated or later)

| Capability | Gate |
|------------|------|
| Thumbnail scoring → CTR model | Enough published videos + Analytics history |
| Prompt performance analysis | Provenance columns + volume |
| Asset effectiveness ranking | Render/upload volume + `assets` history |
| Full web dashboard + Channel Command Center | Ops need + volume |
| Tavily / broad web research | RSS + Reddit + news sufficient for niches |
| Bluesky direction signal | Thin signal today |
| Heavy learned-weight replacement from sparse outcomes | Already partially built; treat as low trust until N↑ |

**Instrument now; analyze when correlations are meaningful.**

---

## Bottom line

Next cycle: **make content people click and watch** (brief + Reddit + RSS) and **get sharper on what to make** (competitors) — not more systems to measure a channel that does not yet produce enough outcomes to measure.

Keep provenance hooks so the measurement phase is ready the moment volume justifies it.

---

*Adopted into project docs 2026-06. Implementation status: see [roadmap.md](roadmap.md) Phases H–K.*
