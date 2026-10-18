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

**Written:** 2026-10-18 night · **HEAD at write:** the wave 112 batch E commit (`git log -1`) ·
**Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; CI read after each batch.

**Cursor is out of usage for the month** - its queue is Claude's (roadmap next five).

**The plan is [hands_off_plan.md](hands_off_plan.md)**; its H1 shipped in wave 111, so the next
five come from its quarter (H2): #1057 re-cuts, the rest of #1042, #354 a stop rule, #457 a
lockfile, #1058 (the operator's Reporting API). `test_docs_lint` holds the backlog at <= 130.

**Wave 112 (five batches, A-E, each pushed):**
- `ops_doctor.save_last` / `last_checks`: `ops status` reuses a result under 12 h (#1307).
- `best_bet._is_roundup_headline` (#1308); overnight `_call_week` (#1309);
  `week_compile.make_thumbnail` (#1310).
- #1136 settled (the operator's yes); a correction line on q6_QBAUrtiQ.
- `authenticity.first_line_take` and the first-line rule in both prompts (#1311;
  FIRST_LINE_RULE pinned off in the suite); `retention.cliff_line`,
  `growth.third_channel_line` (#1079).
- `paid_signal_attribution` on measured outcomes (#1312; the finding is on #1071).
- `video/matchup_card.py`, overlaid by `render_video` (#1042; MATCHUP_CARD pinned off).
- `main._ask_length_and_voices`, `prompt_upload_plan(privacy_kept=)` (#1077);
  `length_recommender` reads the newest 40 measured runs (#1313).

**Live:** Monday's compilation is overnight's (wave 111); the matchup card shows on the next
preview render. **Defects first:** none open of mine.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
