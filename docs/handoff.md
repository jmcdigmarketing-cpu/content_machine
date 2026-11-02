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

**Written:** 2026-11-01 · **HEAD at write:** `41ba596` (wave 143; this wave's commit follows) ·
**Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; read CI.

**Wave 144, the next 15 with S02 (decision 96).** Defects first: the leak-title rule is wrong on
1 of 3 stored titles it flags (run 138, #1961); four sports videos sit under Gaming (#1962). Done
live on the operator's word: runs 120 and 126 refiled as Gaming (101 units, read back 20).
`follow_brief`'s fall-through gives every non-preview Short a line (long video / countdown / Monday
Week in Review); the sync keeps the channel id (`youtube_channel_id`) for `subscribe_line`; long
videos get `payoff_rule`, `long_tags`, `chapter_keywords`, `long_drop_off_lines`; series rows for
Nov 9 (editions), Nov 9-11 (trade deadline), Dec 11 (Game Awards); `drop_drafted_matchups` in the
menu; `leak_as_fact` at the title check; `recategorize --run-id`. The suite turns SERIES_DATED off -
calendar tests switch it on themselves.

**Open:** #1953-#1956, #1959, #1961, #1962. **Next:** S15 with #1866, #1779, #1713, #1961.

**Operator:** publish the Google app (lapses Nov 7); paste the three bio pages; four tracking IDs;
Facebook in Buffer; #1922 and #1956 on a phone; #1962 on your word.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
