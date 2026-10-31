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

**Written:** 2026-10-31 · **HEAD at write:** `1e52c79` (wave 135; this wave's commit follows) ·
**Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; read CI.

**Wave 136, money and reach (decision 88).** Defects first: my first `platform_baselines` skipped
every TikTok/Instagram run in a store with no post of theirs (8 older tests caught it - the first two
platforms are never baselined now); my first `miss_lines` measured lateness from the due time, which
decision 64 sets to 10 PM on purpose (15 of 22 "late") - it measures when Buffer got the post now.
Run 199's publish log is public with a publish time 8 hours ahead (#1917, not fixed). Shipped:
Facebook Reels (`PLATFORMS`, the Reel metadata, per-platform baselines - only Shorts public after a
Page is connected; Buffer has none), late crossposts sent on the worker's next pass (`late_runs`; 8
TikTok and 9 Instagram queued late this week), `publishing/link_page.py` live on R2
(`tapin/links.html`, rebuilt overnight, `ops links`), `ops spend income` and the net line, TikTok's
Creator Rewards line, `prepublish.without_short_affiliates` (#1758's guard).

**Open:** #1917 (run 199's time), #1918 (re-read late crossposts 11-07), #1919 (link page clicks).
**Next five:** #1775 TikTok's safe zone, #1776 TikTok captions, #1791 the cover frame to Buffer,
#1774 each platform's hour (its "YouTube slot + 1 h" meets decision 64's 10 PM - ask), #1751 the FTC
line at publish. Wave 136 was the bridge's last brief.

**Operator:** connect a Facebook Page in Buffer; paste the link page's address into the bios; publish
the Google app (the sign-in lapses Nov 6); `ops spend result --final`; the Associates tag; the 11-06
long draft.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
