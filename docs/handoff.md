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

**Written:** 2026-09-09 · **HEAD at write:** `352c547` · **Tree:** wave 5 + docs,
committing right after this slot.

**Defect first — two shipped features have never run in production.**
`run_trace._slim_signals` strips every URL from the trace, so `pairs_from_trace`
returns `[]`. Measured: **zero `http` matches across all 28 files in
`data/traces/`**. #341's trace path and your #696 quote-trimming fix have watched
nothing on a real run; the tests that prove them feed a synthetic trace with a
top-level `sources` key production never writes. Filed **#702**, and it is pick 1
of the next five. #696 itself was correct — its input is empty.

Also: **#700's filed defect was the smaller one.** The unbounded fetch was real,
but `claim_next`'s SELECT/UPDATE/commit carried **no row lock at all**, so two
workers on the supported Postgres path could claim the same job. The JSON path's
`_lock` is a `threading` lock and does not span processes. Fixed, but
**`skip_locked` is still unproven** (**#704**): SQLAlchemy emits no FOR UPDATE on
SQLite, so the six new tests prove ordering, LIMIT and one-row-per-call, not the
lock. Said so in the test docstring rather than implying otherwise.

**Shipped:** **#701** weekend clock (Sat 20:00 returned Sat 12:00) · **#700** SQL
order + LIMIT + `skip_locked` · **#699** `surfaces` tokens + a palette scanner —
**60 unexempted hexes before, 0 now**; d1a1895 could never have fixed it, since
emission order only wins for selectors *both* blocks declare · **#112** correction
dossier, which needed three substrate fixes first (`to_dict()` dropped every
`citation_line`; nothing set `features["source_urls"]` though it was already
computed and discarded; `.facts.json` reads exactly those two keys and shipped
empty every render) · **#151** brand-kit compiler, deliberately a READ path — the
renderer is **not** re-routed through it.

**The five taken were not the five listed.** #151/#153 had been recommended then
skipped four waves running; operator demoted **#153** and took #151 on purpose.

Fail-first: 37 tests, all watched failing on `352c547` for their named reason.
Three suite failures were mine and fixed — two docs-drift after three new ops
verbs, one real (`test_untouched_run_gains_no_keys` pinned an exact key set that
`claims` now joins; rewritten to assert the rewrite keys are *absent*, which is
what it was actually guarding, and is stronger than before).

Suite **2,833 -> 2,870**; ruff + format clean; mypy **139** (baseline held — three
new errors fixed, not absorbed); `data/` untouched. Backlog **363** open / **581**
done, highest **#708**. Filed open, yours if you want them: **#702 #703 #704 #705
#706 #707 #708**. Next five: **#702 · #704 · #703 · #706 · #707**. Detail:
[planning_log.md](planning_log.md) 2026-09-09.

## Slot — Cursor

**Written:** 2026-09-09 · **HEAD at write:** `f8c39b2` · **Tree:** this wave committing; #153 still uncommitted.

- **Defect first:** #704 could not run until #709 — `payload_json` is Text, Postgres `->>` is json-only (`operator does not exist: text ->> unknown`). Without `skip_locked`, the lock test blocked 2.16s. Wave 5 correction scans would skip after the first stamp; they now pass a per-vault `stamp_path`.
- **Shipped:** #706 keys (J→7000) · #702 structured `source_urls` (`KeyError` on f8c39b2) · #703 `toast_is_due` stamp · #707 QVideoSink duration 2150ms · #704 SKIP LOCKED on `content_machine_test` (0.3s) · #709 jsonb cast.
- **Fail-first:** watched each named failure before restore. Qt tests ran here (system PySide6). CI postgres service is new on this commit. Suite **2,870 -> 2,883**; mypy **139** on committed packages (local tree is 143 from uncommitted extras). `data/` untouched.
- **Not this commit:** #153 (still open in backlog until its own commit), technical QC, chapters, title-script. Next: **#705 · #708 · #431 · #549 · #21**. Backlog **358 open / 587 done**.



