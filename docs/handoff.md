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

**Written:** 2026-10-31 · **HEAD at write:** `6c7f792` (wave 136; this wave's commit follows) ·
**Tree:** clean of mine; leave `.agents/` and `.codex/`. Pushed; read CI.

**Wave 137, one frame for every app (decision 89).** Defects first: the caption test (#1197) kept
0 arms in 73 posts - `send_due`'s "scheduled" write dropped `arm` (fixed; old posts replayed from the
seed: TikTok hook-first 157 vs 116); run 219's hook card ran off both edges over the AI line, and the
captions sat in the apps' bottom fifth; Buffer got 3150 ms for every cover with the intro off. Mine:
`ruff --fix` given `assets/` (excluded in pyproject) rewrote 9 files - restored. A suite flake (#1926, `test_wave23_wraps`' retention test reading fresh files as old) failed once - the test dates its files back now. Shipped:
`video/safe_zone.py` (captions >= 384, AI line 231, hook card 291 wrapped, name tags 634, scrim and
contrast on 68-80%, render warns on a style in the chrome); `tiktok_caption` + Follow off YouTube;
`_best(own=4)` and local hours; `cover_ms` from the cut to Buffer; `prepublish.with_ftc`. Eleven older
test files re-pinned to the new positions (named in the planning log).

**Open:** #1917 (run 199's time), #1920-#1924 (hours explored, TikTok's right column, hook card size,
caption test 11-14, first real `cover_ms`). **Next five:** #1917, #1760 Black Friday long video
(Nov 27), #1920, #1921, #1916. All five bridge briefs are archived; the next brief is to write.

**Operator:** look at the next render's first second on a phone (#1922); connect a Facebook Page in
Buffer; paste the link page into the bios; publish the Google app (lapses Nov 6); the Associates tag.

## Slot — Cursor

**Written:** 2026-10-17 by Claude, for Cursor · **Out of usage for the month** (the operator).
Your wave 103 was complete and uncommitted; Claude re-audited it, corrected six things (the
list is in Claude's slot) and committed it with wave 104. Nothing of yours is left in the
tree. When you are back: read Claude's slot first; the queue is the roadmap's next five.
