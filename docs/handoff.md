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

**Written:** 2026-10-14 · **HEAD at write:** `5272a71` + the wave 86 commit (`git log -1`) ·
**Tree:** clean after the commit, apart from untracked `.agents/` and `.codex/`. Pushed.

**Read before editing:** the overnight task runs the working tree and catches up when the PC
wakes - it started at 5:54 PM on 10-14 in the middle of this wave. Keep the tree importable;
never patch `.py` through a heredoc. The suite pins `NIGHTLY_TASK_QUERY=false` and
`OVERNIGHT_EXPIRE_DRAFTS=false` (never query the operator's task or set aside their drafts),
with `OVERNIGHT_SHELF_MAX=0` and `OVERNIGHT_RENDERS=0`. A draft's record may now say
`review.decision = "expired"`. mypy **98**.

**Cursor:** #1121 #462 #404 #388 #409 are still yours and untouched. Your #374 split is
`SCRIPT_BODY_TIER=cheap` since wave 85 (the operator's call), and `payoff_closer` (#1032)
reports only since wave 83. Shared files this wave: `scripts/ops.py` (`recheck-claims`,
`--wake`, `--expired`, the batch's closing sign-in line), `youtube/oauth.py`
(`short_sign_in`), `core/batch_review.py`, `core/overnight.py`, `core/status.py`,
`core/status_summary.py`, `core/stale_renders.py`, `core/nightly_task.py`, `tests/__init__.py`,
`.env.example`.

**Defects first:**
- **The YouTube sign-in ended 2026-10-13.** Nothing uploads or syncs; the shelf is 3 (132, 126,
  114), so overnight pauses until it drops. The stored numbers are of 10-11.
- The overnight task does not run at 5:00 AM when the PC sleeps (10-14: 5:54 PM).
- The 10-14 run's game drafts narrate games not yet played (#1169, open); the title check held.
- I asked about 6 old drafts; the rule sets aside about 20 the first night (decision §51).

**Shipped:** waves 85-86 - #1159-#1168. 27 of 28 wave 86 tests failed or errored on HEAD
first. Suite 5746, mypy 98, corpus 227. Highest filed #1169.

**In progress:** nothing claimed.

## Slot — Cursor

**Written:** 2026-10-10 · **HEAD at write:** `85ce1d2` · **Tree:** this wave is
uncommitted until the commit that follows. Leave `.agents/` and `.codex/`.

**Defects first:**
- The first full suite (5347) failed the env lint: `VOICE_PACE_FILE` was read
  and not in `.env.example`. Documented beside `TTS_SPEED`.
- #374 changes the script a healthy run writes. Two calls by default. Set
  `SCRIPT_BODY_TIER=premium` for the old single call.
- `ops log --limit 15` printed one warning: YouTube RSS returned 500. That is
  #1121, still open.
- #1088 is still an operator call.

**Shipped:** #990 #400 #380 #995 #374. 16 of 17 new tests failed or errored
first. The restore-flag test was already one premium call. mypy 98.
`roadmap-index`: open 310, done 841, numbered open 258, highest #1121.
Next: #1121 #462 #404 #388 #409. Shared: `scripts/ops.py`, `core/pipeline.py`,
`core/content_engine.py`, `tests/__init__.py`, `.env.example`.
