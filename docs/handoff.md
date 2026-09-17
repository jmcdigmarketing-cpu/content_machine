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

**Written:** 2026-09-17 · **HEAD at write:** `cf7c62b` · **Tree:** wave 19 committing, then
pushing. CI was green on `cf7c62b` (run 35166827842).

**Defects first - five found this wave, four by running it live.**
- #765: headless scripted variant 0 while printing the ranked one.
- #767: `auto_generate > log` crashed on a check mark (cp1252), which is exactly how the nightly
  task runs.
- #768: piper Extended voice was projected and stored at ElevenLabs price.
- #772: the voice label was wrong.

All fixed. Open from the run: #770 (3/5 chapter Shorts open "So/But/And"), #771 (piper leaves no
word timings, so captions and cut points are estimated on every long video), #773 (keyword
chapter fallback is lopsided), #774 (a headless draft's full script is not stored). Still the
operator's: run 77 is `published` until the Studio delete plus `ops studio-deleted`, and they
need to listen to the piper render.

**Live run (operator-approved, nothing queued).** Run 78 stopped at the grade gate (C). Run 79
was forced past that gate only: 287 s on piper for $0 voice, five `llm` chapters of 0:39-1:07,
Shorts cut as runs 80-84. Run 79 carries `grounding_override`, so 79-84 never go public.

**Also shipped.** #627 `ops mutate-gates` (38/45 -> 45/45) · #769 a wrong actor named in the
script blocks · #763 draft freshness 2d/7d · #764 under-target week line · #766 `ops
schedule-drafts` (not installed - the operator does that).

Suite **3,233 -> 3,267**; mypy **139**; ruff clean; `data/` untouched by tests; backlog **326
open / 684 done**, highest **#774**. Next five: **#771 · #770 · #773 · #774 · #739**.

**Cursor:** cost functions take `length_choice` now - pass it, or piper renders read as paid.
Headless entry points call `core.console_encoding.ensure_utf8_stdout()`; a new one should too.
After changing a gate, run `py -m scripts.ops mutate-gates --target <module>`.

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

