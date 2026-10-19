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

**Written:** 2026-10-18 late night · **HEAD at write:** the wave 113 batch 5 commit (`git log -1`)
· **Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; CI read after each batch.

**Cursor is out of usage for the month** - its queue is Claude's (roadmap next five).

**The plan is [hands_off_plan.md](hands_off_plan.md), one section per shortfall** (the Story's
22); their ideas are #1314-#1517 in the backlog. Decision 68: `test_docs_lint` holds the
backlog at <= 300, and wave 113 alone was exempt from "close as many as you file".

**Wave 113 (five batches, each pushed):**
- `buffer_api.map_metrics`, `platform_metrics._remap`, `crosspost.buffer_week` (#1418 #1398).
- `sync_metrics.maybe_sync` from overnight and `jobs/worker._sync_metrics`; the stamp is
  data/metrics_synced.json (#1489).
- `authenticity.ad_limit_reason` in `unattended_block_reason` and `backlog_gate` (#1319).
- `youtube_quota.record_usage(caller=)`, `record_call`, `upload_reserve`
  (`YOUTUBE_UPLOAD_RESERVE`) (#1427).
- `preview_brief`'s follow line (#1322).
- `video/hook_copy.py` (`run_opening`, `hook_offset`, `ensure_hook_copy`) from
  `crosspost._sent_file` and `week_compile` (#1417 #1419).

**Wave 114 in progress (batches A-E):** A (#1518 #1519 #1520 - run 154's Buffer posts
removed with the operator's yes, to resend at YouTube's 10-21 02:00Z), B (#1491 #1323
#1314) and C (#354 #1423 #1507 #1428) done. Next: D #1057, E #457.

**Live:** the worker task now syncs metrics once a day, and Buffer's next sends use the hook
copy. TikTok's own send hour applies (5 measured rows). **Defects first:** none open of mine.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
