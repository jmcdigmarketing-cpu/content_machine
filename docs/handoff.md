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

**Written:** 2026-10-09 · **HEAD at write:** `7f31d49` + the wave 66 commit (`git log -1`) ·
**Tree:** clean after the commit.

**Read before editing:** angle 1 is the operator's own idea (`apis.topic_variants.idea_angle`,
`main._typed_idea`, `run_pipeline(own_idea=, own_topic=)`); `ANGLE_PLAN` is a calm intent;
`apis.topic_tokens` now holds `COMMON_CAPITALISED`, `name_phrases`, `subject_terms`,
`subject_markers`, `names_any` - use them, not a private list. Two default-on LLM passes
(`HOOK_REGEN_ENABLED`, `KEEP_TO_IDEA`) are pinned off in `tests/__init__.py`. TapIn is
`background_mode: local_first`; both channels speak at 1.05. mypy **121**.

**Defects first:**
- The ESPN fixture (`tests/fixtures/signal_payloads/live_scores.json`) is written from ESPN's
  documented shape - this session's network policy blocks site.api.espn.com. Refresh it with
  `record-payloads` on the PC; no injuries yet (#1022).
- Run 119's description still carries the "UFC 305" chapter title (#1009). Its record line is
  right after all (a decision win) - #1011 is reworded.
- `docs/decisions.md` is at its 800-line ceiling: the `local_first` decision is in planning_log
  2026-10-09 instead.

**Shipped:** wave 66 - #1016 #1001 #1002 #1003 #1004 #1005 #1012 #1017 #1018 + #1000 #1019 #1020,
speed 1.05; the next 100 ([optimization_plan_2026-10.md](optimization_plan_2026-10.md)); Cursor's
run ([cursor_brief_2026-10.md](cursor_brief_2026-10.md)). Highest #1079. Next:
**#1008 · #1009 · #1010 · #1013 · #1014**.

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
