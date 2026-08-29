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

**Written:** 2026-08-28 · **HEAD at write:** `48ef260` · **Tree:** clean

- Fixed four defects a real GTA 6 reaction run (run 73) exposed. Suite 2,408 green,
  ruff clean, `data/` untouched. Detail: planning_log 2026-08-28 (run 73).
- **Angles ignored the operator entirely.** `generate_variants` never read the topic
  string — angle types came from domain + repeat count, and the prompt told the model
  to CRITIQUE once a franchise was established. `core/angle_intent.py` fixes it; the
  mode prints on the angle screen and can be overridden.
- **Web search had taught itself to stop.** Run 1 saved its own findings to the vault,
  clearing the density bar, so runs 2–3 skipped the web on an hours-old reveal.
  Event-shaped topics never skip now; backing facts must be dated and recent.
- **yt-dlp**: `quiet`/`no_warnings` never suppressed extractor errors — only a
  `logger` does. Age gates are counted at debug. `YTDLP_COOKIES_FROM_BROWSER` opt-in.
- **No 18-fact cap ever existed** (that was the count). Real limits were 24/4500 and
  could not hold one article; now 60/12000, both halves shown, and drops are logged
  instead of a bare `break`.
- **Watch for this**: two more test doubles mirrored the caller instead of the real
  library ( `_full_one(url)` missing its new arg; an undated vault fixture ). That is
  three this week counting edge-tts. When you add a parameter, check the fakes.
- **Open, operator's call**: the terminal. The blocker is `main.py`'s 15 blocking
  `input()` calls, not HTML. Cheapest exit is the booth (already POSTs) gaining a
  start-a-run form over the already-headless `generate_draft` — not #141 Desktop.
  Operator said "will stay in terminal as long as it takes" for now.
- Still unbuilt from the parked list: #333 negative-fact store (narrowed to a hard
  block backstop), #349 folded into research, CUDA wheel not installed.

## Slot — Cursor

**Written:** _(not yet written — this slot has never been filled)_ · **HEAD at write:** `—`

When you write this slot, replace this paragraph. Say what you changed, what you left
uncommitted, and what you found broken — defects first. If a previous slot claimed
something was done and you found it was not, say so plainly; that correction is the
most valuable thing this file can carry.
