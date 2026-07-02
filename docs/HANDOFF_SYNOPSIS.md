# Handoff synopsis — 2026-07 waves: fact-first, O10, coach, UI themes (2026-07-02)

Use in a fresh Cursor tab to continue `content_machine` without re-reading the full thread.

## Branch / PR

- **Branch:** `fix/credit-efficiency-review` → `main`
- **PR:** https://github.com/jmcdigmarketing-cpu/content_machine/pull/24 (CI green, mergeable)
- **Suite:** 645 tests green · **Pre-PR:** `ruff check .` · `ruff format .` · `python -m unittest discover -s tests`

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

- Apify 403 = auth (30m TTL), 402 = credits — **402 now persists until the real monthly cycle reset** (`core/reset_window.py`, `APIFY_RESET_DAY`, O10)
- YouTube quota-blocked uploads retry 5 min after the real midnight-PT reset
- `RESET_WINDOW_AUTO_ENABLE=false` restores flat TTLs; manual clear: `data/quota_state.json`
- Social signals skip instantly when the Apify breaker is tripped; `SIGNAL_BACKEND=auto` = yt-dlp YouTube fallback
- `py -m scripts.ops reliability` — dashboard (now shows next-reset times + unit meters)

---

## Shipped 2026-07-02 (three waves, all on this branch)

**Wave 1 — fact-first pipeline:** `core/operator_facts.py` (paste, vault, char budget) · angles not titles (`apis/topic_variants.py`) · `core/title_generator.py` after facts+script · grounding gate before render.

**Wave 2 — five roadmap objectives:**
1. **O10** `core/reset_window.py` (see Credit/speed above)
2. **Semantic trade validation** `core/trade_validation.py` — opt-in `SEMANTIC_TRADE_VALIDATION=true`; flags `player → team` pairings never on one fact line (fused-trade catch); warns after Fact grounding, never blocks
3. **Creator coach** `core/creator_coach.py` → `py -m scripts.ops coach` (ranked ideas + why, length, post time, title patterns, cadence, retention)
4. **Weekly digest next actions** — `weekly-report` prints numbered instructions from winners/losers (±3pp noise gate)
5. **Headless key facts** for `auto_generate`

**Wave 3 — terminal UI themes:** `core/themes.py` registry; `CONTENT_UI_THEME=onepiece|zelda|pokemon|dbz|jjba|plain|default` (env → channel `"ui_theme"` in channels.json → default). Skins swap palette (16/256-color, `CONTENT_UI_COLOR_DEPTH`), spinner frames + loading copy, section glyphs, meters (❤❤♡ cadence), mascot panel, celebration art, ≥90-score hype ("IT'S OVER 9000!"). Full-terminal-width sections (cap 100). `meter()` gauges in cadence/reliability/coach; `maybe_print_milestone()`; `print_celebration()`. New batch: **`ops daily-brief`** = daily-sync + coach + reliability + status.

---

## Best 5 terminal commands (outside `py main.py`)

1. `py -m scripts.ops daily-brief` — morning one-shot: fresh data → ideas → quota → queue
2. `py -m scripts.ops coach` — daily ideas + why (fast, no sync)
3. `py -m scripts.ops all-checks` — validate + tests ("done" = CI passes)
4. `py -m scripts.auto_generate --channel tapin --dry-run --facts-file facts.txt` — headless script + gates, no render
5. `py -m scripts.ops reliability` — credit/quota/breaker/cache dashboard

Setup path (fresh machine): `py -m scripts.ops all-setup --channel tapin`.

---

## Open (roadmap next)

1. **O11** — unified quota governor (`core/quota_governor.py`, merges the 3 breakers' state)
2. **Thumbnail A/B** (Phase S remainder)
3. **Batch generation** · signal-breaker persistence (key-hash invalidation)
4. Optional: promote `SEMANTIC_TRADE_VALIDATION` to default-on if precise in live runs

---

## Docs to read first

- `docs/decisions.md` §3 (grounding), §4 (key facts), §4b (title timing), §13b (reset windows), §13c (trade validation)
- `docs/credit_efficiency.md` — O1–O11 (O10 ✅)
- `docs/roadmap.md` — "Current focus (2026-07)" + "UI / experience — themeable skins"
- `docs/debugging.md` — "Script accuracy / hallucinations"

---

## Key files

```
core/themes.py              — theme registry (6 skins), meter(), themed_phase()
core/reset_window.py        — O10 reset cadences (youtube/apify/odds)
core/trade_validation.py    — fused-trade check (opt-in)
core/creator_coach.py       — ops coach (ideas + why)
core/operator_facts.py      — paste, vault, char budget
core/title_generator.py     — title after facts + script
core/fact_grounding.py      — mononyms, word boundaries
core/content_engine.py      — script JSON (no title field)
analytics/weekly_report.py  — digest + next actions
scripts/ops.py              — ~35 subcommands, 5 batches
main.py                     — flow order, theme init, celebrations
```
