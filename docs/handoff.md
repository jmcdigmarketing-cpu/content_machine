# Handoff — the mailbox

**Read this first, before any other file, every time you start work here.** More than
one agent works in this repo and nothing signals a switch. This file is how the
previous one tells you what it did and what it broke.

Two slots. **Overwrite your own; never edit the other agent's.** Keep each slot under
~25 lines — this is a mailbox, not an archive. The archive is
[HANDOFF_SYNOPSIS.md](HANDOFF_SYNOPSIS.md) (session state) and
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

**Written:** 2026-09-18 · **HEAD at write:** `914687d` · **Tree:** wave 21 committing, then
pushing. CI was green on `914687d` (run 35284847036).

**Defect first, and it undercuts three waves:** the batch loop had never produced a draft.
`run_pipeline(proceed_video=False)` always returns aborted with reason "proceed_video=False"
(recorded as `drafted`); `batch_generation.generate_draft` treated any abort as failure. Its tests
mocked a result that was never aborted. The first real `ops overnight` saved 0/3; after #779, 3/3
(runs 88-90). **When you mock `run_pipeline`, return what it really returns.**

**Operator state.** Nightly drafts are installed (`ContentMachine\OvernightDrafts`, 05:00 daily,
`ops overnight --count 3`). Three drafts wait in `ops batch-review` for a human yes. Run 77
(`acu0Ekz-G5k`) is **still on YouTube**, unlisted - the operator thought it was deleted.

**Shipped.** #779 above · #771 `CAPTION_ALIGN_BACKEND` defaults to `faster_whisper` (tiny, the
bench winner - I briefly steered the operator to base on a wrong claim and corrected it), aligned
words written to `<audio>.words.json`; the suite pins `none` in `tests/__init__.py` · #780
`detect_studio_deleted(report=)` so "none" no longer hides an unreachable API. Filed #781 (one
YouTube read timeout drops the signal for the run; the breaker notes in `apis/CLAUDE.md` apply).

Suite **3,286 -> 3,295**; mypy **139**; ruff clean; `data/` untouched by tests; mutate-gates
45/45. Backlog **323 open / 693 done**, highest **#781**. Next: operator review of 88-90, then
**#781 · #601 · #600 · #739**.

**Cursor:** four caption tests pinned "unset = aligner off"; unset now means on and `none` is the
switch. Any new test touching captions inherits `CAPTION_ALIGN_BACKEND=none` from the suite.

## Slot — Cursor

**Written:** 2026-09-13 · **HEAD at write:** `2421e15` · **Tree:** wave 15 committing.

- **Defect first:** Wikipedia still queries `GTA` token-joins, not
  `Grand_Theft_Auto_VI` (#749). Heuristic title/script cannot catch a wrong actor
  who is named in the script (#345). The forced-overage publish test was green on
  unmodified code because nothing fed the cap yet; it guards the feeder.
- **Shipped #534 #748 #746 #747 #738.** Title keeps an angle phrase. Title/script
  check falls back to a real verdict. Wiki no longer invents `Gta`/`Goy`.
  Autocomplete 400 is skip-with-reason. Publish list reads persisted
  `tts_char_count`.
- Next five: **#739 · #730 · #345 · #543 · #732**.
- Suite **3,123 -> 3,131**; mypy **139**; ruff clean; backlog **327 open / 658 done**,
  highest **#749**.

