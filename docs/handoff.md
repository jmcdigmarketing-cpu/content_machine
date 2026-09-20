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

**Written:** 2026-09-20 · **HEAD at write:** `4324373` (wave 29 + wave 28 committing now) ·
**Tree:** one commit, both waves — the operator's call, not two.

**Defects first:**
- **#819 composite does not predict engagement: r=-0.15 over 12 publishes.** First real
  measurement, out of #805. The backlog asserted "uncorrelated" from a 40% hit rate; this is
  the correlation and it is faintly *negative*. Every tie broken on composite is a coin flip.
  `angle_scores` (#807) is the named successor and is itself unvalidated. Biggest open thing.
- **#822 hedging passes the render gate and only costs grade points.** #345 lets an
  unsupported rumor through *if hedged*; #800 then docks the grade per hedge. The cheapest
  route past the hard gate is what the soft score punishes. Your standing note, now filed.
- **#818 calibration is starved by history, not volume.** 37 rows have a grade, 12 an outcome,
  **3** both; `ops calibration` reads "collecting" for months and that is not a bug. And
  **#803's filed text was wrong** (rewritten): `core/authenticity.py:35` has always been
  `_RECENT_RUNS = 12`, never "one script deep".

**Yours to call, Cursor:** **#817** the recurrence pass reads all statuses; the item said
*published*, and narrowing `_recent_scripts` also narrows the similarity **gate**. **#820**
#811's `shutdown(wait=False)` abandons the straggler's thread — same trade you took on #802.
**#821** recurrence is report-only, no `GRADE_VERSION` bump. Untouched: footage folders,
igdb/steam 1/33.

**Watch for:** `with ThreadPoolExecutor(...)` joins on `__exit__`, so #811 drives the pool
explicitly; two fake pools (`test_wave8`, `test_wave9`) broke honestly on it.
`DISCOVERY_DEADLINE_S` is **unset by default**.

Suite **3,437 -> 3,462**; mypy **139** (drifted to 141 behind a green suite, back now); ruff
clean; `data/` untouched. Backlog **326 open / 729 done**, highest **#822**. Next five:
**#818 · #817 · #822 · #819 · #739**.

## Slot — Cursor

**Written:** 2026-09-20 · **HEAD at write:** `8f141c4` · **Tree:** wave 27 committing.

**Defects first:**
- **igdb 1/33 and steam 1/33 stay registered.** #810 retired the true zeros only;
  the known-gap test documents current behaviour. A second empty window, or an
  operator call, would close it. Not silently treated as §19 zero.
- **#345 still lets a hedged rumor through the render gate.** Wave 26 #800 is
  grade-only; this wave did not touch it.
- **TTS cache is on with nothing in it yet.** First live synth still has to
  populate `data/tts_cache`. Suite pin stays `TTS_CACHE=false`.
- **Hung brief/scoring workers are abandoned, not killed.** `shutdown(wait=False)`
  returns; the thread may still run until the provider finishes. The operator
  sees the fallback, not a 138 s / 185 s stall.
- **Untracked footage folders are not this commit:**
  `video/backgrounds/gaming/{multiplayer games,open world,other}/`. Operator
  intake from a parallel Cursor session; `footage-add` licence-file covering a
  mixed GTA folder is still a live footgun if those files are committed later.

**Shipped #806 #807 #810 #812 #802.** Reject `n` then
`Why? [pace / facts / angle / hook / topic / other]:` → `review.reason`.
`score_spread` on recorded angle fixtures. tapology/stats_context/tvmaze/tmdb
retired (modules kept). Overnight retention line, published mp4+sidecars
exempt, apply env-gated. Brief deadline 30 s / scoring deadline 15 s.

**Operator paste:**
```
Why? [pace / facts / angle / hook / topic / other]:
Signals retired: stats_context, tapology, tmdb, trendingnow, tvmaze
```

**Next five:** **#808 · #811 · #803 · #805 · #50**.

Suite **3,406 -> 3,425**; mypy **139**; ruff clean; `data/` untouched. Backlog
**325 open / 720 done**, highest **#811**.
