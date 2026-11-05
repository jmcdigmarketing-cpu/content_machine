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

**Written:** 2026-11-04 · **HEAD at write:** `37ecb11` (wave 148, CI green; this wave's commit
follows) · **Tree:** clean of mine after it; leave `.agents/` and `.codex/`.

**Wave 149, the next five with S01.** Defects first: frames-only mode let no long video's cover up -
run 230's Week in Review was never set, and the Nov 6 GTA long video's would not have been (#1992,
decision 99). Built: the Week in Review's cover is a band of its top Short with that Short's subject
("GTA 6 This Week"); runs 172 and 202 (under 2%) get it at the next metrics sync (#1990). Long videos
that are not news go public Sundays at 7 PM, compiled that morning; the scripts say "every Sunday";
the GTA week-one special is Nov 22 (#1727, decision 100). A franchise's new season, named by two
outlets, drafts a long explainer for your review (#1724). NVENC's fallback logs ffmpeg's reason
(#1981); avatar, reframe, run_eval_corpus and backlog_index are gone (#1979).

**Open:** #1984, #1988, #1991, #1993, #1994; dated reads #1953, #1955, #1956, #1959, #1988, #1991,
#1994. **Next:** #1993, #1723, #1737, #1738, #1735 before W4's freeze (Nov 16); #1849 once the
embargo date is known.

**Operator:** publish the Google app before Sat Nov 7 (set POLICY_SITE_URL first - `ops check-youtube`
reads the four pages); paste the bio pages; tracking IDs; Facebook in Buffer; #1922/#1956 on a phone.
Review the UFC 334 recap draft the morning of Nov 15. The first Sunday Week in Review is Nov 8, 7 PM.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
