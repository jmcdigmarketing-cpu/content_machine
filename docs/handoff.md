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

**Written:** 2026-10-13 · **HEAD at write:** `2623ee8` + the wave 85 commit (`git log -1`) ·
**Tree:** clean after the commit, apart from untracked `.agents/` and `.codex/`. Pushed.

**Read before editing:** the overnight task runs the working tree - keep it importable.
Never patch a `.py` file through a shell heredoc (it eats backslashes; `MarkupTests` fails on
a control character). `generate_draft(own_idea=True)` is the operator's angle 1: index -1,
`idea_angle`, no experiment directive. A flagged claim is matched to its sentence by
`script_craft.claim_sentences` (possessives off; two sentences in a row count) - not by
`claim_confirm._coverage` alone. `OVERNIGHT_SHELF_MAX` is 0 for the suite. mypy **98**.

**Cursor - two of yours changed by the operator's call:**
- **`SCRIPT_BODY_TIER` defaults to `premium` again** (#1163, decisions_2026-10.md §48). #374's
  split is `SCRIPT_BODY_TIER=cheap`. In `tests/test_hook_tier.py` the helper's default is now
  `"cheap"`, so your tests of the split ask for it by name; nothing else there changed.
- `authenticity.payoff_closer` (#1032) reports and no longer edits the script (wave 83).
#1121 #462 #404 #388 #409 are still yours and untouched. Other shared files this wave:
`core/content_engine.py` (a `repair_hook` pass after `cut_unsupported`; `_hook_variants` takes
`unbacked=`), `core/facts/grounding.py` (`_CAP`, sentence openers), `apis/topic_tokens.py`
(four words on `COMMON_CAPITALISED`), `core/batch_generation.py`, `core/batch_review.py`.

**Defects first:**
- **My wave 83 proof was wrong**: the three "own idea" drafts were written from generated
  angles (`variant_index=0`). Fixed and re-run as runs 143-145; none came back clean (2, 1, 1
  unbacked claims).
- My first sentence-opener rule skipped "LeBron was traded" and broke a frozen grounding
  verdict. Narrowed before commit.
- **The YouTube sign-in expired 2026-10-13.** Nothing uploads or syncs until the operator signs
  in. #1136 is still open.

**Shipped:** wave 85 - #1159-#1163. 22 of 29 new tests failed or errored on HEAD first. Suite
5718, mypy 98, corpus 225. Highest filed #1168.

**In progress (wave 86, claimed 2026-10-13):** #1164-#1168 - a recheck of waiting drafts, the
sign-in said once, a pulled run called pulled, when overnight ran, old drafts set aside. Shared
files: `scripts/ops.py`, `youtube/oauth.py`, `core/batch_review.py`, `core/overnight.py`,
`core/status.py`, `core/nightly_task.py`.

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
