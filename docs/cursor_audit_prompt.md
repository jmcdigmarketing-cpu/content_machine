# Cursor audit prompt — Content Machine

> **Historical, and stale.** This was a one-off audit prompt written against commit
> `e6d5c9c` when the suite was 363 tests (it is now ~1958). The repo-state paragraph
> below is no longer accurate — do not treat it as current.
>
> For standing agent instructions use **[../AGENTS.md](../AGENTS.md)** and
> **[../.cursor/rules/content-machine.mdc](../.cursor/rules/content-machine.mdc)**.
> Keep this file only for the audit *framing* in the ground rules section.

Paste the section below into Cursor (Composer/Agent, with the repo open). It is
self-contained. Work at a **senior software engineer** standard.

---

You are auditing **Content Machine**, a Windows/PowerShell Python 3.11 CLI that
auto-generates short-form YouTube videos: signals → score topics → LLM script →
TTS → FFmpeg render → publish, with a closed analytics learning loop and a
2026-policy compliance layer. Two config-driven channels: `tapin` (gaming/UFC)
and `moneywise` (finance). Read these first, in order:
`docs/roadmap.md`, `docs/decisions.md` (ADR-lite — the *why* behind load-bearing
choices), `docs/assessment.md`.

**Repo state (verify, don't assume):** Two previously-divergent feature PRs were
just consolidated into `main` (commit `e6d5c9c`). `main` now contains BOTH:
(1) Phase O authenticity/cadence/outlier, Phase P hook_score, Phase Q captions,
idea-intake, recommenders, moneywise brand kit, dev tooling; and (2) the
recency/quality layer: manual key facts, domain-aware signal gating, signal
circuit breaker, web search (Tavily/Brave), Obsidian facts, vault writeback,
feature store, weekly report, cost meter, recommender confidence surfacing,
fact-grounding post-check, RAWG relevance gate, domain-routed RSS. Baseline:
`363 tests pass`, `ruff check` + `ruff format --check` clean.

## Ground rules (non-negotiable)

1. **Accuracy over speed. Do not delete needed code.** Previous audits removed
   things that were actually used and lost real progress. Deletion is NOT a goal
   of this task. The goal is the most efficient, professional build with **all
   current behavior preserved**.
2. **Prove it before you touch it.** Before proposing removal of any symbol,
   file, or branch of logic, provide evidence it is truly unused: a
   repo-wide search (`rg`) showing zero references, including dynamic/string
   references (`importlib`, `getattr`, `__import__`, entries in JSON/TOML config,
   `scripts/ops.py` subcommands, `py -m module` invocations, test patches like
   `patch("pkg.mod.func")`), and CLI/`gh`/cron entry points. If you cannot prove
   it, leave it and only NOTE it.
3. **Deliberate redundancy is documented in `docs/decisions.md` §13 — do not
   "simplify it away."** Specifically these must remain:
   - `apis/apify_client.py`: the global circuit breaker
     (`apify_disabled`/`disable_apify`/`apify_preflight`) AND
     `apify_credit_exhausted()` (a thin alias imported by `core/ui.py`).
   - `apis/register_signals.py`: the per-signal session circuit breaker AND the
     variant-reuse pinning (different layers).
   - `core/pipeline.py`: both `apify_preflight()` and the `progress=`/`_report`
     discovery feedback.
   - `main.py`: both the fact-grounding warning and the Phase O authenticity gate.
   - `apis/tapology_api.py`: `scrape_enabled()` + `_scrape_enabled` alias.
4. **Never touch secrets or generated artifacts:** `.env`, `config/secrets/*`
   (gitignored), `output/`, `data/` caches, DB files. Do not commit them.
5. **Tests are the contract.** After every change, the full suite must still
   pass and lint/format must stay clean. A change that needs a test deleted or
   weakened to pass is wrong — investigate instead.
6. **Match the codebase.** Comment density, naming, and idioms should look like
   the surrounding code. Targeted edits over rewrites (see ADR §11).

## How to run things

```
py -m ruff check .
py -m ruff format --check .
py -m unittest discover -s tests
```

**Simulate keyless CI before declaring success** (CI runs without secrets): move
`.env` and `config/secrets/youtube_token_tapin.json` aside, run the suite, move
them back. CI gates lint + format + tests on Python 3.11 only (numpy/Pillow pins
require ≥3.11) — keep it green.

## Part A — Double-check the consolidation (do this first, report findings)

Confirm the merge preserved both feature sets and nothing regressed:
1. Run the full suite + lint + format (and the keyless-CI simulation). Report exact counts.
2. Grep-verify both feature sets coexist and are reachable: `apify_preflight`,
   `apify_credit_exhausted`, `find_ungrounded_entities`, `_feed_matches_domain`,
   `_is_relevant`, `confidence_note`, `evaluate_authenticity`, `score_script_hook`,
   `prompt_key_facts`. For each, show the definition site and at least one real caller.
3. Look for merge scars: leftover conflict markers (`<<<<<<<`, `=======`,
   `>>>>>>>`), duplicated function definitions, unreachable post-merge branches,
   imports of names that no longer exist, or two functions that now do the same
   job where only one is wired in. Report; fix only the clearly-broken ones.
4. Confirm `main.py` runs both pre-render checks (grounding warning + authenticity
   gate) and that `display_summary` shows the cost line on every exit path.

## Part B — Efficiency & cleanliness audit (propose, then apply the safe subset)

Audit for a leaner, more professional build **without changing behavior**:

- **Genuinely unused files/modules:** scratch files, stale duplicates, dead
  scripts, orphaned assets, `*-DESKTOP-*` OneDrive conflict copies (the repo
  lives under OneDrive — see the OneDrive git hazard; conflict-copy files are
  safe to remove once confirmed redundant). Prove zero references per rule #2.
- **Dead code within files:** unreachable branches, unused private helpers,
  unused imports/vars (ruff already catches many — run it), commented-out blocks
  that are clearly obsolete. Prove, then remove.
- **Duplication worth consolidating:** repeated helpers across modules (e.g.
  per-module `_engaged_rate`, `_infer_domain`, JSON-load boilerplate, near-identical
  signal scaffolding). Prefer extracting a shared helper ONLY when it reduces real
  duplication without obscuring intent — don't over-abstract.
- **Obvious inefficiency:** redundant recomputation, re-reading files in a loop,
  re-fetching the same data, N+1 patterns, missing reuse of already-computed
  results. Optimize only where it's measurable and the code stays clear.
- **Hygiene:** consistent typing, docstrings on public functions, removal of
  truly stale TODOs (confirm they're done first), config/env-var documentation drift.

Categorize every finding as: **(1) Safe to apply** (proven unused / pure cleanup,
behavior-preserving, tests stay green) — apply these; **(2) Worth doing but needs
judgment** (refactor/consolidation with tradeoffs) — propose with a diff sketch,
do NOT apply unless trivial and obviously correct; **(3) Risky / leave alone**
(touches the deliberate redundancy, public API, or anything you can't prove) —
note only.

## Deliverable

1. A written report: Part A verification results, then Part B findings grouped by
   the three categories above, each with file:line and the evidence.
2. Apply only category (1) (and the trivial, obviously-correct slice of (2)),
   in small focused commits, each with the suite green + lint/format clean.
   End commit messages with a `Co-Authored-By:` line if your workflow adds one.
3. Do NOT push to `main` or open/merge PRs without the maintainer's explicit go.
   Leave categories (2, non-trivial) and (3) as recommendations for sign-off.

Restate the ground rules in your own words before you start, so it's clear you
will not delete anything you cannot prove is unused.
```
