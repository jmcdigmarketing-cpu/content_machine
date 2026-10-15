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

**Written:** 2026-10-14 · **HEAD at write:** `ea9fe42` + the wave 87 commit (`git log -1`) ·
**Tree:** clean after the commit apart from untracked `.agents/`, `.codex/` and my
`tests/test_morning_corrections.py` (wave 88, not yet built). Pushed.

**Read before editing:** the overnight task runs the working tree and catches up when the PC
wakes. Keep the tree importable; never patch `.py` through a heredoc. A schedule pick's brief
now starts "This game has not been played yet" (`event_dates.PREVIEW_PREFIX`); `is_directive`
treats it as the machine's, not the operator's. `CLAIM_FACT_CHAR_BUDGET` is new (24,000). mypy
**98**.

**Cursor:** #1121 #462 #404 #388 #409 are still yours and untouched. Shared files this wave:
`apis/topic_scorer.py` (`_fixture_domain` - a neutral topic only), `apis/blog_rss_api.py` (one
status), `core/batch_generation.py`, `core/claim_verifier.py`, `core/batch_review.py`,
`core/experiment_levers.py`, `.env.example`.

**Defects first:**
- **The YouTube sign-in ended 2026-10-13.** Nothing uploads or syncs; the shelf is 3, so
  overnight pauses until it drops.
- The `blog_rss` `no_key` trip of 10-14 17:55 is in `data/quota_state.json` until 23:55; left.
- The proof drafts' openers: no full stop (#1179), the next sentence said twice (#1180).

**Shipped:** wave 87 - #1169-#1173. 8 of 13 tests failed or errored on `ea9fe42` first. Suite
5759, mypy 98, corpus 232. Highest filed #1182.

**In progress:** wave 88 claimed - #1174 the correction scan reads a page only when it names the
claim's subject, #1175 open corrections in `ops morning`, #1176 the morning offers to sign in,
#1177 `batch-review` cuts flagged sentences, #1178 the thumbnail keeps its title, and #1179-#1180
from the proof drafts. Files: `core/correction_dossier.py`, `scripts/ops.py`, `core/overnight.py`,
`core/batch_review.py`, `assets/thumbnail_compose.py`, `core/content_engine.py` (hook pass).

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
