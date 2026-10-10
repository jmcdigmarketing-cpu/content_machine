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

**Written:** 2026-10-10 · **HEAD at write:** `f98054c` + the wave 72 commit (`git log -1`) ·
**Tree:** clean after the commit, apart from untracked `.agents/` and `.codex/`.

**Read before editing:** footage is chosen in `assets/local_provider.py` - keyword (whole words,
every word of the folder name), alias, game-sport (`apis.topic_scorer.sport_of_game`), domain,
seed, run-domain, llm. No folder and a topic about games -> `footage_choice` records
`(None, "mix")` and `candidate_clips` returns one clip per owned game folder in turn; a sport,
film or finance topic gets nothing and falls to stock. That is the operator's call of
2026-10-10 and reverses #955 for the gaming case only - do not "fix" it back.
`core/owned_beats.topic_clips` uses the same rule. `core.win_shell.known_folder` is where
Desktop and Videos come from.

**Cursor:** shared files touched: `apis/topic_scorer.py` (`sport_of_game`, `names_other_2k`,
beside your `_VIDEO_GAME_RE`), `tests/regression_corpus.json` (14 cases appended),
`docs/roadmap.md` (the next five are unchanged and yours). `assets/fast_cut.py` not touched.

**Defects first:**
- #1111 "the steep price of GPUs" still names the Steep folder.
- #1112 `ops footage-gaps` has no run context, so a neutral soccer angle shows as a mix there.
- `main` is ahead of origin. Nothing was pushed.
- CGFtzpiA1so and run 120's "LINK" source are still the operator's to check.

**Shipped:** wave 72 - #1105 #1106 #1107 #1108 #1109 #1110. 24 of 28 new tests failed first; 4 are guards.
Suite 5182, mypy 109. Highest #1112. Next: **#1080 · #1081 · #1066 · #1083 · #1072** (yours).

## Slot — Cursor

**Written:** 2026-10-10 · **HEAD at write:** `c52b470` · **Tree:** this wave is
uncommitted until the commit that follows. Leave `docs/startup_powershell.md`.
Leave `.agents/` and `.codex/` untracked.

**Defects first:**
- #1088 is still an operator call.
- #1080 a chapter title still ends mid-phrase (run 119). Next, not built.
- A first public-source filter also dropped the Rockstar URL on a GTA topic.
  The shipped check is the fighter's last name only.

**Shipped:** #1102 #1103 #1104 #1045 #1052. Seven new tests failed first
(`kept_angle_topic` missing, `Lose` flagged, `Antonio` split, the Vegas URL
in the scored sources, one file took 7 shots, `pool_without_recent` missing,
the Short's tags were `GTA6`). The league-only source test passed before the
fix. Next: #1080 #1081 #1066 #1083 #1072. Shared file: `core/pipeline.py`.
