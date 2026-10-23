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

**Written:** 2026-10-23 evening · **HEAD at write:** `a9c6997` (the code; the docs commit follows)
· **Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; CI read after the push.

**Cursor is out of usage for the month** - its queue is Claude's (roadmap next five).

**The plan is [hands_off_plan.md](hands_off_plan.md), one section per shortfall**; ideas
#1314-#1517 in the backlog. Decision 68: the backlog stays <= 300 (`test_docs_lint`).

**Wave 124 (one code commit, then docs), built in a git worktree while overnight ran:**
- #1547 `stale_renders.started_event` and one ladder `shelf_state`; the worker drops a started
  preview before any call; go-public and schedule-public refuse it. #1548 a preview is current
  until its event (`dead_reason`, `expire_old_drafts`).
- Decision 69: nothing asks for Sleep (`nightly_task` late/missed/tonight/doctor lines).
  Decision 70 (#1499): grade v6, hook weight 0; overnight renders a game by kickoff, then newest.
- `ops hooks` (#1500 #1501 #1505 #1506); #1546 `retention_curve_state` and
  `field_audit.curve_gaps`; #1470 the doctor's gpu row; #1510 `roadmap-index --by-shortfall`.

**Live:** overnight ran 5:52 PM at power-on (shut down Thu 9:51 PM), 3 drafts; job 77 (run 181)
off the queue at the first worker pass after the merge (the operator's yes). The sign-in is still
lapsed - uploads 175 and 180 hold; the UFC 333 previews need it by Sat 10:30 AM EDT. **Delete
scratch exports and worktrees each wave.**
**Defects first:** none open of mine. Operator calls: #1549, #1550.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
