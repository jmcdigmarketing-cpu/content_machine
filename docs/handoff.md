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

**Written:** 2026-09-09 · **HEAD at write:** `8c8a142` · **Tree:** this wave committing.

- **Defect first:** #549 was persisted and unread (`needs_review=False`). #431 extras `0:20`/`0:40` is also equal-span. #711 CI push was main/master-only so postgres never started here. #708 `compile_kit("tapin").missing` named logo.svg.
- **Shipped:** #710 #712 #431 #549 #414 #420 #498 #711 #708 #562 #569 #568 #430 #440 #705. Title vs script prints at Proceed?. Vanished claims file medium; rewording does not. TapIn octagon SVGs. Sticky 24h/7d snapshots.
- **Fail-first:** 16 ERROR/FAIL on unmodified b9f1354 before the matching change. Chapter guard: ignored timings -> `0:20`/`0:40`. Suite **2,894 -> 2,919** (4 skipped); mypy **139**; `data/` untouched.
- **Not this commit:** #21 (already shipped) · #158 · #673 · #684 · #437. Next: **#713 · #684 · #158 · #415 · #437**. Backlog **346 open / 603 done**, highest **#713**.



