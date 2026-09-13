# Handoff — the mailbox

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

**Written:** 2026-09-13 · **HEAD at write:** `99708d9` · **Tree:** wave 13 + docs,
committing right after this slot, then **pushing** (operator-approved); that CI result
was not known when this was written. Wave 12's CI (run 34773165720) was green.

**Defect first: `ops blocking` and `/next` reported an invented blocker.** They passed
only a channel id, so the render gate graded an empty dict: "report card F" while tapin's
last rendered run (72) grades A. They now read the real last run (`publish_blockers.
publish_status_sentence`). **Cursor: when a function takes optional context, check every
caller actually passes it.**

**Behaviour change, operator call (decisions §31): authenticity and grounding now BLOCK by
default.** Interactive runs ask; `auto_generate` skips the render unless `--force`.
Publishing refuses a *block* verdict only. `warn` in `.env` still turns either off.

- **#737 was worse than filed:** the wheel lacked `storage.repositories` as well as every
  `config/*.json`. Both ship now; a proof build imports them from the unpacked wheel.
- **#736:** builds run on a staged tree, so a stale egg-info cannot change the sdist.
  The audit's token rule no longer flags `design_tokens.json` (found by the proof build).
- **#730:** 23 of 46 real hybrid backgrounds put captions on a game HUD today, but the
  detector still moves captions on 5 of 71 no-overlay clips, so it stays off. I nearly
  filed an overstated #739 - the sampled frames all came from the gameplay segment, so
  the stock segments are unmeasured; #739 is a measurement, not a rule.

Audit: 12 of 19 new tests observed failing first (7 pass by design, named in the log); all
10 in-memory breaks went red; `ops clock-ahead --days 365` no change; the suite passed with
the new gate defaults. Suite **3,086 -> 3,105**, 0 failures, 6 skipped; mypy **139**; ruff
clean; `data/` untouched. Backlog **329 open / 646 done**, highest **#739**. Next five:
**#739 · #738 · #732 · #627 · #628**. Detail: [planning_log.md](planning_log.md) 2026-09-13
wave 13.

## Slot — Cursor

**Written:** 2026-09-09 · **HEAD at write:** `d1776a0` · **Tree:** this wave committing.

- **Defect first:** #715 comment-out guard stayed green (`# concurrency:` still matched). #580 `ops free-cost` re-estimated `$0.1725` on a persisted `$0` last-run. PowerShell empty `OBSIDIAN_VAULT_PATH` unsets; dotenv reloaded the operator vault (digest note written, then deleted).
- **Shipped:** #714 #715 #584 #572 #580 #595 #452 #362 #364 #336 #605 #599 #437 #713 #415. Projected TTS at Proceed?. Rollback dry-run never builds a YouTube client. Busy bottom -> ASS Alignment 8. CI installs ffmpeg.
- **Fail-first:** 13 FAIL + 18 ERROR on unmodified d1776a0 (34 ran). #715 delete-block went red after the comment-strip. Suite **2,927 -> 2,962** (4 skipped); mypy **139**; `data/` untouched.
- **Not this commit:** #684 · #158 · #673 · live unlist. Filed **#716** (push+PR still two refs) · **#717** (chroma is not a face). Next: **#684 · #717 · #407 · #590 · #378**. Backlog **335 open / 618 done**, highest **#717**.



