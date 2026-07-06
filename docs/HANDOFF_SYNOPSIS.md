# Handoff synopsis — 2026-07-06 wave: free backends, batch/A/B, webhooks, O11 governor

Use in a fresh session to continue `content_machine` without re-reading the full thread.

## Branch / PR

- **Branch:** `feat/reddit-free-backend-and-signal-persistence` → `main`
- **Suite:** 720 tests green · **Pre-PR:** `ruff check .` · `ruff format .` · `python -m unittest discover -s tests`
- Prior wave (fact-first, O10, coach, UI themes) merged via PR #24.

---

## Pipeline order (operator)

```
Topic → Discovery (signals + editorial ANGLES) → pick angle → length → KEY FACTS → script → TITLE → grounding → [trade check] → authenticity → render
```

**Titles are NOT chosen at discovery.** Discovery returns short angle lines; `core/title_generator.py` writes the YouTube title after key facts + script + grounding.

---

## Key facts (operator ground truth)

| Feature | Where |
|---------|--------|
| Multi-line paste | Type `paste` at key-facts prompt |
| Vault save (all facts) | `vault/<channel>/_operator_facts/<date>_<topic>.md` |
| LLM packing | Char budget default 4500 (`OPERATOR_KEY_FACT_CHAR_BUDGET`), soft 24 lines |
| Priority | manual → links → vault |
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
- `py -m scripts.ops reliability` — dashboard (breakers, budgets, persisted disables, resets, cache)

---

## Shipped 2026-07-06 (this branch)

1. **Reddit free backend** — `apis/free_backends.fetch_reddit_free` (official OAuth; keyless scraping is 403-blocked); 429s feed the rate-limit cooldown.
2. **Signal-breaker persistence + key-hash invalidation** (O11 seed) — hard signal trips persist across runs (`SIGNAL_BREAKER_PERSIST`); a changed credential env clears the record instantly.
3. **Batch generation** — `py -m scripts.ops batch-drafts --channel tapin --count 3`: N ideas → N render-free draft scripts in `output/<ch>/drafts/` (no TTS spend, no cadence impact).
4. **Script-lever A/B** — `py -m core.experiments start hook_style|cta_style` + `ops experiment` (low-n-safe Bayesian report; winner at P(best) ≥ 95%). Fed by batch-drafts.
5. **Thumbnail A/B** — `py -m core.experiments start thumbnail_style` (close_up vs wide_drama on Flux prompts; Pillow fallbacks never pollute attribution).
6. **Webhook events out** — `EVENT_WEBHOOK_URL` POSTs `run_completed` / `video_published` / `batch_completed`; fire-and-forget daemon thread.
7. **O11 complete** — Apify + LLM router persistence migrated behind `core/quota_governor.py`; unified `snapshot()`; `core/reliability.py` reads via facades. Same scopes/keys, zero env changes.

---

## Best 5 terminal commands (outside `py main.py`)

1. `py -m scripts.ops daily-brief` — morning one-shot: fresh data → ideas → quota → queue
2. `py -m scripts.ops coach` — daily ideas + why (fast, no sync)
3. `py -m scripts.ops all-checks` — validate + tests ("done" = CI passes)
4. `py -m scripts.ops batch-drafts --channel tapin --count 3` — unattended draft scripts (feeds A/B)
5. `py -m scripts.ops reliability` — credit/quota/breaker/cache dashboard

Setup path (fresh machine): `py -m scripts.ops all-setup --channel tapin`.

---

## Open (roadmap next — see "Internal-systems pillars — 2026-H2" in roadmap.md)

*Reoriented 2026-07-06 (decisions §15): Phases T–W folded into five pillars. All
pillar work is proposed / not started — **implementation held for operator review**.*

1. **Pillar 1 — Run Ledger** (do first): per-run trace, `quality_json` persistence,
   `ops traces`/`dossier` viewers, data-quality monitor *(was T + V)*, unit-economics
   join *(was U)*
2. **Pillar 2 — Video Grading System**: pre-publish report card → predicted
   engaged-rate → calibration loop *(data-gated)* → multimodal review *(later)*
3. **Pillar 3 — Fact Engine 2.0**: structured fact store, tiered grounding corpus,
   claim-level verifier, contradiction detection, `web_search` source capture
4. **Pillar 4 — Obsidian knowledge OS**: run dossiers into the vault, vault index,
   playbook read path, structured fact templates
5. **Pillar 5 — Agent layer** (last): Channel Health Agent *(was W)*, verifier stage,
   weekly analyst agent, overnight operator
6. Supporting/unphased: O12 governor follow-ups, router vision path, Whisper local,
   MoneyWise depth, AI Tools/Tech groundwork
7. Optional: promote `SEMANTIC_TRADE_VALIDATION` to default-on if precise in live runs
8. One-time ops: re-auth `youtube.readonly` for tapin; `oauth_setup` for MoneyWise

**Parked / excluded:** Instagram + TikTok platform linking (Phase M, far later) · Benable bot.

---

## Docs to read first

- `docs/decisions.md` §3 (grounding), §4 (key facts), §4b (title timing), §13 (breaker layers), §13b (reset windows)
- `docs/credit_efficiency.md` — O1–O11 (all ✅; O12 candidates under O11)
- `docs/roadmap.md` — "Up next" + "Candidate phases — 2026-H2 expansion"
- `docs/agent_reach_evaluation.md` — free/keyless backend evaluation (SIGNAL_BACKEND)
- `docs/debugging.md` — "Script accuracy / hallucinations"

---

## Key files

```
core/quota_governor.py      — O11 façade: apify/llm/signal persistence + snapshot()
core/quota_state.py         — the dumb TTL'd store underneath (data/quota_state.json)
apis/free_backends.py       — yt-dlp YouTube + Reddit OAuth free backends
core/experiments.py         — A/B lifecycle; core/experiment_levers.py arms
core/batch_generation.py    — ops batch-drafts (render-free volume)
core/events.py              — webhook events out (fire-and-forget)
core/reset_window.py        — O10 reset cadences (youtube/apify/odds)
core/reliability.py         — ops reliability dashboard (governor-backed)
analytics/weekly_report.py  — digest + next actions
scripts/ops.py              — ~38 subcommands, 5 batches
main.py                     — flow order, theme init, celebrations
```
