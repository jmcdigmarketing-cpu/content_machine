# Handoff synopsis — 2026-07-07 wave: Pillars 1–4 shipped + live-run hardening

Use in a fresh session to continue `content_machine` without re-reading the full thread.

## Branch / PR

- **Branch:** `feat/reddit-free-backend-and-signal-persistence` → `main`
- **Suite:** 860 tests green · **Pre-PR:** `ruff check .` · `ruff format .` · `python -m unittest discover -s tests`
- This branch carries three waves: morning (free backends, batch/A/B, webhooks, O11),
  afternoon (Pillars 1–3), **Pillar 4** (Obsidian knowledge OS), and **live-run
  hardening** (link scrape, domain/key-fact drift, grounding noise). Prior wave
  (fact-first, O10, coach, UI themes) merged via PR #24.

---

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
| LLM packing | Char budget default 4500 (`OPERATOR_KEY_FACT_CHAR_BUDGET`), soft 24 lines |
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

## Shipped 2026-07-07 (this branch — Pillar 4)

1. **Run dossiers** — `core/vault_dossiers.py`: `{channel}/_runs/{date}_{slug}-{id}.md`
   (topic, angle, report-card grade, quality summary, cost, script, post-sync actuals +
   video URL). Written fail-open from `_finalize_run`; `refresh_dossiers()` via
   `daily_sync` + `ops vault-sync`. Weekly report → `{channel}/_reports/{date}_weekly.md`.
2. **Vault index** — `core/vault_index.py`: per-process mtime cache behind
   `load_fact_records()` — unchanged notes are `stat()`ed, not re-read.
3. **Playbook layer** — `load_playbook()` / `playbook_block()`: strategy + machine-belief
   bullets feed a bounded "CHANNEL PLAYBOOK" block in the script prompt. Fixed `[strategy]`
   tag parsing (`_tag_set`). Dossiers/reports excluded from facts (`_is_machine_record`).

## Shipped 2026-07-06 (this branch — Pillars 1–3 + morning wave)

1. **Pillar 1 — Run Ledger** — traces, `quality_json`, `ops traces`/`dossier`, data-quality
   monitor, unit economics.
2. **Pillar 2 — Video Grading** — report card, predictor, calibration, prompt evals.
3. **Pillar 3 — Fact Engine 2.0** — structured facts, tiered corpus, claim verifier,
   conflict detection, web-source capture, quality v2.
4. **Morning wave** — Reddit free backend, signal-breaker persistence, batch-drafts,
   script-lever + thumbnail A/B, webhook events, O11 governor.

---

## Best 5 terminal commands (outside `py main.py`)

1. `py -m scripts.ops daily-brief` — morning one-shot: fresh data → ideas → quota → queue
2. `py -m scripts.ops traces` / `ops dossier --run-id N` — run ledger viewers
3. `py -m scripts.ops vault-sync --channel tapin` — beliefs + dossier refresh into vault
4. `py -m scripts.ops batch-drafts --channel tapin --count 3` — unattended draft scripts (feeds A/B)
5. `py -m scripts.ops reliability` — credit/quota/breaker/cache dashboard

Setup path (fresh machine): `py -m scripts.ops all-setup --channel tapin`.

---

## Open (roadmap next)

***Pillars 1–5 all shipped** (decisions §15–17) — the internal-systems reorientation
is complete. `ops health` / `analyst` / `overnight` are live. Remaining:*

1. **Pillar 6 — Video Creation Provider Layer** (decisions §17, overrides §8):
   the new headline track — free/local-first cost-metered provider slots. Full tool
   list + build order: [video_creation_stack.md](video_creation_stack.md). Do-first:
   TTS provider chain + local Kokoro (cost lever), then Whisper alignment, music bed,
   AI video-gen slot.
2. **Pillar 2 remainder**: multimodal rendered-video review *(needs router vision path)*;
   calibration/predictor activate as measured volume accrues.
3. Supporting/unphased: O12 governor follow-ups, router vision path, Whisper local,
   MoneyWise depth, AI Tools/Tech groundwork.
4. Agent follow-ups: overnight facts-file intake (needs `generate_draft(key_facts=)`);
   promote `SEMANTIC_TRADE_VALIDATION` default-on if precise in live runs.
5. Vault housekeeping: cross-day dossier refresh leaves prior-day `_runs/` notes (same
   `run_id`, different date prefix) — safe but clutter; stable-path upsert is a follow-up.
6. One-time ops: re-auth `youtube.readonly` for tapin; `oauth_setup` for MoneyWise.

**Parked / excluded:** Instagram + TikTok platform linking (Phase M, far later) · Benable bot.

---

## Docs to read first

- `docs/decisions.md` §15 (pillar reorientation), §16 (Fact Engine), **§17 (vault OS)**
- `docs/credit_efficiency.md` — O1–O11 (all ✅)
- `docs/roadmap.md` — Pillars 1–4 ✅, Pillar 5 next
- `docs/debugging.md` — playbook vs facts, hallucination triage

---

## Key files

```
core/vault_dossiers.py      — Pillar 4: run dossiers + weekly report into vault
core/vault_index.py         — Pillar 4: mtime-cached vault parse
core/obsidian_facts.py      — load_facts + load_playbook/playbook_block
core/fact_store.py          — Pillar 3: FactRecord, tiers, freshness
core/claim_verifier.py      — Pillar 3: claim verifier + GROUNDING_GATE
core/run_trace.py           — Pillar 1: per-run traces
core/video_grade.py         — Pillar 2: pre-publish report card
core/quota_governor.py      — O11 façade
scripts/ops.py              — ~40 subcommands (vault-sync, traces, dossier, batch-drafts)
main.py                     — interactive flow + gates + report card
```
