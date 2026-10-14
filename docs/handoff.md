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

**Written:** 2026-10-13 · **HEAD at write:** `14246cd` + the wave 83 commit (`git log -1`) ·
**Tree:** clean after the commit, apart from untracked `.agents/` and `.codex/`. Pushed.

**Read before editing:** the overnight task runs the working tree - keep it importable between
edits. The claim check is **not shown the research brief** (`verify_claims` drops `weak_lines`
from the list it numbers); a blocking claim citing a line it was not shown is unsupported.
`OVERNIGHT_SHELF_MAX` is 0 for the whole suite (`tests/__init__.py`) - a test of the shelf
limit sets its own and injects `shelf=`. A draft record now carries `title_warnings`,
`event_at`, `unplayed_result`; `unattended_block_reason` takes `now=`. mypy baseline **98**.

**Cursor:** #1121 #462 #404 #388 #409 are still yours and untouched. **I changed your
`authenticity.payoff_closer` (#1032):** it appended " on " and a lowercased hook word - run 136
was rendered ending "in convincing fashion on tennessee." It now returns the script unchanged
with `closer_answered` False; your test in `tests/test_style_recurrence.py` is renamed and
asserts that. Other shared files: `core/claim_verifier.py`, `core/batch_generation.py`,
`core/batch_review.py`, `core/seasonal_calendar.py`, `core/facts/event_dates.py`,
`core/overnight.py`, `scripts/ops.py` (`--idea` is an alias of `--topic`), `.env.example`,
`tests/__init__.py` (one env line).

**Defects first:**
- **The YouTube sign-in expired 2026-10-13.** Nothing uploads or syncs until the operator runs
  `py -m youtube.oauth_setup --channel tapin`. Stored numbers are of 10-11.
- My plan said 21 of 50 blocked claims were in the facts word for word. Wrong: that matcher
  counted names sharing a line. The one that shipped carries 3. The real cause was the brief.
- The guide said `script-check --idea`; the parser knew only `--topic`. Fixed.
- Run 142's title opened "Factual" - the angle kept its lens name. Open: #1158.
- #1136 runs 92 and 119 are still public with a claim never confirmed.

**Shipped:** wave 83 - #1148 #1149 #1150 #1151 #1152. 50 of 55 new tests failed or errored on
HEAD first. Suite 5650, mypy 98, corpus 210. Highest #1158. Still a ship stage.

**In progress (wave 84, claimed 2026-10-13):** #1153-#1158. Shared files I will touch:
`core/job_queue.py`, `core/stale_renders.py`, `youtube/oauth.py`, `core/overnight.py`,
`core/script_craft.py`, `core/content_engine.py`, `analytics/growth.py`,
`core/source_diversity.py`, `core/correction_dossier.py`, `apis/topic_variants.py`.

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
