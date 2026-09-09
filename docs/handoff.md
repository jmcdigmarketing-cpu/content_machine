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

**Written:** 2026-09-09 · **HEAD at write:** `b9f1354` · **Tree:** #153 removal +
docs, committing right after this slot.

**Cursor — #153 is retired, and it is not a criticism of the build.** Operator's
call, verbatim: *"i dont need to see the caption timing, i dont want to do that
manually."* The timeline was a manual step by construction — drag keyframes,
write `<audio>.captions.json`, next burn reads it — and that is the step they do
not want. **Do not rebuild it.** #713 carries the real problem: a cue that would
cover a face or a score bug should move itself, automatically, with no operator
in the loop.

**Removal was lossless, and measured before I touched anything.** I hashed the
karaoke ASS for a tapin sample before and after: `4ddd7116…` both times. With no
edits sidecar on disk `apply_caption_edits` was a pass-through, so on every real
render the feature had been doing nothing. Captions still come from real
`.words.json` timings, which predates #153 and is untouched.

**Gone:** `core/caption_timeline.py` · `desktop/captions.py` · its tests ·
the ops captions verb · the ops caption-timeline verb · `py -m desktop --captions` · the
`apply_caption_edits` hook in `video/subtitles.py` · the `margins` parameter on
`build_ass_karaoke`, which existed only to carry manual overrides.

**Heads-up, and I did not act on it.** Partway through the removal the three
deleted files reappeared in the working tree, **byte-identical to HEAD**, with the
index deletions still staged and no new commit or reflog entry. That reads as an
editor restoring open buffers rather than you authoring anything, and a second
delete stuck. If it was you and you want any of it back, it is all in `b9f1354` —
say so rather than restoring, since the operator's decision is what removed it.

Earlier today I also audited your `c43c427` and committed your uncommitted tree —
see the previous entry in [planning_log.md](planning_log.md) for #710/#711/#712.

Suite **2,907 -> 2,894** (13 tests removed with the feature); ruff + format clean;
mypy **139**; `data/` untouched. Backlog **361** open / **588** done, highest
**#713**. Next five: **#705 · #708 · #711 · #431 · #21**.

## Slot — Cursor

**Written:** 2026-09-09 · **HEAD at write:** `f8c39b2` · **Tree:** this wave committing; #153 still uncommitted.

- **Defect first:** #704 could not run until #709 — `payload_json` is Text, Postgres `->>` is json-only (`operator does not exist: text ->> unknown`). Without `skip_locked`, the lock test blocked 2.16s. Wave 5 correction scans would skip after the first stamp; they now pass a per-vault `stamp_path`.
- **Shipped:** #706 keys (J→7000) · #702 structured `source_urls` (`KeyError` on f8c39b2) · #703 `toast_is_due` stamp · #707 QVideoSink duration 2150ms · #704 SKIP LOCKED on `content_machine_test` (0.3s) · #709 jsonb cast.
- **Fail-first:** watched each named failure before restore. Qt tests ran here (system PySide6). CI postgres service is new on this commit. Suite **2,870 -> 2,883**; mypy **139** on committed packages (local tree is 143 from uncommitted extras). `data/` untouched.
- **Not this commit:** #153 (still open in backlog until its own commit), technical QC, chapters, title-script. Next: **#705 · #708 · #431 · #549 · #21**. Backlog **358 open / 587 done**.



