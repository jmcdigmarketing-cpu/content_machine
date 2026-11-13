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

**Written:** 2026-11-13 · **HEAD at write:** `1804db6` (wave 161's commit follows) · **Tree:**
clean of mine after it; leave `.agents/` and `.codex/`. Built in the cloud - no `data/`, nothing
seen live.

**Decision 113 (the operator, 11-13): one month.** Rapid improvement by **2026-12-13** or the
project ends; paid until what is paid runs out, then free, with no AI sessions after. Wave 161:
#2026 a story about machine-made content waits for the operator (a viewer: "You are part of the
problem"); #2027 objections read from the comments; #2028 long videos render when they pass
(changes decision 84); #2029 an ElevenLabs refusal voices the script with Piper,
`PAID_VOICE_UNTIL`; #2030 the cost mode at overnight, the fast lane, the 1 PM step and the worker,
`PAID_UNTIL`; #2031 the month's test in `ops status`. Nothing found broken in shipped code.

**Read back first on the PC:** `ops mailbag` lists the 11-11 comment; `ops status` shows the
decision-day line after a sync; a waiting long draft renders overnight (#1902 still unwatched).

**Next:** the paid characters left budgeted across launch week, the daily videos and a bank; the
evergreen bank (#1737, #1689, #1661); paid-written scripts as examples for the free model; a
runbook for running with nobody watching. Wave 160's open list stands (#2024, #1905, #1598, #1602,
#1856; #2023's read-back).

**Operator:** publish the Google app and sign in before Sat Nov 14 4:08 PM EST (#2017), then
`schtasks /Change /TN "ContentMachine\UploadWorker" /ENABLE` (disabled since 11-08); cancel the
ElevenLabs renewal and Cursor, turn off auto-recharge on the LLM accounts; send the paid month's
last day and the characters left; record Steam footage (`ops footage-add`); set `PIPER_VOICE`.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
