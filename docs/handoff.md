# Handoff — the mailbox

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-10-09

**Read this first, before any other file, every time you start work here.** More than
one agent works in this repo and nothing signals a switch. This file is how the
previous one tells you what it did and what it broke.

Two slots. **Overwrite your own; never edit the other agent's.** Keep each slot under
~25 lines — this is a mailbox, not an archive. The archive is
[handoff_synopsis.md](handoff_synopsis.md) (session state) and
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

**Written:** 2026-10-10 · **HEAD at write:** `8069a82` + the wave 74 commit (`git log -1`) ·
**Tree:** clean after the commit, apart from untracked `.agents/` and `.codex/`. Pushed.

**Read before editing:** a video's name comes from `publish_log.video_title(row)` - never
`row.detail`, which is the upload's note (a test fails on a new reader). `publishing/prepublish.py`
runs inside `YouTubePublisher.publish` before any API call; add a check there, not a new gate.
Footage: `assets/local_provider.py` (whole words; a topic about games with no folder cuts the
owned mix - the operator's call, do not "fix" it back). `TITLE_SUGGEST` is `off` in the suite
and `report` for the operator; `reword` is opt-in on purpose.

**Cursor:** your five are untouched (#1080 #1081 #1066 #1083 #1072). Shared files touched:
`core/pipeline.py` (two lines: `features["title_suggest"]`), `core/content_engine.py` (the
suggest step after the title checks), `main.py` (`one_per_day=True`), `scripts/ops.py`
(`publish-dry-run`, `chapters`), `publishing/youtube_publisher.py` (the checklist call),
`tests/__init__.py`, `.env.example`, `tests/regression_corpus.json`.

**Defects first:**
- #1115 run 133 is stored as all-angles with one chapter and no 0:00 list.
- #1116 run 132's title spells "Illia"; suggest and the facts say "Ilia".
- #1117 `last_trace` has no title or mp4 path.
- CGFtzpiA1so and run 120's "LINK" source are still the operator's to check.

**Shipped:** wave 74 - #1113 #1114 #1065 #1055 #1050. 44 of 47 new tests failed first.
Suite 5258, mypy 109. Highest #1117. Next: **#1080 · #1081 · #1066 · #1083 · #1072** (yours).
**In progress (Claude, waves 75-76, uncommitted):** #1115 #1116 #1117 #1075 #1058 #1062 #1034
#1031 #1025 #1063 - skip these.

## Slot — Cursor

**Written:** 2026-10-10 · **HEAD at write:** `adbc3c7` · **Tree:** this wave is
uncommitted until the commit that follows. Leave `.agents/` and `.codex/`.

**Defects first:**
- #1088 is still an operator call.
- #1115 #1116 #1117 are Claude's, in progress. Left alone, with the rest of
  that note (#1075 #1058 #1062 #1034 #1031 #1025 #1063).
- The suite failed on uncommitted `angles_asked` in `core/pipeline.py`.
  That line is Claude's and is not in this commit.

**Shipped:** #1080 #1081 #1066 #1083 #1072. Eight tests failed or errored
first (UFC 322 offered on 2026-11-14, the label ended on "only", no published
minute line, the vault had no fact, `description_fix` missing). The dry-run
vault test was already empty. Next: #995 #990 #374 #400 #380. Shared file:
`scripts/ops.py`.
