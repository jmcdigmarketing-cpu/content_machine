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

**Written:** 2026-09-29 · **HEAD at write:** `8f3dbb4` + the wave 46 commit (`git log -1`)
· **Tree:** clean after the commit.

**Read before editing:** `core/facts/` holds the eight `fact_*` modules (old names are one-wave
aliases); the `core/vault_*` aliases are gone; new E1 code lives in `core/predictions/`.
`FLAT_CEILING` 228. `prompt_key_facts_result` has a facts-room branch when a run window is
attached (`current_bridge()`); the terminal path is unchanged. The suite pins
`WEB_SEARCH_FALLBACK=false`. Every JSON signal needs a pin and a fixture. mypy **123**; corpus 57.

**Defects first:**
- **The facts room never met a real window** (no display here); its model, the prompt hook and
  the bridge round-trip are tested, the Qt dialog is thin and untested.
- **The contract fixtures are still documented shapes** - `ops record-payloads` could not reach any
  API from this container. Run it on the PC.
- The room reads links one after another (#910). Best-bet picks are not recorded (#909).

**Shipped:** #907 #908 #906 #905 #589 #559 #113 #357 #548 #860 (one commit, operator's choice).
Suite **4,097**, the same 8 environmental failures in default/reverse/shuffle, hygiene clean;
backlog **259 numbered open**, highest #912. Next ten in the roadmap, from **#910 · #909 · #911**.

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
