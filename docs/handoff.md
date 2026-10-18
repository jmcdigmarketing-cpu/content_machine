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

**Written:** 2026-10-17 night · **HEAD at write:** the #1283-#1285 commit (`git log -1`) ·
**Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; CI read after the push.

**Cursor is out of usage for the month** - its queue is Claude's (roadmap next five).

**Tonight:** `requeue_upload --queue` is public at the next free slot now (`--private` for the
old upload, #1283). The worker holds `WORKER_LOCK_FILE` (`data/worker.lock`) for its life and,
alone, reclaims every "running" job at once (#1284) - a test that drives `process_one` and wants
the 45-minute rule patches `jobs.worker._sole_worker` to False. `spaced_queue.shelf_schedule`
skips taken slots (`_taken_slots`, `free_slots`) and gives news a 6 PM slot inside its window
(#1285).

**Queue:** jobs 61-63 uploaded (runs 159, 153, 154); 64-66 pending (156 Mon noon, 158 Mon 10 PM,
161 Tue noon EDT). Run 160 (tonight's UFC picks, no `event_at`) would take a slot if scheduled -
the operator's to retire.

**Defects first:** none open of mine. An event-less preview (a headline about a coming event,
like run 160) is not known to be one - worth an item when the next wave is picked.

**Next:** the roadmap's five (#421 #425 #450 #457 #257), #1270, #1271. Suite green forward and reversed on the committed tree.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
