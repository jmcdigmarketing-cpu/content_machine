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

**Written:** 2026-10-10 · **HEAD at write:** `4616fee` + the waves 75-76 commit (`git log -1`) ·
**Tree:** clean after the commit, apart from untracked `.agents/` and `.codex/`. Pushed.

**Read before editing:** a trace has no title, description or script - use
`review_booth.trace_run(trace)`. A video's name is `publish_log.video_title(row)`. A stored
feature key needs a reader (`tests/test_persisted_keys_read`). `READ_ALOUD_REWRITE` and
`TITLE_SUGGEST` are off in the suite. mypy baseline is **98**. Run `ruff check --fix` on named
files only: on the whole repo it rewrites the other agent's open files.

**Cursor:** shared files touched: `core/pipeline.py` (`is_all_angles`, `features["read_aloud"]`),
`core/content_engine.py` (the read-aloud pass, the beats line in the calm branch),
`scripts/ops.py` (`desc-fold`, `free-cost`, `publish-dry-run`, `competitor-health`),
`tests/__init__.py` (two flags, the reach store), `.env.example`, `tests/regression_corpus.json`
(5 cases), `mypy_baseline.txt`.

**Defects first:**
- `ops doctor` now FAILs on `reach`: the YouTube Reporting API is not enabled in the Cloud
  project. The operator's step; #1058 waits on it.
- #1063 is blocked: one competitor on the list, no view counts (#1120).
- #1121 a YouTube 500 on the competitor feed reads as "dead or wrong UC id".
- CGFtzpiA1so and run 120's "LINK" source are still the operator's to check.

**Shipped:** waves 75-76 - #1115 #1116 #1117 #1075 #1118 #1062 #1034 #1031 #1025. 56 of 61 new
tests failed first. Suite 5330, mypy 98. Highest #1121. Next: **#995 · #990 · #374 · #400 · #380**.

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
