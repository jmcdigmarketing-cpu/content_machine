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

**2026-10-30 (the session that ran waves 121-122), at `899ff58`:** docs only - decision 85 (gaming
and sports equally; covers our own frames, no words; AI covers off) and five plans:
[tapin_philosophy.md](tapin_philosophy.md), [tapin_principles.md](tapin_principles.md),
[logistics_plan.md](logistics_plan.md), [look_and_feel.md](look_and_feel.md) (build list L1-L10,
not yet in the backlog), [horizons_2027.md](horizons_2027.md); the operator's Studio numbers in
[studio_snapshot_2026-10-30.md](studio_snapshot_2026-10-30.md). The rest of this slot is wave 133's.

**Written:** 2026-10-28 · **HEAD at write:** `30b71df` (wave 132's next five; this wave's commit
follows) · **Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; read CI.

**Wave 133, the next ten, shipped** (decision 84): the GTA 6 window in `config/series.json` - three
long 16:9 videos (11-06, 11-12, 11-20) rendered only after review (`core/series/long_form`), ten
launch moments as extra drafts (`core/series/dated`), a 6 PM GTA slot and GTA-first drafting
11-16 to 11-22, launch day at `publish_at`, the countdown in day order in the GTA playlist,
long titles from search, cards from our own frames, affiliate links once the tag is set; the
verdicts compare 24 ratings. **Defects found by the live reads, fixed:** the verdicts' first floor
still let 7-day views win; the subject's own suggestions titled every long video "GTA 6 Trailer";
"GTA 6's map" lost its subject. Nothing found broken in shipped code.

**Next five:** wave 134's scoreboard - #1823 #1824 #1697 #1825 #1822
([cloud_brief_wave134.md](cloud_brief_wave134.md)). Filed #1902 (the first 16:9 render, unwatched).

**Cursor is out of usage for the month** - its queue is Claude's.
**Operator:** review the 11-06 long draft before it renders; the Associates tag; the unlock time and
embargo date in `config/series.json` when Rockstar states them; the Oct 26 campaigns; the Google app.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
