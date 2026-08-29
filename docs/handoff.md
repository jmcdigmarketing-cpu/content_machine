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

**Written:** 2026-08-28 · **HEAD at write:** `b0beed0` · **Tree:** clean, 6 commits

- **The tree is committed and green** — 2,381 tests, ruff clean, `data/` untouched.
  Six commits: agent comms, NVENC, edge-tts, signals/dup/ingest, the 23-item wave,
  docs. Previously 78 modified / 34 untracked, which is what this mailbox exists for.
- **The trailer ban is lifted** (operator, 2026-08-28). `.githooks/commit-msg` now
  warns on a missing `Co-authored-by:` instead of rejecting one, and still refuses
  "Generated with". Sign your commits — `py -m scripts.ops agents` shows the split.
- **Cursor: your slot has never been written.** That is the one open item in this
  channel. Rules 14–16 in `.cursor/rules/content-machine.mdc` are the contract.
- **Defects fixed in work that was already green** (detail: planning_log 2026-08-28):
  #419 was inert on the ASR-timed caption path; NVENC fallback broke #309's argv
  promise; #369 could never fire; #394 quarantined healthy off-domain signals;
  edge-tts spoke its own SSML for 23.76s and wrote no word timings; #433 blocked the
  one cross-channel case the operator allowed.
- **Left open on purpose:** #355 recomputes its residual on every metrics sync (needs
  a publish-time prediction — schema change); #340's sidecar has a null
  `ungrounded_count` (written before `build_quality`).
- **Not done, needs the operator:** the CUDA torch wheel (multi-GB) — `ops doctor`
  stays FAIL-visible on `cuda` until then, and it gates nothing.
- **Next:** #416 scene-beat cuts (now unblocked by #417's ingest), and #333 as the
  narrowed backstop the operator specified — a retracted claim is a hard block.

## Slot — Cursor

**Written:** _(not yet written — this slot has never been filled)_ · **HEAD at write:** `—`

When you write this slot, replace this paragraph. Say what you changed, what you left
uncommitted, and what you found broken — defects first. If a previous slot claimed
something was done and you found it was not, say so plainly; that correction is the
most valuable thing this file can carry.
