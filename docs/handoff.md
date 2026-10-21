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

**Written:** 2026-10-20 evening · **HEAD at write:** `9792810` (batches A-B; the batch C commit follows)
· **Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; CI read after each batch.

**Cursor is out of usage for the month** - its queue is Claude's (roadmap next five).

**The plan is [hands_off_plan.md](hands_off_plan.md), one section per shortfall** (the Story's
22); their ideas are #1314-#1517 in the backlog. Decision 68: `test_docs_lint` holds the
backlog at <= 300, and wave 113 alone was exempt from "close as many as you file".

**Wave 117 (four batches, two commits):**
- `nightly_task.power_events` / `power_off_before` (wevtutil, skipped in the suite),
  `late_short`, `wake_doctor`, `worker_gap`, `tonight_line`; `worker._tonight_watch` (#1528
  #1380 #1371 #1337).
- `oauth.sign_in_reminder` keeps the date (#1529); `agent_comms.blame_sha` (#1530).
- `batch_generation.follow_up_topic` (#1452); `worker._toast_public` (#1404);
  `go_public._read_back` (#1392); health's cadence rule (#1435).

**Wave 118 (three batches, two commits):**
- `nightly_task.tonight_text(paused=)` (#1534); `script_craft._names_kept` (#1531);
  `batch_review.unattended_block_reason` warns on "hard to say" (#1535);
  `apis.topic_tokens.split_sentences` in `authenticity` / `script_craft`, ratchet 27 (#1532).
- `deadline_line` names its day (#1533); `status_summary.yours_items` (#1407).
- `chapter_shorts.fill_empty_slots` from overnight (#1430). #1378 met, #1432 not built.

**Live:** overnight renders nothing until the operator decides 3 finished videos (168, 170
unlisted; re-cut 171). The sign-in lapses Wed 10-21 9:36 PM EDT unless the app is published.
Run 176's draft was repaired. **Defects first:** none open of mine.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
