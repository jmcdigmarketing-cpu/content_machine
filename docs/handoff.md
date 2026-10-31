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

**Written:** 2026-10-30 · **HEAD at write:** `ea93bda` (wave 135's countdown fix; this wave's commit
follows) · **Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; read CI.

**Wave 135, caught up and the next 15.** The cloud's `067983b` (decision 85, the five plans) is in;
my wave 134 sits on it (decision 86). Countdown days 21 and 20 were missed - fixed first and alone
(`ea93bda`, #1906): tomorrow's drafted too, countdowns render outside the limit, uploaded for their
own noon (decision 87). Day 20 posted 10-30 11:08 PM ET; day 19 scheduled Sat 6 PM ET. Then the look
list L1-L10 (#1907-#1916): `assets/clip_ledger` (rotation), `clip_tags.without_ui` (motion measured -
7 of 193 clips are menus), platform aliases, `assets/cover_frames` (own-frame covers, never repeated,
the Short opens on the cover's shot), image models only with `THUMBNAIL_AI`, the `long_cover`
experiment; and #1797 #1728 #1827 #1836 #1832 (`core/success/scorecard.py`). `.env`: the Flux key
commented out, `YOUTUBE_THUMBNAIL_UPLOAD=frames` (the operator's yes). Nothing found broken in shipped
code; the live reads fixed two wordings.

**Open:** #1913 (face_forward arm, pick-thumbnail between frames), #1916 (the strip in `ops booth`),
L5's club naming in footage-gaps, the platform folders (operator).
**Next five:** wave 136 - #1754 Facebook Reels, #1772 crosspost within the hour, #1750 link-in-bio,
#1753 income beside spend, #1756 TikTok that can earn.

**Operator:** publish the Google app (the sign-in lapses Nov 6); final campaign counts with
`ops spend result --entry N --subs N --final`; the Associates tag; the 11-06 long draft.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
