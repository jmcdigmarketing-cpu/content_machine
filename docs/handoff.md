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

**Written:** 2026-11-03 · **HEAD at write:** `a1fc7cb` (wave 145, CI green; the docs-sweep commit
follows) · **Tree:** clean of mine after it; leave `.agents/` and `.codex/`. Both pages updated
(Story v65; Back-Home List v68, pruned to 14 items, ticks kept).

**Wave 145, the next 15 with S15, and the grand audit ([audit_2026-11-02.md](audit_2026-11-02.md)).**
Defects first, found live: the Nov 3 countdown was held for its own day count, on a "since launch"
angle, led by a fan's death, and no night would redraft it (#1963-#1966); the follow line was graded
as your idea (#1967); day 15 went public at 9:13 PM ET Nov 3, a day early - left public (#1980,
fixed). Decision 97: never a death story (title, first line, description). Decision 98: the night
carries the gaming share, a menu is counted once, a deleted video is recorded `gone`. Done live on
your word: day 16 redrafted (run 231), approved past the second read, public 8:38 PM ET Nov 3; four
sports videos refiled as Sports (201 units, read back). The cheap free model was retired - replaced
by live test, and an empty LLM answer now fails over. The 16:9 cut is laid out for 16:9 (checked on
run 203's render).

**Open:** #1976-#1979, #1981; dated reads #1953, #1955, #1956, #1959. **Next:** S01 with #1976, #1978,
#1977, #1849. **Overnight** ran 11-03 19:14 on `main` with the countdown fixes copied in before the
commit (the session was interrupted).

**Operator:** publish the Google app before Sat Nov 7 (set POLICY_SITE_URL first - `ops check-youtube`
reads the four pages); paste the bio pages; tracking IDs; Facebook in Buffer; #1922/#1956 on a phone.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
