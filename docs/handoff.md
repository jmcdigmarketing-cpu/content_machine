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

**Written:** 2026-10-18 evening · **HEAD at write:** the wave 111 batch F commit (`git log -1`) ·
**Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; CI read after each batch.

**Cursor is out of usage for the month** - its queue is Claude's (roadmap next five).

**The plan is [hands_off_plan.md](hands_off_plan.md)**; wave 111 shipped all ten of its H1, so
the roadmap's next five come from its quarter (H2). The backlog audit's table:
[backlog_audit_2026-10-18.md](backlog_audit_2026-10-18.md); `test_docs_lint` holds it at <= 130.

**Wave 111 (six batches, A-F):**
- `extra_domains` gains nfl and nba (#1303).
- `snippet_update.writable_status` for every status change, plus `ops status-fields` (#1306;
  seven videos repaired, the operator's yes).
- `voice_notes.correct_names` (#1296).
- tests/__init__.py refuses opens under the real data/ and fails the test by name; `tts` reads
  `run_trace.TRACES_DIR` (#1305).
- `core/predictions/calls.py`: ESPN summary lines, the ledger in data/preview_calls.json,
  `score_calls`, `calls_line`, `picks_graded` (#1304 #991).
- `topic_tokens.names_any` spaces the marker too (49ers).
- `core/predictions/holdouts.py` (#83).
- `video/week_compile.py` and `ops week-compile`; overnight `_week_compile` on Mondays (#138).

**Live:** the first compilation is made by overnight on Monday morning (7 Shorts, 9:50 this week)
and queued for a free slot - the operator said a $0 compilation, public at a slot.

**Wave 112 in progress (batches A-E; a batch not in `git log` was not finished):** A done -
#1307-#1310 (status reuses the doctor result, roundups dropped, the week's games called,
the compilation's thumbnail), B (#1136 settled with the operator's yes) and C (#1311 the
first-line rule, #1079 the gate line, #1312 attribution on outcomes; #1290 not retuned, by
master_plan M4.5) and D (#1042's record card, after the first sentence) done. Next: E #1077 the menu. **Defects first:** none open of mine.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
