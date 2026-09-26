# Content Machine (Content OS)

**Content Machine** is the engine — this repo: the pipeline, signal layer and CLI. **Content OS** is the operator application built on it (desktop app, review booth, tray; decisions §33).

Python CLI for short-form video: discover signals → score topics → LLM script → TTS → FFmpeg render → optional YouTube publish. With a closed analytics learning loop (best-bet topic, recommended length + post-time) and a 2026-policy compliance layer (authenticity check, AI disclosure, cadence guardrail).

**Channels** (`config/channels.json`, domain-driven): `tapin` — gaming & UFC shorts · `moneywise` — finance (markets/crypto/personal finance). Add another by adding a profile + `config/seo/{id}.json`.

Every doc, by class and status: [docs/README.md](docs/README.md). What happens next:
[docs/master_plan.md](docs/master_plan.md) (horizons) and [docs/roadmap.md](docs/roadmap.md)
(the next five). Where the system honestly stands: [docs/audit_2026-09-26.md](docs/audit_2026-09-26.md);
measured ideas for script generation, idea grading and resource use:
[docs/engine_upgrades.md](docs/engine_upgrades.md). Session state:
[docs/handoff.md](docs/handoff.md) (the mailbox) and [docs/handoff_synopsis.md](docs/handoff_synopsis.md).

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Add API keys; put OAuth files in config/secrets/ (see config/secrets/README.md)
# LLM is multi-provider (core/llm_router.py): set DEEPSEEK_API_KEY (+ optional
# OPENROUTER_API_KEY / OLLAMA_MODEL) for a near-free run; OpenAI/Claude are opt-in
# premium upgrades. Routes cheap/extract/premium tiers automatically.

py -m scripts.ops all-setup --channel tapin
py main.py
# Stage 1 window (optional extra): pip install -e ".[app]" then py -m desktop
# Stage 2 look is on that window (token QSS, per-channel chrome). CLI is unchanged.
```

**Windows command cheat sheet:** [docs/startup_powershell.md](docs/startup_powershell.md) — or run `.\scripts\startup.ps1` to print the list.

## Operator commands (batch or one-by-one)

```powershell
py -m scripts.ops list              # all commands
py -m scripts.ops all-setup         # layout + DB + seed + validate + YouTube check
py -m scripts.ops all-checks        # validate + unit tests
py -m scripts.ops all-analytics     # seed + learn-schedule + weights + sync-metrics

# Individual steps
py -m scripts.ops migrate-layout
py -m scripts.ops seed --channel tapin
py -m scripts.ops validate
py -m scripts.ops check-youtube
py -m scripts.ops worker --loop 30
py -m scripts.ops test
py -m scripts.ops seo-refresh --channel tapin   # weekly tag hints
py -m scripts.ops topic-db --channel tapin       # Topic Winners + Graveyard
py -m scripts.ops title-patterns --channel tapin # title patterns that engage (A/B loop)
py -m scripts.ops reliability                    # credit/quota/cache dashboard
```

After pulling schema changes:

```powershell
py -m storage.alembic_runner upgrade head   # preferred (Alembic)
# or: py -m storage.migrate_schema          # legacy ad-hoc DDL
```

Interactive pipeline (not batched): `py main.py`

The `py main.py` start menu:

| Option | Mode | What it does |
|--------|------|--------------|
| 1 | Create new video | Discovery pipeline: best-bet → variants → script → render |
| 2 | Queue manager | Re-queue after deleting a scheduled YouTube video |
| 3 | Intelligence report | Signals + brief + competitors, no script/render |
| 4 | Sync YouTube analytics | Pull engagement metrics into the learning loop |
| 5 | Make a video from my own idea | Intake a topic **or a YouTube link** and generate from it |

**Option 5 — bring your own idea:** paste a plain idea/topic, or a YouTube link
(`watch` / `shorts` / `youtu.be`). When a link is detected it fetches that video's
title (1 quota unit) and asks for your angle, then runs the same discovery →
script → render pipeline with your idea as the locked seed (best-bet is skipped).
Recommended length and post time still apply.

**Intelligence report only** (no script/render — portfolio & freelance deliverable):

```powershell
py -m core.intelligence_report --topic "Marvel Rivals Cyclops" --channel tapin
py -m scripts.ops intelligence-report --topic "UFC 250 Topuria" --channel tapin
# Or: py main.py → menu option 3
# Or: set CONTENT_MODE=intelligence
```

Reports → `output/{channel}/reports/*.md` and `.json` (v2: trajectory, corroboration, opportunity window, explainability). See [docs/analyst_intelligence.md](docs/analyst_intelligence.md), [docs/positioning.md](docs/positioning.md), [docs/case_study.md](docs/case_study.md).

Re-queue after **deleting** on YouTube: `py -m scripts.queue_manage --channel tapin` (or `py main.py` → Queue manager)

Re-upload never-uploaded MP4s: `py -m scripts.requeue_upload --channel tapin --queue`

Status: `py -m scripts.ops status --channel tapin`

Credit/quota dashboard (Apify + LLM budgets, breakers, cache hit-rate): `py -m scripts.ops reliability`

Daily direction sync: `py -m scripts.ops daily-sync --channel tapin`

If something breaks, start with [docs/debugging.md](docs/debugging.md).

## Development

```powershell
pip install -e ".[dev]"      # ruff, mypy, pytest, pre-commit
pre-commit install           # run lint+format on every commit

ruff check .                 # lint
ruff check . --fix           # lint + autofix
ruff format .                # format
mypy analytics apis core config storage   # type check (lenient baseline)
python -m unittest discover -s tests -t .  # tests (pytest also works: `pytest`)
```

Tooling is configured in [`pyproject.toml`](pyproject.toml) (canonical deps +
ruff/mypy/pytest config). CI runs lint, format-check, a type-check baseline, and
the test suite on Python 3.11 (the version the pinned deps are validated on) — see [.github/workflows/ci.yml](.github/workflows/ci.yml).

## Project layout

| Path | Purpose |
|------|---------|
| `main.py` | Interactive CLI entry (CM banner + optional Luffy mascot) |
| `config/` | Settings, `channels.json`, `paths.py`, `secrets/` (gitignored) |
| `core/` | Pipeline, UI, TTS, LLM engine, `intelligence_report.py`, `ascii_art.py` |
| `apis/` | Signal providers, scoring, cache |
| `analytics/` | Metrics sync, post timing, TapIn seed |
| `assets/` | Stock/local backgrounds, thumbnails, hybrid composite |
| `publishing/` | YouTube publisher, repurpose scaffold, idempotency |
| `storage/` | Postgres/JSON repositories, Alembic runner |
| `alembic/` | Schema migrations (`0001` baseline, `0002` thumbnail scores) |
| `jobs/` | Upload/render worker |
| `youtube/` | OAuth + upload + thumbnails |
| `sports/` | ESPN scoreboard helper (`live_scores` signal) |
| `data/` | Local JSON runtime (cache, memory, jobs — gitignored) |
| `output/` | Generated media (gitignored) |
| `docs/` | Architecture, roadmap, scheduling, debugging |
| `scripts/` | `ops.py`, `queue_manage.py`, `requeue_upload.py`, `daily_sync.py`, `status.py`, `startup.ps1`, `update_luffy_art.py` |
| `video/` | Render, subtitles, channel intro; `backgrounds/` for local gameplay |
| `tests/` | Unit tests |

**UI env:** `CONTENT_UI_ASCII` (banner), `CONTENT_UI_MASCOT` (`luffy` default; `false`/`none` to hide).

## Docs

- [Roadmap](docs/roadmap.md) — phase checklist (source of truth)
- [Engine upgrades](docs/engine_upgrades.md) — measured ideas: script, grading, resources
- [Intelligence phase (H–K)](docs/intelligence_phase.md) — post D–G: brief, RSS, competitors, what to defer
- [Architecture](docs/architecture.md) — modules and data flow
- [Positioning & product split](docs/positioning.md) — intelligence layer vs production tail
- [Case study](docs/case_study.md) — portfolio narrative + sample report link
- [Data sources](docs/data_sources.md) — stats scrapers, blog RSS, APIs
- [Signals & sources (operator)](docs/signals_and_sources.md) — signal health, zero-score troubleshooting
- [Debugging & operations](docs/debugging.md) — common errors, fixes, env tuning
- [Post scheduling](docs/post_scheduling.md) — queue and `publishAt`
- [Credit & spend efficiency](docs/credit_efficiency.md) — Apify/signal breakers, LLM router cost, quota/spend optimization backlog
- [Changelog](docs/change_log.md) — major updates by theme

## Background video (hybrid default)

TapIn uses **hybrid** mode: local gameplay from `video/backgrounds/` (~45% of runtime) plus stock B-roll (Pexels/Pixabay) for the rest. See `video/backgrounds/README.md`.

Override in `.env`: `BACKGROUND_MODE=hybrid|stock|local` or per channel in `config/channels.json`.
