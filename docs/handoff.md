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

**Written:** 2026-10-22 night · **HEAD at write:** `9d4610d` (the code; the docs commit follows)
· **Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; CI read after the push.

**Cursor is out of usage for the month** - its queue is Claude's (roadmap next five).

**The plan is [hands_off_plan.md](hands_off_plan.md), one section per shortfall**; ideas
#1314-#1517 in the backlog. Decision 68: the backlog stays <= 300 (`test_docs_lint`).

**Wave 122 (two batches, `d67b929` `9d4610d`), built on `053978c`:**
- **#1542, a defect:** `youtube_metrics.refresh_publish_metrics` stored nothing after a video's
  24h snapshot since 10-05 - fixed; the next `sync-metrics` on the PC heals the rows.
- `apis/team_gazetteer` (NHL/MLB/EPL) in `title_generator.broken_team_name` (#1481);
  `script_check` names a broken team, `caption_timing.line_bounds` + `topic_tokens.name_spans`
  keep names on one cue (#1482); `thumbnail_compose.short_headline` (#1483).
- `nightly_task.start_beat` / `beat_gap_line` from `ops overnight`, read by `ops status` and the
  morning (#1468; `OVERNIGHT_BEAT=false` in the suite); `tests/test_health_writers.py` (#1473).

**Live:** nothing run on the PC this wave - replayed on synthetic data. **Defects first:** #1542
is fixed in code and waits for one sync to heal the stored rows; #1540 (the #599 thumbnail check
likely cannot fail) is still filed, not fixed. None open of mine otherwise.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
