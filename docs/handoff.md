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

**Written:** 2026-09-16 · **HEAD at write:** `d2790d2` · **Tree:** wave 18 committing, then
pushing. CI was green on `d2790d2` (run 35040382680).

**Defects first.** Nothing found broken in wave 17's code. Two things are still the
operator's: run 77 (`acu0Ekz-G5k`) is still `published` in the store until they delete it in
Studio and run `py -m scripts.ops studio-deleted --channel tapin`; and all-angles has
never met a real script (#755) - the Shorts menu now prints the measurement table, it just
needs the run. My wave 17 slot here had a heredoc-mangled line (a real newline and a
backspace byte); this rewrite removes it.

**Wave 18 - operator answered four questions first.** **#760** `ops batch-review`: one pass
over overnight drafts, y/n/later/q, render the yeses, space them; decisions live in each
draft's `meta.json` so it resumes · **#762** spaced slots go public at their time; a
grounding override (or a Short cut from one) stays unlisted · **#761** `ops retire-renders`
- applied on tapin, 5 retired · **#345** `core/claim_types.py`: hedged rumor warns,
award/result/stat blocks, untyped strict · **#756** labels · **#749** franchise pages ·
**#755** `ops chapters --run-id N`.

23/27 new tests red first (4 are guards). Suite **3,206 -> 3,233**; mypy **139**; ruff clean;
`data/` untouched; backlog **326 open / 674 done**, highest **#764**. Next five:
**#755 · #763 · #764 · #627 · #739**.

**Cursor:** `gate_blocks` no longer means "any unsupported claim" - read
`core.claim_types.blocking_unsupported`. `queue_spaced_uploads` now defaults to public;
pass `privacy_status` only to force something else. Write regexes and prompt strings with
the editor, not a shell heredoc - both of my wave 17 escaping bugs came from that.

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

