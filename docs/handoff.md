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

**Written:** 2026-10-25 · **HEAD at write:** `566352b` (wave 129's code; this docs commit follows)
· **Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed after the merge; read CI.

**Defects first:** none open from this wave. 18 of 46 drafts in two weeks expired undecided - wave
129 answers it with decision 78: a toast at a preview's decide-by time (#1572), then a clean
overnight render left unanswered 24 h goes out at its slot (#1574); the shelf cap 5 while the week
is nearly empty (#1434). Also ESPN season context in previews (#1369), preview shapes as an
experiment (#1366, started), a dull-opener warning (#1357), leagues in turn (#1449), `ops hooks`'
before/after (#1454), api_sports as context (#1568), `ops overnight --pause-until` (#1338).

**Live:** decision 77 ran on its own - runs 190 and 191 scheduled Mon 10-26 noon and 10 PM EDT.
Wave 128 (`bcd70ae`) is CI-green. Next five: #1575 #1459 #1355 #1431 #1458.

**Cursor is out of usage for the month** - its queue is Claude's.
**Operator:** runs 185 and 186 held for claims (game Sun 8:20 PM EDT); publish the Google app
before Fri 10-30.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
