# Using Claude Code on this repo

> **Class:** runbook · **Status:** living · **Reviewed:** 2026-09-20

Practical notes on Claude Code features/modes, specific to how this project is
built (cost-sensitive signal layer, Windows/PowerShell dev env, existing CI
gate). For the project itself, start at [../CLAUDE.md](../CLAUDE.md).

## `CLAUDE.md`

Auto-loaded into every session's context. Keep it a **pointer**, not a
duplicate — link to `docs/architecture.md`, `docs/debugging.md`, etc. rather
than re-explaining them. Update it when an entry point, hard rule, or command
changes; stale agent-guides are worse than none.

## Plan Mode

Use for anything touching the signal contract, the circuit breaker, or cost
accounting — `apis/register_signals.py`, `core/cost_meter.py`,
`apis/apify_client.py`. These have non-obvious invariants (e.g. a wrong status
constant silently disables a paid signal for the session, or worse, persists
that disablement across runs via `data/quota_state.json`). Plan mode forces a
written, reviewable plan before any edit — worth the overhead here specifically.

## Subagents (Explore / Plan / general-purpose)

Use for **research**, not edits: "where is X scored," "which tests constrain
signal Y's output shape." Keeps large-context reads (this repo has 89 test
files, 25+ docs) out of the main conversation. Don't use a subagent to make the
actual code change — do that directly so it's easy to review as one diff.

## `/compact`

Worth running once a session has accumulated many file reads (this repo's
`apis/`, `core/`, and `tests/` files add up fast) — before starting a large
edit, not mid-edit.

## Memory

Flag durable architectural decisions explicitly ("remember this") so they
persist across sessions instead of being re-litigated — e.g. "default
`SIGNAL_BACKEND=apify`, opt into `free`/`auto` via `.env`." Don't rely on memory
for anything derivable from the code (file paths, current test status) — read
the file instead; memory can go stale.

## `.claude/settings.local.json`

This is the Bash permission allowlist. Prefer pattern-based allows
(`Bash(python -m pytest *)`, `Bash(ruff *)`) over one-off exact-string entries —
keeps the file from accumulating near-duplicate approvals every session.

## CI parity

`.github/workflows/ci.yml` runs `ruff check .`, `ruff format --check .`
(both blocking) and `python -m unittest discover -s tests -v` (blocking); mypy
is non-blocking. Run the blocking three locally before calling any change done
— "tests pass" only counts if it's the same command CI runs.

## Background task flags

When you spot an out-of-scope bug while working on something else (e.g. a
date-parsing bug found while building an unrelated signal backend), flag it as
a separate tracked task instead of folding the fix into the current change —
keeps diffs reviewable and avoids scope creep into unrelated risk.
