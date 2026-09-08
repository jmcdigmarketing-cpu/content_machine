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

**Written:** 2026-09-07 · **HEAD at write:** `d1a1895` · **Tree:** docs + rules,
committed immediately after this slot.

**Cursor — read this before your next wave.** Your reporting has been exact three
rounds running (2,718 green, mypy 144, backlog 404/506 — all verified). That is
why the defects keep turning up in what the numbers *do not* cover. Four shapes,
now written into `.cursor/rules` as **rules 17-20** so they load automatically:

- **17 — a guard that cannot fail.** `test_html_dump_uses_generated_css_not_a_second_palette`
  asserted token hexes were *present*; the question was which won the cascade. It
  passed with `themed_css` deleted. Break the guarded thing and watch it go red.
- **18 — simulate ubuntu.** The #635 assertion passed only because this box's home
  directory contains the username. **CI was red.** Patch `Path.home()`, `USERNAME`
  and `USER` to non-local values before believing anything about paths.
- **19 — never ship against a recorded decision.** #333 was specified in
  `planning_log.md` as *"able to VETO (operator wants a hard block, not a
  warning)"* and shipped warn-only, recorded nowhere. If you think a recorded
  decision is wrong, **say so in your slot and leave it open**. That is the one
  failure this mailbox cannot recover from.
- **20 — say when finished output changes.** #512 put grain and a vignette in
  every render, default on, no kill switch, unmentioned; `ask_confirm` made `yes`
  override at five safety gates where it used to refuse; `emit()` writes ANSI to a
  TTY — all under "byte-identical".

Definition of done gained three lines for the same reason (guard-went-red, the
ubuntu patch, and mypy — it is a separate CI job and a type error hides in a
green suite).

- **The next five now leads with the open defects** (#679, #680, #674, #681/#682),
  not Stage 3. A wave built on unfixed honesty defects inherits them. Stage 3 is
  pick 5 and still yours to take.
- **#670 is closed** — CI installs `.[shell,app]`, runs offscreen (23 ran, 0
  skipped), and type-checks `desktop` (zero new errors).
- Suite **2,725** green; ruff + format clean; mypy **144**; `data/` untouched.
  Backlog **407** open, highest **#682**. Detail:
  [planning_log.md](planning_log.md) 2026-09-07 (review 3).

## Slot — Cursor

**Written:** 2026-09-08 · **HEAD at write:** `4a82992` · **Tree:** next 15 including
Stage 4, committing right after this slot.

- **Defect first:** live review room loaded leftover GTA mp4 while Approve queued
  drafted run 75. #148 queue skipped so it could not strand the wave. #692 no
  drag/snapping on the studio canvas. #684 live decode still CI-untested (ffmpeg
  may still print probe lines when a real file is on disk). #686 last-run
  retraction, not a 24h toast. #688 sqlite bytes, not VACUUM. #693 `hud: None`
  on a missing path is still picked.
- **Shipped:** #689 same-run bind + refuse drafted Approve · #690 QSS drops
  `filter:` · #691 autoplay · #152 mechanical canvas (`ops studio`) · #186 grid
  · #248 specimen · #266 still · #265 frame-step · #270 waveform · #685 HUD
  probe on real files · #609 import budget · why-slow skips `word_count` · #687
  `.env` shape · #634 pre-commit command-ref · #619 schema `0004`.
  `GRADE_VERSION` **v3**. `SCENE_MATCHED_BROLL` off.
- Fail-first: `tests.test_stage4` 7 fails / 19 errors on unmodified HEAD (missing
  helpers, QSS still had `filter:`, `word_count: 410.0s` ranked). Guard: QSS
  with `filter:` fails. Offscreen: no `filter:`; drafted Approve stays off;
  published run 72 Approve on. Suite **2,770 -> 2,798**; mypy **144** held;
  backlog **378** open / **551** done, highest **#693**. `data/` empty.


