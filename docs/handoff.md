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

**Written:** 2026-10-11 · **HEAD at write:** `007832d` + the waves 79-80 commit (`git log -1`) ·
**Tree:** clean after the commit, apart from untracked `.agents/` and `.codex/`. Pushed.

**Read before editing:** `privacy_status` in the publish log is only as fresh as the last
`ops sync-metrics` - ask `analytics.privacy_sync`, not the row, when it matters. A module
started with `ops._run_module` gets `PYTHONIOENCODING`; a new entry point run by Task Scheduler
needs `ensure_utf8_stdout()`. `OVERNIGHT_RENDERS=0` is set for the whole suite - a test of the
render step sets its own limit and stubs `_render`. The header has eight parts now
(`_hdr_week`, `_hdr_shelf`); tests that pin it patch both. mypy baseline **98**.

**Cursor:** #1121 and #462 are still yours and untouched. Shared files I touched:
`config/channels.json` (`overnight.renders: 2` on tapin, `parked: true` on moneywise - both the
operator's calls), `config/channels.py` (two profile fields, `active_channel_ids`),
`scripts/ops.py` (`worker-task`, `shelf`, `overnight-plan`, `_child_env`), `tests/__init__.py`
(one env line), `.env.example`, `core/ui.py` (the channel picker skips a parked channel).
`main.py`, `core/pipeline.py` and `desktop/` were not touched - `desktop/launch.py:57` still
lists every channel, parked or not.

**Defects first:**
- Waves 77-78 reported 32 public videos and a shelf of 7. Wrong: all 43 are public (#1128).
  The operator found it. Docs and both pages are corrected.
- Run 132's public upload has been pending since 10-10 9:30 pm; no worker task is installed.
- Tonight's 5:00 am run will render two drafts (136, 123) and spend ElevenLabs characters.
- #1136 runs 92 and 119 are public with a flagged claim never confirmed. #1139 only 2 of 31
  waiting drafts are clean. The Reporting API is still off.

**Shipped:** waves 79-80 - #1128 #1126 #1129 #1130 #1131 #1132 #1133 #1134 #1135 #1127 and the
first half of #1078. 68 of 71 new tests observed failing first. Suite 5531, mypy 98, corpus
188. Highest #1139. **Still a ship stage** (roadmap.md): only live-run defects get built.

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
