# Handoff — the mailbox

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-09-26

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

**Written:** 2026-09-26 · **HEAD at write:** the single wave-32 commit on `main` after
`cdb01d8` (`git log -1`) · **Tree:** clean; `data/` untouched.

**Defects first:**
- **CI on `main` was red at `cdb01d8` and it was mine.** Wave 31's commit *subject* carried a
  U+2192 arrow; `core/agent_comms.render` reads `git log -1` and the cp1252 guard failed in both
  unit-test legs (run 159). `render` is now console-safe by construction (#838); the hook still
  accepts non-ASCII subjects (#839, filed). Keep subjects ASCII.
- **`angle_scores` had 0 rows because nothing persisted them** - `_finalize_run` dropped what
  `run_discovery` computed (#819). Three waves called that "no population". Fixed; the tie is
  unchanged until `angle_correlation` is positive at n>=5.
- **Queued signals started after the discovery deadline** (#820) - `shutdown` had no
  `cancel_futures`. Paid POSTs are now refused after the deadline; free stragglers still cache.
- The mypy ratchet caught its first real error (a `no-redef` of mine) one wave after going
  blocking. It works.

**Shipped:** #826 claim-type coverage line · #820 `apis/run_deadline` · #824 per-component r +
`n_for_significance` (|r|=0.32 needs n>=36; rubric untouched) · #821/#819 measurement + lines
(open, waiting on your `py -m scripts.ops calibration` numbers) · #835 #837 #838 fixed on the way.

**Operator:** run `py -m scripts.ops calibration` on the archive and paste the component,
recurrence and claim-type lines into the next planning entry - this box has no archive.

Suite **3,550**, identical in default/reverse/shuffle (8 environmental here); mypy **129**;
ruff clean; backlog **329 open / 743 done**, highest **#839**. Next five:
**#836 · #839 · #830 · #832 · #831**.

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
