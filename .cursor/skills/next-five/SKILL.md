---
name: next-five
description: >-
  Take the next five roadmap items, audit, commit, then brainstorm the next
  five. Use when the operator says "next five", "next N tasks", or asks for a
  wave implemented, audited and committed.
---

# The four-step session (Content OS)

This repo already works in waves, and `planning_log.md` calls it "Step 2 of a
four-step session". Nothing wrote the steps down, so each one has been rebuilt
from memory and each has gone wrong in a recorded way: a wave sat uncommitted in
the working tree for six days against rule 14; an agent plan file reached the
repo root and survived a week because nobody looked before `git add -A`; a slot
written after the last suite run tripped the 120-line mailbox cap and reported
green anyway; and two of a recommended five were parked in `HANDOFF_SYNOPSIS.md`
while sitting at picks 1 and 5.

## The loop (non-negotiable)

1. **Refamiliarize, then verify it.** Read `docs/handoff.md` first. Prose goes
   stale and `git log` does not, so check the slot's claimed HEAD:
   `git log <sha>..HEAD --oneline`, `git status --short`, `py -m scripts.ops
   agents`. Re-run the suite before building on a green claim you did not make
   this session.
2. **Verify the next five before trusting the list.** `docs/roadmap.md`'s
   recommendation is prose and drifts. For each item check `docs/backlog.md` for
   its real text and size, and grep `docs/HANDOFF_SYNOPSIS.md` for it - an item
   listed "Still parked" there is not next. Check that anything it names as a
   dependency exists in code: #333's stated trigger, #341, does not.
3. **Build each one fail-then-fix**, per [tdd](../tdd/SKILL.md). Order cheapest
   and safest first so the risky one cannot strand the rest.
4. **Audit before committing** - see below. Not a re-run of the tests.
5. **Brainstorm the next five and write the docs** - see below.
6. **Commit.** One wave, one commit, unless the operator says otherwise.

## The audit is a separate pass

The Definition of done in `.cursor/rules/content-machine.mdc` is the checklist:
ruff and format clean, suite green with the count **increased**, each new test
observed failing first, `git status --short data/` empty, every new function
reachable from a production caller, operator-facing output actually run and
pasted, no new WARNING on a healthy run.

Two of those catch real defects and are usually skipped. **Run mypy** and compare
against the recorded baseline - a new type error hides in a green suite. And
**grep each new symbol for a production caller**; a helper only the tests reach
is a feature that does not exist.

Report it the way `planning_log.md` does: how many behavioural regressions were
added, **how many were observed failing before their fix**, one bullet per defect
saying what the code did and what it does now, and a Proof paragraph of measured
numbers.

## Writing the wave down

Counts come from `py -m scripts.ops roadmap-index`, never hand-typed. Then, in
this order:

- tick the shipped items in `docs/backlog.md` with what was measured, and file
  what you found on the way as new numbered items;
- rewrite `docs/roadmap.md`'s "Recommended next five", saying why the list
  changed;
- append the dated entry to `docs/planning_log.md` - prompt verbatim, what was
  picked and why it differs from the recommendation, shipped 1..N, the findings
  with `file:line`, what was deliberately not done, the audit, the closing count
  line;
- prepend the wave to `docs/HANDOFF_SYNOPSIS.md` and demote the previous one;
- **write your `docs/handoff.md` slot last, then re-run the suite.** The slot is
  an edit. It has broken a test.

## Commit

`.githooks/commit-msg` is active: it **rejects** any "Generated with ..." line
and warns when no `Co-authored-by:` trailer is present. Bodies are ASCII - `->`,
not an arrow glyph. Say what was broken and how you know; name the measurement,
not the intention. State the fail-first claim explicitly, and name what was left
open with its item number.

Before `git add -A`, run `git status --porcelain | grep '^??'` and read the list.
Agent plan files, scratch output and stray reports do not belong in the repo.

## Do not

- Do not trust a `[x]` as proof the defect is fixed. #323 shipped, was marked
  done, and had not broken the variant tie it named.
- Do not move a report-card component without stamping `GRADE_VERSION` and
  saying so - `core/grade_calibration.py` re-grades all history with today's code.
- Do not leave the wave in the working tree (rule 14), and do not `git stash`
  here: `video/backgrounds/*` are permission-locked and `stash push -u` fails
  partway, deleting untracked files.
