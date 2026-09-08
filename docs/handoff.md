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

**Written:** 2026-09-08 · **HEAD at write:** `1f2082f` · **Tree:** clean after this
commit — docs only, no code touched this pass.

- **Defect first:** nothing new found; this was a read-only refamiliarization pass.
  Still open and unchanged: **#699** `_CSS` regrowing a second hex palette ·
  **#700** `claim_next` dropped `LIMIT 1` · **#701** `"this weekend"` resolves to
  Saturday noon on a Saturday evening · **#684** live decode still CI-untested ·
  **#112** dossier still does not auto-fire (#686 only toasts).
- **Committed Cursor's uncommitted docs tree** — the two GPT-6 files plus the
  planning_log / HANDOFF_SYNOPSIS pointers. They were sitting untracked; that is
  the fifth time work has been left in the tree, so it is now in git.
- **Read the GPT-6 pair.** Opinion, briefing-based, not a repo inspection — it does
  not override the roadmap. Its diagnosis converges with review 4 independently:
  the recurring shape is integration failure that looks like success. Three of its
  "first" items are already ours (#700 single-job claiming, #701 date freshness,
  #684 a real tiny-video test). **Unresolved for the operator:** it says defer
  caption choreography and visual polish, and #151 / #153 sit at 4 and 5 in the
  next five. Do not silently reverse that either way. `SCENE_MATCHED_BROLL` stays
  off (part 2 item 6).
- No suite run this pass — no Python changed. Last measured at `1f2082f`: **2,833**
  green, mypy **139**, backlog **361** open / **576** done, highest **#701**.
  Next five unchanged: **#699 · #684 · #112 · #151 · #153**. Review-4 detail:
  [planning_log.md](planning_log.md) 2026-09-08.

## Slot — Cursor

**Written:** 2026-09-08 · **HEAD at write:** `1f2082f` · **Tree:** docs only, uncommitted.

- **Defect first:** none from this pass. Open from Claude still stand: #699
  token hex · #700 `LIMIT 1` · #701 `"this weekend"` · #684 live decode ·
  #112 dossier. GPT-6 parts 1–2 are opinion, not recorded decisions — do
  not silently reverse the current next-five. Do not enable
  `SCENE_MATCHED_BROLL` from part 2 item 6.
- **Saved:** [gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md)
  and [gpt6_part2_upgrades_2026-09-08.md](gpt6_part2_upgrades_2026-09-08.md).
  Pointers in planning_log + HANDOFF_SYNOPSIS. No code. Not committed.



