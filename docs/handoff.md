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

**Written:** 2026-11-06 · **HEAD at write:** `6835e68` (wave 151, CI green; this wave's commit
follows) · **Tree:** clean of mine after it; leave `.agents/` and `.codex/`.

**Wave 152, the next ten.** Broken and not fixable by code: the fast lane missed the TNF final - the
PC slept 20:22-05:07 and the operator wants no wake timers (#1999 drafts it at overnight instead).
Built: the night's lead order (launch week, marquee injury #1613, fight week #1612, marquee breakout
#1599); the fast lane's injury, weigh-in (#1874) and press-conference (#1890) kinds; no end card on
a Short (#1622); three a day Nov 7-20 (#1648, read 11-27); five drafts on a wide night (#1653); the
UFC 334 match-up long video, drafted Nov 10 (#1892); the marquee list learns (#1597). Decision 103.

**Open:** #1648, #1984, #1988, #1991, #1994, #1996, #1997, #1998, #1999, #2000. **Next:** #1999,
#1623, #1626, #1877, #1687 before W4's freeze (Nov 16); #1849 once the embargo date is known.

**Operator:** publish the Google app before Sat Nov 7 - the sign-in lapses and uploads stop (set
POLICY_SITE_URL first; `ops check-youtube` reads the four pages); bio pages; tracking IDs; Facebook in
Buffer; #1922/#1956 on a phone. Review the UFC 334 match-up draft on Nov 10, the recap on Nov 15.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
