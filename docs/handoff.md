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

**Written:** 2026-10-16 evening · **HEAD at write:** `80d5141` (wave 97) + the wave 98 commit
(`git log -1`) · **Tree:** clean of mine after the commit; leave `.agents/` and `.codex/`.
Pushed (no Cursor commit sat under mine).

**Cursor - your queue, from the operator (2026-10-16):** first your own five, **#1215 #514
#418 #463 #545**; then these five, filed with their evidence in `docs/backlog.md`:
**#1221** a neutral headline made a gaming best bet by its feed (`core/best_bet._domain_for_feed`
- with #1215), **#1227** the correction scan fetches URL fragments every run
(`core/correction_dossier.py`, `description_extras.collect_source_urls`), **#1228** a fast-cut
shot timed out at 120 s (`assets/fast_cut.py`), **#1229** one overnight draft per child process
(`core/overnight.py`), **#1043** clip index tagged by team. Commit locally, one commit per item
or pair, each test failing first - **do not push**: Claude reviews, corrects and pushes your
commits in the operator's next prompt.

**Shared files of mine (committed and pushed - read before editing):** `core/nightly_task.py`
(`record_overnight`, `overnight_stop_line`), `scripts/ops.py` (`cmd_overnight` records its start
and finish), `core/review_booth.py` (`_pulled`), `core/publish_blockers.py` (the record's quality
wins), `apis/topic_variants.py` (`_subject_terms` whole names, `_is_label` folds hyphens),
`core/title_generator.py` (`broken_team_name`, `title_cut_off`), `core/authenticity.py` (stance
patterns), `core/content_engine.py` (`_maybe_inject_insight`: calm intents get the neutral beat,
not own ideas or hope), `core/batch_review.py`, `tests/__init__.py` (`OVERNIGHT_RECORD_FILE`).

**Read before editing:** topic words come from `apis/topic_tokens` - `_subject_terms` was a
private tokenizer and split "New England". `#660`'s "a calm explainer gets no beat" is reversed by
the operator (#1226); its test now asks for the "what to watch" beat. mypy 96.

**Defects first:**
- Overnight is paused: the shelf holds 3 (155 and 126 queued, 114 never uploaded) and nothing
  sends uploads. Run 157 is clean and next in line.
- The 10-16 crash's cause is unknown; `faulthandler` will name it next time.

**Shipped:** waves 97-98 - #1222-#1226. 8 of 8 and 8 of 13 tests failed on `dd9e131` first.
Corpus 276. Highest filed #1229.

**In progress:** nothing claimed. Next prompt: review Cursor's commits, correct, push.

## Slot — Cursor

**Written:** 2026-10-15 · **HEAD at write:** `1bf7c72` · **Tree:** this wave is
uncommitted until the commit that follows. Claude's waves 93-94 are uncommitted
on `core/authenticity.py`, `core/batch_review.py`, and
`tests/test_insight_and_holds.py`. They are not in this commit. Leave
`.agents/` and `.codex/`.

**Defects first:**
- An untagged Contender Series headline is still nba. Filed #1215. #1210-#1214
  are Claude's.
- The run id is bound only after `record_content_run`.

**Shipped:** #1184 #1209 #1208 #456 #392. Each new test failed first. Live
doctor: `Apify: operational`. Suite 5914, one failure in
`test_happy_path_saves_draft_and_meta`: Claude's uncommitted
`core/batch_generation.py` leaves the verdict empty. mypy 96.
`roadmap-index`: open 298, done 942, numbered open 246, highest #1215.
Next: #1215 #514 #418 #463 #545.
