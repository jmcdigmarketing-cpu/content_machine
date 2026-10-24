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

**Written:** 2026-10-23 late · **HEAD at write:** `64980f3` (the code; the docs commit follows)
· **Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; read CI after the push.

**Cursor is out of usage for the month** - its queue is Claude's (roadmap next five).

**Wave 126 (`bd56b27` then `64980f3`, then docs):** #1558 a held run's job reserves no slot
(`spaced_queue.job_reserves_slot`); #1559 the pass line; #1556 variants ranked by measured traits
(`rank_by_traits`, the scorer until a channel has learned); #1502 the `hook_rewrite` experiment
(`batch_generation.hook_arm_env`); #1540 thumbnails.set's answer confirms; #1509 #1515 in
`roadmap-index`.

**Live (the operator's yes):** run 175 set for Sun 10 PM EDT; the PC stays asleep tonight - run
184 (job 80) should take Sat noon EDT at the reset pass: **check `worker_task.log`**. Runs 185 and
186 are held for a flagged claim. Pages are two waves behind. Sign-in lapses Fri 10-30.
**Defects first:** none open of mine.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
