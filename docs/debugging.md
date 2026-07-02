# Content OS — Debugging & Operations

Operator-focused guide for diagnosing failures, validating config, and recovering from common errors. For architecture context see [architecture.md](architecture.md); for phase status see [roadmap.md](roadmap.md).

---

## Quick diagnostic flow

Run these in order when something fails before or during `py main.py`:

```powershell
cd C:\dev\content_machine

# 1. Layout + channel config
py -m scripts.ops migrate-layout
py -m config.validate_channels --channel tapin

# 2. Database (if using Postgres)
py -m storage.init_db
py -m storage.migrate_schema

# 3. YouTube upload readiness
py -m youtube.check_setup --channel tapin

# 4. Unit tests (fast regression)
py -m unittest discover -s tests -v

# Or batch:
py -m scripts.ops all-checks --channel tapin
```

Enable verbose logs when reproducing:

```powershell
$env:CONTENT_LOG_LEVEL = "INFO"    # or DEBUG
$env:CONTENT_QUIET_LOGS = "0"
py main.py
```

---

## LLM providers (multi-provider router)

All runtime LLM calls go through `core/llm_router.py` (tiers `cheap`/`extract`/
`premium`). Check which provider each tier resolves to:

```powershell
py -c "import config.settings; from core import llm_router as r; [print(t, r.resolve_tier(t)) for t in ('cheap','extract','premium')]"
```

| Symptom | Likely cause | Fix |
|---|---|---|
| All tiers resolve to `openai` despite DeepSeek/OpenRouter keys set | `.env` not loaded **or** keys missing/misnamed | Run the check above **with** `import config.settings` (it loads `.env`). Confirm exact var names: `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY` |
| Cheap tier still on DeepSeek, not OpenRouter | `OPENROUTER_API_KEY` not seen | Must be that **exact** name in `.env` (not `OPENROUTER_KEY`) |
| Ollama never selected | `OLLAMA_MODEL` not set (an API key alone does nothing) | Set `OLLAMA_MODEL=<pulled model>` (`ollama list`) + run `ollama serve`; optional `OLLAMA_BASE_URL` for a remote host |
| Premium script quality dropped | premium routed to a free model | It's free DeepSeek-V3 by default; to pay for top quality set `LLM_PREMIUM_PROVIDER=openai` (`LLM_PREMIUM_MODEL=gpt-4o`) or `=anthropic` |
| OpenRouter calls intermittently fail | free `:free` models are rate-limited | Expected on the free tier; provider **failover** is a planned follow-up ([credit_efficiency.md](credit_efficiency.md) O5). For now set `LLM_CHEAP_PROVIDER=deepseek` to avoid it |
| Want to force one provider everywhere | — | Set `LLM_<TIER>_PROVIDER` / `LLM_<TIER>_MODEL` per tier |

Provider keys + the full free-setup guidance live in `.env.example`. Routing
rationale: [decisions.md](decisions.md) §14. Spend/credit efficiency:
[credit_efficiency.md](credit_efficiency.md).

---

## Batch operator commands (`scripts/ops.py`)

| Command | Purpose |
|---------|---------|
| `py -m scripts.ops list` | List all subcommands |
| `py -m scripts.ops all-setup --channel tapin` | migrate-layout → init-db → seed → validate → YouTube check |
| `py -m scripts.ops all-checks --channel tapin` | validate + unit tests |
| `py -m scripts.ops all-analytics --channel tapin` | seed → learn-schedule → weights → sync-metrics |
| `py -m scripts.ops validate --channel tapin` | `config.validate_channels` |
| `py -m scripts.ops worker --loop 30` | Background upload/render worker |
| `py -m scripts.ops seo-refresh --channel tapin` | Refresh trending tag hints |
| `py -m scripts.ops test` | Full test suite |

Individual modules (same as ops, for scripting):

- `py -m storage.migrate_layout` — move root `signal_cache.json`, memory JSON, secrets into `data/` and `config/secrets/`
- `py -m analytics.seed_tapin --channel tapin` — seed learning + publish history
- `py -m analytics.learn_schedule --channel tapin` — compare static vs learned post slots
- `py -m analytics.sync_metrics` — refresh YouTube Analytics into `publish_log`
- `py -m analytics.compute_weights --channel tapin` — print learned signal weights

---

## Re-queue after deleting on YouTube (before publish time)

If you **deleted** a scheduled video on YouTube, the DB still thinks it was uploaded. Reset and re-queue:

```powershell
py main.py
# Channel → Start → 2) Queue manager

# Or CLI:
py -m scripts.queue_manage --channel tapin
py -m scripts.queue_manage --channel tapin --run-id 7 --requeue --schedule
py -m jobs.worker --loop 30
```

`--reset` clears `publish_log` only; `--requeue` resets and enqueues a new upload job.

## Re-upload rendered videos

Use when MP4 exists but YouTube upload **never** ran or failed:

```powershell
py -m scripts.requeue_upload --channel tapin
py -m scripts.requeue_upload --channel tapin --run-id 4
py -m scripts.requeue_upload --channel tapin --run-id 4 --queue
```

Then run the worker: `py -m jobs.worker --loop 30` (or `py -m scripts.ops worker --loop 30`).

**Note:** Re-uploading does not regenerate scripts. Bad UFC copy requires a **new pipeline run** with updated signals (see [UFC script accuracy](#ufc-script-accuracy) below).

---

## Common errors and fixes

### `config.validate_channels` — unknown `weight_overrides` keys

**Symptom:**

```
ERROR: tapin: unknown weight_overrides keys: ['asset_provider_order', 'background_mode', ...]
ERROR: tapin: weight_overrides values must be numeric
```

**Cause:** Channel-only fields were nested inside `weight_overrides` instead of the channel root.

**Fix:** In `config/channels.json`, keep **only numeric signal weights** under `weight_overrides`. Put these at the **channel root**:

- `background_mode` — `hybrid` | `stock` | `local`
- `hybrid_local_ratio` — e.g. `0.45`
- `asset_provider_order` — e.g. `["local", "pexels", "pixabay"]`

Re-run: `py -m config.validate_channels --channel tapin`

---

### Discovery crash on `cache_manager.save_cache` / `open(...)`

**Symptom:** Traceback through `apis/register_signals.py` → `set_cache` → `save_cache` → `open(path, "w")`.

**Likely causes:**

- OneDrive locking `data/signal_cache.json` during parallel variant scoring
- Very large cache file (hundreds of keys) rewritten on every signal fetch
- Legacy `signal_cache.json` still at repo root while writes target `data/`

**Fixes:**

1. Run `py -m storage.migrate_layout` so cache lives under `data/`.
2. Retry; cache writes are **atomic** with retries and **non-fatal** (discovery continues with a warning if write fails).
3. Temporarily pause OneDrive sync on the project folder, or exclude `data/` from sync.
4. Optional: delete `data/signal_cache.json` to reset (signals will refetch).

**Logging:** Look for `Signal cache write skipped` at `CONTENT_LOG_LEVEL=WARNING` or above.

---

### `SyntaxError: '(' was never closed` in `core/content_engine.py`

**Cause:** Truncated file (incomplete `client.chat.completions.create` block).

**Fix:** Ensure `generate_content_package` ends with closed `create()`, JSON parse, and return dict. Verify:

```powershell
py -m py_compile core\content_engine.py
py -c "from core.content_engine import generate_content_package; print('ok')"
```

---

### `ModuleNotFoundError: cache_manager` (or other root modules)

**Cause:** Imports still pointing at pre-layout root paths after move to `apis/`, `core/`, `config/`.

**Fix:** Use package imports, e.g. `from apis.cache_manager import ...`, not `from cache_manager import ...`.

---

### YouTube `check_setup` NOT READY after OAuth

**Checks:**

1. Token file exists: `config/secrets/youtube_token_tapin.json` (path from `channels.json` → `youtube.oauth_token_path`).
2. Client secrets: `config/secrets/client_secrets.json` (or channel override).
3. `.env`: `YOUTUBE_UPLOAD_ENABLED=true`
4. `py -m youtube.check_setup --channel tapin` uses `_client_secrets_path()` under `config/secrets/`, not repo root.

Re-auth: `py -m youtube.oauth_setup --channel tapin`

---

### Videos rendered but never on YouTube / worker says "No pending jobs"

**Symptom:** Runs show `rendered` in status; publish queue empty or jobs `failed`; nothing scheduled in YouTube Studio.

**Cause:** YouTube Data API **daily quota** is shared between discovery (`youtube` signal search, ~101 units/call) and uploads (`videos.insert`, **~1,600 units**). When discovery uses ~9,900/10,000 units, uploads are blocked even though OAuth `check_setup` says READY.

**Check:**

```powershell
py -m scripts.ops status --channel tapin
```

Look for `YouTube API quota: BLOCKED for uploads` and `Failed upload jobs (quota)`.

**Fix (after quota resets — midnight Pacific):**

```powershell
# Option A: reset failed jobs from today
py -m scripts.requeue_upload --channel tapin --retry-failed-quota
py -m jobs.worker --loop 30

# Option B: queue specific runs (16–20, etc.)
py -m scripts.requeue_upload --channel tapin --run-id 20 --queue
py -m jobs.worker --loop 30
```

**Prevent:** In `.env`:

```env
YOUTUBE_LIGHTWEIGHT=true
CONTENT_SKIP_SIGNALS=youtube
```

Use comma-separated game/fighter names in topics to reduce repeated discovery searches.

---

### Run ID not found / requeue lists different IDs

**Symptom:** `--run-id 12` not found; only 1, 2, 4 exist.

**Cause:** `content_runs` table/JSON only contains runs actually recorded by the pipeline.

**Fix:** `py -m scripts.requeue_upload --channel tapin` (no `--run-id`) lists rendered, not-uploaded runs with paths. Use an ID from that list.

Older runs may store MP4 under `output/video/` instead of `output/tapin/video/` — requeue resolves paths from the run record.

---

### UFC script accuracy

**Symptom:** Wrong fighters, weight class, retired names, or wrong event number.

**Root causes (historical):**

- News signal did not pass headlines into the LLM
- No UFC-specific brief or Tapology/event context

**Current mitigations:**

| Layer | Module |
|-------|--------|
| UFC news + Reddit context | `apis/ufc_context_api.py` |
| Tapology event/bouts scrape | `apis/tapology_api.py` (cache: `data/tapology_cache.json`) |
| Script rules matrix | `core/script_brief.py` |
| LLM prompts + JSON output | `core/content_engine.py` |
| Facts injection | `_format_signal_facts()` in `content_engine.py` |

**Debugging steps:**

1. Run discovery and inspect signal health in CLI (Tapology / `ufc_context` should be ON or explain quota/403).
2. If Tapology returns 403, rely on `ufc_context` (NewsAPI + Reddit) — do not expect bout cards from scrape.
3. Regenerate content for the topic; do not re-upload old MP4s with bad scripts.
4. Lower temperature is set in `generate_content_package` (~0.55) with `response_format=json_object`.

**Env:** `CONTENT_SKIP_SIGNALS=tapology` to disable slow/blocked Tapology only.

---

### Script accuracy / hallucinations (NBA, trades, fresh news)

**Symptom:** Script asserts trades/rosters that are wrong or stale; **Authenticity ✓ 100/100** anyway; **Fact quality ✓** with many signal lines.

**Important:** Phase O authenticity checks **structure** (variation, authorial take, word count) — **not** factual correctness. The **Fact grounding** section (before authenticity in `main.py`) is the factual check.

| Check | What it measures | What it does *not* measure |
|-------|------------------|----------------------------|
| Fact quality preview | Signal/brief line count | Whether script claims match those lines |
| Fact grounding | Proper nouns / mononyms in script vs facts corpus | Semantic truth of headlines |
| Authenticity (Phase O) | Template-stamp risk + recap vs take | Factual accuracy |

**Common causes from live runs:**

1. **Obsidian vault strategy notes** — bullets like “Fraud narratives outperform…” are engagement heuristics, not event facts. Notes tagged `strategy` / `playbook` or bullets matching strategy markers are **excluded** from vault suggestions (`core/obsidian_facts.py`). At the prompt, type `n` to skip vault suggestions when unsure.
2. **Key facts** — all facts save to `vault/<channel>/_operator_facts/`; LLM gets a **char budget** (default 4500, `OPERATOR_KEY_FACT_CHAR_BUDGET`). Pasted + link facts rank before vault. Type **`paste`** + Enter to drop a whole trade tracker block. UI shows collected vs packed-for-LLM counts.
3. **Discovery angles ≠ YouTube title** — discovery picks editorial angles; the publishable title is generated **after** key facts + script (`core/title_generator.py`). Ignore slop-looking angle lines — the final title uses your facts.
4. **ESPN / some news URLs** — bot protection (AWS WAF) blocks `link_facts` fetch. Use **`paste`** mode with article text; do not rely on ESPN URLs.
5. **Apify 403** — session disables social signals; summary shows the real `apify_status()` reason (not always “out of credits”). Set `SIGNAL_BACKEND=auto` for yt-dlp YouTube when Apify is dead.
6. **Single-name athletes** — grounding flags mononyms (e.g. `LeBron`) when absent from the facts corpus.

**What to do:**

1. At key facts: `n` for vault unless bullets are dated/event facts; type **`paste`** and paste the full Yahoo trade block (or 3–5 concrete lines).
2. Pick a discovery **angle** (not a headline) — the YouTube title appears after script generation.
3. After script generation, read **Fact grounding** before **Authenticity**. Fix or add key facts if specifics are listed.
4. Regenerate — do not re-upload an old MP4 with a bad script.

**Env:** `OBSIDIAN_VAULT_PATH`, `OPERATOR_KEY_FACT_CHAR_BUDGET=6000` for trade-heavy nights, `MAX_OPERATOR_KEY_FACTS=24`.

---

### Tapology signal inactive / 403

Tapology is HTML scrape (no API). Sites may block automated requests.

- Cached results in `data/tapology_cache.json` may still serve stale data
- Pipeline continues; `ufc_context` and `news` remain fallbacks
- Check logs at INFO for `tapology` status in signal health lines

---

### Postgres vs JSON confusion

| Symptom | Check |
|---------|--------|
| Seed says PostgreSQL but CLI shows empty runs | `DATABASE_URL` in `.env`; `py -m storage.init_db` |
| Learning not updating | `record_learning_outcome` only on completed runs; channel_id must match |
| Jobs not processing | `py -m jobs.worker`; jobs in DB or `data/jobs.json` |

---

### Hybrid background / no local gameplay

1. Add clips to `video/backgrounds/` (see `video/backgrounds/README.md`).
2. Channel `background_mode: hybrid` and `hybrid_local_ratio` in `config/channels.json`.
3. Override: `BACKGROUND_MODE=hybrid` in `.env`.
4. If local provider finds no file, chain falls through to stock only.
5. If hybrid FFmpeg compose fails (common with HEVC `.mov` on Windows), the pipeline **falls back to stock-only** and logs a warning — re-run render; fix by converting local clips to H.264 `.mp4` or set `BACKGROUND_MODE=stock` temporarily.

Composite implementation: `assets/composite.py` + `assets/manager.py`.

---

### Windows / Python environment

- Prefer **one** Python for CLI and deps: system `Python311` or project `.venv`, not mixed.
- `tzdata` required for `zoneinfo` post scheduling on Windows: `pip install tzdata`
- FFmpeg must be on `PATH` for render and hybrid concat

---

## Render progress and YouTube thumbnails (Phase K)

**Render:** Staged CLI progress with elapsed timer (`CONTENT_RENDER_PROGRESS=1`). Thumbnails written to `output/{channel}/thumbnails/` when `THUMBNAIL_MODE=auto`.

**Upload:** After `videos.insert`, the worker calls **`thumbnails.set`** when `YOUTUBE_THUMBNAIL_UPLOAD=auto` (default) and a thumbnail file exists for the `content_run_id` (from the assets table) or the newest file in the channel thumbnails folder. Uses ~50 API quota units. If the channel is not eligible for custom thumbnails, status is `ineligible` — the video upload still succeeds; use Studio when eligible. Set `YOUTUBE_THUMBNAIL_UPLOAD=off` to skip.

---

## Logging and performance tuning

| Variable | Effect |
|----------|--------|
| `CONTENT_RENDER_PROGRESS` | `1` (default) prints `[elapsed]` stage lines + FFmpeg %; set `0` to silence |
| `THUMBNAIL_MODE` | `auto` (default) generates `output/{channel}/thumbnails/*.jpg`; `off` skips |
| `YOUTUBE_THUMBNAIL_UPLOAD` | `auto` (default) calls `thumbnails.set` after upload when a file exists; `off` skips |
| `BFL_API_KEY` / `FLUX_API_KEY` | Optional Flux image API; without key, Pillow fallback still runs |
| `CONTENT_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` (default) |
| `CONTENT_QUIET_LOGS` | Suppress noisy library loggers when `1` |
| `CONTENT_SKIP_SIGNALS` | Comma list, e.g. `trends,tapology` |
| `VARIANT_REUSE_SIGNALS` | Signals pinned during variant scoring (default `youtube`) |
| `YOUTUBE_CACHE_TTL_SECONDS` | YouTube signal cache TTL |
| `USE_LEARNED_POST_SLOTS` | `auto` enables analytics-derived slots |
| `LEARNED_WEIGHT_BLEND` | Blend static vs learned signal weights |
| `USE_SIGNAL_SYNTHESIS` | Optional `_synthesis` metadata in registry |

**Slow discovery:** Skip `trends`; ensure signal cache is healthy; variant scoring runs up to 5 parallel `build_registry` calls — large cache amplifies write contention.

---

## Signal cache internals

- **Path:** `data/signal_cache.json` (migrated from root via `migrate_layout`)
- **TTL:** 3 hours default; per-signal override (e.g. YouTube 6h, live scores dynamic)
- **Thread safety:** In-process lock; atomic replace on save
- **Failure mode:** Warn and continue (no crash on write failure)

Manual inspect:

```powershell
py -c "from apis.cache_manager import load_cache; print(len(load_cache()), 'keys')"
```

---

## Channel profile checklist (TapIn)

After editing `config/channels.json`:

```powershell
py -m config.validate_channels --channel tapin
```

Required concepts:

- `domain`, `output_subdir`, `post_schedule`
- `tts.voice_id` or `tts.voice_pool`
- `weight_overrides` — numeric signal keys only
- `background_mode`, `hybrid_local_ratio`, `asset_provider_order` — **root level**
- `youtube.oauth_token_path`, `youtube.client_secrets_path` (optional overrides)

Use TapIn in CLI: select channel 2, or `CONTENT_CHANNEL_ID=tapin`.

---

## Test targets for regressions

```powershell
py -m unittest discover -s tests -v
```

Notable suites:

- `tests/test_validate_channels.py` — channels.json schema rules
- `tests/test_learn_post_timing.py` — learned slots
- `tests/test_render_video.py` — FFmpeg filter graph
- `tests/test_pipeline_smoke.py` — mocked pipeline path

---

## When to escalate / open a code change

| Issue | Action |
|-------|--------|
| Repeated cache lock on OneDrive | Exclude `data/` from sync or move repo outside OneDrive |
| Tapology permanently blocked | Rely on `ufc_context`; consider official API if added later |
| Wrong scripts after fixes | New `run_pipeline`, not requeue |
| Schema drift on Postgres | `py -m storage.migrate_schema` before new features |
| Secrets in git | Rotate keys; never commit `.env` or `config/secrets/*` |

---

*Last updated: 2026-06 — aligns with layout cleanup, hybrid backgrounds, UFC research signals, ops/requeue CLIs, and cache hardening.*
