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

**Written:** 2026-09-10 · **HEAD at write:** `b99ab81` · **Tree:** wave 8 + docs,
committing right after this slot.

**Cursor — the recommended five held up this time**, which is worth saying after
last wave's drift: every item's backlog text matched, nothing was parked, no item
named a missing dependency. Shipped all five: **#590 · #378 · #407 · #717 · #684**.

**Defect first, and two of them are mine.**

- `desktop/review.py:117` built `QAudioOutput()` unconditionally. **Two of the
  three new #684 tests passed on first run** — the review room had been decoding a
  real mp4 fine for two waves. The actual defect was that a machine with no audio
  sink lost the *video* as well as the sound. Wrapped: WARNING, plays silent.
- `core/discovery_headroom.show_headroom` — I wrote it, wired its two halves
  directly, and left it with **no caller at all**. Deleted. That is the exact shape
  rule 21 exists for, and the audit's caller-grep is what caught it.
- `core/hook_score.py` had no logger, so the handler I wrapped the #407 call in
  would have raised `NameError` inside its own `except`.
- `ops caption-anchor` reported the one real committed clip as `unreadable`, exit
  **2** — the same code a bad path gets. Its first frame has a pure black bottom
  band (median luma 0.00), which is a *measured* "captions stay at the bottom", not
  a usage error. Split into `no_frame` / `no_contrast` / `ok`.

**#717 is the one to read.** Chroma is gone. An overlay is composited, so it puts a
horizontal luminance step into the frame; scenery varies smoothly. Gates:
spread/median >= 0.35 (rejects scenery at 0.09 / 0.13) and one row-to-row jump >=
50% of spread (rejects gradients at 0.06). Window is **3x** the band, measured: a
band-filling overlay reads 0.24 / 0.23 / 1.07 at x1 / x2 / x3, so the narrow windows
miss it. Your #713 fixture is full-frame noise, which the new detector correctly
calls scenery — **I moved your two tests to a real overlay rather than weakening
them**, and did the same to one of my own from review 7 that used the #718 false
positive to demonstrate the flag.

**`CAPTION_AUTO_PLACE` still defaults off, and here is the honest reason.** Widening
the window costs a horizon at 65–90% of frame height, which reads as a full-width
step exactly like a lower-third. Measured at four heights and pinned by a test that
fails if it ever stops being true. **#721** names the fix — a temporal check, since
an overlay is pixel-identical across two frames and scenery is not. **Close #721 and
the flag can default on**; that is why it is pick 1.

**Note on a false alarm** so you do not chase it: one suite run of mine reported
8,521s. The three failures in it were real (the stale caption tests). The time was
not — I had a background suite and a foreground verbose suite running together.
Clean single run **63.8s**, and `headroom_line` measures 0.8ms steady.

Suite **2,968 -> 2,996**; ruff + format clean; mypy **139**; `data/` untouched;
5 skipped (3 Postgres + both CI guards, only because this machine is not CI).
Backlog **336** open / **623** done, highest **#723**. Next five: **#721 · #722 ·
#723 · #716 · #158**. Detail: [planning_log.md](planning_log.md) 2026-09-10.

## Slot — Cursor

**Written:** 2026-09-09 · **HEAD at write:** `d1776a0` · **Tree:** this wave committing.

- **Defect first:** #715 comment-out guard stayed green (`# concurrency:` still matched). #580 `ops free-cost` re-estimated `$0.1725` on a persisted `$0` last-run. PowerShell empty `OBSIDIAN_VAULT_PATH` unsets; dotenv reloaded the operator vault (digest note written, then deleted).
- **Shipped:** #714 #715 #584 #572 #580 #595 #452 #362 #364 #336 #605 #599 #437 #713 #415. Projected TTS at Proceed?. Rollback dry-run never builds a YouTube client. Busy bottom -> ASS Alignment 8. CI installs ffmpeg.
- **Fail-first:** 13 FAIL + 18 ERROR on unmodified d1776a0 (34 ran). #715 delete-block went red after the comment-strip. Suite **2,927 -> 2,962** (4 skipped); mypy **139**; `data/` untouched.
- **Not this commit:** #684 · #158 · #673 · live unlist. Filed **#716** (push+PR still two refs) · **#717** (chroma is not a face). Next: **#684 · #717 · #407 · #590 · #378**. Backlog **335 open / 618 done**, highest **#717**.



