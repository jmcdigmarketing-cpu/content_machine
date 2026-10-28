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

**Written:** 2026-10-28 · **HEAD at write:** `40dda17` (the bridge; this commit follows) · **Tree:**
clean of mine; leave `.agents/` and `.codex/`. Pushed; read CI.

**The phase is the bridge** ([bridge_plan.md](bridge_plan.md), decision 82), now with the math to
the bar and the top 30 ([bridge_scores.md](bridge_scores.md) scores all 300), a calendar to
2027-02-01 ([bridge_calendar.md](bridge_calendar.md)) and a build-ready brief per wave.

**Next, in order:** wave 132 ([cloud_brief_wave132.md](cloud_brief_wave132.md)), then **133 the GTA
6 window** ([cloud_brief_wave133.md](cloud_brief_wave133.md) - the countdown should start 10-29 and
"everything we know" be public by 11-10; GTA 6 launches 11-19), then
[134](cloud_brief_wave134.md) the scoreboard, [135](cloud_brief_wave135.md) speed and loops,
[136](cloud_brief_wave136.md) money and reach. Checkpoints Dec 1, Jan 5, Jan 31.

**Fixed today (#1897):** the console windows the operator saw - overnight's render and draft
children never hid their own children's windows; each child's `main` now calls
`hide_child_windows()`, and `tests/test_child_windows.py` guards it.

**Cursor is out of usage for the month** - its queue is Claude's.
**Operator:** end the two Oct 26 campaigns in Studio and send the final numbers (and the Oct 8
row); Amazon Associates and a Facebook Page in Buffer; publish the Google app before Fri 10-30.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
