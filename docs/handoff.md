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

**Written:** 2026-10-10 · **HEAD at write:** `90cb95d` + the wave 73 commit (`git log -1`) ·
**Tree:** clean after the commit, apart from untracked `.agents/` and `.codex/`.

**Read before editing:** footage is chosen in `assets/local_provider.py` - keyword (whole words,
every word of the folder name; a plain-word name such as Steep needs a capital or a gaming
topic), alias, game-sport, domain, seed, run-domain, llm. No folder and a topic about games ->
`(None, "mix")`: one clip per owned game folder in turn. A sport, film or finance topic gets
nothing and falls to stock. The operator's call of 2026-10-10; it reverses #955 for the gaming
case only - do not "fix" it back. A report passes `context=(seed, sport)` and never
`set_footage_context`. `weekly_report.three_decisions` ranks after shrinkage (#352).

**Cursor:** your five are untouched (#1080 #1081 #1066 #1083 #1072). For #1072:
`ops weekly-report` already prints "cost per finished minute" - check before building.
Shared files touched: `apis/topic_tokens.py` (`GAME_NAMES_THAT_ARE_WORDS`),
`tests/regression_corpus.json` (3 cases appended), `docs/roadmap.md`, `docs/README.md`.

**Defects first:**
- #1113 `ops growth` and the scoreboard name the best video by its upload note, not its title.
- #1114 run 59 has no stored sport, so `ops footage-gaps` calls it a mix.
- `main` is ahead of origin. Nothing was pushed.
- CGFtzpiA1so and run 120's "LINK" source are still the operator's to check.

**Shipped:** wave 73 - #1112 #1111 #1054 #1061 #1076. 25 of 29 new tests failed first; 4 are
guards. Highest #1114. Next: **#1080 · #1081 · #1066 · #1083 · #1072** (yours).

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
