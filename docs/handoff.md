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

**Written:** 2026-09-17 (2nd) · **HEAD at write:** `b4e06fe` · **Tree:** wave 20 committing,
then pushing. CI was green on `b4e06fe` (run 35174734027).

**Read this before touching the voice policy.** #758 sent Long/Extended to piper to kill 91% of
spend. The operator listened to run 79 on 2026-09-17 and called it **clearly worse**. #775 reverses
it: `TTS_PROVIDER_LONG` has no default, so long-form is paid again; piper stays as the Shorts mix
(1 in 6). `.env.example` carries the verdict beside both knobs. Do not "optimise" this back.

**Volume framing from the same call:** a long video is **1-2 a month**; the **3-5/week target is
Shorts**. The bill is mostly Shorts rates, which is why paid long-form was affordable again.

**Defect found this wave:** batch review preferred the #774 run-id script sidecar over the draft
folder's own `draft.md` - a test collision caught it; the folder's copy wins now. Nothing else in
wave 19's code was broken.

**Also shipped.** #776 weekly spend warning off the traces (`SPEND_WARN_WEEKLY_USD`, default $5,
warn-only, in `ops status` and `ops overnight`) · #770 `trim_chapter_openers` drops a
back-referencing first word before TTS, so cut Shorts inherit clean hooks (run 79's cuts 2/4/5) ·
#773 the keyword fallback stays within half a share of its target (576/8/10/10/21 ->
120/132/120/132/121) · #774 the final script sits beside the trace · #777 `ops retire-renders
--run-id`, used on the piper test renders 79-84.

Suite **3,267 -> 3,286**; mypy **139**; ruff clean; `data/` untouched by tests; `ops mutate-gates`
45/45. Backlog **323 open / 690 done**, highest **#777**. Next five:
**#771 · #739 · #730 · #728 · #628**.

**Cursor:** four tests across waves 17 and 19 pinned the piper long-form default and now pin the
opt-in path instead - if you see piper in a voice test, read its docstring before trusting it.
`ops retire-renders` takes `--run-id` now. Run `py -m scripts.ops mutate-gates` after any gate change.

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

