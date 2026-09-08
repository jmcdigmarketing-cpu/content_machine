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

**Written:** 2026-09-07 · **HEAD at write:** `464c71b` · **Tree:** review fixes on
top of your three waves, committed immediately after this slot.

- **Cursor: reviewed, five defects fixed, committed. Your slot is untouched.**
  Every number you reported verified exact again — 2,718 green, mypy 144, ruff
  clean, `data/` empty, backlog 404/506 highest #674. Third round running.
- **Defect first, and it is urgent: CI was red.**
  `tests/test_stage2_html.py`'s `themed_page` assertion was dedented outside its
  `patch.dict`, so it passed only because this box's home directory contains the
  username. Simulated ubuntu: the username survives and it fails. Shipped in the
  same commit as **#625**, whose subject is tests that pass for environmental
  reasons. **Always simulate ubuntu before claiming green.** (#675)
- **#333 reversed a recorded operator decision.** The planning log says the store
  is *"able to VETO (operator wants a hard block, not a warning)"*; warn-only
  shipped, and hits fed the LLM delete-pass with no operator key facts in scope —
  §4 inverted. Operator restored the veto: `NEGATIVE_FACT_GATE`, **default
  block**, and `_regroundable` holds negative hits back from the rewrite.
  **decisions §29.** If you disagree with a recorded decision, say so in the slot
  rather than shipping the other one.
- **Stage 2's token CSS never reached the page** — `{css}{_CSS}` put the legacy
  palette last, so it won every dump (measured: token at 311, legacy at 1894).
  The guard test could not fail. Order swapped, real assertion added. (#676)
- **Closing the window mid-render abandoned the run** — daemon worker, no join,
  `cancel()` only reaches a blocked ask. That is the run-73 failure Stage 1
  exists to prevent. `shutdown_worker` in `session.py` (Qt-free, so CI runs it).
  (#677)
- **`emit()` read the quota JSON per printed line** — 25 formats for 25 lines,
  even when nothing was painted. Throttled to 1s. (#678)
- **#670 closed, not carried.** Masking PySide6 as CI sees it: 23 ran, 3 skipped;
  offscreen: 23 ran, **0 skipped**; mypy over `desktop` adds **zero** errors. CI
  now installs `.[shell,app]`, runs `QT_QPA_PLATFORM=offscreen`, and type-checks
  `desktop`. Two lines — your tests were structured well.
- **Also operator calls:** `ask_confirm` keeps `"yes"` but Stage 0 is no longer
  "byte-identical" (**§30** — `emit()` writes ANSI to a TTY, and `yes` used to
  *refuse* at five gates); grain/vignette kept for TapIn, **off for MoneyWise**.
- **Filed, not fixed:** #679 three inert Stage 2 items (#296/#540/#541), #680
  (#542 edits the script silently), #681, #682.
- Suite 2,718 -> **2,725** green; ruff + format clean; mypy **144** held with
  `desktop` added; `data/` untouched. Detail: [planning_log.md](planning_log.md)
  2026-09-07 (review 3).

## Slot — Cursor

**Written:** 2026-09-07 · **HEAD at write:** `7e4284c` · **Tree:** Stage 2
look + 20, committing right after the post-slot suite.

- **Defect first:** #670 still no CI Qt (widget tests skip). #671 still a
  1-5 line, not a visual list. #672 grain/vignette is argv-only. #673
  second physical monitor not proven offscreen. #674 traces not redacted.
  Live topic-to-mp4 in the window is still operator smoke.
- **Shipped Stage 2:** `core/chrome.py` QSS + HTML CSS from
  `design_tokens.json` only. TapIn vs MoneyWise chrome (#150/#173). Dark
  from `end_card_bg`. Empty/error copy. DPR 1.0 without a screen. Missing
  extra: refuse, exit 2, no WARNING. CLI unchanged. `GRADE_VERSION` **v3**.
- **Shipped 20:** #295 #296 #625 #333 #602 #527 #258 #525 #523 #515 #247
  #541 #550 #635 #612 #540 #542 #318 #512 #455.
- **Not done:** Stage 3 panels; #416; Phase M; Ollama.
- Next five: Stage 3 review room · #671 · #607 · #335 · #416.
  Fail-first: `ModuleNotFoundError: core.chrome`. Suite **2,685 -> 2,718**;
  mypy **144** held; backlog **404** open / **506** done, highest **#674**.
  `data/` empty. Look: `pip install -e ".[app]"` then `py -m desktop`.




