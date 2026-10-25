# Cloud brief — wave 128, tonight's default (October 2026)

> **Class:** plan · **Status:** living · **Reviewed:** 2026-10-24

The operator, 2026-10-24 evening: *"lets continue with plan making and documentation. write a
mockup to take into the cloud, which will be default for tonight."* This page is that wave: a Claude
cloud session builds it tonight from origin's `main`, the way waves 121-122 were built in the cloud.
Every item was diagnosed on the operator's PC the same afternoon, with the measurements below;
each fix comes with the test data it needs, because **the cloud has none of the PC's data** - no
`data/` (traces, snapshots, quota), no `output/`, no database, no keys.

Every item is a numbered line in [backlog.md](backlog.md) (the spec's source); the operator's two
answers are [decision 76](decisions_2026-10.md). This page is the order, the files, the test data and
the definition of done.

## Start here - the prompt to paste into the cloud session

```text
You are Claude Code in a cloud session on content_machine. Tonight's default is wave 128.
1. git pull. Read docs/handoff.md first (both slots), then docs/cloud_brief_2026-10.md in full:
   it is the order, the files, the test data and the definition of done. Each item's backlog line
   in docs/backlog.md is its source.
2. Work the wave with the next-five skill (.claude/skills/next-five/SKILL.md) and tdd: every new
   test fails on the unmodified code first; say how many did in the commit.
3. You have no data/, output/, database or keys. Build and test from the brief's fixtures only.
   Leave the brief's LOCAL checks for the PC session and list them in your handoff slot.
4. Done: ruff check . ; ruff format --check . ; python scripts/mypy_ratchet.py (92 or fewer) ;
   python -m unittest discover -s tests -t . -v ; python -m scripts.ops test --order reverse.
5. Commit to main signed "Co-Authored-By: Claude <noreply@anthropic.com>", push, read CI
   (gh run list). Then the docs in the skill's order, your docs/handoff.md slot last.
Nothing outward: no uploads, schedules, claim confirmations, sign-ins.
```

## Ground rules for this wave

- **Defects first, cheapest first** - the order below. The finished-game item (6) is last so it cannot
  strand the rest.
- Before editing a file: `python -m scripts.ops regressions <file>` lists the old fixes guarding it.
  A defect gets a case in `tests/regression_corpus.json` - **append in place, never re-serialize the
  file**. Expectation keys: `equals`, `contains`, `not_contains`, `includes_all`, `excludes_any`,
  `truthy`, `falsy` (`core/regression_corpus.py`).
- Do not touch `core/cost_meter.py`, `apis/apify_client.py`, the quota state or `data/`. Signals keep
  `make_signal()`'s shape (`apis/CLAUDE.md`). Topic words come from `apis/topic_tokens`.
- Tests: `unittest.TestCase`, no network, no writes to `data/` or `output/` (`tests/CLAUDE.md`). New
  tests go in `tests/test_wave128.py`.
- The PC's overnight run imports the PC's own checkout, not origin - pushing tonight cannot affect it.

## The wave, in build order

### 0. #1570 - the suite stops reading the operator's experiment store

`data/experiments.json` exists on the PC since 14:50 on 10-24 (overnight's first hook-rewrite
assignment, #1502). `config.paths.EXPERIMENTS_FILE` is the one `data/` store `tests/__init__.py` does
not redirect, so on the PC `test_wave17` (2 tests) and `test_stage3_honesty` (1) fail the #1305
guard - "this test opened the operator's data/ (data/experiments.json via core/experiments.py:50
_load)" - and a test that records an assignment would write into the operator's live arms. CI has
no `data/`, so it is green.

- Fix: `patch.object(_paths, "EXPERIMENTS_FILE", _suite_store("experiments.json"))` beside the other
  `_paths` redirects (`core/experiments` imports the name inside each function, so patching the
  module attribute reaches it). The five tests that patch `EXPERIMENTS_FILE` themselves must still.
- Test: under the suite, `config.paths.EXPERIMENTS_FILE` is inside the suite store, not `data/` - it
  fails today.
- **LOCAL:** in the PC's checkout, `python -m unittest tests.test_wave17 tests.test_stage3_honesty`
  passes.

### 1. #1560 - the claim check sees ESPN's record

Run 185 ("Chiefs vs Seahawks NFL Week 7 picks") was held for "The Chiefs are 5-0". Two causes:

**(a) A date read as a record.** `core/facts/conflicts._RECORD_RE`
(`\b(\d{1,2})\s*-\s*(\d{1,2})(?:\s*-\s*(\d{1,2}))?(?!\s*%)`) finds "10-14" inside "2026-10-14". The
operator lines were dated headlines, so `find_fact_conflicts` called ESPN's record a disagreeing
record and `drop_conflicting_lines` removed it (5 lines dropped) before the claim check ran.

- Fix: a record is never part of a longer dash-joined number - no digit or `-` immediately before
  it, none after it. Same guard on the record cue in `apis/nfl_entities._SPORT_CUES`
  (`\d{1,2}-\d{1,2}`), which today makes `team_names_in("2026-10-14 · best phone chargers")` return
  `["Los Angeles Chargers"]`.
- Test data (verbatim shapes from run 185):

```python
OPERATOR = ("2026-10-14 · Seahawks rule 3 players OUT for Week 6 showdown with Denver Broncos — "
            "https://sports.yahoo.com/articles/seahawks-rule-3-players-week-222452387.html "
            "(re: Seattle Seahawks miss key players)")
ESPN = ("ESPN team (as of 2026-10-24):\n"
        "- Kansas City Chiefs: 5-0; next: Kansas City Chiefs at Seattle Seahawks (2026-10-26)\n"
        "- Seattle Seahawks: 3-3; next: Kansas City Chiefs at Seattle Seahawks (2026-10-26)")
# find_fact_conflicts([OPERATOR], ESPN) -> no "record" conflict (today: 2)
# "10-14-2026" is no record either; tests/test_fact_conflicts.py's "Islam is 19-0" vs
# "record 18-0-0" still is.
# core.claim_verifier.carried_by_facts("The Chiefs are 5-0.", ESPN.splitlines()) -> the Chiefs line
```

**(b) The wrong game.** The topic was "NFL Week 7 picks and score predictions: Chiefs edge Seahawks,
Bengals over Ravens - all 5 angles". `apis/live_scores_api._nfl_signal` reads team pages for
`teams[:2]` but matches the board with nicknames of *all* teams; Chiefs-at-Seahawks and
Bengals-at-Ravens both scored 2 and board order picked Bengals at Ravens, so no game line said the
game is in Seattle. The NBA board path in `get_live_scores_signal` matches the same way, and
`apis/nba_teams.teams_in_topic` returns `TEAM_NICKNAMES` order, not topic order.

- Fix: match the board on the topic's **first two** teams in topic order - a small pure helper
  (e.g. `_lead_pair(names, topic)`) used by both paths; `_other_league_signal` already does this.
- Test: patch `sports.espn.get_team` (any team page - reuse `tests/fixtures/signal_payloads/
  live_scores.json`'s `response`) and `sports.espn.get_scoreboard` to return a board whose
  **first** event is "Cincinnati Bengals at Baltimore Ravens" and second "Kansas City Chiefs at
  Seattle Seahawks" (`_parse_event` reads `name`, `status.type`, and each competitor's
  `team.displayName`, `homeAway`, `score`, `winner`). Expect `matched_game["event_name"] ==
  "Kansas City Chiefs at Seattle Seahawks"`. Same shape for an NBA topic naming four teams.
- Corpus cases: the dated operator line (`core.facts.conflicts:find_fact_conflicts`, `falsy`), the
  dated "chargers" line (`apis.nfl_entities:team_names_in`, `falsy`), the lead pair on a four-team
  NFL topic and a four-team NBA topic (`equals`).
- **LOCAL** (PC session): run 185's saved key facts against `format_signal_facts(load_snapshot(185))`
  give no record conflict, and `carried_by_facts` carries claim 1. Nothing is recorded on run 185;
  the operator still runs `ops verify-claim`.

### 2. #1567 - an NFL topic with "game" in it reads as gaming

`apis/topic_scorer.infer_topic_domain` returns `gaming` for "Chicago Bears defense struggles against
Atlanta's early passing game" and "Green Bay's running game faces Chicago's defensive front" (runs
148 and 135), and `register_signals._gated_signal_names` then cuts `live_scores`, `odds` and `sports`.

- Fix: when the gaming read rests on the bare word "game" and `apis.nfl_entities.team_names_in`
  names a team (no video-game title named - `_VIDEO_GAME_RE`), the topic is `nfl`. "Green Bay" names
  no nickname today; a two-word alias for the Packers (no other league has a Green Bay team) covers
  it. Keep "Madden 27: the Bears' ratings" as `gaming`.
- Tests: the two live topics read `nfl` and keep `live_scores` ungated; the Madden topic stays
  `gaming`; `tests/test_run98_domain.py` and `tests/test_signal_gating.py` still pass. Run
  `python -m scripts.ops regressions apis/topic_scorer.py` first - this function has ~40 callers.
- Corpus case: the Bears topic (`apis.topic_scorer:infer_topic_domain`, `equals: "nfl"`).

### 3. #1565 - the thumbnail check cuts the letterbox on all four sides

Run 164's live thumbnail **is ours**: a 16:9 image (1280x720) that YouTube letterboxes top and
bottom in the 480x360 `hqdefault` (lit rows 45-314). `youtube/thumbnail_check._cut_letterbox` cuts
dark columns only - and it averages each column over the black rows too - so the distance was 13
bits (limit 12). With the rows cut first, then the columns of what remains: 8 bits.

- Fix: cut dark rows first, then dark columns on the row-cut image.
- Test (Pillow, as `tests/test_wave127.LiveThumbnailTests` does): a 1280x720 image with a shape,
  resized to 480x270 and pasted at (0, 45) on a black 480x360 frame, reads `same_image` True; a
  different image in the same frame False; the existing vertical (side-bar) case still True.
- **LOCAL:** `py -m scripts.ops thumbnail-check --channel tapin` shows run 164 as ours.

### 4. #1566 - the sport scrapers stay in their sport (decision 76)

In `apis/register_signals._gated_signal_names`: `_MMA_ONLY_SIGNALS` (`ufc_context`, `tapology`) are
gated on `nba` and `nfl` topics as they are on `soccer`; `api_sports` (the soccer API,
`v3.football.api-sports.io`) is gated on every topic that is not `soccer`, the channel-based neutral
path included. Measured over 60 runs: `ufc_context` ran on all 9 NBA runs and fed nothing; on NFL it
fed 1 of 16 (BBC NFL headlines under "MMA RSS"); `api_sports` fed nothing on 14 NFL runs and fed
"Kickers Offenbach (Germany)" and other soccer clubs into NBA runs 133, 142, 145 and 151.

- Tests: an NBA and an NFL topic gate `ufc_context`, `tapology` and `api_sports`; a soccer topic
  (`tests/test_run98_domain.RUN98`) keeps `api_sports`; a UFC topic keeps `ufc_context`; a neutral
  topic on `tapin` gates `api_sports`. The existing gating tests keep passing.

### 5. #1370 - `ops signal-audit` by topic domain

`core/runs/signal_audit.report_lines` lists signals across all runs. Add `domain_lines(runs)`: group
the runs by `apis.topic_scorer.infer_topic_domain(run.topic)` ("neutral" when empty), and per domain
one line - runs, the signals that fed most, and the signals that ran but never fed - using
`contribution_rows` on each group. `report_lines` prints them under one header.

- Test: `RunSignals` fixtures (two NBA topics whose `ufc_context` signal is active but renders no fact
  lines, `news` that does) give a line naming `ufc_context` as ran-never-fed for nba.
- **LOCAL:** `py -m scripts.ops signal-audit --channel tapin` - expect nba to list `ufc_context`
  before the gating ships and not after, as new runs replace old ones.

### 6. #1362 + #1363 - a finished game is what it means, and its facts postdate the whistle

Decision 76 (the operator: "What it means + next call"). Today the script prompt says "if it says
recap / results, RECAP WHAT HAPPENED" (`core/content_engine.py`, VOICE block) and nothing ties a
recap to ESPN's final. Run 185's facts also held "NFL Week 7 picks: Seahawks defeat Chiefs; Rams
prevail over Raiders - Los Angeles Times (22 Oct 2026)" - a pick that reads as a result.

- `apis/live_scores_api._parse_event` keeps ESPN's event `date` (`event.get("date")`) - one more key
  in `data`, the signal shape unchanged.
- In `core/facts/event_dates.py`, beside `preview_brief`:
  - `finished_game(signals, topic)` - `signals["live_scores"]["data"]["matched_game"]` when
    `completed` is true and the topic names both sides' nicknames as whole words; else None.
  - `result_brief(game)` - a fixed directive: ESPN's final in one sentence, then what it changes for
    each side (record, standing, next game, from the facts), ending on a call about the next game
    argued from the facts; never retell plays, drives or quarters in order.
  - `drop_pregame_results(text, game)` -> `(kept_text, dropped_lines)`: drop a line that names both
    sides (`_side_words`), carries a result word (`_RESULT_RE`) and whose every date
    (`core.facts.recency._preview_dates`) falls before the game's day; a line with no date stays.
  - `_RESULT_RE` has "defeated" and "defeats" but not "defeat" or "prevail(s/ed) over", so today it
    misses "Seahawks defeat Chiefs" (checked). Add both - `unplayed_result` uses the same pattern and
    should catch them too; "Undefeated Chiefs" must still not match.
- `core/content_engine.py`, where `drop_future_dated` runs (~line 1951): with a finished game and a
  brief that is not a preview (`PREVIEW_PREFIX`), add `result_brief` to `extra_directive` (it prints
  as STYLE DIRECTIVE) and pass `signal_facts` through `drop_pregame_results`; record
  `finished_game` (its event name) and `pregame_results_dropped` (the count) on the run's features
  the way `features_from_conflicts` is recorded. A small pure helper keeps this testable without
  `run_pipeline`.
- Test data:

```python
GAME = {"event_name": "Kansas City Chiefs at Seattle Seahawks", "completed": True,
        "status": "Final", "away_team": "Kansas City Chiefs", "home_team": "Seattle Seahawks",
        "away_score": "20", "home_score": "24", "winner": "Seattle Seahawks",
        "date": "2026-10-26T00:20Z"}
DROPPED = "NFL Week 7 picks: Seahawks defeat Chiefs; Rams prevail over Raiders - Los Angeles Times (22 Oct 2026)"
KEPT = ["NFL Week 7 early odds: Undefeated Chiefs are underdogs - CBS Sports (19 Oct 2026)",
        "Seahawks beat Chiefs 24-20 as Seattle's defense held - ESPN (26 Oct 2026)",
        "Seahawks beat Chiefs 24-20",
        "ESPN live/final (use as source of truth for score and winner): Kansas City Chiefs 20 at "
        "Seattle Seahawks 24 — Final — winner: Seattle Seahawks"]
# finished_game({"live_scores": {"data": {"matched_game": GAME}}}, "Seahawks beat Chiefs: what it means") -> GAME
# ... with "completed": False -> None ; topic "Bengals over Ravens" -> None
# result_brief(GAME) names the final and asks for a call on the next game
# a preview brief (PREVIEW_PREFIX) gets no result brief
```

- Corpus case: the runner cannot look inside a tuple result, so give the line test its own pure
  function (e.g. `is_pregame_result(line, game)`, used by `drop_pregame_results`) and pin the Los
  Angeles Times line with `truthy`, `GAME` passed as a kwarg.

## When the wave is done

- **Docs, in the skill's order:**
  - tick #1570 #1560 #1565 #1566 #1567 #1362 #1363 #1370 in [backlog.md](backlog.md) with what was
    measured (the LOCAL checks stay named as not yet run);
  - the roadmap's next five;
  - a [planning_log.md](planning_log.md) entry;
  - wave 128 into [handoff_synopsis.md](handoff_synopsis.md), with wave 125 rolled to the archive;
  - your [handoff.md](handoff.md) slot last, then the docs tests.
- **If time remains** - the next candidates, in order:
  - #1568, `api_sports` printed as raw JSON in the facts. It is soccer-only after item 4, and
    still raw there.
  - #1569, four uploads with no thumbnail asset on record. It needs `data/`, so it is LOCAL; skip
    it in the cloud.
  - #1366, three preview structures rotated.
  - #1369, season context in previews.
- **The PC session afterwards:** ff-merge, run the LOCAL checks above, update the operator's two
  pages.
