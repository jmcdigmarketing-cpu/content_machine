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

**Written:** 2026-10-25 · **HEAD at write:** `3226422` (wave 131's code; this docs commit follows)
· **Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed after the merge; read CI.

**Defects first:** runs 185 and 186 were held for a claim until their game started and nothing
pushed them - a held preview now toasts within 6 hours of its game and `ops status` names the game
(#1582); the captions spelled numbers as the voice said them - they show the script's (#1583).

**Decision 80 (the operator):** one YouTube search per topic per run, the second caller booking
nothing (#1579); 9 of the 11 playlists made - YouTube's limit refused the 10th, the worker
retries once a day (#1584); the menu's domains by organic views per video, shrunk (#1448).
Also long sentences split (#1360), holds recorded and counted weekly (#1585), the Oct 13 drafts
as fixtures (#1339), #1353 pinned, #1586 filed. Next five: #1459 #1458 #1431 #1355 #1332.

**Cursor is out of usage for the month** - its queue is Claude's.
**Operator:** publish the Google app before Fri 10-30; #1586 - keep NFL previews at 32 organic
views a Short? Runs 185 and 186 stay unlisted (their game was played).

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
