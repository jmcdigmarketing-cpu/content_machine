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

**Written:** 2026-10-22 evening · **HEAD at write:** `f4351fe` (the code; the docs commit follows)
· **Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; CI read after the push.

**Cursor is out of usage for the month** - its queue is Claude's (roadmap next five).

**The plan is [hands_off_plan.md](hands_off_plan.md), one section per shortfall**; ideas
#1314-#1517 in the backlog. Decision 68: the backlog stays <= 300 (`test_docs_lint`).

**Wave 123 (one code commit, then docs), built on the cloud's `ab47464` (waves 121-122):**
- The pop-ups: `win_shell.hide_child_windows` (+ `share_std`) in every `.pyw`; `nightly_task`'s
  four console calls flagged; `scripts/ops_task.pyw` + `schedule-drafts --windowless` - the
  operator's overnight task now runs `pythonw ... ops_task.pyw overnight` (read back).
- #1544 painted words; #1485 `topic_tokens._whole_teams`; #1465 #1467 + a disk check in
  `render_unattended`; #1480 `analytics/field_audit.py` in the weekly report.

**Live:** 16 console windows in the 20:37 worker pass, 0 after. The sign-in is still lapsed -
uploads 175, 180, 181 hold; #1542's rows heal at the first sync after it. C: was at 0 GB free
(old suite copies, deleted; 11 GB free) - **delete scratch exports each wave**.
**Defects first:** none open of mine.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
