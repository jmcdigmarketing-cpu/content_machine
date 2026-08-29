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

**Written:** 2026-08-28 · **HEAD at write:** `43a34bf` · **Tree:** clean

- **Backlog is now 455 open, highest #644.** Added #481–#644 (164 items) weighted
  to what the desktop programme does not cover. `ops roadmap-index` for counts —
  never hand-count.
- **The Craft wave is in `roadmap.md`, and its ordering rule matters:** video craft
  is permanent (burned into every video, no toolkit change touches it), terminal is
  the daily driver for the 16–19 waves the app takes, and **booth chrome dies with
  Stage 3** — so only the cheapest booth items are worth doing at all. Do not
  reorder this without reading why.
- **Stage 0 still goes first** because the Craft wave reads its design tokens
  (#170). Polishing before tokens exist invents the palette twice.
- **Five inert features found by reading, filed as #641–#644:** six ANSI themes
  that no channel can reach (`ui_theme` is `None` everywhere, so "themeable skins
  shipped 2026-07-02" has never rendered), an empty `tts_voice_pool`, unset
  `local_tts_voice`, and two `.env.example` keys read nowhere. **#644 is the
  config-coverage test that catches this class** — build it before hunting more by
  hand.
- **Measured, if you touch performance:** CLI start 1.89s, of which
  `elevenlabs.client` 0.51s + `googleapiclient` and `sports.espn` 0.68s are eager
  imports a session may never use (#607–#609). Env surface 392 read vs 273
  documented (#639).
- **Two signals are failing on every run** and should be retired rather than
  repaired per decisions §19: `trendingnow.games` DNS, and YouTube RSS id
  `UCq-Fj5jknLsUf-MWSik4vhQ` 404 (#583, #584).
- **Still open from before:** 49 items carry no size tag (#632). Three test doubles
  drifted from their real signatures this week (#625) — when you add a parameter,
  check the fakes.

## Slot — Cursor

**Written:** _(not yet written — this slot has never been filled)_ · **HEAD at write:** `—`

When you write this slot, replace this paragraph. Say what you changed, what you left
uncommitted, and what you found broken — defects first. If a previous slot claimed
something was done and you found it was not, say so plainly; that correction is the
most valuable thing this file can carry.
