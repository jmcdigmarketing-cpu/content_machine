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

**Written:** 2026-08-28 · **HEAD at write:** `5959440` · **Tree:** 72 modified, 32 untracked (nothing committed)

- **Nothing in this wave is committed.** The whole 23-item wave plus edge-tts, clip
  ingest, #389 and #433 exists only as working-tree changes. A fresh clone or CI sees
  none of it.
- Finished the 23-item wave (NVENC #38, FastAPI shell #147, CUDA doctor + 20 from
  331–480). Suite went 2,296 → 2,347.
- **Defects I found and fixed in work that was already green:**
  - `#419` did nothing on the caption path that actually ships — the rebalance was in
    `split_script_into_lines` (estimated timing) while real runs use
    `caption_timing.group_into_lines`. Fixed both.
  - NVENC fallback broke `#309`: the persisted "success" argv was the **failed**
    `h264_nvenc` command. `video/encoder.py::executed_cmd` now reports what ran.
  - `#369` could never fire — it estimated from `script=""`, pricing TTS at $0, so a
    realistic `PROJECTED_COST_MAX_USD` was unreachable. Its own test asserted
    `script == ""`, pinning the bug.
  - `#394` quarantine used a denylist; `rawg`/`odds`/`sports` return bare INACTIVE when
    off-domain, so three off-domain topics in one batch disabled RAWG. Now an allowlist.
  - **edge-tts spoke the XML**: `Communicate` escapes its input, so `edge_ssml()` made a
    3.94s line synth as **23.76s** of "speak version equals one point zero". Now uses
    `apply_pronunciation_lexicon`; `edge_ssml` deleted. Also `boundary="WordBoundary"` —
    7.x defaults to SentenceBoundary, so `.words.json` was never written.
  - `#433` blocked the one case the operator allowed: `infer_domain` reads by subject,
    so "GTA 6 economic impact" classified `gaming`. Added `_lens_for` treatment cues.
- **Left open on purpose:** `#355` residual is recomputed on every metrics sync;
  `#340` sidecar has a null `ungrounded_count` (written before `build_quality`).
- **Verified for real, not by probe:** NVENC encodes on this box (1080x1920 h264, exact
  duration); edge-tts synthesises against the live endpoint with 11 real word timings.

## Slot — Cursor

**Written:** _(not yet written — this slot has never been filled)_ · **HEAD at write:** `—`

When you write this slot, replace this paragraph. Say what you changed, what you left
uncommitted, and what you found broken — defects first. If a previous slot claimed
something was done and you found it was not, say so plainly; that correction is the
most valuable thing this file can carry.
