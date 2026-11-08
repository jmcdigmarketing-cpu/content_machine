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

**Written:** 2026-11-07 · **HEAD at write:** `4f53c66` (the channel page, CI green; this wave's
commit follows) · **Tree:** clean of mine after it; leave `.agents/` and `.codex/`.

**Wave 160, the next 10.** Defects first: a render that stops moving sat forever (the operator: `ops
all` stops at ~80%) - now killed after 120 s and retried, ffmpeg never reading the console (#2020;
its cause not reproduced, #2024); six accepted drafts held overnight's cap (#2021); the playlist
store lost an id (#2022). Built: #1810 (+ #2018), #1719, #1828, #1826, #2007, #2008, #2009. #1786
measured as covered, #1856 left open, #1850 parked (operator). Decision 111.

**Open:** #1600, #1621, #1646, #1648, #1668, #1721, #1723, #1786, #1856, #1984, #1988, #1991, #1994,
#1996-#1998, #2000, #2003-#2006, #2010-#2014, #2016, #2017, #2023, #2024. **Next:** #2017
(operator), #2024, #1905, #1598, #1602, #1856.

**Operator:** the sign-in lapses Sat Nov 14 4:08 PM EST unless the Google app is published (set
POLICY_SITE_URL, `ops check-youtube`, publish, sign in once more). The three current accepted drafts
(runs 233, 241, 248) render at your next batch-review; a stalled render now says so and retries.
Give the ElevenLabs key `user_read` (#2014); enter the monthly subscriptions.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
