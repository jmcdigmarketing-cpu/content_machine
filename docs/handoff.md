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

**Written:** 2026-09-13 · **HEAD at write:** `08700c1` · **Tree:** wave 10 + docs,
committing right after this slot, then **pushing** (waves 8-10 reach CI for the
first time; result not known when this was written).

**Defect first.** `core/quota_state.py:51-65` swallowed read errors, so a corrupt
ledger read 0 everywhere and the tray chip (`core/win_notify.py:331`) showed the
whole ElevenLabs budget as leftover (#724). And **#721's detector measured pixels the
render crops away**: the render centre-crops to 9:16, so an overlay in a 16:9 clip's
margins could move captions (#726, fixed with `caption_place.render_crop`).

Shipped the recommended five: **#719 · #720 · #724 · #725 · #726 · #158 (panel, closed)**.

- **Real footage, at last:** 32 NBA 2K clips in `video/backgrounds/gaming/sports/2k26`
  have genuine score bars. With the crop: 22 TOP, 6 missed, 4 bottom; 12 production
  hybrids unchanged. Four TOP verdicts confirmed by eye; **no false TOP**. The 6 misses
  are real bars (checked by eye) and are **#727**. `CAPTION_AUTO_PLACE` stays on.
- **#725:** `ops clock-ahead --days 365` - no test changes result a year ahead. It
  runs two full suites (~2 min). **Cursor: run it once when you pin a date.**
- **#158:** `ops cost-panel` / `py -m desktop --cost`; UNKNOWN renders `?`, never `0`.
- **#719** ticked on CI run 34416158840's log; **#720** guarded (broken in memory, since
  its fix predates the test).

Audit: 18 of 21 new tests observed failing first (the other 3 are a pre-existing fix's
guard and two over-correction guards). All 7 in-memory breaks went red. Suite
**3,022 -> 3,043**, 0 failures, 5 skipped; mypy **139**; ruff clean; `data/` untouched.
Backlog **330 open / 634 done**, highest **#728**. Next five: **#727 · #631 · #639 ·
#636 · #728**. Detail: [planning_log.md](planning_log.md) 2026-09-12 wave 10.

## Slot — Cursor

**Written:** 2026-09-09 · **HEAD at write:** `d1776a0` · **Tree:** this wave committing.

- **Defect first:** #715 comment-out guard stayed green (`# concurrency:` still matched). #580 `ops free-cost` re-estimated `$0.1725` on a persisted `$0` last-run. PowerShell empty `OBSIDIAN_VAULT_PATH` unsets; dotenv reloaded the operator vault (digest note written, then deleted).
- **Shipped:** #714 #715 #584 #572 #580 #595 #452 #362 #364 #336 #605 #599 #437 #713 #415. Projected TTS at Proceed?. Rollback dry-run never builds a YouTube client. Busy bottom -> ASS Alignment 8. CI installs ffmpeg.
- **Fail-first:** 13 FAIL + 18 ERROR on unmodified d1776a0 (34 ran). #715 delete-block went red after the comment-strip. Suite **2,927 -> 2,962** (4 skipped); mypy **139**; `data/` untouched.
- **Not this commit:** #684 · #158 · #673 · live unlist. Filed **#716** (push+PR still two refs) · **#717** (chroma is not a face). Next: **#684 · #717 · #407 · #590 · #378**. Backlog **335 open / 618 done**, highest **#717**.



