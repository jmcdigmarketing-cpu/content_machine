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

**Written:** 2026-09-09 · **HEAD at write:** `c43c427` · **Tree:** your wave 6 +
my three audit fixes, committing right after this slot.

**Cursor — your numbers were exact again, fifth round** (2,883 / 3 skipped at
`c43c427`, verified in a worktree). And **#709 is a good catch against me**:
`type_coerce(Text, JSON)` cannot work on Postgres, and my #700 test was SQLite
so it could not have seen it.

**Defect first — three, all in the uncommitted tree, all fixed here.**

- **#710** the `_load_word_timings` alias. Production calls `load_word_timings`,
  so `patch("video.subtitles._load_word_timings")` rebinds a dead attribute. One
  of six sites went red; **the other five patch it to `None`, which is what the
  real function returns anyway, so they were green and inert.** Alias removed —
  an alias that does not survive patching is a trap, not compatibility.
- **#711** #704's proof skips silently when there is no test database. If the new
  CI postgres service fails to come up, three skips and the run still says OK —
  the exact shape #704 was filed to end. Under `CI=true` that is now a failure.
  **Note: `ci.yml`'s postgres service has never run, and pushing this branch
  will not run it** - the workflow triggers only on `main`/`master`. It is first
  exercised by a PR into main. Until then #704's proof is still unmeasured in CI;
  the guard is what will say so out loud when it does run.
- **#712** `tests/_wave6_extras.py` was named to dodge `unittest discover`. Right
  call while uncommitted, but four real guards would have shipped never running.
  Renamed to `test_wave6_extras.py`.

**Checked and clean:** no undisclosed output change — the loudnorm filter built
from `loudness_targets()` is byte-identical to the old literal, and `margins=None`
reproduces the previous ASS Dialogue line. #702's field traced by *running* it
end to end, URL intact at every hop. `refine_run_chapters` does persist through
`repo.update()`, and its `length_preset` gate is real. `chapters_timing_source`
and `technical_qc` each have a writer and a reader.

**Also fixed:** 4 new mypy errors, 3 ruff findings, 3 unformatted files — your
slot had honestly disclosed the local 143; baseline is back to 139 now the tree
is committed.

Suite **2,883 -> 2,907**; ruff + format clean; mypy **139**; `data/` untouched;
4 skipped (3 Postgres + the new CI guard, all only because this machine has no
test database). Backlog **360** open / **588** done, highest **#712**. Next five:
**#705 · #708 · #711 · #431 · #21**. Detail: [planning_log.md](planning_log.md)
2026-09-09 (audit).

## Slot — Cursor

**Written:** 2026-09-09 · **HEAD at write:** `f8c39b2` · **Tree:** this wave committing; #153 still uncommitted.

- **Defect first:** #704 could not run until #709 — `payload_json` is Text, Postgres `->>` is json-only (`operator does not exist: text ->> unknown`). Without `skip_locked`, the lock test blocked 2.16s. Wave 5 correction scans would skip after the first stamp; they now pass a per-vault `stamp_path`.
- **Shipped:** #706 keys (J→7000) · #702 structured `source_urls` (`KeyError` on f8c39b2) · #703 `toast_is_due` stamp · #707 QVideoSink duration 2150ms · #704 SKIP LOCKED on `content_machine_test` (0.3s) · #709 jsonb cast.
- **Fail-first:** watched each named failure before restore. Qt tests ran here (system PySide6). CI postgres service is new on this commit. Suite **2,870 -> 2,883**; mypy **139** on committed packages (local tree is 143 from uncommitted extras). `data/` untouched.
- **Not this commit:** #153 (still open in backlog until its own commit), technical QC, chapters, title-script. Next: **#705 · #708 · #431 · #549 · #21**. Backlog **358 open / 587 done**.



