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

**Written:** 2026-09-12 · **HEAD at write:** `7c57b82` · **Tree:** wave 9 + docs,
committing right after this slot.

**Defect first: the suite was red when I arrived.** `tests/test_next15_wave2.py:282`
pinned `now` to 2026-09-09 while `get_competitor_prompt_block` reads the real clock.
It was green on 09-10 when I reported it and red on 09-12. Fixed; **#725** files the
other 64 pinned dates in 12 test files. **Cursor: when you pin a date, check that the
code under test actually takes `now`.**

Shipped the recommended five: **#716 · #723 · #722 · #721 · #158 (core slice)**.
**#718** is closed by its own stated condition.

- **`CAPTION_AUTO_PLACE` now defaults ON** (operator call). **#721** requires #717's
  step AND a band that stays still while the footage above moves: per-column static
  excess >= 0.25. Real clips: horizons <= +0.05, overlays >= +0.36. Stills,
  locked-off shots and clips under 1s never move. This changes finished karaoke
  renders; it is disclosed in the commit. Unmeasured on a genuine burned-in overlay:
  **#726**.
- **Your caption tests changed shape, not strength.** A still PNG is no longer
  evidence of an overlay, so the flag tests fix the detector's verdict and assert
  both flag states. The real overlay -> top proof is an encoded clip in
  `tests/test_wave9.py`. For the spatial gate alone, use `overlay_reading(p)["step"]`.
- **#722**: the shipped typed YouTube date had already rotted into CLOSED.
  Recurring rows are now `derive: youtube|apify`.
- **#158 core**: `ops cost-tower`. Running it caught two defects of mine (a real $0
  printed as `-`; the daily reset shown as NEAR), both fixed test-first. **#724**:
  ElevenLabs chars still read 0 when the store is unreadable.
- **#716**: push and PR share one CI group, so the later run cancels the other.

Audit: 24 of 26 new tests observed failing first (the other 2 guard against
over-suppression). Each of 7 fixes was broken in memory and every guard went red.
Suite **2,996 -> 3,022**, 0 failures, 5 skipped; mypy **139**; ruff clean; `data/`
untouched. Backlog **334 open / 628 done**, highest **#726**. Next five: **#724 ·
#725 · #726 · #158 panel · #719/#720**. Detail: [planning_log.md](planning_log.md)
2026-09-12.

## Slot — Cursor

**Written:** 2026-09-09 · **HEAD at write:** `d1776a0` · **Tree:** this wave committing.

- **Defect first:** #715 comment-out guard stayed green (`# concurrency:` still matched). #580 `ops free-cost` re-estimated `$0.1725` on a persisted `$0` last-run. PowerShell empty `OBSIDIAN_VAULT_PATH` unsets; dotenv reloaded the operator vault (digest note written, then deleted).
- **Shipped:** #714 #715 #584 #572 #580 #595 #452 #362 #364 #336 #605 #599 #437 #713 #415. Projected TTS at Proceed?. Rollback dry-run never builds a YouTube client. Busy bottom -> ASS Alignment 8. CI installs ffmpeg.
- **Fail-first:** 13 FAIL + 18 ERROR on unmodified d1776a0 (34 ran). #715 delete-block went red after the comment-strip. Suite **2,927 -> 2,962** (4 skipped); mypy **139**; `data/` untouched.
- **Not this commit:** #684 · #158 · #673 · live unlist. Filed **#716** (push+PR still two refs) · **#717** (chroma is not a face). Next: **#684 · #717 · #407 · #590 · #378**. Backlog **335 open / 618 done**, highest **#717**.



