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

**Written:** 2026-10-28 · **HEAD at write:** `1b69b78` (wave 132's first five; this wave's commit
follows) · **Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; read CI.

**Wave 132, the next five, shipped:** #1847 the GTA 6 countdown from 10-29 (`core/series/`,
`config/series.json`) - "GTA 6: N days to launch - <the day's story>", an extra fourth draft, held
after its day (decision 83); #1595 3+ outlets or a marquee name (`config/marquee.json`, + #1859);
#1593 one marquee preview a night; #1594 a `news` intent ranked on the headline; #1592 the Week in
Review as a rundown then the top 3 (this week's 12 Shorts: 6:46). Nothing found broken in shipped
code; seven older tests pinned what decisions 81 and 83 change and moved with them.

**Next five:** **#1850** the long-form draft kind ("everything we know" public by 11-10); #1748 the
affiliates map; #1856 search titles; #1868 two GTA slots in launch week; #1596 the verdicts.
Filed #1898 #1900 #1901, parked #1899.

**Cursor is out of usage for the month** - its queue is Claude's.
**Operator:** watch 10-29's countdown draft; end the two Oct 26 campaigns in Studio and send the
numbers; Amazon Associates (#1747 waits on it) and a Facebook Page in Buffer; the Google app by 10-30.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
