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

**Written:** 2026-10-18 afternoon · **HEAD at write:** the wave 110 commit (`git log -1`) ·
**Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; CI read after the push.

**Cursor is out of usage for the month** - its queue is Claude's (roadmap next five).

**The plan is [hands_off_plan.md](hands_off_plan.md)** (themes A-E, H0/H1/H2); it supersedes
optimization_plan_2026-10.md. The backlog audit closed 188 of 258 - read
[backlog_audit_2026-10-18.md](backlog_audit_2026-10-18.md) before reopening anything;
`test_docs_lint` holds the backlog at or under 130.

**Wave 110:** `menu_line` flushes (#1297). One slot rule - `batch_review.plan_review_slots`,
`slot_for_run` in the menu and `auto_generate`, `plan_spaced_uploads` on `free_slots`,
`_ASAP_LEAD` for a game with no slot (#1295); bare `ops crosspost` is the round, `pack` packs
public only (#1298). `go_public._log_rows`, a reschedule logs "public", `waiting_line` and the
worker's scheduled-live pass read the real row shape (#1299). `best_bet.idea_feeds` /
`rank_by_coverage` / `coverage_note` (#1300). `core/predictions/calls.py`, `game_detail` line,
`with_calls`, `batch_generation.draft_brief` (main.py too), `PREVIEW_CALLS` (#1301). `all` has no
suite; `suite_hygiene.without_dotenv` around `ops test` (#1302).

**Live:** 52tS6g1fu_k public (Buffer 11:45); 3nlkdFTjxe0 public 22:00Z - its log row says
"private" (a hand edit was refused), so the worker's read-back sends it.

**Defects first:** none open of mine. **Next:** wave 111 in batches - the plan's "Next ten"
(the operator answered #1303 yes, #138 a $0 compilation, #991 Picks graded, #83 holdouts 1 in 5);
a batch that is not in `git log` was not finished. Batch A (the plan's H1/H2) and B (#1303
#1269 #104 #1059 #1306 #1296; seven videos' embedding restored, the operator's yes) and C
(#1305: a test may not open the real data/ - the suite is green in the real tree too) and D
(#1304: calls from ESPN's summary, kept in data/preview_calls.json, scored; `names_any`
now names the 49ers) and E (#991 Picks, graded; #83 holdouts in data/holdouts.json) are
committed. Left: F, #138 the weekly compilation.
Suite 6,313, forward and reversed.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
