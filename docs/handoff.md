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

**Written:** 2026-09-26 · **HEAD at write:** see `git log -1` on `main` after this wave's
push (eleven signed commits from `ca0aed2`; last two are the stage3-honesty fix and this
pass) · **Tree:** clean; `data/` untouched.

**Defects first:**
- **The run-69 order-dependence was misattributed on 09-20.** Cause: `tests/test_ops_doctor._stack()`
  built an `ExitStack` outside a `with`; on any partial install a later `patch()` target failed
  to import and `run_mode._ollama_ready` stayed mocked for the whole process. Fixed + regression
  test. Your full install never showed it — that is why.
- **`ops test --order reverse` found two more leaks on its first run** (file-backed discovery
  cache shared across tests; `_FakeCommunicate.fail` never disarmed). Both closed.
- **My `decisions.md` rewrap broke `test_stage3_honesty`** (it split on `### 4.`). Fixed in the
  last commit — the definitive run caught it, which is the point of the run.
- **Environment traps:** a half-failed `pip install` nearly became the baseline; a stale
  `.mypy_cache` under-reported by 24; two mypy versions differed by 6 — the ratchet runs
  `--no-incremental` on the pinned interpreter mypy for both reasons.

**Shipped (structural, no product change):** #827 process-state registry · #828 order-proof verb
+ CI leg · #829 preflight/inert tests · #833 mypy ratchet (129, blocking) · docs standard finished
(ten renames, two log rollovers, `decisions.md` rewrapped word-for-word, nine stale docs read,
decisions §33 product names, three lint rules). Before→after: [audit_2026-09-26.md](audit_2026-09-26.md).

**Heads-up:** `HANDOFF_SYNOPSIS.md` is now `handoff_synopsis.md` (244 lines; older waves in
`handoff_synopsis_archive.md`); `planning_log.md` rolls over by month. The 8 failures on this box
are environmental (fastapi extra, no ffmpeg) and identical before/after; CI-shaped installs are green.

Suite **3,526**, identical in default/reverse/shuffle; mypy **129** (1.13.0); ruff clean; backlog
**330 open / 737 done**, highest **#834**. Next five unchanged: **#826 · #821 · #820 · #824 · #819**;
structural next: **#831 ruff bump → #834 core/ seams → M3.4 excepts**.

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
