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

**Written:** 2026-11-03 · **HEAD at write:** `00d546e` (wave 145's docs sweep, CI green; this wave's
commit follows) · **Tree:** clean of mine after it; leave `.agents/` and `.codex/`.

**Wave 146, the next five with S01.** Defects first: the second read held run 231's countdown opener
against its long title (#1978 - an opener naming GTA 6 or Nov 19 is now on its story); run 170's
37,270 paid views were never recorded, because a video is synced only while young (#1977 - the sync
asks paid views to date and the paid total counts them). Caught in the audit before the commit: the
first #1977 build would have read run 170's organic views as 0 in the menu's domain order. Found and
filed: an older video's synced views freeze (#1983); a compilation title says "GTA" for an
unresearched GTA 6 Short (#1982). Built: the 16:9 cut's end card (#1976, rendered on a test clip);
last month's best Shorts on the 1st (#1743, Dec 1 first; October's dry run 6:34); a long video on a
Short past 1,000 organic views in 5 days (#1740, drafted for your review).

**Open:** #1979, #1981-#1984; dated reads #1953, #1955, #1956, #1959, #1984. **Next:** S01 with #1722
(UFC 334, Nov 14), #1746, #1736, #1982, #1983; #1849 once the embargo date is known. **Overnight**
05:00 runs this wave (merged before it); its sync makes the first paid checks.

**Operator:** publish the Google app before Sat Nov 7 (set POLICY_SITE_URL first - `ops check-youtube`
reads the four pages); paste the bio pages; tracking IDs; Facebook in Buffer; #1922/#1956 on a phone.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
