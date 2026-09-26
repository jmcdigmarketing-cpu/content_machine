# Handoff synopsis — 2026-09-26: wave 32, the 09-20 five

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-09-26

Use in a fresh session to continue `content_machine` without re-reading the full thread.

GPT-6 playground review (2026-09-08, briefing-based): [gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md) and [gpt6_part2_upgrades_2026-09-08.md](gpt6_part2_upgrades_2026-09-08.md). Not a recorded operator decision.

> Older waves and the 2026-07/08 shipped-notes are frozen verbatim in
> [handoff_synopsis_archive.md](handoff_synopsis_archive.md); this file keeps the newest three
> waves plus the standing operator sections (docs_standard.md §7).

## Last wave — 2026-09-26 (Claude Code): wave 32 #826 #820 #824 #821 #819

The roadmap's five, taken in the order cheapest-and-safest first. This container has no run
archive (`data/` holds two files), so #824 and #821 shipped the **measurement** they lacked,
unit-tested on the fake-repo fixture; the archive's numbers come from the operator's
`py -m scripts.ops calibration`. Three of the five had a wiring gap the map had missed.

- **#826** `core/claim_types.claim_type_coverage` - a run is typed when a claim carries a type,
  not when `unsupported_types` exists (`merge_reversals` pads it with `""`). Line in
  `ops calibration` and the weekly report: `Claim types: N of M verified runs carry per-claim
  types - the rest predate #345 and cannot be backfilled`.
- **#820** `apis/run_deadline` Event: `_fetch_all` sets it at the deadline, `run_actor` refuses
  the POST after it (`cancelled_after_deadline`, named in the dropped stub), and the executor
  cancels the *queued* signals too - they were starting after the drop. Free stragglers still
  cache. Measured: 1.5 s straggler under a 0.3 s deadline -> 0 POSTs.
- **#824** per-component Pearson + `n_for_significance`: **|r|=0.32 needs n>=36**. Lines say
  "not significant - do not retune the rubric on it". Rubric untouched, no `GRADE_VERSION` bump.
- **#821** (open) recurrence vs engaged-rate correlated and printed with its decision rule;
  `recurrence_line` reads `_RECURRENCE_MIN`; `ops grade` now prints it (#837).
- **#819** (open) `angle_scores` had 0 rows because `_finalize_run` never persisted them. Now in
  `features_json` + `quality["angle_score"]`; `angle_line` says `collecting (0 of N)`. Tie
  unchanged. #836 filed: an approximate backfill from `variants_json` is possible.
- **Found:** #835 weekly report `runs_total` bug; **#838 CI on `main` was red at `cdb01d8`** -
  wave 31's commit subject carried a U+2192 arrow and `ops agents`' cp1252 guard read it from
  `git log`; `render` is now console-safe by construction. #839 filed (hook should refuse it).

**Verify:** `python -m unittest tests.test_claim_type_coverage tests.test_deadline_cancels_paid_calls
tests.test_component_calibration tests.test_recurrence_calibration tests.test_angle_score_persisted
tests.test_agent_handoff` · `py -m scripts.ops calibration` · `py -m scripts.ops grade --run-id <id>`.

**Still open:** roadmap next five **#836 #839 #830 #832 #831**; #821/#819 wait on the operator's
calibration numbers, not on code.

## Previous — 2026-09-26 (Claude Code): wave 31 structural #827 #828 #829 #833

Executed the 09-20 audit instead of writing a third one about the same findings; the
before→after is [audit_2026-09-26.md](audit_2026-09-26.md). Ten signed commits, no product
behaviour changed.

- **#827** `core/process_state.py`: one reset point for process-global state, 23 modules
  registered, run before every test from `tests/__init__.py`.
- **#828** `ops test --order reverse|shuffle --seed N` + CI leg `Unit tests (reversed order)`.
  The run-69 symptom was `tests/test_ops_doctor._stack()` — an `ExitStack` built outside a
  `with`, leaking `run_mode._ollama_ready` whenever a later `patch()` target failed to import
  (partial installs only). First reversed run found two more leaks; all closed.
- **#829** one-line missing-modules notice; inert tests fixed; Pillow skips fail under CI.
- **#833** `scripts/mypy_ratchet.py`: 129 on pinned mypy 1.13.0, blocking on increase.
- Docs: ten renames (links rewritten), `handoff_synopsis.md` 1,849 → 244, `planning_log.md`
  rolled over by month, `decisions.md` rewrapped word-for-word, nine never-reviewed docs
  corrected, decisions §33 (Content Machine = engine, Content OS = operator app), three new
  lint rules, roadmap/backlog repaired, **#830–#834** filed.

**Verify:** `py -m scripts.ops test --order reverse` · `py scripts/mypy_ratchet.py` ·
`python -m unittest tests.test_docs_standard tests.test_docs_lint`.

**Still open:** roadmap next five **#826 #821 #820 #824 #819** (product); #830–#834
(structural, M3). `planning_log.md` rolls over again at month end.

## Previous — 2026-09-20 (Claude Code): wave 30 #817 #818 #822 #739 #823

Second measurement wave, and the one where the measurements started saying no. **Two items
closed without a behaviour change because the numbers said not to**, and one closed because its
filed text was wrong.

Verifying the recommended five moved two slots. Three waves had shipped measurements carrying
**zero rows** (`hedge_density`, `grade_score`, `style_recurrence_*`, `angle_spread`) because no
run had been generated since - that became **#823**. **#819 came out**: it asks what to use
instead of composite and names `angle_scores`, which has 0 rows and cannot be backfilled.
**I first called #739 blocked on "0 stock clips" - that was wrong**, I had looked only in
`video/backgrounds/`; there are 52 in `assets/cache/`.

- **#823** `ops backfill-quality`, mirroring `backfill_features`: as-of window via the new
  `build_quality(recent=)`, carries forward what it does not own, dry run by default. Applied on
  the operator's call - **87 rows, measured runs 3 -> 12**.
- **#824, what that immediately revealed:** grade vs engaged-rate **r=-0.32 over 12 videos**,
  worse than composite's -0.15 on the same twelve. Both scores the pipeline ranks on are
  anti-correlated with engagement. **Not significant at n=12 - filed "do not retune on this".**
- **#822** measured first: the hedged-rumor escape has fired **0 times** in 37 verified runs.
  Neither gate nor rubric moved. The real gap was that `warn_only_unsupported` was never
  persisted; now `gate_waived` with a card reader.
- **#739** measured over 8 fractions/clip and **rejected**: gameplay 147 clips, ALWAYS 2,
  intermittent 90, median 0.25; stock 52, ALWAYS 0, ever 6. `ops footage --persistence`.
- **#818** coverage line (37/12/3). **#817** settled by measurement, no code change.

Found: **#824** anti-predictive card · **#825** `--force` was read by four ops verbs, declared by
none, *and* hardcoded to False after `parse_args` · **#826** per-claim types exist only from run
76, and unlike #818 are **not** backfillable.

Caught in audit, self-inflicted: right after applying #823 the snapshot line claimed "today's
rubric reproduces every one" - tautological for a backfilled grade. Rows now stamped
`grade_backfilled`. Also deleted a `_pinned_window` monkeypatch after writing it green, in
favour of the `recent=` passthrough.

Next five: **#826 · #821 · #820 · #824 · #819**. Suite **3,462 -> 3,487**; mypy **139**; ruff
clean; `data/` untouched; backlog **325 open / 734 done**, highest **#826**.

## Pipeline order (operator)

```
Topic → Discovery (signals + editorial ANGLES) → pick angle → length → KEY FACTS → [fact conflicts] → script → TITLE → grounding → [trade check] → tier warnings → claim verifier → authenticity → report card → render → [vault dossier]
```

**Titles are NOT chosen at discovery.** Discovery returns short angle lines; `core/title_generator.py` writes the YouTube title after key facts + script + grounding.

**Vault mirror (Pillar 4):** when `OBSIDIAN_VAULT_PATH` is set, every drafted/rendered run writes `{channel}/_runs/{date}_{slug}-{id}.md`; `daily_sync` / `ops vault-sync` refresh dossiers with post-sync actuals. Strategy notes feed a bounded `CHANNEL PLAYBOOK` block in the script prompt (style, not facts).

---

## Key facts (operator ground truth)

| Feature | Where |
|---------|--------|
| Multi-line paste | Type `paste` at key-facts prompt |
| Vault save (all facts) | `vault/<channel>/_operator_facts/<date>_<topic>.md` (stamped `tier: operator` + `verified_at`) |
| LLM packing | Char budget default 12000 (`OPERATOR_KEY_FACT_CHAR_BUDGET`), soft 24 lines |
| Priority | manual → links → vault |
| Conflicts | Operator facts win — contradicting signal/web lines dropped pre-prompt (`FACT_CONFLICT_FILTER`) |
| Playbook | Strategy/belief notes → `CHANNEL PLAYBOOK` prompt block (NOT facts) |
| Run dossiers | `vault/<channel>/_runs/` — records of what we made, never read back as facts |
| Link scrape | Yahoo/list items OK; ESPN WAF → use `paste`; Bing search/captcha blocked; `ck/a` unwraps |
| Sports on TapIn | `infer_domain(key_facts=)` + NBA script matrix — pasted NBA facts override gaming default |
| **Headless** | `auto_generate --facts-file <paste-block.txt> --fact "..."` (repeatable) |

---

## Credit / speed

- **O1–O11 backlog complete** ([credit_efficiency.md](credit_efficiency.md)). `core/quota_governor.py`
  is the single façade over `data/quota_state.json`: Apify exhaustion + usage cache, LLM daily
  spend, persisted signal disables (key-hash invalidated), `snapshot()` for the dashboard.
- Apify 403 = auth (30m TTL), 402 = credits — persists until the real monthly cycle reset
  (`core/reset_window.py`, `APIFY_RESET_DAY`, O10)
- `SIGNAL_BACKEND=apify|free|auto` — `free`/`auto` serve `youtube_competitors` via yt-dlp and
  `reddit` via official OAuth (free script app) at $0; Twitter/TikTok stay Apify
- The claim verifier adds **one extract-tier LLM call per script** (free-first chain, §14);
  `CLAIM_VERIFIER_ENABLED=false` opts out
- Vault reads are **mtime-cached in-process** (`core/vault_index.py`) — no extra cost, big win
  for `batch-drafts` (N ideas × `load_facts` per run)
- `py -m scripts.ops reliability` — dashboard (breakers, budgets, persisted disables, resets, cache)

---

## Best 5 terminal commands (outside `py main.py`)

1. `py -m scripts.ops daily-brief` — morning one-shot: fresh data → ideas → quota → queue
2. `py -m scripts.ops traces` / `ops dossier --run-id N` — run ledger viewers
3. `py -m scripts.ops vault-sync --channel tapin` — beliefs + dossier refresh into vault
4. `py -m scripts.ops batch-drafts --channel tapin --count 3` — unattended draft scripts (feeds A/B)
5. `py -m scripts.ops reliability` — credit/quota/breaker/cache dashboard
6. `py -m scripts.ops feeds` — RSS source health (ok/stale/dead); run monthly, feeds die quietly

Setup path (fresh machine): `py -m scripts.ops all-setup --channel tapin`.

---

## Open (roadmap next)

**Pickup:** take the Pillow/requests/MoviePy dependency wave when a real render
can verify it. Candidates **23–28** (remaining caption/thumb aesthetics) and **56–90** leftovers sit at
the bottom of Next up. Phase M stays parked. **#147 FastAPI still skipped.**

**Already done (do not re-open):**
- Ten-small-task wave (2026-08-25): MoneyWise persona; #21, #22, #31, #39,
  #53, #262, #271, #298, and #299.
- Post-wave-4 pickup (2026-08-25): #313, #282, #308–310, #232 and #122.
- Caption-text from the script (`video/caption_retext.py`, 2026-08-16). The **$0 TTS
  switch** is unblocked and waiting on two *operator* calls: judge
  `output/samples/piper_lessac_run65.mp3`, then re-run
  `py -m scripts.bench_script_duration` (Piper reads ~20% slower).
- Silent `pass` handlers (S110/S112, 2026-08-16).
- **PR #34 merged 2026-08-19** (`6389e87`), CI green on `main`. All seven stale PRs
  **#26–#32 closed**. Pre-merge check: Alembic `0004`, 4/4 FKs, 37/37 feeds, 1,433
  tests. `feat/research-intake-repair` and `feat/trade-validation-default-on` are in
  `main` and safe to delete.
- Coverage wave: `prepend_channel_intro`, `process_one` quota gate, `_defer_for_quota`,
  `build_render_ffmpeg_command` **done**. Remaining: **`youtube/oauth.py` tests**
  (never `config/secrets/`) and the `coverage` extra (report only, no CI %).
- Router vision path (2026-08-20): thumbnail scorer uses `llm_router.complete` with
  image parts; `core/llm_client.py` deleted. Pillar 2 *rendered-video* review is still
  later. Semantic authenticity (`AUTHENTICITY_SEMANTIC`) default-on, warn-never-block.
- Cheap-tier dead slugs: OpenRouter cheap repointed on live test; Ollama reports
  unavailable when nothing is pulled (run 66 / run 70). `ops free-doctor` now says
  **pull** vs **serve** vs OpenRouter throttled fallback.

**Still open:**
1. **Reinstall the venv** after the Pillow 11.3 / requests 2.32.4 / moviepy-drop
   pin change, then do a real thumbnail/render. Do not start with clip-from-source,
   avatar, #147 FastAPI, or Phase M.
2. **Pillar 6 remainder** — seams live; heavy backends wait on a **CUDA torch**
   build (`2.8.0+cpu` on an RTX 4070 Ti), not on hardware. Clip-from-source and
   storyboard still not started. [providers_runbook.md](providers_runbook.md),
   [video_creation_stack.md](video_creation_stack.md).
3. **Pillar 2 remainder** — multimodal rendered-video review (vision path now
   exists); calibration/predictor stay volume-gated (10 measured vs threshold 15).
4. **Unphased:** MoneyWise depth, AI Tools/Tech groundwork. Overnight `--facts-file`
   is wired. Vault wolverine-only bullets (no franchise string) still attach.
5. **Vault:** stable-path dossier upsert (date-prefix clones the same `run_id`).
6. **One-time ops:** re-auth `youtube.readonly` for tapin; `oauth_setup` for MoneyWise.
7. **Do not merge** `origin/claude/docs-optimization-review-a4l104` (9 commits, no
   PR, last touched 2026-07-21, old base — same shape as #27).
   `origin/feat/reddit-free-backend-and-signal-persistence` is in `main`; delete it.

**Parked / excluded:** Instagram + TikTok platform linking (Phase M) · Benable bot.

---

## Docs to read first

- `docs/decisions.md` §15 (pillar reorientation), §16 (Fact Engine), **§17b (vault OS)**
- `docs/credit_efficiency.md` — O1–O11 (all ✅)
- `docs/roadmap.md` — Pillars 1–7 ✅ (Pillar 6 backends parked on CUDA torch); post-wave-4 pickup shipped
- `docs/providers_runbook.md` — Pillar 6 tool → module → env → proof index
- `docs/debugging.md` — playbook vs facts, hallucination triage

---

## Key files

```
apis/mma_stats_api.py       — API-SPORTS MMA fighter records (replaced Tapology)
core/feed_health.py         — RSS ok/stale/dead checker behind `ops feeds`
core/signal_facts.py        — per-signal -> prompt formatting (add a branch for new data keys)
core/vault_dossiers.py      — Pillar 4: run dossiers + weekly report into vault
core/vault_index.py         — Pillar 4: mtime-cached vault parse
core/obsidian_facts.py      — load_facts + load_playbook/playbook_block
core/fact_store.py          — Pillar 3: FactRecord, tiers, freshness
core/claim_verifier.py      — Pillar 3: claim verifier + GROUNDING_GATE
core/run_trace.py           — Pillar 1: per-run traces
core/video_grade.py         — Pillar 2: pre-publish report card
core/quota_governor.py      — O11 façade
core/providers.py           — Pillar 6: provider-slot contract (ProviderResult, run_chain)
core/link_facts.py          — goose3-first article extraction (+ BeautifulSoup fallback)
docs/providers_runbook.md   — Pillar 6: tool → module → env → proof index
scripts/ops.py              — ~40 subcommands (vault-sync, traces, dossier, batch-drafts)
main.py                     — interactive flow + gates + report card
```
