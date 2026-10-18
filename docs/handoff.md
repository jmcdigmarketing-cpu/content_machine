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

**Written:** 2026-10-18 late morning · **HEAD at write:** the wave 109 commit (`git log -1`) ·
**Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; CI read after the push.

**Cursor is out of usage for the month** - its queue is Claude's (roadmap next five).

**Wave 109:** `authenticity._STANCE_PATTERNS` gained what-to-watch and conditional calls;
`batch_review.authenticity_now` re-reads a draft held only for `original_insight` (its meta is
not rewritten) - `unattended_block_reason` and the review card use it (#1292).
`hook_score.extract_hook` uses `operator_facts.sentences` (public now) (#1293).
`batch_review.deadline_line` / `review_order`, printed in status, the overnight report and
batch-review (#1294). `channel_health._unmeasured_recent` (#1291). `core/facts/voice_notes.py` +
`ops voice-facts`; `apply_booth_facts(origin=)` (#450). Data: `data/youtube_quota.json`
2026-10-18 used 5,561 -> 761, the operator's yes (copy in my scratchpad).

**Live:** run 165 (Chargers at Chiefs, 20:25Z) has no slot before kickoff - noon is run 153's.
The operator has the by-hand route; #1295 is their call.

**Defects first:** none open of mine.

**Next:** #1295 (a question first), the roadmap's five (#421 #425 #457 #293), #1296. Suite 6,284, forward and reversed.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
