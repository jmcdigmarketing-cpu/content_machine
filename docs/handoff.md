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

**Written:** 2026-09-20 · **HEAD at write:** `0d5d23c` · **Tree:** wave 25 committing, then
pushing. CI was green on `0d5d23c` (run 35476144912). **Documentation only - no code changed.**

**Defects first, all found by measuring `data/traces/*.json` (38 runs) rather than reading docs:**
- **The TTS cache has never been used.** `TTS_CACHE` is absent from the operator's `.env`,
  `data/tts_cache/` does not exist, `tts_cached` is false wherever recorded - while TTS is
  **$6.09 of $7.27 (84%)** of all spend. #71 and #402 built it; nothing switched it on (#809).
- **28% of the report card is a constant.** Authenticity scores 100/100 on **22 of 38** runs
  (#804). Hook, median 78, is the only component that discriminates.
- **Intent detection reads `default` on 9 of the 10** runs that record it (#801).
- **Six signals have never returned anything** inside a 58.7 s median discovery (#810).
- **A duplicate open #351** had been inflating the open count since 2026-08-30; removed.

**What exists now:** [engine_upgrades.md](engine_upgrades.md) holds the measured baseline, the
ranked ideas in three sections, and a "not worth doing" list (token-spend optimisation, more
signals, a second signal cache, re-weighting before #804, significance at n~10). Filed
**#799-#812**; narrowed **#575 #561 #50 #374 #611 #83** with the evidence.

**Operator calls this session:** one new doc rather than addenda to two; the next build wave
weights **script quality**. Next five: **#799** (rewrite-pass ledger, first because everything
else in the script section is judged through it) · **#800** (hedge density, decides
`decisions.md` §25) · **#801** · **#809** · **#804**.

Suite **3,381** unchanged; mypy **139**; ruff clean; `data/` untouched. Backlog **335 open / 710
done**, highest **#812**.

**Cursor:** the open counts moved by 14 filed plus one duplicate removed - if a count looks wrong
against an older note, re-run `py -m scripts.ops roadmap-index` rather than trusting the prose.

## Slot — Cursor

**Written:** 2026-09-20 · **HEAD at write:** `29ae92d` · **Tree:** wave 26 committing.

**Defects first:**
- **TTS cache is on with nothing in it yet.** Live `ops reliability` printed
  `TTS cache: on, 0 file(s), 0/3 hits (0%)`. The polarity flipped; the first live
  synth has to populate `data/tts_cache` before spend moves. Suite pin stays
  `TTS_CACHE=false`. A bare `discover -s tests` (no `-t .`) can now write that
  directory the same way it already can write other stores.
- **#345 still lets a hedged rumor through the render gate.** #800 is grade-only.
- **#50 is still the next authenticity input.** Wave 26 stopped the 100/100 ceiling;
  it did not add learned insight markers.

**Shipped #799 #800 #801 #809 #804.** Rewrite ledger on the card; hedge density
drops grounding (closes §25); intent replay on the 38 recorded topics; TTS cache
default-on; authenticity `points` continuous, gate still binary, `GRADE_VERSION`
**v4** (historical letters re-grade). `_WEIGHTS` untouched.

**Next five:** **#806 · #807 · #810 · #812 · #802**.

Suite **3,381 -> 3,406**; mypy **139**; ruff clean; `data/` untouched. Backlog
**330 open / 715 done**, highest **#812**.

