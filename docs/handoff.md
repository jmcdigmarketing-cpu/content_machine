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

**Written:** 2026-09-19 · **HEAD at write:** `e7e9521` · **Tree:** wave 24 committing, then
pushing. CI was green on `e7e9521` (run 35455523599).

**Defects first - two found in this wave's own debug sweep:**
- **#797** `data/tmp/hybrid_backgrounds` held 60 composed backgrounds / **4.2 GB**, oldest
  2026-06-04. Nothing had ever swept them; `_compose` now prunes past 3 days (2,636 MB freed).
- **#798** with 3-8 s shots, one mid-shot brightness sample let near-black shots back in
  (5% -> 9% of frames). Shots over 4 s are read at a third and two thirds, scored on the darker.
- **#788 is narrowed, not done.** The band reading first called a bright sky a plate (0.233, the
  cap, on 8/8 GTA clips); requiring a sharp edge fixed that and also lost the 2K score bug, which
  is partial-width. Measurements only ever *add* crop - GTA's mission text is white-on-nothing,
  not a luminance step, so `BACKGROUND_CROP_BOTTOM` stays the floor.

**Operator ask, shipped:** #792 shots 3-8 s, random, never within a second of the last one
(`BACKGROUND_CUT_MIN`/`MAX`; wave 22's `BACKGROUND_CUT_SECONDS` reads as the midpoint) - the wave
22 guards moved with the reversal instead of being deleted. #796 parallel shot encodes
(`BACKGROUND_SHOT_WORKERS=4`). #793 `footage-add --path <folder>`. #795 `preview-render
--seconds N`. `ops footage --apply` measured all 141 clips and stores bands in the clip index.

Operator calls this session: caption height is fine (so #730/#731/#739 are not next), no stock
footage for the empty niches, footage order does not matter.

Suite **3,351 -> 3,381**; mypy **139**; ruff clean; mutate-gates 45/45; `data/` untouched by
tests. Backlog **322 open / 710 done**, highest **#798**. Next: the operator's files (#786),
#788's partial-width half, #611.

**Cursor:** `cut_points` takes `span=`/`rng=` now and is random by default - pin both in a test
rather than asserting a shot count. `build_shot_command` reads the clip index through
`assets/clip_bands.crop_for_clip`, so a shot's crop depends on the measured clip.

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

