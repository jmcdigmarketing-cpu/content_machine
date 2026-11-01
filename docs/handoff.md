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

**Written:** 2026-11-01 · **HEAD at write:** `251837f` (wave 139; this wave's commit follows) ·
**Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; read CI.

**Wave 140, the next five with S02 (decision 92).** A countdown, a launch moment and a long video
end on their true reason to follow (`follow_brief`, in the creative brief). A draft that still reads
as a recap gets one more insight pass after every other pass (`recap_rewrite`; `RECAP_REWRITE`, off
in the suite - a model call) and review prints what recaps earned (`recap_cost_line`). S06 reads the
saved scripts with today's detector: 4 of 48, not 9. A failed YouTube read in the crosspost round is
None and says so; `keep_cover` copies the frame cover into output/<channel>/thumbnails;
`retire_renders(why=)` and `ops retire-renders --why wrong` - S03 counts them (waiting to 11-29).
Runs 204 and 205's TikTok posts were cleared and are scheduled for Sun 11 PM EST.

**Open:** #1940-#1943. **Next:** S01 (#1315 first) with #1929, #1942, #1934, #1935.

**Operator:** publish the Google app (lapses Nov 7); turn on the Reporting API (S11); the hook card
on a phone (#1922); Facebook in Buffer; the bio link; the Associates tag.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
