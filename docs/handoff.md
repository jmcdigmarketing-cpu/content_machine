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

**Written:** 2026-10-19 night · **HEAD at write:** the wave 116 batch C+D commit (`git log -1`)
· **Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; CI read after each batch.

**Cursor is out of usage for the month** - its queue is Claude's (roadmap next five).

**The plan is [hands_off_plan.md](hands_off_plan.md), one section per shortfall** (the Story's
22); their ideas are #1314-#1517 in the backlog. Decision 68: `test_docs_lint` holds the
backlog at <= 300, and wave 113 alone was exempt from "close as many as you file".

**Wave 115 (four batches, three commits):**
- `captions.caption_quota_ok` (#1525); `prepublish.with_disclosure` (#1524 - xpPz3ewlNJ8 fixed
  with the operator's yes); the sync's analytics-scope check (#1523).
- `oauth.sign_in_expiry_line`, `jobs/worker_log.last_pass_line`, `growth.subscriber_flags` in
  `ops status` (#1437 #1402 #1325); `config.paths.WORKER_TASK_LOG`.
- `win_notify.toast_daily` (stamps data/toast_days.json) from `crosspost.step` and the worker's
  `_overnight_watch` (#1399 #1372); `prepublish.with_compilation_link` (#1317).
- #1422 closed as already met (the headline shows the hook on frame one).

**Wave 116 (four batches, three commits):**
- `job_queue.quota_wait` / `quota_held_line` (#1526); `upload_queue._logged_runs`,
  `queue_lines`, `two_week_line` (#1527 #1429). Run 161 moved to Thu 10-22 noon (operator's yes).
- `worker._hold_for_sign_in` / `_reslot_after_hold` / `_sign_in_watch`; `oauth.sign_in_mode`,
  `publish_app_hint` (#1439 #1438 #1443 #1445).
- `script_craft.unfinished_ending` / `run_on_sentences` in `script_check`,
  `topic_tokens.place_words` (#1334 #1352); `crosspost.sync_status` retries once (#1400).

**Live:** the sign-in lapses Wed 10-21 9:36 PM EDT unless the app is published - then uploads
hold, not fail. Job 74 (run 173) uploads after the 3:05 AM EDT reset. Renders 168 and 170
sit unlisted; re-cut 171 waits. **Defects first:** none open of mine.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
