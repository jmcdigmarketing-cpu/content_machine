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

**Written:** 2026-10-15 · **HEAD at write:** `a10d971` + the wave 90 commit (`git log -1`) ·
**Tree:** clean after the commit, apart from untracked `.agents/` and `.codex/`. Pushed.

**Read before editing:** TikTok and Instagram go out through Buffer's API since wave 89
(`publishing/buffer_api.py`, `publishing/video_host.py`, the API half of
`publishing/crosspost.py`); the suite pins `CROSSPOST_AUTO=false` and, since wave 90,
`ENV_LINT_FILE` (the `.env` line check must never read the operator's file). Best bets place
this week's games after the other picks, at most `BEST_BET_SCHEDULE_MAX` (2) in five
(`best_bet.with_games`). mypy **98**. Patch scripts go through the Write tool - a Bash heredoc
turned `\n` into newlines again in wave 90.

**Cursor:** #1121 #462 #404 #388 #409 are still yours and untouched. **Offered to you, the
operator's choice of four:** #1194 `[XL]` one video, three feeds - learning per platform from
TikTok and Instagram results (#1195-#1199). Brief, files, definition of done and a paste-ready
prompt: `docs/initiative_cross_platform.md`; a pointer at the top of `cursor_brief_2026-10.md`.
The operator says whether it comes before or after your Phase A. Shared files this wave:
`core/best_bet.py`, `core/ui.py`, `main.py`, `core/batch_review.py`, `core/secrets_doctor.py`,
`core/ops_doctor.py`, `publishing/crosspost.py` (`run_state_line`), `tests/__init__.py`,
`.env.example`.

**Defects first:**
- Nothing can go to TikTok or Instagram yet: the R2 keys are not in `.env`, and the Buffer
  channel ids are not kept (`crosspost channels --apply`). Buffer answers: TikTok
  `tapinmedia47`, Instagram `tapinmedia03` (business).
- `.env` lines 35-36 are not NAME=value; the header now says so.

**Shipped:** waves 89-90 - #1185-#1193. 31 of 31 and 12 of 12 tests failed or errored on HEAD
first. Suite 5823, mypy 98, corpus 244. Highest filed #1199.

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
