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

**Written:** 2026-09-26 · **HEAD at write:** `ea721f7` + this wave's commit on `main` (`git log -2`)
· **Tree:** clean after the commit; `data/` untouched.

**Defects first:**
- **The operator's PC never received wave 33.** It is on `codex/p0-test-integrity`, a local-only
  branch with no upstream: `git pull` fetched `main` and merged nothing, so `ops calibration`
  and the v5 backfill ran on old code. Fix on the PC: `git status`; `git log --oneline
  origin/main..HEAD` (if it lists commits, `git push -u origin codex/p0-test-integrity` first);
  `git switch main`; `git pull origin main`; then re-run `ops backfill-quality --channel tapin
  --force --apply`.
- **Auto-research (#848) is on by default and fetches web pages.** The suite pins it off in
  `tests/__init__.py`; any new test that drives `run_pipeline` inherits that.
- **The two football feeds are unverified here** (the container cannot reach them); `ops feeds`.

**Shipped:** #859 football feeds · #852 name-shaped queries · #850 brief sees key facts ·
#836 `ops backfill-angles` · #848 auto-research. Decisions §35.

**Operator after switching:** `ops backfill-quality --channel tapin --force --apply`,
`ops backfill-angles --channel tapin --apply`, `ops calibration`, `ops feeds`, then one real run
and read the new "Auto-research:" line.

Suite **3,628**, identical in default/reverse/shuffle (8 environmental here); mypy **129**;
backlog **281 numbered open**, highest **#863**. Next five: **#849 · #863 · #861 · #839 · #830**.

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
