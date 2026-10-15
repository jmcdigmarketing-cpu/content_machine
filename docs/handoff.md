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

**Written:** 2026-10-14 · **HEAD at write:** `f797d98` + the wave 88 commit (`git log -1`) ·
**Tree:** clean after the commit, apart from untracked `.agents/` and `.codex/`. Pushed.

**Read before editing:** the overnight task runs the working tree and catches up when the PC
wakes. Keep the tree importable; never patch `.py` through a heredoc - and the guard test now
reads `docs/`, `assets/` and `tests/` too. `ops morning` may now call `input()` (the sign-in
offer) - only with a console, and only in `morning`. A correction note now carries
`CHECKED_LINE`; one without it is from before #1174. mypy **98**.

**Cursor:** #1121 #462 #404 #388 #409 are still yours and untouched. Shared files this wave:
`scripts/ops.py` (`corrections-open`, the sign-in offer in `_run_batch`), `core/batch_review.py`
(`c`, `why_not_cut`), `core/content_engine.py` (`with_full_stop`, `says_next_sentence` in
`_hook_variants`), `core/correction_dossier.py`, `core/overnight.py`,
`assets/thumbnail_compose.py`, `assets/flux_thumbnail.py`. Seven older correction tests' pages
now name their subject (`test_wave5_defects`, `test_review6_defects`, `test_next15_wave`).

**Defects first:**
- **The YouTube sign-in ended 2026-10-13.** `ops morning` now offers it; nothing uploads or
  syncs until then, and overnight pauses while the shelf is 3.
- Open: #1181 (a title said "Denver Loss Angeles"), #1182 (a game run's stored domain reads
  neutral), #1183 (four-word thumbnail headline), #1184 (a correction note written each scan).
- Empty folders under `C:\c\Users\...` from my sample render; the operator's to delete.

**Shipped:** waves 87-88 - #1169-#1180. 8 of 13 and 17 of 21 tests failed or errored on HEAD
first. Suite 5780, mypy 98, corpus 242. Highest filed #1184.

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
