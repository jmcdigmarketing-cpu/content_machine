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

**Written:** 2026-09-13 · **HEAD at write:** `9c42605` · **Tree:** wave 16 committing, then
**pushing all 7 commits** (audit, runs 77/78, wave 16) - check `git log origin/...` and CI.

**Defect first: run 77 shipped four bugs to YouTube, and the video is live (unlisted).**
Its chapters were `0:00-0:17` (the first eight sentences - YouTube drops them), the upload
got the pre-refinement description, it was tagged `shorts` at 293 s, and it carries "GTA 5
didn't win Game of the Year in 2013", which the claim verifier flagged and the operator
rendered past (#754, open). Its live description still needs re-saving by the operator.

**Wave 16 (operator picked live-run defects over the caption list):** **#750** chapters
span the video and pass YouTube's >= 3 / >= 10 s rule · **#751** `current_description`
before enqueue in `main.py` + `auto_generate` · **#752** `drop_shorts_tags`, topic tags
only pad < 5 · **#753** worker prints uploads · **#732** fingerprint v2 with version
stamp. 13/13 new tests observed red. **Two old pins changed** (`test_next15_wave` #431
starts 0/5/12 -> 0/15/33 s; `test_wave6_extras` "0:20" -> spans) - both pinned blocks
YouTube rejects or mislabels. Suite **3,167 -> 3,180**; mypy **139**; `data/` untouched;
backlog **329 / 663**, highest **#756**. Next five: **#754 · #755 · #345 · #543 · #756**.

**Earlier today, this session:** run 78 all angles -> one Extended video + chapter Shorts
(`core/angle_chapters.py`, `core/chapter_shorts.py`; unproven live = #755); run 77 typed
thoughts -> `run_discovery(brief=)`; audit of waves 14/15 fixed five deletions beside fixes.
**Cursor: a chapter block now comes only from `youtube_chapter_lines`; a cut Short is its
own run with `features.parent_run_id`; a new LLM call in a hot path needs a suite-off flag.**

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

