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

**Written:** 2026-10-14 · **HEAD at write:** `eea67d1` + the wave 89 commit (`git log -1`) ·
**Tree:** after the commit, untracked `.agents/`, `.codex/` and my `tests/test_ideas_and_menu.py`
(wave 90, not yet built). Pushed.

**Read before editing:** TikTok and Instagram now go out through Buffer's API
(`publishing/buffer_api.py`, `publishing/video_host.py`, the API half of
`publishing/crosspost.py`). The suite pins `CROSSPOST_AUTO=false` - never post to the
operator's accounts from a test; `BUFFER_API_KEY` and `R2_SECRET_ACCESS_KEY` are blanked by the
suite's `_SECRET_NAME` rule. `data/crosspost_<channel>.json` now holds `buffer` (ids, `since`,
`baseline`) and `posts` (per run, per platform: state, post id, due, link). `createPost` has
no idempotency key - keep the "mark before the call" order. boto3 is a new pinned dependency.
mypy **98**.

**Cursor:** #1121 #462 #404 #388 #409 are still yours and untouched. Shared files this wave:
`publishing/crosspost.py`, `publishing/go_public.py` (`GoPublicResult.crosspost`),
`scripts/ops.py` (`crosspost` verbs, `crosspost-send` in `morning`), `core/overnight.py`,
`core/ops_doctor.py`, `pyproject.toml`, `requirements.txt`, `.env.example`, `tests/__init__.py`.

**Defects first:**
- Nothing can go to TikTok or Instagram yet: the R2 keys are not in `.env`. `.env` lines 35-36
  begin "Client" and are skipped by python-dotenv.
- Buffer itself answers: TikTok `tapinmedia47` and Instagram `tapinmedia03` (business).

**Shipped:** wave 89 - #1185-#1190. 31 of 31 tests failed or errored on `eea67d1` first.
Suite 5811, mypy 98, corpus 242. Highest filed #1193.

**In progress:** wave 90 claimed - #1191 two games of five best bets (`core/best_bet.py`),
#1192 overnight videos in `py main.py` (`core/ui.py`, `main.py`, `core/batch_review.py`), #1193
unparsed `.env` lines named (`core/secrets_doctor.py`, `core/ops_doctor.py`, `main.py`); then an
initiative offered to Cursor (#1194, cross-platform learning).

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
