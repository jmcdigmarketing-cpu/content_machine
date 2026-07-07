# Handoff synopsis — 2026-07-06 wave 2: Pillars 1–3 shipped (ledger, grading, fact engine)

Use in a fresh session to continue `content_machine` without re-reading the full thread.

## Branch / PR

- **Branch:** `feat/reddit-free-backend-and-signal-persistence` → `main`
- **Suite:** 833 tests green · **Pre-PR:** `ruff check .` · `ruff format .` · `python -m unittest discover -s tests`
- This branch now carries two waves: the morning wave (free backends, batch/A/B,
  webhooks, O11 governor) **and** Pillars 1–3 of the internal-systems reorientation
  (decisions §15). Prior wave (fact-first, O10, coach, UI themes) merged via PR #24.

---

## Pipeline order (operator)

```
Topic → Discovery (signals + editorial ANGLES) → pick angle → length → KEY FACTS → [fact conflicts] → script → TITLE → grounding → [trade check] → tier warnings → claim verifier → authenticity → report card → render
```

**Titles are NOT chosen at discovery.** Discovery returns short angle lines; `core/title_generator.py` writes the YouTube title after key facts + script + grounding.

---

## Key facts (operator ground truth)

| Feature | Where |
|---------|--------|
| Multi-line paste | Type `paste` at key-facts prompt |
| Vault save (all facts) | `vault/<channel>/_operator_facts/<date>_<topic>.md` (stamped `tier: operator` + `verified_at`) |
| LLM packing | Char budget default 4500 (`OPERATOR_KEY_FACT_CHAR_BUDGET`), soft 24 lines |
| Priority | manual → links → vault |
| Conflicts | Operator facts win — contradicting signal/web lines dropped pre-prompt (`FACT_CONFLICT_FILTER`) |
| Link scrape | Yahoo/list items OK; ESPN WAF → use `paste` |
| **Headless** | `auto_generate --facts-file <paste-block.txt> --fact "..."` (repeatable) |

---

## Credit / speed

- **O1–O11 backlog complete** ([credit_efficiency.md](credit_efficiency.md)). `core/quota_governor.py`
  is the single façade over `data/quota_state.json`: Apify exhaustion + usage cache, LLM daily
  spend, persisted signal disables (key-hash invalidated), `snapshot()` for the dashboard.
  Check points stay layered (decisions §13) — governor unifies state/persistence/reporting only.
- Apify 403 = auth (30m TTL), 402 = credits — persists until the real monthly cycle reset
  (`core/reset_window.py`, `APIFY_RESET_DAY`, O10)
- YouTube quota-blocked uploads retry 5 min after the real midnight-PT reset
- `RESET_WINDOW_AUTO_ENABLE=false` restores flat TTLs; manual clear: `data/quota_state.json`
- `SIGNAL_BACKEND=apify|free|auto` — `free`/`auto` serve `youtube_competitors` via yt-dlp and
  `reddit` via official OAuth (free script app) at $0; Twitter/TikTok stay Apify
- The claim verifier adds **one extract-tier LLM call per script** (free-first chain, §14);
  `CLAIM_VERIFIER_ENABLED=false` opts out
- `py -m scripts.ops reliability` — dashboard (breakers, budgets, persisted disables, resets, cache)

---

## Shipped 2026-07-06 (this branch — afternoon wave: Pillars 1–3)

1. **Pillar 1 — Run Ledger** (decisions §15): `core/run_trace.py` per-run traces
   (`data/traces/`), `content_runs.quality_json` (Alembic `0003`) built by
   `core/run_quality.py` for every path, `ops traces` / `ops dossier --run-id N`
   viewers, `core/data_quality.py` monitor, unit-economics join (`ops economics`).
2. **Pillar 2 — Video Grading** : `core/video_grade.py` pre-publish report card
   (0–100 + letter, shown before render + `ops grade`), data-gated engaged-rate
   predictor + calibration loop (`ops calibration`), prompt-eval set
   (`ops prompt-eval`), `analyst_accuracy` realigned to engaged-rate.
3. **Pillar 3 — Fact Engine 2.0** (decisions §16): `core/fact_store.py` structured
   facts from vault frontmatter (tier/verified_at/expires; expired notes drop,
   provenance+freshness tiebreak ranking); `core/grounding_tiers.py` tiered corpus
   (operator|link|web|signal|brief|context — YouTube titles are context, not facts;
   high-stakes/low-tier warnings); `core/claim_verifier.py` claim-level LLM verifier
   (default-on, `GROUNDING_GATE=warn|block`); `core/fact_conflicts.py` pre-script
   contradiction detection (operator wins, losing lines dropped);
   `capture_web_sources()` web_search URLs → `_sources.md`; quality_json **v2**
   (+ claim_support_rate, unsupported/conflict/tier-warning counts) penalizing the
   grade's grounding component.

### Shipped 2026-07-06 (this branch — morning wave)

1. **Reddit free backend** — `apis/free_backends.fetch_reddit_free` (official OAuth; keyless scraping is 403-blocked); 429s feed the rate-limit cooldown.
2. **Signal-breaker persistence + key-hash invalidation** (O11 seed) — hard signal trips persist across runs (`SIGNAL_BREAKER_PERSIST`); a changed credential env clears the record instantly.
3. **Batch generation** — `py -m scripts.ops batch-drafts --channel tapin --count 3`: N ideas → N render-free draft scripts in `output/<ch>/drafts/` (no TTS spend, no cadence impact); draft meta now carries grade inputs + fact-engine outputs.
4. **Script-lever A/B** — `py -m core.experiments start hook_style|cta_style` + `ops experiment` (low-n-safe Bayesian report; winner at P(best) ≥ 95%). Fed by batch-drafts.
5. **Thumbnail A/B** — `py -m core.experiments start thumbnail_style` (close_up vs wide_drama on Flux prompts; Pillow fallbacks never pollute attribution).
6. **Webhook events out** — `EVENT_WEBHOOK_URL` POSTs `run_completed` / `video_published` / `batch_completed`; fire-and-forget daemon thread.
7. **O11 complete** — Apify + LLM router persistence migrated behind `core/quota_governor.py`; unified `snapshot()`; `core/reliability.py` reads via facades. Same scopes/keys, zero env changes.

---

## Best 5 terminal commands (outside `py main.py`)

1. `py -m scripts.ops daily-brief` — morning one-shot: fresh data → ideas → quota → queue
2. `py -m scripts.ops traces` / `ops dossier --run-id N` — run ledger viewers (new)
3. `py -m scripts.ops all-checks` — validate + tests ("done" = CI passes)
4. `py -m scripts.ops batch-drafts --channel tapin --count 3` — unattended draft scripts (feeds A/B)
5. `py -m scripts.ops reliability` — credit/quota/breaker/cache dashboard

Setup path (fresh machine): `py -m scripts.ops all-setup --channel tapin`.

---

## Open (roadmap next — see "Internal-systems pillars — 2026-H2" in roadmap.md)

*Pillars 1–3 shipped this branch (decisions §15–16). Remaining:*

1. **Pillar 4 — Obsidian knowledge OS**: run dossiers into the vault, vault index
   (replace the per-call `rglob` scan), playbook read path. *(Structured fact
   templates landed with Pillar 3.)*
2. **Pillar 5 — Agent layer** (last): Channel Health Agent *(was W)*, weekly analyst
   agent, overnight operator. *(Verifier stage landed with Pillar 3.)*
3. **Pillar 2 remainder**: multimodal rendered-video review *(later — needs router
   vision path)*; calibration/predictor activate as measured volume accrues.
4. Supporting/unphased: O12 governor follow-ups, router vision path, Whisper local,
   MoneyWise depth, AI Tools/Tech groundwork
5. Optional: promote `SEMANTIC_TRADE_VALIDATION` to default-on if precise in live
   runs (the claim verifier now covers trades generically — see decisions §16)
6. One-time ops: re-auth `youtube.readonly` for tapin; `oauth_setup` for MoneyWise

**Parked / excluded:** Instagram + TikTok platform linking (Phase M, far later) · Benable bot.

---

## Docs to read first

- `docs/decisions.md` §3 (grounding), §4 (key facts), §13 (breaker layers), §15 (pillar reorientation), **§16 (Fact Engine 2.0)**
- `docs/credit_efficiency.md` — O1–O11 (all ✅; O12 candidates under O11)
- `docs/roadmap.md` — "Internal-systems pillars — 2026-H2" (Pillars 1–3 ✅)
- `docs/agent_reach_evaluation.md` — free/keyless backend evaluation (SIGNAL_BACKEND)
- `docs/debugging.md` — "Script accuracy / hallucinations"

---

## Key files

```
core/run_trace.py           — Pillar 1: per-run trace writer (data/traces/)
core/run_quality.py         — quality_json v2 builder (hook/auth/grounding/fact-engine)
core/run_ledger.py          — ops traces / dossier viewers + quality persistence
core/video_grade.py         — Pillar 2: pre-publish report card (ops grade)
core/fact_store.py          — Pillar 3: FactRecord, tiers, freshness, frontmatter
core/grounding_tiers.py     — tiered corpus + high-stakes/context warnings
core/claim_verifier.py      — claim-level LLM verifier + GROUNDING_GATE
core/fact_conflicts.py      — pre-script contradiction detection (operator wins)
core/quota_governor.py      — O11 façade: apify/llm/signal persistence + snapshot()
core/experiments.py         — A/B lifecycle; core/experiment_levers.py arms
core/batch_generation.py    — ops batch-drafts (render-free volume)
scripts/ops.py              — ~40 subcommands, 5 batches
main.py                     — flow order, gates (authenticity + grounding), report card
```
