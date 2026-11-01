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

**Written:** 2026-11-01 · **HEAD at write:** `9181fa0` (wave 138; this wave's commit follows) ·
**Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; read CI.

**Wave 139, the shortfalls measure themselves (decision 91).** Defects first: S10's first reading
found 8 crossposts in a week never sent - `_hand_post` took a sibling's own Buffer post (same story)
for a "hand post" (runs 199, 204, 205, 206, 208, 220); fixed, and `ops crosspost unclaim --apply`
clears the recent false ones (the operator: send the recent, skip the stale countdown). S06: 9 public
videos scored as neutral recaps (#1936). Shipped: `core/success/shortfalls.py` + `ops shortfalls`
(each check run, its number printed: 7 met, 2 built, 2 waiting, 2 yours, 6 not yet, 3 no measure);
the nine closed in hands_off_plan.md; S07 rewritten; overnight keeps 14 nights; S22's sweep parked
47 lowest-scored bridge ideas (open 342 -> 295) and a test holds the 300 ceiling.

**Open:** #1933-#1937. **Next:** one shortfall a wave - S02 (subscribers from videos) first - with
#1936, #1930, #1932, #1933.

**Operator:** publish the Google app (lapses Nov 7); turn on the Reporting API (S11); the hook card
on a phone (#1922); Facebook in Buffer; the bio link; the Associates tag.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
