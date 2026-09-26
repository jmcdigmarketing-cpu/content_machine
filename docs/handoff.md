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

**Written:** 2026-09-26 · **HEAD at write:** `1a7fdc2` + this docs commit on `main` (`git log -3`)
· **Tree:** clean after the commit; `data/` untouched.

**Defects first:**
- **CI run 162 was red, and it was mine**: a backlog line added *after* the final suite run
  named an unbuilt `ops` verb. Fixed in `1a7fdc2`, verified in a clean worktree; CI run 164 green, real-ffmpeg test included. Run every doc
  edit before the suite, not just this slot.
- **Every multi-sentence ElevenLabs render since 09-20 was voiced twice** (#840): the TTS join
  wrote relative paths into the ffmpeg concat list. Fixed; the real-ffmpeg test runs in CI only.
- **Football ran as gaming** (#841): a keyword-less topic took the channel's domain. Gating,
  brief, templates and feeds now use the topic's own domain.
- **Old `_operator_facts` notes hold scraped text at operator tier.** Not migrated (your vault);
  they no longer pin. #857 is the dry-run re-tier.

**Shipped:** #840-#847 (TTS, domain, soccer, signal hygiene, fact intake, card v5) and the docs:
[vault.md](vault.md), [tooling_review_2026-09-26.md](tooling_review_2026-09-26.md), master_plan
M4.5-M4.7 (sample schedule, logic-first retunes), facts room #860, seven retired desktop items
closed, API/env drift fixed. Decisions §34.

**Operator:** `git pull`; `py -m scripts.ops calibration`; `py -m scripts.ops backfill-quality
--channel tapin --force` then `--apply` (v5 re-stamp); next render should show one TTS charge.
`positioning.md` contradicts the private-tool rule - your call.

Suite **3,601**, identical in default/reverse/shuffle (8 environmental here); mypy **129**;
backlog **283 numbered open**, highest **#860**. Next five: **#848 · #852 · #859 · #850 · #836**.

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
