# Handoff synopsis — 2026-09-26: wave 33, run 98

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-09-26

Use in a fresh session to continue `content_machine` without re-reading the full thread.

GPT-6 playground review (2026-09-08, briefing-based): [gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md) and [gpt6_part2_upgrades_2026-09-08.md](gpt6_part2_upgrades_2026-09-08.md). Not a recorded operator decision.

> Older waves and the 2026-07/08 shipped-notes are frozen verbatim in
> [handoff_synopsis_archive.md](handoff_synopsis_archive.md); this file keeps the newest three
> waves plus the standing operator sections (docs_standard.md §7).

## Last wave — 2026-09-26 (Claude Code): wave 33, run 98 #840-#847 + plans

The operator's run 98 (tapin, "Manchester City ofund guilty, what does this mean for the prem")
and five questions. Answers are in [planning_log.md](planning_log.md); the sample-size one is
also in [master_plan.md](master_plan.md) M4.5 (n=23 cannot see a weak effect; r=0.3 needs ~85
videos, so retunes are logic-driven until then).

- **#840** sentence-TTS join wrote relative paths into the ffmpeg concat list: every
  multi-sentence ElevenLabs render since 09-20 was voiced twice. Absolute entries now.
- **#841 #842** the topic's domain comes from the topic (`infer_topic_domain`,
  `effective_domain`, `off_niche_note`); football is TapIn's (`soccer` domain, matrix,
  weights, `extra_domains`, per-domain sign-off and tags). Decisions §34.
- **#843** RAWG question words, Twitch site-wide viewers, fan-out question halves, Steam
  junk, and popularity dumps as "verified facts" - all gone.
- **#844-#846** page titles are metadata; JS shells retry the proxy; `LINK_FACT_MAX_LINES`;
  pasted-link lines are `tier: link` in `_link_facts/`; borrowed vault lines never pin;
  pasted-link lines with no contact with the angle are listed, Enter drops, `k` keeps.
- **#847** report card v5: topic 0.12 -> 0.05 (operator: lower, keep).
- **Docs:** [vault.md](vault.md) (new), [tooling_review_2026-09-26.md](tooling_review_2026-09-26.md)
  (new, verified), master_plan M4.5-M4.7, desktop facts room **#860**, seven long-retired
  desktop items closed, `.env.example` and API-doc drift fixed.
- **CI:** run 162 went red on a docs line I added after the last suite run (#857 named an
  unbuilt `ops` verb); fixed in `1a7fdc2`.

**Verify:** `py -m scripts.ops test --order reverse` · `python -m unittest tests.test_run98_domain
tests.test_run98_fact_intake tests.test_run98_signal_facts tests.test_tts_concat_paths
tests.test_grade_v5`.

**Operator:** `git pull`; `py -m scripts.ops calibration`; `py -m scripts.ops backfill-quality
--channel tapin --force` then `--apply`; after the next render `ops reliability` should show
TTS-cache hits and one charge. Optional: `API_SPORTS_KEY` for football signals.

## Previous — 2026-09-26 (Claude Code): wave 32 #826 #820 #824 #821 #819

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

## Pipeline order (operator)

```
Topic → Discovery (signals + editorial ANGLES) → pick angle → length → KEY FACTS → [fact conflicts] → script → TITLE → grounding → [trade check] → tier warnings → claim verifier → authenticity → report card → render → [vault dossier]
```

**Titles are NOT chosen at discovery.** Discovery returns short angle lines; `core/title_generator.py` writes the YouTube title after key facts + script + grounding.

**Vault mirror (Pillar 4):** when `OBSIDIAN_VAULT_PATH` is set, every drafted/rendered run writes `{channel}/_runs/{run_id}_{slug}.md` (layout: [vault.md](vault.md)); `daily_sync` / `ops vault-sync` refresh dossiers with post-sync actuals. Strategy notes feed a bounded `CHANNEL PLAYBOOK` block in the script prompt (style, not facts).

---

## Key facts (operator ground truth)

| Feature | Where |
|---------|--------|
| Multi-line paste | Type `paste` at key-facts prompt |
| Vault save (all facts) | typed lines -> `vault/<channel>/_operator_facts/` (`tier: operator`); pasted-link lines -> `_link_facts/` (`tier: link`, since run 98) |
| LLM packing | Char budget 12000 (`OPERATOR_KEY_FACT_CHAR_BUDGET`), line cap 150 (`MAX_OPERATOR_KEY_FACTS`); only lines typed this run pin |
| Priority | typed → links → vault; pasted-link lines with no contact with the angle are listed first (Enter drops, `k` keeps) |
| Conflicts | Operator facts win — contradicting signal/web lines dropped pre-prompt (`FACT_CONFLICT_FILTER`) |
| Playbook | Strategy/belief notes → `CHANNEL PLAYBOOK` prompt block (NOT facts) |
| Run dossiers | `vault/<channel>/_runs/` — records of what we made, never read back as facts |
| Link scrape | Yahoo/list items OK; ESPN WAF → use `paste`; Bing search/captcha blocked; `ck/a` unwraps |
| Sports on TapIn | domain from the topic (`infer_topic_domain`); football is TapIn's (`soccer`, §34); NBA/NFL/UFC/soccer matrices; pasted sport facts still override |
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

The live list is [roadmap.md](roadmap.md) "Recommended next five"; this is the standing context.

1. **Operator, after pulling:** `ops calibration`, `ops backfill-quality --force` (v5 re-stamp),
   check `ops reliability` for single TTS charges. #821 and #819 wait on those numbers.
2. **Product next:** #848 auto-research · #852 entity-aware signal queries · #859 soccer feeds ·
   #850 brief sees key facts · #836 angle-score backfill (feeds #849).
3. **Structural (master_plan M3):** #839 hook refuses non-ASCII subjects · #830 · #832 · #831
   ruff bump · #834 `core/` seams.
4. **App:** #860 facts room is the proposed next panel ([desktop_app.md](desktop_app.md)).
5. **Operator calls, standing:** `positioning.md` still pitches a micro-SaaS surface, which
   contradicts the private-tool constraint in [roadmap.md](roadmap.md) - the charter is yours
   to rewrite or archive. One OAuth consent then `ops playlists --apply`; gameplay files for
   the empty niches (#786); remote branch deletions this environment cannot do.

**Parked / excluded:** Phase M (Instagram + TikTok) · Benable bot · Edge TTS as default (§28).

---

## Docs to read first

- `docs/decisions.md` §15 (pillar reorientation), §16 (Fact Engine), **§17b (vault OS)**, **§34 (topic domain, football, link tier, v5)**
- `docs/vault.md` — the vault end to end
- `docs/master_plan.md` — the forward plan, with the sample schedule in M4
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
