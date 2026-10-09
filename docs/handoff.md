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

**Written:** 2026-10-09 · **HEAD at write:** `1b43610` + the wave 67 commit (`git log -1`) ·
**Tree:** clean after the commit.

**Read before editing:** angles are scored on the seed's signals now (`pipeline._seed_score_variant`;
`VARIANT_SIGNAL_RESCORE=true` is the old per-angle fetch); stale angles drop in
`topic_variants._clean_angle_lines` via `core/facts/event_dates`; chapter titles are chosen by
`angle_chapters.choose_chapter_title` and stored with `title_source`/`title_note`; the trim uses
`content_engine._trim_to_cap`. The parent hold has one rule, `go_public.override_held` - patch it
there. mypy **121**.

**Cursor, in your files (wave 67):** `core/chapter_shorts.py` gained `SHORTS_MIN_SECONDS = 20`
(your A5 figure) and its verdict text - nothing else. A5's remaining work is unchanged. B2's engine
half is `core.facts.claim_confirm` (the brief says so).

**Defects first:**
- The ESPN fixture is still the documented shape, not a live capture (#1022 / record-payloads).
- Run 119's published description still says "UFC 305 ..." - fixed in new runs, not old ones
  (#1066); its claims can now be confirmed with `ops verify-claim`.
- `docs/decisions.md` is at its 800-line ceiling; decisions go in planning_log.

**Shipped:** wave 67 - #1008 #1009 #1010 #1013 #1014 (+ the title's past-year check, the corpus
runner's `select: 0`). Filed #1080-#1083. Highest #1083. Next:
**#1007 · #1006 · #1011 · #1033 · #1060**.

## Slot — Cursor

**Written:** 2026-09-20 · **HEAD at write:** `096c13b` · **Tree:** footage intake only;
do not commit Claude's uncommitted calibration/clip-band files.

**Defects first:**
- **`footage-add` still overwrites the folder `license` string.** Fortnite (32 owned)
  and Marvel Rivals (16 owned) would have been labelled third-party. Mixed yaml
  rewritten after import (GTA V pattern). Same footgun on the next mixed folder.
- **Pinned `yt-dlp==2026.6.9` 403s YouTube DASH.** Probe worked; download needed a
  temp 2026.8.19 extractor. Pin unchanged.
- **Twitch, Football, AI still empty.** This batch did not fill them.

**Intake (7/7 gameplay, muted 1080p H.264, not committed):**
Forza Horizon 5 `flUiLwMaiOU` CC-BY; Fortnite `Am18G4IDNnM` CC-BY mixed;
Steep `EnGiQrWBrko` CC-BY; Mario Kart 8 `npz4T7sznog` title-claims reuse;
CSGO `QnA_YwbRZ2k`+`OikR-0gh8QE` title-claims reuse; Marvel Rivals
`stsnPWyDSLE` CC-BY mixed. `ops footage --channel tapin`: Marvel Rivals 17,
Fortnite 33 on disk. New folders are umbrella-only.

**Operator paste:**
```
Footage per playlist niche ...
  Marvel Rivals    Marvel Rivals (17 clips, ...)
  Twitch           NO FOOTAGE
  Football         NO FOOTAGE
  AI Development   NO FOOTAGE
```
