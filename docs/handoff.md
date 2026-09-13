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

**Written:** 2026-09-13 · **HEAD at write:** `e7ef6ad` · **Tree:** run 77 typed-thoughts
change **committed locally on top of the audit, neither pushed**.

**Latest — run 77 (operator: "i should be able to enter my thoughts for an idea … in the
topic").** Defect first: typed thoughts were the search string for every signal (Trends
searched a comma fragment and served a stale cached "Goy"), the angle LLM never saw them,
and 3 of 5 angle lines were a preamble plus raw lens labels. Now the Topic prompt takes
thoughts (multi-line too): discovery searches a short seed ("GTA 6"), `run_discovery(brief=)`
feeds the thoughts to angle generation, intent, ranking and the cache key, and angle replies
are cleaned with one re-ask. `tests/test_typed_thoughts.py` 10/10 red first. Suite
**3,141 -> 3,152**. **Cursor: `run_discovery` and `generate_variants` take `brief` now —
pass the operator's words, not a longer topic.** Detail: planning_log run 77.

**Earlier this session — audit of waves 14 + 15:**

**Defects first — five, all in waves 14/15, all fixed test-first** (`tests/test_wave15_audit.py`,
6 of 10 red on `b872736`). The wave tests asserted only run 76's strings, so a deletion
beside each fix stayed green:

- `fact_grounding._LEADING_STOPWORDS`: #745 **replaced** run 66's what/why/how/who/which/
  that/this/these with Start/Read/Compare/Restricted ("Why Jason Duval" was an entity).
- #748's heuristic title check failed any Title Case title, even one the script backs.
- #741's chrome filter dropped every fact containing `affiliate`; `about the author`
  matched "about the authorities".
- #744's cheap judge ran on every discovery with no off switch, and **the suite made 8 real
  `complete()` calls**. New `ANGLE_LLM_JUDGE` (default on); `tests/__init__.py` sets it off.
- `angle_ranker._thesis_terms` regex lacked a leading `\b`.

**Cursor: when you add to a list, diff the list — and a new LLM call in a hot path needs
a flag the suite turns off.**

Everything else checked out: every run_76.md measurement reproduced, and Google Suggest
really 400s on the 173-char seed. Suite **3,131 -> 3,141**, 6 skipped; mypy **139**;
ruff clean; backlog unchanged (**327 / 658**, #749). Leftovers (Wiki drops capitalised
`Will`/`Long`; a "Paste the…" fact enters paste mode) are in
[run_76.md](run_76.md) §Audit. Next five unchanged: **#739 · #730 · #345 · #543 · #732**.

## Slot — Cursor

**Written:** 2026-09-13 · **HEAD at write:** `2421e15` · **Tree:** wave 15 committing.

- **Defect first:** Wikipedia still queries `GTA` token-joins, not
  `Grand_Theft_Auto_VI` (#749). Heuristic title/script cannot catch a wrong actor
  who is named in the script (#345). The forced-overage publish test was green on
  unmodified code because nothing fed the cap yet; it guards the feeder.
- **Shipped #534 #748 #746 #747 #738.** Title keeps an angle phrase. Title/script
  check falls back to a real verdict. Wiki no longer invents `Gta`/`Goy`.
  Autocomplete 400 is skip-with-reason. Publish list reads persisted
  `tts_char_count`.
- Next five: **#739 · #730 · #345 · #543 · #732**.
- Suite **3,123 -> 3,131**; mypy **139**; ruff clean; backlog **327 open / 658 done**,
  highest **#749**.

