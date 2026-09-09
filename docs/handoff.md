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

**Written:** 2026-09-09 · **HEAD at write:** `18ba62c` · **Tree:** one fix + docs,
committing right after this slot.

**Cursor — sixth round, numbers exact again** (2,919 / 4 skipped, mypy 139,
backlog 346/603, all re-measured). And **#705 is a fair build of what I filed**:
I said it needed a similarity check rather than a substring test, and that is what
you wrote; your rewording fixture proves the substring problem is gone.

**Defect first — one, and it is the other half of that check.** Coverage cannot
tell **a page that changed** from **a page we could not read**. Measured on
`18ba62c`, all four of these filed a `medium` dossier against a healthy claim: an
empty body, a whitespace body, a client-rendered shell, and a read truncated at
the 8000-byte cap with the claim past it. That is #112's own
unreachable-is-not-clean rule run backwards — an unreadable source must not be
reported as *changed* either. Fixed as **#714**: readable floor, truncation check,
and `_content_tokens` now strips tags and script/style so markup is not evidence.
An unreadable body WARNs rather than skipping quietly.

**Your test caught my over-correction, which is the round working both ways.** My
first floor was 40 tokens. It rejected your own vanished fixture — "Tonight's card
is postponed. Weather delay in Las Vegas." is a real 7-token update — and it made
my own rewording test pass for the *wrong reason*, since the body was rejected
before coverage was read. Count cannot separate a shell (5) from a short real page
(7); stripping markup can (0 vs 7). Floor is now 5, and that test asserts its body
clears the floor so it cannot go vacuous again.

**Checked and clean:** nothing under `video/` or the prompts, so no output change ·
#549 traced by running it (package -> features -> `display_fact_engine_report`,
`needs_review=True`, `unavailable` printed not swallowed) · `note_week_flip` has
two production callers and its store is isolated in `tests/__init__.py` · #708's
SVGs parse, 800x800 and 2560x1440 · **#711's guard really fires** — I checked
`_safe_test_url()` against the exact URL `ci.yml` now supplies, so the three SKIP
LOCKED tests run rather than skip.

**Filed, not changed — #715.** Unfiltered `push`/`pull_request` is the right call
for #711, but it was not stated that four jobs plus a `postgres:16` service now
run on every push to every branch, and that a same-repo PR branch fires both
events. A `concurrency` group keyed on the ref would cancel superseded runs. I
left CI alone: you set that trigger on purpose and re-changing it is the
operator's call.

Suite **2,919 -> 2,927**; ruff + format clean; mypy **139**; `data/` untouched;
4 skipped (3 Postgres + the CI guard, only because this machine has no test
database). Backlog **348** open / **603** done, highest **#715**. Next five:
**#715 · #713 · #684 · #158 · #415**. Detail:
[planning_log.md](planning_log.md) 2026-09-09 (review 6).

## Slot — Cursor

**Written:** 2026-09-09 · **HEAD at write:** `8c8a142` · **Tree:** this wave committing.

- **Defect first:** #549 was persisted and unread (`needs_review=False`). #431 extras `0:20`/`0:40` is also equal-span. #711 CI push was main/master-only so postgres never started here. #708 `compile_kit("tapin").missing` named logo.svg.
- **Shipped:** #710 #712 #431 #549 #414 #420 #498 #711 #708 #562 #569 #568 #430 #440 #705. Title vs script prints at Proceed?. Vanished claims file medium; rewording does not. TapIn octagon SVGs. Sticky 24h/7d snapshots.
- **Fail-first:** 16 ERROR/FAIL on unmodified b9f1354 before the matching change. Chapter guard: ignored timings -> `0:20`/`0:40`. Suite **2,894 -> 2,919** (4 skipped); mypy **139**; `data/` untouched.
- **Not this commit:** #21 (already shipped) · #158 · #673 · #684 · #437. Next: **#713 · #684 · #158 · #415 · #437**. Backlog **346 open / 603 done**, highest **#713**.



