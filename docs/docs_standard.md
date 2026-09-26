# Documentation standard

> **Class:** reference · **Status:** living · **Reviewed:** 2026-09-26

How docs in this repo are named, classified, headed, and retired. Enforced by
[`tests/test_docs_standard.py`](../tests/test_docs_standard.py), because AGENTS.md is
right that a written rule has not been enough here on its own.

The problem this solves is recorded in [audit_2026-09.md](audit_2026-09.md) §2: 46 docs,
~114k words, five filename conventions, no index, eight overlapping roadmap-shaped
files, and twelve different live test counts — a corpus that had grown faster than any
reader, human or agent, could hold.

## 1. The doc card

Line 1 is the H1. Line 2 is blank. **Line 3 is the doc card**, and nothing else goes
above it:

```markdown
# Providers runbook

> **Class:** runbook · **Status:** living · **Reviewed:** 2026-09-20
```

An `archived` doc adds one more field, and the target must exist:

```markdown
> **Class:** plan · **Status:** archived · **Reviewed:** 2026-09-20 · **Superseded by:** [master_plan.md](master_plan.md)
```

Three fields, one line, greppable. `Reviewed` means *a human or agent read this and it
was still true* — it is not the edit date, and bumping it without reading is the one way
to make this whole scheme worthless.

## 2. The six classes

Class answers *what kind of doc is this*; status answers *is it still true*. The pair is
what keeps a plan from silently becoming history.

| Class | Answers | Status it carries | Rule |
|---|---|---|---|
| `index` | where is everything | `living` | Exactly one: [README.md](README.md) |
| `charter` | why this exists | `living` | Changes when the product changes, not when code does |
| `reference` | how it works **now** | `living` | Must be true at HEAD. A wrong reference doc is worse than none |
| `runbook` | how do I do X | `living` | Task-shaped, imperative, starts at the command |
| `plan` | what happens next | `living` \| `archived` | **One canonical plan per horizon.** A second one is archived |
| `snapshot` | what was true on a date | `frozen` | Never edited after the day. Superseded by a newer dated file |
| `log` | append-only history | `frozen` | Append at the top or bottom, never rewrite |

`snapshot` and `log` can never be `living` — the lint enforces it. That is the whole
trick: an audit, an assessment, a strategy memo and a handoff are *frozen artifacts*,
and pretending otherwise is what produced a corpus where half the "current" docs
described a system from two months ago.

## 3. Naming

- `snake_case.md` — the default, and already the majority.
- `snake_case_YYYY-MM.md` — any `snapshot`. The date belongs in the filename so the
  successor is obvious and nobody has to open the file to learn it is old.
- No `SCREAMING_CASE`, no `kebab-case`, no `CamelCase2026H2`.

`LEGACY_NAMES` in the lint held the ten pre-standard names; it has been empty since
2026-09-26 and may only stay that way. A rename updates its inbound links in the same commit — they are
load-bearing (`roadmap.md` has 28 of them) and `tests/test_docs_lint.py` fails on a
broken one. Leave a redirect stub only where a link from outside the repo may exist, the
way [ROADMAP.md](../ROADMAP.md) does. Repairing a link inside a `frozen` doc is a
mechanical fix, not a rewrite, and is the one edit those docs accept.

## 4. The metric rule

> **A number that changes is either generated or dated.**

Bare counts of tests, subcommands, signals, or modules are banned from `living` docs and
enforced for test counts. In a `living` doc, cite the command instead:

```markdown
Test count: `python -m unittest discover -s tests -t .`
```

In a `snapshot` or a `log`, a hard number is correct — it was true on the day, and the
doc card says which day.

The lint enforces this for test, subcommand, command, signal and module counts in `living`
docs. A **generated** doc is the other legitimate home for a number: `ops_commands.md` is
written by `py -m scripts.ops command-ref` and byte-checked against its generator in CI
(its doc card is emitted by the generator, with a date bumped only when the generator
changes — a per-run date would break the byte check). A hand edit to a generated doc is
a defect.

## 5. Lifecycle

1. **New doc** → pick a class, write the card, add a line to [README.md](README.md). The
   lint fails on an orphan, so this is not optional.
2. **Still true?** → bump `Reviewed` after actually reading it.
3. **Superseded** → set `Status: archived`, add `Superseded by:`, and leave the body
   alone. Deleting history loses the reasoning; archiving keeps it and marks it.
4. **Frozen by nature** → a dated snapshot is written once. Do not go back and "update"
   an audit; write the next one and supersede it.

## 6. Where a new thing goes

| You are writing | Put it in |
|---|---|
| A decision and its reasoning | [decisions.md](decisions.md) — a new numbered §, never a new file |
| What shipped | [change_log.md](change_log.md) |
| What was discussed and decided in a session | [planning_log.md](planning_log.md) (CLAUDE.md requires this) |
| Where the work stands right now | [handoff_synopsis.md](handoff_synopsis.md) |
| The next N months | [master_plan.md](master_plan.md) — the canonical plan |
| Item-level open work | [roadmap.md](roadmap.md) |
| A point-in-time verdict on the system | a new `audit_YYYY-MM.md` snapshot |

If a new idea does not fit one of those, it is probably a `§` in an existing doc rather
than doc number 50.

## 7. Size budget and log rollover

A `log` grows by design, so it rolls over instead of being trimmed: when the live file
passes the ceiling, the older period moves **verbatim** into a dated sibling
(`planning_log_2026-08.md`, `handoff_synopsis_archive.md`), frozen, indexed, and linked
from the live file's header. The live file keeps the current period plus any standing
sections. Nothing is rewritten; the split is a move.

### Living docs

A `living` doc may not exceed 800 lines (`LIVING_LINE_CEILING` in
`tests/test_docs_standard.py`; `backlog.md` is exempt as the inventory, `snapshot` and `log`
docs by class). `roadmap.md` has its own lint at under 200. The 2026-09 split that got the
corpus there is [master_plan.md](master_plan.md) M2. If a section wants to grow without
bound, it is a `log`, and logs get their own file.
