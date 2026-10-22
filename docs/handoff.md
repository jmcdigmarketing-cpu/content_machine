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

**Written:** 2026-10-22 · **HEAD at write:** `db00be1` (the code; the docs commit follows)
· **Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; CI read after the push.

**Cursor is out of usage for the month** - its queue is Claude's (roadmap next five).

**The plan is [hands_off_plan.md](hands_off_plan.md), one section per shortfall**; ideas
#1314-#1517 in the backlog. Decision 68: the backlog stays <= 300 (`test_docs_lint`).

**Wave 121 (two batches, `c74cab7` `db00be1`), built on `9e03058`:**
- `retention.first_seconds_text(stayed=)` (#1538); `topic_tokens.trim_name`, `part_of_team`,
  `abbreviations_in`, `NFL_ABBR_TEAMS` / `NBA_ABBR_TEAMS` in `names_for` and `subject_terms`
  (#1539 #1487); `title_generator.broken_team_name` reads each mention (#1486).
- `channel_health`: `UNKNOWN` (#1472), `record_history` / `history_lines` + `ops health
  --history` (#1475), `THRESHOLDS` / `THRESHOLDS_VERSION` (#1479), `_entered_cost_sub` (#1478).
- `privacy_sync.fetch_status` reads `status,snippet`, `studio_edits` (#1390);
  `nightly_task.crash_frame` in the stopped line (#1469). #1391 closed by measurement.
- Changed on purpose: test_pillar5_agents' fail-open test pins unknown, not yellow "n/a".

**Live:** nothing run on the PC this wave - each item was replayed on synthetic data. The
sign-in lapsed 10-21 9:36 PM EDT; uploads hold until the operator signs in. **Defects first:**
#1540 (the #599 thumbnail check likely cannot fail) is filed, not fixed; none open of mine.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
