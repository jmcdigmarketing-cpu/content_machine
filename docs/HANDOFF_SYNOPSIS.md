# Handoff synopsis — fact-first pipeline + credit efficiency (2026-07-02)

Use in a fresh Cursor tab to continue `content_machine` without re-reading the full thread.

## Branch / PR

- **Branch:** `fix/credit-efficiency-review` → `main`
- **PR:** https://github.com/jmcdigmarketing-cpu/content_machine/pull/24
- **Pre-PR:** `ruff check .` · `ruff format .` · `python -m unittest discover -s tests`

---

## Pipeline order (operator)

```
Topic → Discovery (signals + editorial ANGLES) → pick angle → length → KEY FACTS → script → TITLE → grounding → authenticity → render
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
| Writing tips filtered | `is_writing_tip()` in vault + link extract |

---

## Credit / speed (Apify 403)

- Apify 403 vs 402 distinct messages; auth TTL 30m (`APIFY_AUTH_FAILURE_TTL_SECONDS`)
- Twitter/Reddit/TikTok skip instantly when Apify breaker tripped
- `SIGNAL_BACKEND=auto` — yt-dlp YouTube when Apify dead
- `py -m scripts.ops reliability` — one dashboard

---

## Shipped in this wave

- `core/operator_facts.py` — parse, dedupe, vault, char-budget prompt packing
- `core/title_generator.py` — post-script fact-grounded title
- `apis/topic_variants.py` — angles not clickbait titles
- Fact grounding: mononyms, word boundaries, vault strategy filter
- `finalize_run_observability()` — cache stats at pipeline end
- `auto_generate` — grounding gate before render

---

## Shipped 2026-07-02 (second wave)

1. **O10** — `core/reset_window.py`: Apify 402 persists to the real cycle reset (`APIFY_RESET_DAY`); YouTube retries after midnight PT; `RESET_WINDOW_AUTO_ENABLE`
2. **Semantic trade validation** — `core/trade_validation.py`, opt-in `SEMANTIC_TRADE_VALIDATION` (fused-trade check; warns, never blocks)
3. **Phase S coach** — `py -m scripts.ops coach` (ideas + why, length, post time, patterns, cadence); weekly-report now prints **Next actions**
4. **Headless key facts** — `auto_generate --facts-file <paste-block> --fact "..."`

## Open (roadmap next)

1. **O11** — unified quota governor
2. **Thumbnail A/B** (Phase S remainder)
3. **Batch generation** · signal-breaker persistence (key-hash invalidation)

---

## Operator playbook (NBA / trades)

1. Discovery: pick an **angle**, ignore headline-style lines
2. Key facts: `n` at vault unless dated trade bullets; **`paste`** Yahoo block
3. Read **Fact grounding** after script — not just Authenticity
4. Title prints under script before render prompt

---

## Docs to read first

- `docs/decisions.md` §3 (grounding), §4 (key facts), §4b (title timing)
- `docs/debugging.md` — "Script accuracy / hallucinations"
- `docs/credit_efficiency.md` — O1–O11
- `docs/roadmap.md` — "Current focus (2026-07)"

---

## Key files

```
core/operator_facts.py      — paste, vault, char budget
core/title_generator.py     — title after facts + script
core/fact_grounding.py      — mononyms, word boundaries
core/link_facts.py          — HTML/list extract, WAF
core/obsidian_facts.py      — strategy filter
core/content_engine.py      — script JSON (no title field)
apis/topic_variants.py      — discovery angles
main.py                     — flow order, title display
```
