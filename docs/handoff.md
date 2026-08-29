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

**Written:** 2026-08-29 · **HEAD at write:** `675edc5` · **Tree:** clean —
the run-74 fix is committed on `consolidate/2026-08-27` and pushed, as one commit
(the change spans `ui.py` / `operator_facts.py` / `link_facts.py` across all four
phases, so splitting it would have needed partial staging and risked a red SHA).

- **Cursor is out until 2026-09-06** (monthly limit reached, operator's word). Until
  then this mailbox has one reader: assume nobody else is mid-edit, but keep writing
  the slot anyway — the gap is exactly when a missed note goes stale unnoticed.

- **Defect first: `Proceed?` no longer stops on an unrecognised answer, and that is
  a deliberate contract change.** Only `n` / `N` / `no` / Enter stop; everything
  else re-prompts (3 asks). This overturns candidate 325's
  `test_a_stray_keystroke_is_still_a_stop`, which I renamed and inverted. Run 74
  was discarded by the word **`by`** — Engadget's byline label, left in the console
  buffer by a paste at the **Fact** prompt. Two characters, one word, so 325's
  prose detector never fired. If you think re-prompting is wrong, read
  `docs/debugging.md` → Live-run 74 before changing it back.
- **Facts are no longer sliced at 400 chars.** `_MAX_KEY_FACT_CHARS` is now a split
  width, not a truncation point (`split_at_sentences`). `link_facts` and
  `parse_pasted_block` route through it too. **If you add a new fact source, split —
  do not slice.** A severed clause reads to a model as a finished, vague statement.
- **The prompt budget now ranks (`core/fact_selection.py`) and it is calibrated on
  one run.** Weights: recency .35 / novelty .25 / relevance .20 / specificity .20,
  scaffolding −.45. They separate run 74's 15 furniture lines from its 15 real
  details with a 0.27 margin — on run 74's data. **#647 is validating them against
  `data/traces/*.json`; treat them as provisional until that lands.**
- **Do not reach for `score_vault_fact` as a general fact ranker.** Measured, it
  scored run 74's Slim Jim carjacking mechanic at **0.03** — it rewards echoing the
  signal corpus, which is backwards for a pasted article whose purpose is to add
  what the signals lack. That is why `novelty` exists and relevance is the smallest
  weight.
- **Selection happens at intake, not in `facts_for_prompt`.** `prompt_key_facts_result`
  is the only place that knows provenance (typed vs scraped vs vault, and the page's
  publication date), so it ranks once and hands the chosen set downstream.
  Consequence: **`scripts/auto_generate.py` still packs in insertion order** (#646).
- **Two dead signals were costing 30 of a 37.8s discovery.** `trendingnow` retired
  (#583 closed) via a new `RETIRED_SIGNALS` map in `apis/signals_bootstrap.py` —
  the free-signal equivalent of §19's Apify kill switch. **#584 (YouTube RSS 404) is
  still open.** YouTube timeout 15s → 8s plus a process-level unreachable latch;
  `reset_session_breaker` clears it.
- **A gate was rewarding what two others banned:** `authenticity._INSIGHT_MARKERS`
  counted `"here's the thing"` as an authorial take while `persona_lint` and the
  script prompt both banned it — that is why run 74 scored authenticity 100/100.
  Removed; `tests/test_gate_agreement.py` keeps the three lists from drifting apart.
- **Did not do, on purpose:** the report card still does not weight length, though
  run 74 shipped 277 words against a 300-word floor and graded A. A length component
  changes the meaning of every historical grade — filed as **#645**.
- **Warning from my own session:** `git stash push -u` fails partway in this repo
  (`video/backgrounds/*` are permission-locked), leaving tracked edits on disk *and*
  in the stash while deleting untracked files. Recovered via
  `git checkout 'stash@{0}^3' -- <files>`. **Don't stash here.**
- Suite 2,415 → **2,515 green**; `ops all-checks` clean; ruff clean; mypy 148 (two
  of mine fixed, none introduced). Backlog 455 → 460 open, highest **#650**.

## Slot — Cursor

**Written:** _(not yet written — this slot has never been filled)_ · **HEAD at write:** `—`

When you write this slot, replace this paragraph. Say what you changed, what you left
uncommitted, and what you found broken — defects first. If a previous slot claimed
something was done and you found it was not, say so plainly; that correction is the
most valuable thing this file can carry.
