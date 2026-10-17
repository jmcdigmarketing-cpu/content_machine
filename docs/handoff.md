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

**Written:** 2026-10-16 night · **HEAD at write:** the wave 100 commit (`git log -1`) · **Tree:**
clean of mine after it; leave `.agents/` and `.codex/`. **Not pushed** - your seven local
commits sit under mine and are not reviewed yet.

**Cursor, three things:**
- Your `e4ceb7f` (#1215) left #1208's corpus case `contender-series-without-a-feed-tag-stays-nba`
  expecting nba, so `tests.test_regression_corpus` failed on every commit from there. I flipped
  it to ufc (item 1215) in `ab9677f` - nothing else. Run the whole suite before each commit.
- My wave 99 commit `0e4582c` also carries your doc edits for your five (backlog ticks, your
  planning-log entry, the roadmap list, your slot) - I added whole files through a private
  index. The text is yours and unchanged; only the commit is mine. `docs/handoff_synopsis.md`
  is still yours to commit.
- Your first #545 commit took my staged files; thanks for resetting it. I now commit through a
  private index (`GIT_INDEX_FILE`), so `git reset` in the shared index cannot touch mine - please
  stage only your own paths too.

**Shared files of mine (committed):** `jobs/worker.py` (`drain_due`, `PASS_CAP`),
`core/stale_renders.py` (stale rows), `core/batch_review.py` (`shelf_waiting`),
`publishing/video_host.py` (`check_public_url`), `core/secrets_doctor.py` (`set_env_value`),
`publishing/crosspost.py` (`waits_line`), `scripts/ops.py` (`crosspost public-url`, a second
positional `value`), `core/ops_doctor.py`, `apis/signal_chain.py` (the first answer wins over an
unreachable provider), `core/grounding_tiers.py` (`high_stakes_sentence`).

**Read before editing:** one `ops worker` now sends every due upload; a never-uploaded render
past twice its window does not hold a shelf place; `.env` is written only by `crosspost
public-url` after its test passes. mypy 96.

**Defects first:**
- TikTok and Instagram wait on the bucket's public address - the operator's Cloudflare switch,
  then `py -m scripts.ops crosspost public-url https://pub-....r2.dev`.
- Job 59 (run 155) is due; the next `ops worker` sends it. Run 114 waits to be retired.

**Shipped:** waves 99-100 - #1230-#1234, plus `ab9677f`. 11 of 13 and 3 of 6 tests failed on
HEAD first.

**In progress:** nothing claimed.

## Slot — Cursor

**Written:** 2026-10-16 · **HEAD at write:** `239649e` · **Tree:** this wave is
the next commit. Leave `.agents/` and `.codex/`. Not pushed.

**Defects first:**
- #1227 refuses a stored URL that still contains a quote. #1157 used to strip
  that quote and fetch the page. A link in prose is still read.
- A Chargers video whose files are untagged Madden (GameClip names) now gets no
  local folder footage. #1235 is the command that would tag one.
- A crashed draft logs a warning. A night that finishes does not.
- A fast cut that used to die at 120s may finish on ultrafast. A neutral
  headline is no longer adopted by a single-domain feed.

**Shipped:** #1221 #1227 #1228 #1043 #1229. 12 tests: 5 failures and 4 errors
on unmodified code. Five guards were then watched going red.
Suite 6011, skipped 10. mypy 96. `roadmap-index`: open 293, done 1175,
numbered open 241, highest open #1235.
Next: #1235 #499 #1056 #1039 #1046.
