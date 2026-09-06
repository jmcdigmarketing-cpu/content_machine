# Handoff — the mailbox

**Read this first, before any other file, every time you start work here.** More than
one agent works in this repo and nothing signals a switch. This file is how the
previous one tells you what it did and what it broke.

Two slots. **Overwrite your own; never edit the other agent's.** Keep each slot under
~25 lines — this is a mailbox, not an archive. The archive is
[HANDOFF_SYNOPSIS.md](HANDOFF_SYNOPSIS.md) (session state) and
[planning_log.md](planning_log.md) (why, append-only).

## Verify before you trust it

Prose goes stale; git does not. Every slot records the HEAD it was written at, so you
can check the claim instead of believing it:

```bash
git log <sha-from-the-slot>..HEAD --oneline
git status --short
```

If the slot says "committed" and `git log` shows nothing, the work is sitting
uncommitted in your tree — that has happened four times. If `git status` shows files
the slot never mentions, the other agent is **still working right now**: re-read any
file immediately before you edit it, and never `git checkout` a file to discard changes
you did not make.

Both agents commit as the same git author, so **sign your commits** —
`Co-authored-by: Cursor <cursoragent@cursor.com>` or
`Co-authored-by: Claude <noreply@anthropic.com>`. The trailer says *who*; the SHA anchor
above says *what has happened since*. You need both. (The hook used to reject these;
the operator lifted that ban on 2026-08-28.)

One command reads all of it — signed split, uncommitted count, and whether each slot is
behind HEAD:

```bash
py -m scripts.ops agents
```

## Write your slot before you stop

Not after the last edit — *as* the last edit. A slot written from memory next session
is the thing this file exists to replace. State defects before wins; if you found
nothing broken, say that explicitly rather than leaving it implied.

---

## Slot — Claude Code

**Written:** 2026-09-05 · **HEAD at write:** `73671ce` · **Tree:** committed as one
wave immediately after this slot — `git log -1` is the record, not this line.

- **Cursor returns 2026-09-06.** This slot is the first one you will read.
- **Defect first, mine: the 2026-08-30 wave sat uncommitted for six days**,
  against rule 14. It is in this commit with the 2026-09-05 wave, at the
  operator's call (I argued for two commits and was overruled).
- **Four grade components have now moved across the two waves.** Historical
  report-card letters are **not comparable** to new ones. `VideoGrade.version`
  now records which rubric produced which — `GRADE_VERSION` v2,
  `QUALITY_VERSION` v3 — but **`grade_calibration` still re-grades all history
  with today's code**, which is #662 and roadmap pick 1. Do not trust a
  calibration number until it lands.
- **The canary's first cut was backwards** and called 15 of 33 signals dead;
  most were healthy sources with no match for a UFC probe topic. Fixed to the
  signal-contract vocabulary. If you touch `core/signal_canary.py`, keep
  `STATUS_INACTIVE` on the healthy side — that is decision §18 turned inward.
- **#402 not shipped on purpose.** `generate_audio` is ~147 lines over four
  provider branches; extract the seam (**#658**) first. Filing it beat
  half-shipping a cache that silently misbills.
- **Shipped:** #654, #645, #383, #533's detector+tables, #657. New modules:
  `core/angle_ranker.py`, `core/signal_canary.py`. New skill:
  `.claude/skills/next-five/SKILL.md` (+ `.cursor` mirror) — the four-step
  session written down.
- **The audit caught two things a green suite did not:** mypy 148 -> 149, and an
  import left unused. Run mypy against the baseline; it is not in CI.
- Suite 2,546 -> **2,573** green; ruff + format clean; mypy **148**; `data/`
  untouched. Backlog 463 -> **465** open, highest **#663**.
- Why this five and what each measured: [planning_log.md](planning_log.md)
  2026-09-05. Session state: [HANDOFF_SYNOPSIS.md](HANDOFF_SYNOPSIS.md).

## Slot — Cursor

**Written:** 2026-09-06 · **HEAD at write:** `73671ce` · **Tree:** dirty, not mine.
Recon only. No commit. `git log 73671ce..HEAD` is empty; `ops agents` shows 39
modified + 7 untracked, Cursor slot previously never written.

- **Defect first: Claude's 08-30 slot is behind the dirty tree.** It left #533
  undone on purpose. The working copy now has detector + `INTENT_ANGLES` tables
  (comment dated 2026-09-05) and tests for them. The other half is still open:
  `research_brief` still defaults `short_debate`, `content_engine` still orders
  `TAKE A SIDE` / a hot-take close, backlog #533 is still `[ ]`.
- **Same wave, also past the slot:** `#645` length is already in
  `_WEIGHTS` (10%), `#383` `core/signal_canary.py` + `ops signal-canary` exist
  untracked. Roadmap still lists both as next-five *open*.
- **Still true from Claude's slot:** false comment at
  `register_signals.py:322-324`; `#655` `⚠` is not cp1252-safe; `#654`/`#656`
  filed; grades after the insight/hook edits are not comparable to history.
- **`HANDOFF_SYNOPSIS.md` is stale** — last wave is 08-28 Piper mix at 2365
  tests. Live mailbox + planning_log 08-30 are the real state.
- **I changed nothing else.** Untracked `cached-strolling-popcorn.md` looks like
  a leftover Claude plan; do not commit it.
