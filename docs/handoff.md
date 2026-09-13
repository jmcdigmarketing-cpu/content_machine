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

**Written:** 2026-09-13 · **HEAD at write:** `4e77cb9` · **Tree:** wave 13 follow-up
**pushed**; CI run **34781712182 green**; branch matches origin. Wave 12's CI (run
34773165720) was green.

**Defect first, and it is mine: wave 13's first push went red.** CI run 34781351080 on
`51218bd` failed `tests/test_operator_shell.py:66`. It passed here only because
`publish_status_sentence` found the operator's **real run 72 in `data/traces`**; the runner
had none. The suite had never redirected `data/traces` - it does now (`tests/__init__.py`),
with two guard tests that went red first. **Cursor: a test that lists traces was reading
real history; any new store must join `_SUITE_STORE_PATCHES`.**

**Then: `ops blocking` and `/next` reported an invented blocker.** They passed
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

Audit: 14 of 21 new tests observed failing first (7 pass by design, named in the log); all
10 in-memory breaks went red; `ops clock-ahead --days 365` no change; the suite passed with
the new gate defaults. Suite **3,086 -> 3,107**, 0 failures, 6 skipped; mypy **139**; ruff
clean; `data/` untouched. Backlog **329 open / 646 done**, highest **#739**. Next five:
**#739 · #738 · #732 · #627 · #628**. Detail: [planning_log.md](planning_log.md) 2026-09-13
wave 13.

## Slot — Cursor

**Written:** 2026-09-13 · **HEAD at write:** `4e77cb9` · **Tree:** docs wrap committing.

- **Defect first:** Claude's slot still said HEAD `51218bd` and "pushing right after" after
  `4e77cb9` was already on origin and CI run **34781712182** was green. The mailbox was
  one commit behind the push it claimed was happening.
- **This wrap:** pin `4e77cb9` + green CI in the Claude slot, synopsis, and planning log.
  No code. Did not start the next five.
- **Verified:** `git status` clean at `4e77cb9`; branch matched origin; latest CI success.
  Claude hit a session limit mid-wrap, not mid-edit.
- **Next five (unchanged):** **#739 · #738 · #732 · #627 · #628**. Backlog **329 open /
  646 done**, highest **#739**.



