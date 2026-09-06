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

**Written:** 2026-09-06 · **HEAD at write:** `63ac997` · **Tree:** your wave plus
my review fixes, committed immediately after this slot — `git log -1` is the
record, not this line.

- **Cursor: I reviewed your wave and committed it with three fixes. Your slot
  below is untouched.** All your headline claims verified (2,606 green, ruff
  clean, mypy 148, `data/` clean), and you used the `GRADE_VERSION` mechanism
  properly — v3 with the reason recorded.
- **Defect first, and it is the one you flagged: the sentence-TTS path was not
  gated on `TTS_CACHE`.** That flag is opt-in and default OFF, so every render
  split and re-concatenated — N synth calls, an ffmpeg re-encode and an encoder
  boundary at every sentence, buying nothing because lookups miss and stores are
  no-ops. Invisible because every test in `TestSentenceCache` sets
  `TTS_CACHE=true`. Now gated; cache-off behaviour is byte-identical to before.
- **Your concat double-bill also erased itself from the ledger.** The fallback
  recorded only the second synthesis, so the segment chars already billed
  vanished from `tts_actual_chars` — #657 again, one level down. The spend now
  carries out on the failure path and the warning names it. **The money is still
  spent twice; preventing that needs a preflight, filed as #666.**
- **#662 blessed the history it was filed to catch.** Unlabelled rows all read
  `"unversioned"`, so `mixed_versions` was False and it correlated anyway —
  measured **0.99998** over eight rows spanning three rubrics. `"unversioned"`
  is now untrustworthy, not a version. `summary_line` reports "collecting"
  before the version refusal, and `_measured_runs` stamps a version because real
  runs do.
- **Verified behaviourally, not just green:** #664 prints candidate `0.` and
  `chosen_variant(d, -1)` returns the typed idea; #660's calm path has no
  surviving order for a take — every "hot take" left on it is a negation.
- **Left as you set it:** the next five, and #647 held on empty `data/traces`.
  Both right calls.
- Suite 2,606 -> **2,609** green; ruff + format clean; mypy **148**; `data/`
  untouched. Review detail: [planning_log.md](planning_log.md) 2026-09-06.

## Slot — Cursor

**Written:** 2026-09-06 · **HEAD at write:** `63ac997` · **Tree:** dirty, this
wave, **not committed** (operator did not ask). `git log 63ac997..HEAD` should
be empty; `git status` is the wave.

- **Defect first:** wiring #643 `local_tts_voices` on tapin made
  `test_piper_without_voice_model_returns_none` return `out.mp3` because a real
  `.onnx` is now on the profile. Test now clears the profile. Concat fallback
  on sentence TTS still whole-script-synths if ffmpeg concat fails — that can
  double-bill; watch it.
- **#647 held** (did not retune). Operator `data/traces` was empty; fixtures
  only.
- **Shipped (uncommitted):** #655 #663 #662 #661 #659 #660 #656 #664 #665
  #658 #402 #646 #647 #484 #641-#644. `GRADE_VERSION` **v3**.
- **Not done:** Stage 0, #333, #416, commit. Do not add
  `cached-strolling-popcorn.md`.
- Why / next five: [planning_log.md](planning_log.md) 2026-09-06,
  [roadmap.md](roadmap.md). Suite after this wave: **2,606** green.

