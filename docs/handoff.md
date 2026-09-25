# Handoff — the mailbox

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-09-25

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

**Written:** 2026-09-20 · **HEAD at write:** `096c13b` (wave 30 committing now) ·
**Tree:** clean but for the three footage folders, which stay yours.

**Defects first:**
- **#824 the report card is anti-predictive: grade vs engaged-rate r=-0.32, n=12.** Worse
  than composite's -0.15 (#819), same twelve videos. #19 graded 79.4 -> p4; #17 graded 69.5
  -> p71. **Both scores the pipeline ranks on are anti-correlated with engagement.** At n=12
  this is not significant - filed explicitly as *do not retune the rubric on it*.
- **#825 `--force` was read by four ops verbs and reachable by none.** Never declared, *and*
  `main` set `args.force = False` after `parse_args`. `backfill-cost`, `competitor-sync` and
  `daily-sync` have therefore never actually been force-run. Fixed, with a ratchet.
- **#826 per-claim types exist only from run 76 on**; 27 verified runs store a flat list, so
  76 of 84 unsupported claims cannot be told apart by bar. Unlike #818 this is **not**
  backfillable - #823 does not re-run the verifier.
- **Self-inflicted, caught in audit:** after applying #823 the snapshot line read "today's
  rubric reproduces every one" - tautological, since the backfill computed those with today's
  rubric. Rows now stamped `grade_backfilled`.

**Two items closed with no behaviour change, on purpose.** **#822** - the hedged-rumor escape
has fired **0 times** in 37 verified runs, so neither the gate nor the hedge penalty moved; the
waiver is recorded instead, re-decide at n>=10. **#739** - measured at last (gameplay 147 clips,
ALWAYS **2**, intermittent 90, median 0.25; stock 52, ALWAYS 0, ever 6): both premises fail and
the source rule **does not ship**. It also explains #730's false moves. **#817** closed because
its filed text was wrong, not its code.

**Heads-up:** I ran `ops backfill-quality --apply` on the operator's explicit call - **87 tapin
rows rewritten**, measured runs 3 -> 12. Re-runnable with `--force`. `ops footage --persistence`
is new and slow (8 decodes/clip).

Suite **3,462 -> 3,487**; mypy **139**; ruff clean; `data/` untouched. Backlog **325 open / 734
done**, highest **#826**. Next five: **#826 · #821 · #820 · #824 · #819**.

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
