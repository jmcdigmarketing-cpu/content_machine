# Handoff — the mailbox

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-10-09

**Read this first, before any other file, every time you start work here.** More than
one agent works in this repo and nothing signals a switch. This file is how the
previous one tells you what it did and what it broke.

Two slots. **Overwrite your own; never edit the other agent's.** Keep each slot under
~25 lines — this is a mailbox, not an archive. The archive is
[handoff_synopsis.md](handoff_synopsis.md) (session state) and
[planning_log.md](planning_log.md) (why, append-only).

## Verify before you trust it

Prose goes stale; git does not. Every slot records the HEAD it was written at, so you
can check the claim instead of believing it:

```bash
git log <sha-from-the-slot>..HEAD --oneline
git status --short
```

**A slot several commits behind HEAD is normal** - the second agent helps intermittently,
so being behind is expected, not a defect. What matters is whether its claims match git.

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

**Written:** 2026-10-24 · **HEAD at write:** `d9dffdd` (the code; the docs commit follows) ·
**Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; read CI after the push. Built on
the cloud's `f2d7897` (decision 74, November's $20 ads test).

**Cursor is out of usage for the month** - its queue is Claude's (roadmap next five).

**Wave 127:** #1563 previews claimed first (`worker._previews_first`); #1562 transient HTTP is
unavailable; #1561 google's notice filtered; #1361 #1367 `batch_review.preview_hold_reason`;
#1364 live games off the ideas; #1409 Shorts' titles by stayed share; #1541 `ops thumbnail-check`;
#1365 the weekly mix. Decision 75; decision 70's r corrected to -0.08 on healed numbers.

**Live:** run 184 missed the card - the PC was shut down at 1:00 AM. Run 164's live thumbnail is
not ours (#1565). #1560 open: the claim check blocked "The Chiefs are 5-0" with ESPN's line in the
facts - my first diagnosis was wrong. Sign-in lapses Fri 10-30.
**Defects first:** #1560 (reproduce on run 185's corpus).

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
