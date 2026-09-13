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

**Written:** 2026-09-13 · **HEAD at write:** `608636d` · **Tree:** wave 11 + docs,
committing right after this slot, then **pushing**; that CI run is the proof for #729
and was not known when this was written.

**Correction to my last slot, defect first.** Wave 10's CI went green (run
34741028834), but the green hid **#729: all 23 widget tests skipped** as "PySide6 extra
not installed" although the wheel installed. Ten files swallowed the real import error,
and `ci.yml` claimed "23 ran, 0 skipped". Fixed with `tests/qt_support.requires_qt`
(never skips under `CI=true`) plus the GL/EGL/xkb apt packages. **Cursor: use
`@requires_qt` for any new Qt test, never a bare `skipUnless`.**

**Second correction: wave 10's "no false TOP" was wrong.** On 50 labelled real stock
clips the detector moved captions on 2 with no overlay. Operator call:
**`CAPTION_AUTO_PLACE` is default off again.** Threshold 0.25 -> 0.18 finds 22 -> 26 of
30 real 2K score bars with no new false TOP. Open: **#730** (stock false positives),
**#731** (4 misses).

- **#636:** traces scrub secrets by value and URL param; `ops trace-secrets-scan`: 28
  traces, 0 hits.
- **#639:** `ops env-lint`: 326 read / 273 documented / 73 undocumented, frozen in
  `config/env_lint_baseline.json`. **A new env key you read must go in `.env.example`,
  or a test fails.**
- **#631:** core coverage prints in the CI log only; nobody has read it yet.
- Found by running it: `ops caption-anchor` printed typed thresholds; now read live.

Audit: 23 of 26 new tests observed failing first (3 pass by design); all 9 in-memory
breaks went red. Suite **3,043 -> 3,069**, 0 failures, 6 skipped; mypy **139**; ruff
clean; `data/` untouched. Backlog **329 open / 639 done**, highest **#732**. Next five:
**#730 · #731 · CI coverage table · #630 · #640**. Detail:
[planning_log.md](planning_log.md) 2026-09-13 wave 11.

## Slot — Cursor

**Written:** 2026-09-09 · **HEAD at write:** `d1776a0` · **Tree:** this wave committing.

- **Defect first:** #715 comment-out guard stayed green (`# concurrency:` still matched). #580 `ops free-cost` re-estimated `$0.1725` on a persisted `$0` last-run. PowerShell empty `OBSIDIAN_VAULT_PATH` unsets; dotenv reloaded the operator vault (digest note written, then deleted).
- **Shipped:** #714 #715 #584 #572 #580 #595 #452 #362 #364 #336 #605 #599 #437 #713 #415. Projected TTS at Proceed?. Rollback dry-run never builds a YouTube client. Busy bottom -> ASS Alignment 8. CI installs ffmpeg.
- **Fail-first:** 13 FAIL + 18 ERROR on unmodified d1776a0 (34 ran). #715 delete-block went red after the comment-strip. Suite **2,927 -> 2,962** (4 skipped); mypy **139**; `data/` untouched.
- **Not this commit:** #684 · #158 · #673 · live unlist. Filed **#716** (push+PR still two refs) · **#717** (chroma is not a face). Next: **#684 · #717 · #407 · #590 · #378**. Backlog **335 open / 618 done**, highest **#717**.



