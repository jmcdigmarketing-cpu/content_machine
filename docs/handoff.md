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

**Written:** 2026-09-27 · **HEAD at write:** `c0ed1a0` + this wave's commit on `main` (`git log -2`)
· **Tree:** clean after the commit; `data/` untouched.

**Read before editing:** `py -m scripts.ops regressions <file>` (43 cases). A voice is resolved
through `core/tts.resolve_tts_config` inside a `voice_context` - never pick one per synth call.
Debate tags are stripped in `generate_content_package`; anything reading the script after that
sees clean text. A render test must patch `record_render_assets`, `update_content_run_media` and
set `THUMBNAIL_MODE=off`, or it writes `data/assets.json` and thumbnails (it did, once, this wave).

**Defects first:**
- **Nothing here was heard (#889).** No ElevenLabs key or ffmpeg in the container: the tests
  cover the segment plan, the voices asked for, word timings and stripped tags. Operator: one
  debate run and one quotes run on the PC.
- **#888** the run dossier shows the voices only after the overnight rewrite.
- **#887** "Use these? [Enter=all]" (vault review path) is #878's sibling, left as an operator call.
- **#876** game names outside the franchise list read neutral. **#879** "UFC week 2" named no series.
- **Use `python -m ruff`, never bare `ruff`, here:** bare is 0.15.8, CI pins 0.8.4.

**Shipped:** #883 · #884 · #885 · #886 · #877 · #878. The operator's steps from wave 38 are done
(re-auth, recategorize 9 updated, run 99 public, Doctor 14 of 14).

Suite **3,755**, identical in default/reverse/shuffle (8 environmental here); mypy **129**;
backlog **284 numbered open**, highest **#889**. Next five: **#849 · #879 · #876 · #855 · #870**.

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
