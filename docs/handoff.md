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

**Written:** 2026-10-15 · **HEAD at write:** `3912225` + the wave 91 commit (`git log -1`) ·
**Tree:** NOT clean - Cursor's uncommitted work is in it (logging, competitor sync, brand-safety
lexicon, dead-air, host concurrency; new tests `test_brand_lexicon`, `test_feed_down`,
`test_run_log`, `test_dead_air`). My commit carries my hunks only: `scripts/ops.py`,
`docs/backlog.md`, `.env.example` and `tests/regression_corpus.json` hold both of ours, and I
staged mine by hunk. Untracked `.agents/`, `.codex/` and my `tests/test_*` for wave 92 aside.

**Cursor, read this:** before I saw you were working, one repo-wide `ruff check --fix` and
`ruff format .` of mine ran over your in-progress files (layout only - e.g. `tests/test_run_log.py`
was re-wrapped; its F841 / SIM222 were left for you). Nothing of yours is staged or committed by
me. Shared files of mine this wave: `scripts/ops.py` (BATCHES `all` + `morning`, the queued-upload
offer in `_run_batch`, `_crosspost_api`), `jobs/worker.py` (`_crosspost_after_upload`,
`send_queued_uploads`), `publishing/crosspost.py`, `publishing/buffer_api.py` (`draft`),
`publishing/video_host.py` (public address only). Your five and #1194-#1199 stay yours.

**Read before editing:** `ops all` now ends with the morning (decision §56). Crossposting is
switched on (`data/crosspost_tapin.json` `buffer.since`, 44 baseline runs); the automatic round
leaves a video already posted by hand in Buffer (§57). Buffer reads the bucket's public address
only - a presigned link answers HEAD with 403 and Buffer refuses it (§58). mypy **98**.

**Defects first:**
- Nothing goes to TikTok or Instagram until `R2_PUBLIC_BASE_URL` is set (public access on the
  bucket). `.env` lines 35-36 still unparsed.
- Overnight ran at 4:52 PM on 10-15 (the PC slept at 5:00 AM).

**Shipped:** wave 91 - #1200-#1204, #1207. 17 of 20 tests failed or errored on `3912225` first.
Suite 5861 with Cursor's uncommitted tests in it (one of theirs errored while its module was
being written; mine all pass), mypy 98, corpus 247 in my commit (250 with Cursor's).

**In progress:** wave 92 claimed - #1205 the arc's week counter (`core/topic_graph.py`,
`core/best_bet.py`), #1181 the lost "Los", #1182 a game run's stored domain, #1183 the thumbnail
headline (`assets/thumbnail_compose.py`), #1206 old descriptions re-laid at upload.

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
