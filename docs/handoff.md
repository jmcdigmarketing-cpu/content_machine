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

**Written:** 2026-10-16 · **HEAD at write:** `2fe6f3d` (wave 95) + the wave 96 commit
(`git log -1`) · **Tree:** clean of mine after the commit; leave `.agents/` and `.codex/`.
Pushed.

**Cursor:** two for you. **#1221** - overnight's draft 2 today was "TikToker Dr Food walks free
months after life sentence for smuggling drugs in sweets": `infer_topic_domain` says neutral, and
a gaming-tagged feed made it `gaming` in `best_bet._domain_for_feed` (beside your #1215; I did not
touch `core/best_bet.py`). **#1222** is filed, not taken: `ops blocking` describes run 139, a
pulled run. Shared files of mine: `core/nightly_task.py` (`stopped_line`, `overnight_stop_line`,
`enable_crash_traceback`), `core/batch_review.py` (`_timing_lines`, `drafts_made_since`,
`dead_reason` first in the gate, "n" sets aside), `core/run_quality.py` (`run_fact_count`),
`core/run_features.py` + `core/content_engine.py` (`fact_lines`), `core/publish_blockers.py`,
`core/batch_generation.py`, `core/facts/enrichment.py` (`used_fact_lines`), `core/data_quality.py`,
`config/settings.py` (`load_env_file`), `scripts/ops.py`, `scripts/worker_task.pyw`.

**Read before editing:** `key_facts_count` is still the pasted facts; `fact_lines` is what a run
was written from - read it through `run_quality.run_fact_count`. `config.settings` mutes
python-dotenv's "could not parse" record and logs the doctor's line instead. A dead draft (its
game started, or past its window) is the first reason in `unattended_block_reason`. mypy 96.

**Defects first:**
- Overnight crashed today at 4:32 PM after 1 of 3 drafts (0xC0000374, heap corruption, the only
  Python crash in 30 days; the WER report needs admin). Cause unknown - `faulthandler` is on now,
  so a next one names its Python line in `output\logs\overnight-last.log`.
- Nothing goes to TikTok or Instagram until `R2_PUBLIC_BASE_URL` is set. Run 126 is overdue (no
  worker task). 37 older runs keep `fact_lines`-less scores (outside the approved back-fill).

**Shipped:** waves 95-96 - #1216-#1220. 16 of 17 tests failed or errored on `58dafb6` first, and
10 of 12. Corpus 270. Highest filed #1222.

**In progress:** nothing claimed.

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
