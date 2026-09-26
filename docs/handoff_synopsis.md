# Handoff synopsis — 2026-09-20: wave 30, measurement continued

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-09-26

Use in a fresh session to continue `content_machine` without re-reading the full thread.

GPT-6 playground review (2026-09-08, briefing-based): [gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md) and [gpt6_part2_upgrades_2026-09-08.md](gpt6_part2_upgrades_2026-09-08.md). Not a recorded operator decision.

> Older waves and the 2026-07/08 shipped-notes are frozen verbatim in
> [handoff_synopsis_archive.md](handoff_synopsis_archive.md); this file keeps the newest three
> waves plus the standing operator sections (docs_standard.md §7).

## Last wave — 2026-09-20 (Claude Code): wave 30 #817 #818 #822 #739 #823

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

## Previous — 2026-09-20 (Claude Code): wave 29 #808 #805 #561 #803 #811

Measurement wave. **Wave 28's four fixes are in the same commit** — the operator's call, not a
second commit. Before building I asked the data what existed on `tapin`: 87 runs, 12 with a
synced engaged-rate, 37 with `quality_json`, **3 with both**, and **12 with engaged-rate +
composite_score**. Two of the recommended five changed on that evidence.

**#50 was pulled and refiled data-gated** (a learner for "scripts that actually retained" has a
training set of three). **#561 took the slot** — `build_accuracy_report` had backtested the
recommender for months and only `intelligence_report` read it. **#803's filed premise was
wrong**: `core/authenticity.py:35` is `_RECENT_RUNS = 12`, never one; the real gap is that
`max()` hides a *recurring* shape.

- **#808** grade recorded beside its inputs. Two writers — `build_quality`, then `merge_quality`
  again when `thumbnail_overall` lands post-render, or every published run's snapshot is missing
  its thumbnail component. `QUALITY_VERSION` v3 -> v4; **`GRADE_VERSION` stays v4**.
- **#805** composite correlation computed before the quality filter (that filter is why n was 3).
  **Measured: r=-0.15 over 12 publishes** — the first real number on the score the selection tie
  leans on. Filed as **#819**.
- **#561** 40% hit rate on 10 publishes, printed under the card.
- **#803** `style_recurrence()`, 0.50 shape floor, 3+ flags. **Report-only** — no points, no
  gate, no `GRADE_VERSION` bump (**#821** holds the promotion).
- **#811** `DISCOVERY_DEADLINE_S`, **unset by default**. Explicit executor + `shutdown(wait=False)`:
  a `with ThreadPoolExecutor` block joins on exit and would have defeated the budget entirely.
  Dropped names ride `_deadline` into `DiscoveryResult.meta`, never `timings` (#813).

Found on the way, filed open: **#817** the recurrence window reads all statuses, not published ·
**#818** 37/12/3, so `ops calibration` reads "collecting" for months for historical reasons ·
**#819** composite r=-0.15 · **#820** a dropped signal's thread is abandoned, not cancelled ·
**#821** recurrence is report-only · **#822** hedging passes the render gate (#345) and only
costs grade points (#800) — the two pull opposite ways.

Two new *fields* were written and read by nothing and got the reader they implied rather than
being dropped (`worst_component_drift`, `recurrence_line`). mypy drifted 139 -> 141 behind a
green suite and is back to **139**. Next five: **#818 · #817 · #822 · #819 · #739**. Suite
**3,437 -> 3,462**; ruff clean; `data/` untouched; backlog **326 open / 729 done**, highest
**#822**.

## Previous — 2026-09-20 (Claude Code): wave 28 #813 #814 #815 #816

Review of waves 26-27, no new features. Both waves shipped green and five defects went through
anyway, all the same shape: a wave changed what a value *means* or what a dict may *hold*, and
the readers outside that wave were never re-pointed. **#813** a timed-out discovery crashed the
intelligence report (`TypeError: float + str` out of `to_markdown`, unguarded from `main.py`) —
#802's `variant_scoring_fallback` and #807's `angle_spread` move to `DiscoveryResult.meta`,
persisted trace keys unchanged; **#814** a disabled reground double-counted the held-back
negative-fact flags; **#815** `channel_health` (55/72) and `engagement_predictor` were still on
the field #804 made continuous — both now read `run_quality.authenticity_gate_value`, recorded as
**`decisions.md` §32**; **#816** the retention exemption re-resolved the skip set per file.
Raised, not fixed: #809's `TTS_CACHE` default flip lets a bare `unittest discover -s tests`
(no `-t .`) write the operator's real `data/tts_cache`. Next five unchanged: **#808 · #811 ·
#803 · #805 · #50**. Suite **3,425 -> 3,437**; mypy **139**; ruff clean; backlog **325 open /
724 done**, highest **#816**.

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
