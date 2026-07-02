# Handoff synopsis — credit-efficiency review + script accuracy (2026-06-23)

Use this in a fresh Cursor tab to continue work on `content_machine` without re-reading the full audit thread.

## Branch / state

Work spans a debugging pass on the **multi-provider LLM router** and **credit-efficiency** layer, plus a **live-run accuracy** fix after an NBA offseason TapIn session (`py main.py`, channel `tapin`).

Run before PR:

```powershell
cd C:\dev\content_machine
ruff check .
ruff format .
python -m unittest discover -s tests
```

Branch target: `fix/credit-efficiency-review` (or successor) off `main`. PR-only to `main`.

---

## What the live run exposed (operator transcript)

| Symptom | Root cause | Fix status |
|---------|------------|------------|
| ESPN URL → "Could not extract facts" | ESPN returns HTTP 202 + AWS WAF challenge | ✅ `link_fetch_issue()` + clearer UI message |
| Summary: "Apify ran out of credits" but log: `403` | `display_summary` always said "credits" | ✅ uses `apify_status()` |
| 9 key facts "injected" but vault heuristics won | Cap 5; vault listed before manual in LLM order | ✅ manual+links prioritized; UI shows sent vs collected |
| Vault: "Fraud narratives outperform…" (8 bullets) | Strategy/playbook notes treated as ground truth | ✅ filtered in `obsidian_facts.py` |
| Script wrong on LeBron/Kawhi; Authenticity 100/100 | Phase O ≠ factual check; mononyms not grounded | ✅ mononyms + word-boundary grounding + **Fact grounding** CLI section |

---

## Piece 4 — script accuracy stack (shipped)

### 1. Obsidian vault (`core/obsidian_facts.py`)

- Excludes notes tagged `strategy` / `playbook` / `heuristic` / `content-tips` or under `strategy/` paths.
- Filters bullets matching strategy markers unless they contain factual anchors (dates, trades, scores, `$`).
- Lines prefixed `Machine belief:` (from `vault_writeback`) are **kept** — channel analytics priors, not playbook fluff.
- Evergreen **factual** notes still surface; evergreen **playbook** notes do not.

### 2. Sports / grounding (`core/fact_grounding.py`)

- Extracts mononyms (e.g. `LeBron`, `Kawhi`) not already in multi-word phrases.
- Grounding uses whole-token match in corpus (not substring).
- Still **flags only** — does not block render unless operator chooses.

### 3. Key facts priority (`core/ui.py` + `core/content_engine.py`)

- Order sent to LLM: **manual → link extracts → vault**.
- `key_facts_for_prompt()` shows exactly which facts pass `_sanitize_key_facts` (cap 5 × 300 chars).
- Vault prompt label: "factual match(es)".

### 4. CLI (`main.py` + `core/ui.py`)

- New **`Fact grounding`** subsection **before** Authenticity.
- Lists ungrounded entities, key facts that reached the LLM, and explicit note that Authenticity ≠ factual accuracy.
- Extra line before render prompt when grounding failed.

---

## Earlier review fixes (still in tree)

| Area | Change |
|------|--------|
| `quota_state.increment_value` | Atomic LLM daily spend RMW |
| `llm_router.reset_usage` | Resets `_budget_warned` per run |
| `link_facts._is_bot_blocked` | WAF detection |
| Tests | +8–10 around quota, Apify summary, link fetch, grounding, vault |

---

## Intentionally NOT changed

- **ADR §6 / §13** — Apify global breaker vs per-signal breaker remain separate.
- **MAX_OPERATOR_KEY_FACTS = 5** — cap unchanged; priority order fixed instead.
- **Authenticity gate scoring** — still structure/policy, not truth-checking.
- **ESPN scraping** — no headless browser; operator must paste text when WAF blocks.

---

## Open follow-ups (optional next PRs)

1. **Apify 403 root cause** — ✅ distinct messages for 403 auth vs 402 credits; shorter `APIFY_AUTH_FAILURE_TTL_SECONDS` for auth failures; `ops reliability` hints.
2. **`flush_cache_stats` timing** — ✅ discovery flush + `finalize_run_observability()` at pipeline end (`main.py`, `auto_generate.py`).
3. **Semantic fact validation** — headline says X traded to Y; require trade verbs in corpus (higher false-positive risk).
4. **Raise key-facts cap via env** — ✅ `MAX_OPERATOR_KEY_FACTS` (1–20, default 5).
5. **`scripts/auto_generate.py`** — ✅ mirrors `display_grounding_report`; blocks render on grounding failure unless `--force`.

---

## Key files touched

```
core/obsidian_facts.py      — strategy filter
core/fact_grounding.py      — mononyms + word boundaries
core/content_engine.py      — key_facts_for_prompt()
core/ui.py                  — prompt_key_facts order, display_grounding_report, Apify summary
core/link_facts.py          — WAF / link_fetch_issue
main.py                     — grounding section before authenticity
docs/debugging.md           — script accuracy section
docs/decisions.md           — §3, §4 updates
tests/test_obsidian_facts.py
tests/test_fact_grounding.py
tests/test_link_facts.py
tests/test_display_summary.py
```

---

## Operator playbook (NBA / fresh news)

1. Key facts: `n` at vault unless bullets are dated trade lines.
2. Paste 3–5 concrete facts (or Yahoo text) — not ESPN URLs.
3. Read **Fact grounding** after script — not just Authenticity.
4. `py -m core.reliability` or `py -m scripts.ops reliability` for Apify/LLM/cache state.

---

## Docs to read first in a new tab

- `docs/decisions.md` §3 (grounding), §4 (key facts), §6 (breakers), §13 (don't collapse redundancy)
- `docs/debugging.md` — "Script accuracy / hallucinations"
- `docs/credit_efficiency.md` — O1–O11 credit-efficiency waves
