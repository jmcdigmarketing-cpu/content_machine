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

**Written:** 2026-09-15 · **HEAD at write:** `ec11b6f` · **Tree:** wave 17 committing, then
pushing. CI was green on `ec11b6f` (run 34797145521).

**Defect first, and it is the operator's to finish:** run 77 is still live (unlisted,
`acu0Ekz-G5k`) carrying "GTA 5 didn't win Game of the Year in 2013". The operator is
deleting it in Studio; run `py -m scripts.ops studio-deleted --channel tapin` afterwards so
cadence and economics stop counting it. **All-angles (run 78) has still never met a real
script** - that is #755 and it needs a live run.

**Wave 17 - the four areas the operator picked, in one wave.** **#754** a render past the
grounding gate is persisted on the run, named in `ops blocking`, and cannot be uploaded
public · **#757** `core/spaced_queue.py` gives each chapter Short its own open slot inside
the cadence cap (live: 3 queued, 2 held back) · **#758** Long/Extended voice is
`TTS_PROVIDER_LONG` (piper, $0) because TTS is **$13.50 of $14.85** all-time spend ·
**#543** the operator's own line is quoted verbatim and re-checked after every rewrite ·
**#759** an intermittent partner behind HEAD now reads as normal, in `ops agents` and here.

26/26 new tests observed red first. Suite **3,180 -> 3,206**; mypy **139**; ruff clean;
`data/` untouched; backlog **328 open / 668 done**, highest **#760**. Next five:
**#755 · #760 · #345 · #756 · #749**.

**Cursor:** a Short cut from chapters is its own run (`features.parent_run_id`); queue
several with `core.spaced_queue`, never one upload per session. Voice provider now depends
on the length preset - set `TTS_PROVIDER` explicitly to pin it. Two of my own bugs this
wave came from shell heredoc escaping (`
` became real newlines in a prompt string, ``
became backspace bytes in a regex); the suite did not catch either - importing the module
and printing the compiled value did.

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

