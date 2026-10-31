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

**Written:** 2026-10-30 · **HEAD at write:** `067983b` (the cloud's 10-30 plans; this wave's commit follows) ·
**Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; read CI.

**Wave 134, the next five, shipped.** The operator's background drop first (files only, no commit):
19 YouTube downloads were recorded as owned - now credited generically (#1903, decision 86 - the cloud took 85 on 10-30 - no file
written into the library); Call of Duty, Black Ops and Counter-Strike topics reach their folders
(#1904, `config/footage_aliases.json`). Then the scoreboard: #1823 the bars as data, #1824 engaged
views (stored by the next sync), #1697 organic subscribers "at most 166" until the campaigns' counts
are final, #1825 the race clock (96 days), #1822 the scoreboard in `ops ypp`, the weekly report and
`ops status`. Nothing found broken in shipped code.

**Caught up 10-30:** the cloud's `067983b` (decision 85, the five plans, look_and_feel's L1-L10) is
under this commit. Live: countdown days 21 and 20 were missed (the PC off at 5 AM; one render went to
a game) - day 20 posted by hand at 11:08 PM ET (rXPoLUQnWow) after a sign-in renewal; `.env` now has
YOUTUBE_THUMBNAIL_UPLOAD=off and the Flux key commented out (the operator's yes).

**Next 15 (wave 135):** the countdown a day ahead (defect), look_and_feel's L1-L10 in its order, and
wave 134's 6-10 - #1797 #1728 #1827 #1836 #1832. Filed #1905 (each uploader named).

**Cursor is out of usage for the month** - its queue is Claude's.
**Operator:** enter the Oct 26 campaigns' final counts with `ops spend result --entry N --subs N
--final`; publish the Google app (the sign-in lapses Nov 6); the Associates tag; the 11-06 long draft.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
