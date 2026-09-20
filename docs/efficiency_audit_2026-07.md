# Efficiency audit — dead code, hardcoding, waste (2026-07)

> **Class:** snapshot · **Status:** frozen · **Reviewed:** 2026-09-20

> **Harvested 2026-08-17 from PR #30 (`claude/efficiency-audit`), which was closed
> unmerged.** Kept for the duplication analysis (~500 LOC genuinely removable), which has
> **not** been actioned. **Its "not installed" record is out of date:** the 2026-08 audit
> found `whisperx`, `faster_whisper`, `piper` and `ctranslate2` all already installed, and
> that the "needs a GPU box" items are blocked by `torch` being a **CPU build** on a
> machine that has an RTX 4070 Ti — an install, not hardware
> ([providers_runbook.md](providers_runbook.md)).

*Report only — no code changed.* A targeted follow-up to
[code_audit_2026-07.md](code_audit_2026-07.md), asking three specific questions:
**what's dead, what's hardcoded, and where is the waste** — plus a standing record of
**which external additions are not installed**, so nothing is assumed working that isn't.

Every number is reproducible with the command shown. **Vulture output was filtered by
hand** — most of its hits are false positives (test helpers, decorator-registered
commands, documented seams), and those are called out explicitly rather than reported
as findings.

---

## 0. Headline: 56k LOC is not bloated — the wins are duplication-shaped

| Where | LOC | Files | Read |
|---|---|---|---|
| `core/` | 20,076 | 98 | ~205 LOC/file avg — healthy except outliers |
| `tests/` | 14,495 | 133 | **26% of the tree is tests** — a strength, not bloat |
| `apis/` | 8,898 | 63 | 29 signal modules ≈ 124 LOC each — reasonable |
| everything else | ~12.7k | 94 | analytics 2.5k, storage 2.2k, assets 1.8k, video 1.1k … |

**Genuinely removable code totals roughly 500 LOC (~1.2% of source).** The honest
answer to "how do we make 56k more efficient" is: *deleting code isn't the lever.*
The levers are **de-duplication** (§3), **one oversized module** (§4.3), and **not
carrying capability you haven't installed** (§1).

---

## 1. ⚠ Not installed — the external additions (standing record)

Per the operator: **the GitHub additions were never properly installed.** Verified in a
clean clone:

**Cloned reference repos — all absent** (they're gitignored/local-only by design, so
absence here is expected; recorded because the *seams* that need them are live code):

| Repo | Seam that needs it | Status |
|---|---|---|
| `ComfyUI/` | `core/comfy_client.py` (190 LOC) | ❌ absent — AI b-roll / thumbnails / upscale inert |
| `ai-marketing-skills/` | `core/grade.py` (78 LOC), `prompts/expert_panel/` | ❌ absent — Expert-Panel grading inert (`EXPERT_PANEL_ENABLED`) |
| `qiaomu-anything-to-notebooklm/` | `core/vault_ingest.py` (166 LOC) | ❌ absent (pattern only) — multi-source ingest limited |
| `system_prompts_leaks/` | `core/run_eval_corpus.py` (78 LOC), `prompts/eval_corpus/` | ❌ absent — the guardrail regression harness has no corpus |

**`[providers]` / `[free]` backends — none importable here:** `kokoro`, `soundfile`,
`whisperx`, `TTS`, `ultralytics`, `piper`, `goose3`, `ddgs`, `yt_dlp`.

> **Caveat:** this is a bare container, so it cannot prove the operator's local state —
> only that nothing is installed *by default*. The list is recorded so the seams'
> inert status is explicit rather than assumed.

### What this actually costs
**~757 LOC of seam code is dormant** (`comfy_client` 190, `vault_ingest` 166, `grade`
78, `run_eval_corpus` 78, `music` 69, `caption_align` 58, `ai_video_provider` 47,
`avatar` 36, `reframe` 35). All are **env-gated and default-off**, so they fail open —
this is *deferred capability, not waste*. But three consequences are worth stating:

1. **Free mode is not actually $0-ready without installs.** It needs **`piper`**
   (local voice — without it Free mode **blocks at render** by design) and **`ddgs`**
   (keyless DuckDuckGo search). Per [free_mode.md](free_mode.md), `pip install -e ".[free]"`.
2. **Pillar-2 grading is running without its qualitative half** — `EXPERT_PANEL_ENABLED`
   can't do anything with the personas absent.
3. **The prompt-eval corpus harness has nothing to replay**, so guardrail regressions
   aren't being caught by it.

**Recommendation:** don't install everything. Install **`.[free]`** (piper + ddgs — small,
high value, unlocks the $0 path) and treat ComfyUI/whisperx/ultralytics as
install-when-needed. Add a line to `ops free-doctor`-style output showing which optional
backends are absent so this is visible at a glance instead of silent.

## 2. Dead code — real, but small (133 LOC, 0.3%)

### 2.1 Genuinely unreferenced (verified in **both** src and tests)

| LOC | Symbol |
|---|---|
| 46 | `apis/balldontlie_api.py:134 get_balldontlie_stats_signal` |
| 16 | `core/ui.py:495 display_competitor_pulse` |
| 13 | `publishing/registry.py:38 publishers_for_channel` |
| 12 | `apis/scrapers/base.py:124 lines_from_table` |
| 8 | `analytics/competitor_context.py:152 competitor_angle_hints` |
| 7 | `apis/nfl_entities.py:87 is_nfl_topic` |
| 6 | `core/grounding_tiers.py:108 tier_counts` · 6 `core/utils.py:5 generate_filename_from_topic` |
| 5 | `publishing/registry.py:31 enabled_publish_platforms` |
| 2–4 | `core/themes.py theme_names` · `core/ascii_art.py startup_banner` · `core/best_bet.py _filter_on_brand` · `core/content_engine.py _format_signal_facts` · `apis/apify_catalog.py source_enabled` |

**Total: 133 LOC across 14 functions.** Note `_format_signal_facts` is labelled a
"backward-compatible alias" — back-compat for a caller that no longer exists.
`get_balldontlie_stats_signal` (46 LOC) is the only substantial one.

### 2.2 What is **NOT** dead (vulture false positives — do not delete)
- **`reset_*` / `clear_cache` helpers** — vulture flags ~10 of them because `tests/`
  was excluded from its scan. All are used: `reset_apify_state` (6 test files),
  `reset_llm_breaker` (4), `reset_cache` (4), `reset_cache_stats`/`reset_reddit_token`/
  `reset_session_breaker`/`reset_llm_spend`/`reset_dead_voices` (2 each). **Test
  infrastructure, not dead code.**
- **`scripts/ops.py cmd_*`** — registered via the `@_register` decorator.
- **`core/avatar.py`, `core/reframe.py`, `core/run_eval_corpus.py`** — documented
  Pillar-6 seams / a CLI entry point (`py -m core.run_eval_corpus`). `reframe.py`
  notably exists *so that the AGPL-3.0 Ultralytics dependency is an explicit choice
  rather than an accidental `pip install`* — that's good design, not cruft.

## 3. Hardcoding — the actual LOC story (1,657 lines)

**46 module-level literal constants of ≥15 lines each total 1,657 LOC** — ~4% of source,
**12× larger than all the dead code combined.** Biggest:

| Lines | Constant |
|---|---|
| 116 | `apis/topic_scorer._LEARNED_PROFILES` |
| 114 | `core/themes.THEMES` |
| 111 | `core/fact_grounding._MONONYM_SKIP` |
| 111 | `apis/learned_weights._DOMAIN_PROFILES` |
| 90 | `core/fact_grounding._COMMON_WORDS` |
| 67 | `video/scene_plan._STOP` |
| 60 | `core/obsidian_facts._GENERIC_TOKENS` · 42 `._STOPWORDS` |

### 3.1 ⭐ Five overlapping stopword vocabularies
Measured set-overlap between the five:

| Pair | Overlap |
|---|---|
| `obsidian._GENERIC_TOKENS` vs `obsidian._STOPWORDS` | **95% of the smaller** — near-duplicates **in the same file** |
| `best_bet._STOP_WORDS` vs `fact_grounding._COMMON_WORDS` | **84%** |
| `scene_plan._STOP` vs `fact_grounding._COMMON_WORDS` | **77%** |
| `scene_plan._STOP` vs `best_bet._STOP_WORDS` | **74%** |

Five hand-maintained lists (169 / 107 / 66 / 59 / 31 entries) that mostly say the same
thing. **A shared `core/vocab.py` with named subsets** (`GENERIC`, `PROSE_FILLER`,
`QUERY_NOISE`) would cut ~200 LOC and — more importantly — stop the five from drifting
apart. They already have: a word filtered in one path survives in another.

### 3.2 Two domain-profile tables (227 LOC)
`apis/topic_scorer._LEARNED_PROFILES` (116) and `apis/learned_weights._DOMAIN_PROFILES`
(111) both map domain → signal weights. Worth confirming whether they're two views of
one concept; if so, one table with a derivation is ~100 LOC lighter and removes a
silent-divergence risk.

### 3.3 Reference data living in Python (~71 LOC)
`apis/nfl_entities.NFL_TEAM_NICKNAMES` (36) + `apis/nba_teams.TEAM_NICKNAMES` (35) are
**data, not logic** — they belong in `config/` JSON alongside `channels.json` /
`data_sources.json`, where they can be edited without a code change. The repo already
has this pattern (`config/voices.json` was explicitly moved this way: *"Adding voices is
config, not code"*).

### 3.4 Hardcoded *results* — clean ✅
Only **5** functions in the tree return a bare constant, and 2 are in tests. The two in
`apis/apify_client.py` (`apify_get_usage`/`apify_set_usage`) are deliberate no-op
fallbacks defined inside an `except ImportError`. **The codebase is not full of stubbed
or faked results** — worth stating plainly, since that was the concern.

## 4. Waste — mostly clean, with two real items

### 4.1 ✅ Not problems (checked and cleared)
- **No import-time file I/O anywhere** in src — verified by AST over top-level
  statements only. Startup does no disk work.
- **Hot config loaders are memoized** — `config/channels.py` and `config/seo.py` both
  use `@lru_cache`; `apis/apify_catalog.py` uses a module cache. JSON isn't re-parsed
  per call.

### 4.2 ⭐ The canonical free-mode helper exists — and nothing uses it
`core/run_mode.py:54` defines exactly the right function:

```python
def free_mode_strict() -> bool:
    """True when the never-pay guards are armed (set by Free mode)."""
```

**Zero modules import it.** All three paid seams reimplemented it privately —
`core/llm_router.py:272 _free_mode_strict`, `core/tts.py:253 _free_mode_strict`, and an
inline env read in `apis/apify_client.py:240`. This upgrades the previous audit's
finding: it isn't *"we should centralize this"* — **it is already centralized and being
ignored.** The fix is ~4 lines (import the shared helper, delete two private copies),
after which a test can assert every paid seam consults the one guard.

### 4.3 `core/ui.py` — 1,420 LOC and accelerating
796 → 951 → **1,420** across three audits. The single biggest maintainability drag in
the tree; splitting it is worth more than any deletion in §2.

## 5. What to actually do (ranked by value ÷ effort)

| # | Action | Effort | Payoff |
|---|---|---|---|
| 1 | Use the existing `run_mode.free_mode_strict()` in all 3 seams (§4.2) | `[XS]` | Correctness — closes the guard-drift risk |
| 2 | `pip install -e ".[free]"` (piper + ddgs) (§1) | `[XS]` | Makes Free mode actually usable |
| 3 | Surface absent optional backends in `free-doctor` output (§1) | `[S]` | Stops silent inertness |
| 4 | Merge the 5 stopword lists into `core/vocab.py` (§3.1) | `[S]` | ~200 LOC + stops semantic drift |
| 5 | Delete the 14 dead functions (§2.1) | `[S]` | 133 LOC, zero risk |
| 6 | Move team nicknames to `config/*.json` (§3.3) | `[S]` | ~71 LOC out of code; editable as data |
| 7 | Reconcile the two domain-profile tables (§3.2) | `[M]` | ~100 LOC + removes divergence risk |
| 8 | Split `core/ui.py` (§4.3) | `[M]` | The real maintainability win |

**Realistic total reduction: ~500 LOC (1.2%).** Do these for *coherence*, not for size —
items 1–3 are the ones that change behavior, and item 1 is a genuine correctness fix.

## 6. Reproduce these numbers

```bash
# LOC by directory
for d in apis core tests video assets analytics storage publishing scripts config; do
  find ./$d -name '*.py' | xargs wc -l | tail -1; done
# dead-code candidates (then filter by hand — see §2.2)
pip install vulture && python -m vulture . --min-confidence 60 \
  --exclude ".venv,alembic,data,output,tests"
# large literal constants (AST, >=15 lines)  → see §3
# constant-return functions                  → see §3.4
# import-time I/O + memoization              → see §4.1
```

---

## Cross-references
[code_audit_2026-07.md](code_audit_2026-07.md) (the broader health pass) ·
[strategy_2026H2.md](strategy_2026H2.md) (why "don't add generation features") ·
[free_mode.md](free_mode.md) (the `.[free]` install) ·
[groundwork_2026Q3.md](groundwork_2026Q3.md) (what each external addition was for) ·
[roadmap.md](roadmap.md).
