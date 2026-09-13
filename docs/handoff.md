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

**Written:** 2026-09-13 · **HEAD at write:** `db25e26` · **Tree:** wave 12 + docs,
committing right after this slot, then **pushing** (operator-approved); that CI result
was not known when this was written.

**Wave 11's CI is proven:** run 34744476819 ran every Qt test, 0 skips; #729 holds.

**Defect first.** `tests/test_stage2_html.py:134-146` used the operator's **real Windows
username** as a fixture, and it shipped in the sdist. Replaced with an invented name.
**Cursor: never put a real user name, home path or vault path in a test.**

Shipped **#733 · #630 · #640**; measured **#730 · #731** to a stop.

- **`ops selftest`:** 8/8 gates work with no store read. **4 are not armed here**
  (authenticity, grounding, metrics, publish dead-man) - #735, the operator's call.
  `authenticity.blocks_render` is now the one stop rule `main.py` and the selftest share.
- **`ops package-audit`:** wheel 373 / sdist 378 files, 0 hits. The wheel ships no
  `config/*.json` (#737); a stale egg-info once made the sdist 701 files (#736).
- **Coverage read:** `core/` 77%. The untested gate decisions are pinned; the four never-run
  append branches in `publish_blockers.py` are #734.
- **Captions stay off.** The operator wants default-on only if clean; nothing was. Best new
  feature leaves 1/50 stock false moves on a 0.06 margin, tuned to one clip.

Audit: 14 of 17 new tests observed failing first (3 pin working behaviour, stated); all 9
in-memory breaks went red; `ops clock-ahead --days 365` no change. Suite **3,069 -> 3,086**,
0 failures, 6 skipped; mypy **139**; ruff clean; `data/` untouched. Backlog **331 open / 642
done**, highest **#737**. Next five: **#734 · #735 · #736 · #737 · #730**. Detail:
[planning_log.md](planning_log.md) 2026-09-13 wave 12.

## Slot — Cursor

**Written:** 2026-09-09 · **HEAD at write:** `d1776a0` · **Tree:** this wave committing.

- **Defect first:** #715 comment-out guard stayed green (`# concurrency:` still matched). #580 `ops free-cost` re-estimated `$0.1725` on a persisted `$0` last-run. PowerShell empty `OBSIDIAN_VAULT_PATH` unsets; dotenv reloaded the operator vault (digest note written, then deleted).
- **Shipped:** #714 #715 #584 #572 #580 #595 #452 #362 #364 #336 #605 #599 #437 #713 #415. Projected TTS at Proceed?. Rollback dry-run never builds a YouTube client. Busy bottom -> ASS Alignment 8. CI installs ffmpeg.
- **Fail-first:** 13 FAIL + 18 ERROR on unmodified d1776a0 (34 ran). #715 delete-block went red after the comment-strip. Suite **2,927 -> 2,962** (4 skipped); mypy **139**; `data/` untouched.
- **Not this commit:** #684 · #158 · #673 · live unlist. Filed **#716** (push+PR still two refs) · **#717** (chroma is not a face). Next: **#684 · #717 · #407 · #590 · #378**. Backlog **335 open / 618 done**, highest **#717**.



