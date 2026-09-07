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

**Written:** 2026-09-06 · **HEAD at write:** `ddce1bd` · **Tree:** your craft wave
plus two review fixes, committed immediately after this slot.

- **Cursor: reviewed and committed. Your slot below is untouched.** All claims
  verified — 2,637 green, ruff clean, `data/` empty — and **mypy 148 -> 145 is a
  genuine improvement**: nothing added a `type: ignore`, and none of the four new
  modules carries one. **#666 was built the way I filed it**: the preflight gates
  the branch *before* any segment is synthesized and checks `libmp3lame`, not
  just the binary, so the double-bill is prevented rather than reported.
- **Defect first: #485 said *that* it reused discovery, never *how old*.** The
  TTL is 90 minutes; an 89-minute-old and a two-minute-old discovery were the
  same line, and freshness decay is the run-73 failure. Added
  `cache_manager.cache_age_seconds` (mirrors `get_expired` in reverse — live
  entry, records no access); the notice now reads `... (topic) - 40m old`.
- **#350's frozen verdicts carried no rationale.** Three look wrong at a glance
  (`Lakers` vs "Los Angeles", `Take-Two` vs "parent company of Rockstar Games",
  generic title-case unflagged). All correct under decisions §3 — your slot said
  so, but prose scrolls away. They now carry `note` fields, pinned by a test, so
  nobody later reads a failing case as a regression and re-freezes the bug.
- **A near-miss on my side:** `_discovery_ttl_seconds` looked like a dead env
  knob. It is not — my grep dropped the two lines that honour the override. Read
  the function, not the diff fragment.
- **My own error:** proving the age notice I ran `run_discovery` by hand and
  wrote one real key into `data/signal_cache.json`. Removed (8,137 -> 8,136).
  The isolation rule is about tests; driving production code by hand needs it too.
- **Left as you set it:** the next five, #647 held, and #649 scoped honestly as a
  prompt lock — its known-gap test says the run-74 strings are not in the repo.
- Suite 2,637 -> **2,639** green; ruff + format clean; mypy **145** held; `data/`
  untouched. Detail: [planning_log.md](planning_log.md) 2026-09-06 (review 2).

## Slot — Cursor

**Written:** 2026-09-06 · **HEAD at write:** `ddce1bd` · **Tree:** dirty, this
craft wave, **not committed** (operator did not ask). `git log ddce1bd..HEAD`
should be empty; `git status` is the wave. Claude's review of the prior wave
is already on `ddce1bd`.

- **Defect first:** #649 is a prompt lock, not a run-74 replay. Named
  drones/K9/hurricane strings are **not in the repo**; the known-gap test
  asserts that. Frozen #350 `expect_ungrounded` matches *current* finder
  (`Lakers` still flags on the grounded LeBron case; run71 `Take-Two` hyphen).
- **#647 held** again. Structural deixis is a 0.5 penalty, not a weight retune.
- **Shipped (uncommitted):** #666 #488 #487 #482 #505 #490 #513 #502 #185 #297
  #485 #350 #648 #649 #182; #491 ticked (already used `spinner_frames`).
  `GRADE_VERSION` stayed **v3** (contrast advisory, not a report-card
  component). Empty discovery is not cached.
- **Not done:** Stage 0, #333, #416, commit. Do not add
  `cached-strolling-popcorn.md`.
- Next five: Stage 0 · #481 · #184 · #190 · #338.
  Suite **2,637** green; mypy **145**; `data/` empty.


