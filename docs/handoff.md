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

**Written:** 2026-10-31 · **HEAD at write:** `82b78c3` (wave 137; this wave's commit follows) ·
**Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; read CI.

**Wave 138, the next five (decision 90).** Defects first: run 199's TikTok post went out 31 hours
before YouTube publishes it - the round held it three passes, then the 10-30 21:07 CDT pass's
YouTube read failed and "a failure holds nothing" (fixed: a record slot still ahead holds a run;
the failed read itself is still silent, #1930); the booth showed another run's thumbnail (the
newest file in thumbnails/, never a frame cover) and the ledger called frame covers "pillow"
(fixed). Shipped: `send_due`'s slot hold, `run_thumbnail` + `cover_strip_html`, 130 px caption
sides (`SIDE_PX`; hook card keeps 920), `explore_hour` (1 in 8, noon/3/6/8 PM), the
`black-friday-deals` long row (Nov 23) with up to three `deals_only` links. Six older pins moved
with the narrower text (named in the planning log).

**Open:** #1927-#1932 (hour test 12-01, the Black Friday draft, Cyber Monday, the silent YouTube
read, Instagram's buttons, covers swept after 3 days). **Next five:** #1930, #1932, #1929, #1752,
#1919.

**Operator:** look at the next render's first second on a phone (#1922); connect a Facebook Page in
Buffer; paste the link page into the bios; publish the Google app (lapses Nov 6); the Associates tag
(the Black Friday video's links need it).

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
