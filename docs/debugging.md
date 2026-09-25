# Content OS — Debugging & Operations

> **Class:** runbook · **Status:** living · **Reviewed:** 2026-09-20

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
| Fact conflicts (Pillar 3) | Operator facts vs signal/web disagreement (trades, results, champions) — **before** the LLM call | Conflicts among non-operator sources |
| Tier warnings (Pillar 3) | High-stakes claims grounded only by web/brief; entities grounded only by YouTube titles | Claims the tier layer can't parse |
| Claim verifier (Pillar 3) | Per-claim support against the fact corpus, with the citing line (LLM, extract tier) | Facts wrong in the corpus itself |
| Authenticity (Phase O) | Template-stamp risk + recap vs take | Factual accuracy |

Since Pillar 3 (decisions §16), unsupported claims / conflicts / tier warnings also
land in `quality_json` v2 and drag the report card's grounding component — check
`ops dossier --run-id N`. `GROUNDING_GATE=block` turns unsupported claims into a
render gate (interactive asks to override; headless needs `--force`).

**Common causes from live runs:**

1. **Obsidian vault strategy notes** — bullets like “Fraud narratives outperform…” are engagement heuristics, not event facts. Notes tagged `strategy` / `playbook` or bullets matching strategy markers are **excluded** from vault fact suggestions (`core/obsidian_facts.py`). Since Pillar 4, those same notes **do** feed the bounded `CHANNEL PLAYBOOK` prompt block (clearly labeled NOT facts). At the prompt, type `n` to skip vault suggestions when unsure.
2. **Key facts** — all facts save to `vault/<channel>/_operator_facts/` (full set, never capped); the LLM gets a **char budget** (default 12000, `OPERATOR_KEY_FACT_CHAR_BUDGET`). Since run 74 the budget is spent by **ranking** rather than by insertion order (`core/fact_selection.py`): operator-typed facts are pinned, article scaffolding is penalised, and recency is weighted heaviest. Facts are **split at sentence boundaries**, never sliced mid-sentence. Pasting a multi-paragraph article straight at the `Fact N` prompt now works — blank lines are paragraph breaks while the paste is still arriving — and **`paste`** + Enter is still there for very large blocks. UI shows collected vs packed, plus what was held back and why.
3. **Discovery angles ≠ YouTube title** — discovery picks editorial angles; the publishable title is generated **after** key facts + script (`core/title_generator.py`). Ignore slop-looking angle lines — the final title uses your facts.
4. **ESPN / some news URLs** — bot protection (AWS WAF) blocks `link_facts` fetch. Use **`paste`** mode with article text; do not rely on ESPN URLs. Yahoo/MSN article links can also pull sidebar "Related:" items — `link_facts` now scopes to `<article>` and drops nav noise; if a link still looks polluted, **`paste`** the paragraph block instead. Live-run 71: an MSN GTA-6-leaker URL returned **headline only**; the operator later pasted the body at **Proceed?** / the PowerShell prompt instead of the key-facts `paste` mode — see **Live-run 71** below.
5. **Apify 403** — session disables social signals; summary shows the real `apify_status()` reason (not always “out of credits”). Set `SIGNAL_BACKEND=auto` for yt-dlp YouTube when Apify is dead.
6. **Single-name athletes** — grounding flags mononyms (e.g. `LeBron`) when absent from the facts corpus. Common transition words (`Meanwhile`, `Rookie`, `Bottom line`) are **not** flagged.
7. **Claim verifier vs token grounding** — token grounding can pass while the claim verifier fails: the verifier checks whether the *claim* is backed, not just whether names appear. Operator key facts are now **prioritized** in the verifier's fact window (signal corpus used to crowd them out past the 6000-char cap). If pay-cut lines are in your pasted facts but still flag unsupported, re-run after pull — or add the exact stat as a key fact.
8. **TapIn + real sports** — topics like "2027 standings / award races" without the word "NBA" used to inherit TapIn's `gaming` domain and drift to Marvel Rivals. Fixed: expanded NBA keywords + **key facts override** the channel default; script brief adds an NBA matrix and drops the gaming-franchise nudge. If you still see esports language, add more concrete NBA team/player facts and regenerate.
9. **Bing redirect/search URLs** — paste the **destination** article URL (or use `paste` for ESPN). Bing search pages and captcha interstitials are blocked; `ck/a` tracking links are unwrapped when possible.

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

### Live-run 74 (2026-08-29) — one buffered word discarded the run

Same window, same shape as run 71, and the run-71 fix did not cover it. The CLI
did not crash: Python exited cleanly, printed *Stopped before render*, and the
article the operator wanted as ground truth was thrown away one paragraph in.

The run-71 advice ("do not paste at `Proceed?`") does not help here, because the
operator never pasted at `Proceed?`. They pasted at the **Fact** prompt, which is
exactly where the article belongs. What answered `Proceed?` was a line the
console had been holding since that paste.

#### The chain, in order

1. **`Fact 51` — Engadget returned HTTP 403.** The CLI correctly told the operator
   to paste the article text instead.
2. **They pasted at the `Fact N` prompt without typing `paste` first.** That prompt
   reads one line per `input()`, so line 1 became fact 51 and line 2 became fact 52.
3. **The article's first blank line ended intake.** A paragraph break is
   indistinguishable from "operator pressed Enter" to a loop whose exit condition is
   `if not fact: break`. Two lines of a forty-paragraph article were kept;
   `read_multiline_paste` had known this since run 71 and required *two* blank lines,
   but only inside `paste` mode — the default prompt never got the rule.
4. **The remaining paragraphs stayed in the Windows console input buffer** and
   auto-answered every prompt that followed.
5. **`Proceed?` received `by`** — Engadget's byline label, the line that happened to
   be next in the buffer. `_looks_pasted("by")` is `False` (two characters, one
   word), so candidate 325's re-prompt did not fire and the gate fell through to
   `return ("stop", …)`. **4.7 minutes of work discarded without a word.**
6. **Everything after `by` fell through to PowerShell**, producing the
   `CommandNotFoundException` wall (`Dave`, `Rockstar`, `Arguably`, `signaling`) and
   two `>>` continuations from unbalanced parentheses in the article prose.

`by` is the whole lesson. Run 71 was fixed by teaching the gate to recognise
*prose*; run 74 was ended by a two-letter word that no prose detector will ever
catch. The gate had to stop guessing.

#### What changed

- **`core/console_input.py`** (new) — `input_pending()`, `read_pending_lines()`,
  `drain_stdin()`. Promoted out of `main.py`, where an equivalent existed but was
  wired only to the option-5 idea flow, discarded what it found, and had a
  `return` inside the `try` that let a Windows failure fall through to the POSIX
  branch.
- **A blank line ends fact intake only when nothing is buffered.** Otherwise it is
  a paragraph break. Whatever is still buffered when the loop does end is offered
  back: *"N more pasted line(s) arrived after the blank line — add them as facts?"*
  This is what actually rescues a 403 fallback.
- **`Proceed?` stops only on `n` / `N` / `no` / Enter.** Every other unrecognised
  answer re-prompts, up to three asks. Declining is still instant. Buffered input
  is drained before the first ask, so a paste cannot reach the gate at all — the
  re-prompt is the second line of defence, not the first.

#### The other half: facts arrived truncated mid-sentence

Independent of the abort, every fact was hard-sliced at 400 chars
(`_MAX_KEY_FACT_CHARS`), producing lines like *"…the campaign will progress
through a chapter-based"*. That does not read as a truncation to a language
model; it reads as a finished, vague statement, and the model resolves the
vagueness by inventing. The cap had no quality rationale — it was a runaway-blob
guard implemented as `line[:400]`.

It is now a **splitter**: `split_at_sentences` emits whole sentences, and a single
over-long sentence survives intact. Only a blob with no sentence punctuation at
all is cut, at word boundaries, with a trailing ellipsis. The display was lying in
the same direction — `print_fn(f"    + {ex[:90]}")` printed no ellipsis at all, so
a shortened *line on screen* was indistinguishable from a shortened *fact in the
prompt*. `_elide` now names the hidden character count.

#### And the budget stopped truncating at all

Of the 54 facts packed into that prompt, roughly fifteen were article furniture —
*"Below, you'll find everything shown off during the GTA 6 Extended Look:"*,
*"Check out the five biggest takeaways below."*, *"Note: All of these details are
compiled from various previews…"* — while six wanted stars, the Slim Jim
carjacking minigame, the 80-hour playthrough and the November 19 date sat in the
tail that never fit. Raising the ceiling would have packed more furniture.

`core/fact_selection.py` ranks the pool instead: operator-typed facts pinned,
scaffolding penalised (not blacklisted — a furniture-shaped line carrying a hard
number still competes), and the rest scored on recency (weighted heaviest),
novelty, specificity, and relevance. Every exclusion carries a reason and prints.

One measured finding worth keeping: `score_vault_fact` scored the Slim Jim
mechanic at **0.03**. It measures how much a line echoes the existing signal
corpus — the right question for a vault note, the wrong one for a pasted article,
where the *point* is to add what the signals lack. That is why relevance is the
smallest weight here and `novelty` exists.

#### Also observed in the same run

- **`trendingnow.games` failed again** (DNS/TLS, `Max retries exceeded`), as it has
  for weeks. Retired per decisions §19 — reason recorded in
  `apis/signals_bootstrap.RETIRED_SIGNALS`, module kept for revival.
- **`youtube` and `youtube_comments` both timed out**, 30s of a 37.8s discovery,
  because both route through `apis/youtube_api` and each waited out the full 15s
  socket timeout against the same dead endpoint. Timeout cut to 8s, and a
  process-level latch makes the second call fail fast once the first has timed out.
  A read timeout is transient, so the session breaker never fired for it.
- **Two gates disagreed about the same phrase.** The log said
  `persona lint: but here's the thing` and the report said
  `original_insight: has an authorial take ('here's the thing')`, four lines apart
  — and the second is why the script scored authenticity **100/100**. The phrase is
  banned by `core/persona_lint.py` *and* by the script prompt's own banned list, so
  rewarding it laundered a style defect into an A. Removed from
  `_INSIGHT_MARKERS`; `tests/test_gate_agreement.py` stops the three lists
  disagreeing again.
- **The persona-lint hit never reached a decision surface.** `core/pipeline.py`
  already carried it into `features["persona_lint"]`; nothing displayed it. Now
  shown before `Proceed?` as a style line (it does not raise the fact-review flag).
- **The script shipped 277 words against a 300-word floor and still graded A.**
  The expansion loop runs *before* `_maybe_improve_hook`,
  `_maybe_recenter_on_key_facts`, `_maybe_inject_insight` and
  `_maybe_reground_script` — all of which can remove text — and nothing measured
  the script again afterwards, so the loop's exit condition was checked against
  text the operator never saw. `_relength_after_postprocessing` re-checks, and
  reverts a late expansion that reintroduces unsupported specifics: hitting a word
  count is never worth walking back the grounding pass.
- **Not fixed, deliberately:** the report card still does not weight length. Adding
  a length component would change the meaning of every historical grade, which is a
  bigger decision than this run justifies. The `[SHORT]` line still prints directly
  above the card.

#### What to do next time (same window)

- **Paste an article at `Fact N` freely.** Blank lines no longer end intake while
  the paste is still arriving, and anything left over is offered back. `paste` mode
  still works and is still slightly safer for very large blocks.
- **`Proceed?`** — only `n` / `N` / `no` / Enter stop. A stray token re-prompts.
- If a link is blocked, the message now names the reader-proxy escape hatch
  (`LINK_READER_PROXY=1`) alongside the paste fallback.

---

### Live-run 71 (2026-08-21) — pasted article hit PowerShell, not the CLI

This was **not** a Python crash, a broken `all-setup`, or PowerShell “randomly
executing” the article. After `py main.py` stopped, the **same window** was a
normal PowerShell prompt. Clipboard text (article body + sidebar ads) was then
typed as shell commands.

#### What the session actually did

1. **`py -m scripts.ops all-setup`** completed: layout 0 files moved, DB tables
   verified, Alembic at head, 44 TapIn videos seeded, channel config OK,
   YouTube **READY** (`config/secrets/youtube_token_tapin.json`).
2. **`python main.py`** — TapIn (2), create video (1), Standard cost mode,
   best-bet **3** (Polygon: *GTA 6 Leak and Wolverine Rage Are Symptoms of
   Gaming's Summer of Hate*). Discovery **~58s**. Cadence 2/5. Run **id 71**.
3. **Signals:** 8 active. YouTube + youtube_comments **timed out**.
   `trendingnow.games` **max retries**. Wikipedia/news/IGDB/Steam inactive
   (no match). RSS/trends/web_search/competitors/TikTok/autocomplete/Twitch/RAWG
   on. RSS 404 on one YouTube channel id (`UCq-Fj5jknLsUf-MWSik4vhQ`).
4. **Key facts:** vault auto-attached **4 off-topic** bullets (NetEase / Marvel
   Rivals S9, Wolverine costume, SEGA IP). MSN GTA-6-leaker URL: **headline
   only** (JS-heavy scrape). Operator typed one Take-Two/Microsoft/Discord
   sentence; empty line ended the prompt. **6 facts packed** (1017 / 4500
   chars). Article **body** was **not** in the fact window.
5. **Script + title** generated (~435 words). The claim verifier found
   **7 of 12 claims unsupported** (the Rockstar hack, the DMCA takedowns, the
   Wolverine “rage state” / stiff-animation polish claims). Only **5** were
   printed — the WARNING truncates the list at `[:5]`
   (`core/content_engine.py:918`); the count is the honest number.
   The later **12/12 backed** line is *not* a second opinion from a different
   check — it is the **same** verifier re-run on a **rewritten** script.
   `_maybe_rewrite_unsupported_claims` (`core/content_engine.py:435`, default-on
   via `CLAIM_REGEN_ENABLED`) spends one premium call restating each unsupported
   claim as attributed speculation, re-verifies, and adopts the rewrite when the
   count drops. That is why the draft reads “Reports claim a hacker
   breached…”, “allegedly showed”, “reportedly swift”. **Nothing was verified
   between the two numbers — the claims were hedged, not evidenced.** Working as
   designed; read `12/12` as “no bare assertions left”, not “all claims true”.
6. At **`Proceed? [y = render / + longer / - shorter / 1-4 length / N = stop]:`**
   the operator pasted *“On Thursday, Take-Two Interactive filed subpoenas…”*
   instead of `y` / `N`. `prompt_proceed_or_length` (`core/ui.py`) only treats
   `y`, `+`, `-`, and `1`–`4` as continue; **anything else is stop**. Pipeline
   printed **Stopped before render** (draft kept: title + script, no MP4).
   Est. cost **$0.028**. Wall **~30.6 min**.

Python then **exited**. The next `PS C:\dev\content_machine>` is the shell,
not a key-facts `paste` block.

#### Why PowerShell printed `CommandNotFoundException`

Each subsequent paste was a **new command line**. PowerShell takes the first
token as a cmdlet/program name:

| Pasted line (from the page, not the CLI) | First token PowerShell tried to run |
|---|---|
| `Fast Way To Get Rid Of Mice (2026)` | `Fast` (sidebar ad) |
| `mice` / `Sponsored` / `call to action icon` | same — page chrome |
| `·` (middle-dot bullet) | `·` |
| `Amazon:` / `Walmart:` / `PlayStation Store:` / `Xbox Store:` | store headings |
| `Standard Edition PS5 - $79.97` | `Standard` (pre-order block) |

A longer IGN/Kotaku-style paste also hit PowerShell’s **parser**, not “search”:

- **`user(s)`** — `(s)` is a **subexpression**. PowerShell tried to run a
  command named `s` → `The term 's' is not recognized` at that character.
- Unmatched **quotes / parentheses** across lines put the shell in
  continuation mode (`>>`). More paste was **one incomplete statement**, not
  a new `py main.py` prompt.
- Dollar amounts (`$79.97`) are variables; they did not need to resolve for
  the first-token errors above.

None of those strings were Content Machine commands. The CLI never saw them.

#### What to do next time (same window)

- **Article body as facts:** at **Fact N**, type `paste`, Enter, then paste,
  then an empty line. Do **not** paste at **Proceed?**
- **Proceed?:** `y` (render), `N` (stop), `+`/`-`/`1`–`4` (relength). A URL
  or paragraph is a stop.

> **Superseded by run 74 (2026-08-29).** Both bullets above described the
> behaviour of the time. A paste at **Fact N** no longer needs `paste` mode, and
> at **Proceed?** only `n` / `N` / `no` / Enter stop — everything else re-prompts.
> Run 74 showed why the run-71 fix was too narrow: the line that ended that run
> was the single word `by`, which no prose detector catches.
- If you already see `PS C:\dev\content_machine>`: **Ctrl+C** once to cancel
  a `>>` continuation, then `py main.py` again. Run 71 is a **draft** — Queue
  manager will not have an MP4 until you render.
- If the scrape warning says **headline only**, do not assume the article is
  in the vault; use `paste` or `LINK_READER_PROXY=1`.

#### The quality read-out from the same run (the draft graded **A**)

The draft that stopped at Proceed scored **A (91/100)** with grounding
**100/100**. Four things in the same log argue against trusting that grade here:

- **The title was never checked, and it is wrong.** `GTA 6 Leak Forces Rockstar
  to Subpoena Microsoft and Discord Records` — the subpoenas were filed by
  **Take-Two Interactive**, Rockstar's parent, which is what the operator's own
  key fact said (“the parent company of Rockstar Games has resorted to filing
  subpoenas”). `generate_title` runs *after* grounding and the claim verifier
  and is deliberately fail-open (`core/title_generator.py:89`); **no check reads
  the title it returns.** A grounding score of 100 says nothing about the
  headline — the one line the audience reads first.
- **The fact corpus was polluted, and the polluted count fed the grade.** RAWG
  keyword-matched “Wolverine rage” to three 1990s games (*Adamantium Rage* 1994,
  *Wolverine's Rage* 2001, *Wolverine* 1991), and the vault auto-attached four
  Marvel Rivals / SEGA bullets. None relate to a GTA 6 leak. The authenticity
  gate still cited **“18 verified fact(s)”** as its substance evidence.
- **Variant scoring produced no ranking.** All five angles scored exactly
  **100.0**, so `Choose 1-5 (Enter = best)` offered a tie dressed as a ranking.
- **The operator was the run, not the machine.** 30.6 min wall = **25.6 min at
  prompts** + 5.0 min machine, $0.028 spent, **no video produced**.

None of these were fixed in this pass — recorded here as observed behaviour.

---

### Toasts and quiet hours

A silent overnight run is not necessarily a broken toast. `CONTENT_TOAST_DND` (default
on) mutes Action Center toasts while **any** configured channel is inside its
`quiet_hours` window - `tapin` and `moneywise` are both 1-8am ET, so routine toasts
(ffmpeg done, overnight drafts, upload scheduled, uploads-left) are expected to be
silent overnight.

**Breaker toasts are exempt** and still fire at 3am: Apify, signal, LLM and ElevenLabs
trips pass `urgent=True`. If one of *those* is missing, it is a real fault - check
`CONTENT_TOAST` first, then whether `_toast_powershell` is failing.

Resolution is deliberately machine-level, not per-channel: `toast()` has no channel to
hand down, and a desktop notification interrupts the person, not a channel. The first
version of this asked `quiet_hours_reason()` with no channel at all, which resolved to
the `default` channel - which has no `quiet_hours` block - so it muted nothing at any
hour. `QUIET_HOURS=false` disables the window entirely; `CONTENT_TOAST_DND=false`
disables only the toast muting.

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

*Last updated: 2026-08-29 — live-run 74 (a buffered `by` from a Fact-prompt paste answered `Proceed?` and discarded the run); fact intake survives a raw paste, facts split at sentences instead of slicing at 400 chars, and the prompt budget now ranks facts rather than taking the first N.*
