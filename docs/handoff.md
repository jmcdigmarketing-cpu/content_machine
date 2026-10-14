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

**Written:** 2026-10-13 · **HEAD at write:** `57a4e5f` + the waves 81-82 commit (`git log -1`) ·
**Tree:** clean after the commit, apart from untracked `.agents/` and `.codex/`. Pushed.

**Read before editing:** the overnight task runs the working tree - keep it importable between
edits; it ran waves 81-82 uncommitted and wrote runs 137-139. On Windows `sys.stdin.isatty()`
is true for the NUL device: use `scripts.ops._has_console()` before any prompt in a batch.
YouTube writes content types `shorts` / `videoOnDemand` - compare through
`youtube_metrics._content_type`. A draft's finished-script check is `script_clean` on the run
and in the draft record; `unattended_block_reason` reads it. mypy baseline **98**.

**Cursor:** #1121 #462 #404 #388 #409 are still yours and untouched. Shared files I touched:
`core/content_engine.py` (two passes after `rewrite_claims`: `cut_unsupported`, `hold_stance`;
`strip_label` on the title; `script_clean` in the package), `core/pipeline.py`, `core/ui.py`,
`core/batch_generation.py`, `scripts/ops.py` (`morning`, `overnight-last`, `script-check`,
`_has_console`, a flush in `_run_module`), `.env.example` (`CUT_UNSUPPORTED`).

**Defects first:**
- **The YouTube sign-in expired 2026-10-13** (`invalid_grant`). Nothing uploads or syncs until
  the operator runs `py -m youtube.oauth_setup --channel tapin`. The stored numbers are of 10-11.
- Overnight rendered two wrong videos on 10-13 (run 139: a win written before the game, its
  title flagged; run 136: a preview two days late, last line "on tennessee"). Both pulled -
  jobs 56 and 57 cancelled, renders retired. The causes are open: #1148-#1152.
- Your `authenticity.payoff_closer` (#1032) wrote that last line. I will change it in #1149.
- My first `ops ypp` pace line was wrong as labelled; fixed before this commit (#1144).
- #1136 runs 92 and 119 are still public with a claim never confirmed.

**Shipped:** waves 81-82 - #1137 #1138 #1139 #1140-#1147. 58 of 64 new tests failed or errored
on HEAD first. Suite 5595, mypy 98, corpus 201. Highest #1157. Still a ship stage.

**In progress (waves 83-84, claimed 2026-10-13):** #1148-#1157, all from the 10-13 run. Shared
files I will touch: `core/authenticity.py`, `core/claim_verifier.py`, `core/batch_generation.py`,
`core/batch_review.py`, `scripts/ops.py`, `youtube/oauth.py`, `.env.example`.

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
