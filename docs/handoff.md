# Handoff — the mailbox

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-10-03

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

**Written:** 2026-10-03 · **HEAD at write:** `79697ee` + the wave 53 commit (`git log -1`)
· **Tree:** clean after the commit.

**Read before editing:** the suite sets `CONTENT_SKIP_DOTENV=1` and blanks every variable
ending `_KEY/_KEYS/_TOKEN/_SECRET/_PASSWORD/_BOT` (`tests/__init__.blank_secrets`) - a test
that needs a key sets it with `patch.dict`. A search seed with no names comes from
`topic_scorer.domain_phrases`; angles past the scoring deadline are scored on the seed
(`meta["unscored_on_seed"]`). `register_signals.base_pool_seconds()` feeds the trace's
`signal_seconds`. mypy baseline **122**.

**Defects first:**
- #930: 9 failures only the operator's PC showed - seven tests reached the network with the
  real keys from `.env`; two harness checks assumed Linux / no colour. Fixed, reproduced here.
- #931-#933 from the soccer run: first-clause seed "State of the sport...", five angles
  dropped silently at the deadline, Headroom printed three times.
- This container lost its dev extras (fastapi, langdetect) mid-session; reinstalled.
- Carried: no emoji render seen (#914).

**Shipped:** #930-#933 #929 #591 #573 #586; #587 closed (no per-call retries exist). Suite
**4,343**, 0 network attempts, `data/` clean; backlog **238 numbered open**, highest #938.
Next five (operator's tracking picks): **#934 · #935 · #936 · #937 · #114**.

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
