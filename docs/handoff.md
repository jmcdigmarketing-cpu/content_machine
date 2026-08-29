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

**Written:** 2026-08-28 · **HEAD at write:** `c66a250` · **Tree:** clean

- **The roadmap is now four files.** `roadmap.md` (111 lines, what to do now) ·
  [`desktop_app.md`](desktop_app.md) (the Windows app programme) ·
  [`backlog.md`](backlog.md) (all 291 open items) ·
  [`roadmap_archive.md`](roadmap_archive.md) (history, no open work). Counts
  reconcile exactly against the 1,981-line original. **Use `ops roadmap-index`,
  never hand-count** — the old header was wrong by one for months.
- **Read `desktop_app.md` before touching anything app-shaped.** #141 is retired
  as a checkbox: it was the container for 21 other items, and it is now 8 staged
  waves. Toolkit is **PySide6/Qt**, decided against WebView2 and written down with
  the reasoning.
- **Every XL and L now has a decision** — 6 XL → 0 (two retired outright on the
  private/local constraint), and of 34 L, 21 became app stages and 3 were retired.
  Do not re-open a retired item without reading why in `desktop_app.md`.
- **Next is Stage 0 — Seams** (one wave, no window): the `ask()` seam over
  `main.py`'s 15 blocking prompts, the `emit()` output sink, design tokens (#170).
  The terminal must stay byte-identical; there is a scripted test backend for
  `ask()` so this is provable rather than assumed.
- Earlier today: the run-73 defect wave (reaction angles, web-search recency,
  yt-dlp quiet, fact budgets). Detail in planning_log 2026-08-28.
- **Known, not yet done:** 49 open items carry no `[S/M/L/XL]` size tag —
  `ops roadmap-index` reports the count. Worth a tidy pass.
- **Watch for this**: three test doubles this week mirrored the caller instead of
  the real library and passed while the real path was broken. When you add a
  parameter, check the fakes.

## Slot — Cursor

**Written:** _(not yet written — this slot has never been filled)_ · **HEAD at write:** `—`

When you write this slot, replace this paragraph. Say what you changed, what you left
uncommitted, and what you found broken — defects first. If a previous slot claimed
something was done and you found it was not, say so plainly; that correction is the
most valuable thing this file can carry.
