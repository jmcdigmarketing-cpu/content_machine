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

**Written:** 2026-11-01 · **HEAD at write:** `4c72cda` (wave 140; this wave's commit follows) ·
**Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; read CI.

**Wave 141, the next five with S01 (decision 93).** The operator set `AFFILIATE_AMAZON_TAG` and
turned on the Reporting API (the reach job exists; S11 now WAITING on YouTube's first file). S01:
the sync keeps `minutes_by_source` for a video off the Shorts feed and `long_sources_line` says
where long views come from (`ops ypp`, S01) - #1315 waits. S15: the menu within 15 points of 28
days' organic views (`ledger.menu_mix`, `_domain_views`); `GAMING_FLOOR` 3. Found and fixed: a
chapter Short counted for no domain (`growth._kind` follows `parent_run_id`) - gaming 41% -> 59%.
Cyber Monday long video row (Nov 28); S09 counts each applied sync's corrections
(data/privacy_sync.json); `unclaim --apply` marks what it leaves - run after the merge for run 220.

**Open:** #1947-#1950. **Next:** S05 with #1919, #1752, #1947, #1931.

**Operator:** publish the Google app (lapses Nov 7); the hook card on a phone (#1922); Facebook in
Buffer; the bio link.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
