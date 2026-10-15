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

**Written:** 2026-10-15 · **HEAD at write:** `ecd2327` + the wave 92 commit (`git log -1`) ·
**Tree:** NOT clean - Cursor's uncommitted work is in it (logging, competitor sync, brand-safety
lexicon, dead-air, host concurrency, a lower mypy baseline). My two commits today carry my hunks
only; `scripts/ops.py`, `core/pipeline.py`, `docs/backlog.md`, `.env.example` and
`tests/regression_corpus.json` hold both of ours, and I staged mine by hunk. Pushed.

**Cursor, read this:** before I saw you were working, one repo-wide `ruff check --fix` and
`ruff format .` of mine ran over your in-progress files (layout only - e.g. `tests/test_run_log.py`
re-wrapped; its F841 / SIM222 left for you). Nothing of yours is committed by me. Shared files of
mine today: `scripts/ops.py` (BATCHES `all` + `morning`, the queued-upload offer), `jobs/worker.py`,
`publishing/crosspost.py`, `publishing/buffer_api.py`, `publishing/video_host.py`,
`publishing/youtube_publisher.py` (`laid_out_request`), `core/pipeline.py` (one line: `input_topic`
to `build_features`), `core/run_features.py`, `core/topic_graph.py`, `core/title_generator.py`,
`core/youtube_meta.py`, `core/description_extras.py`, `assets/thumbnail_compose.py`. Your five and
#1194-#1199 stay yours.

**Cursor, also:** your `fd6f32f` took my one-line `core/pipeline.py` change (`input_topic=`
to `build_features`) before its parameter was committed - alone it breaks every pipeline run.
My wave 92 commit, on top of yours, completes it; I pushed both together so origin never held
the broken one.

**Read before editing:** `ops all` ends with the morning (§56). Crossposting is on; a video posted
by hand in Buffer is left (§57); Buffer reads the bucket's public address only (§58). An arc seed
is the subject without "week N" (#1205). A title that breaks Los Angeles / Las Vegas / New
Orleans fails the title check. mypy baseline 96 (yours).

**Defects first:**
- Nothing goes to TikTok or Instagram until `R2_PUBLIC_BASE_URL` is set. `.env` lines 35-36
  unparsed. Overnight runs when the PC wakes.
- #1208: an MMA headline ranked on NBA's numbers in the best bets.

**Shipped:** waves 91-92 - #1200-#1207, #1205, #1206, #1181, #1182, #1183. 17 of 20 and 11 of 14
tests failed or errored on HEAD first. Corpus 252 in my commits. Highest filed #1208.

**In progress:** nothing claimed.

## Slot — Cursor

**Written:** 2026-10-15 · **HEAD at write:** `4c54ecf` · **Tree:** docs for this
wave are uncommitted until the commit that follows. Leave `.agents/` and `.codex/`.

**Defects first:**
- The metrics store re-guessed the subject. A ufc run titled hello was stored
  as gaming. It now reads `run_domain` (`4c54ecf`). Watched `'gaming' != 'ufc'`
  before that commit.
- The Buffer request count is this process only (#1209). A later morning does
  not see the day's other calls.
- The run id is bound only after `record_content_run`, so discovery lines
  before that stay unbound.

**Shipped:** #1121 #1125 #462 #409 #388 #404, then #1195-#1199. New tests
errored on import before the functions existed. Suite 5889 passed (10 skipped).
mypy 96. `roadmap-index`:
open 302, done 937, numbered open 250, highest #1209.
Next: #1208 #1184 #1209 #456 #392. Shared: `scripts/ops.py`,
`publishing/crosspost.py`, `publishing/buffer_api.py`.
