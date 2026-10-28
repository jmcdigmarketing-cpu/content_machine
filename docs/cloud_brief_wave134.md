# Cloud brief — wave 134: the bridge's scoreboard

> **Class:** plan · **Status:** living · **Reviewed:** 2026-10-28

Every later wave is judged on the bridge's four numbers ([bridge_plan.md](bridge_plan.md), decision
82): organic Shorts views (engaged), long-form hours, organic subscribers, money outside YouTube -
and the cost per 1,000 organic views. Today `ops ypp` reads a fixed bar (4,000 hours / 10M views),
counts all views rather than engaged ones, and counts every subscriber including the ads'. This wave
makes the numbers right and puts them where the operator reads. Planned for W3 (Nov 9-15) in
[bridge_calendar.md](bridge_calendar.md). **The cloud has no `data/`, `output/`, database or keys.**

## Start here - the prompt to paste into the cloud session

```text
You are Claude Code in a cloud session on content_machine. Build wave 134, the bridge's scoreboard.
1. git pull. Read docs/handoff.md (both slots), then docs/cloud_brief_wave134.md in full. Each
   item's backlog line (#1822-#1846, #1697, #1797, #1728 in docs/backlog.md) is its source.
2. next-five skill and tdd: each new test fails on the unmodified code first; say how many did.
   New tests in tests/test_wave134.py.
3. Build and test from the fixtures only; list the LOCAL checks in your handoff slot.
4. Done: ruff check . ; ruff format --check . ; python scripts/mypy_ratchet.py (92 or fewer) ;
   python -m unittest discover -s tests -t . -v ; python -m scripts.ops test --order reverse.
5. Commit (ASCII body) with your Co-Authored-By trailer, push, read CI; docs in the skill's order,
   your handoff slot last. Nothing outward.
```

## Ground rules

As in [cloud_brief_wave132.md](cloud_brief_wave132.md#ground-rules-for-this-wave). Analytics calls
in tests are fakes shaped like the real responses - never the network. The stores are redirected by
`tests/__init__.py`; a new store gets its redirect there.

## The wave, in build order

### 1. #1823 B10.2 - the YPP bars as data, with dates

**Now:** `core/ypp_readiness.py` - `WATCH_HOURS_TARGET = 4000.0`, `SHORTS_VIEWS_TARGET = 10_000_000`.

**Build.** `config/ypp.json`:

```json
{"bars": [
  {"from": "2023-06-13", "subscribers": 1000, "hours": 4000, "shorts": 10000000,
   "source": "YouTube Help"},
  {"from": "2027-02-01", "subscribers": 1000, "hours": 8000, "shorts": 20000000,
   "source": "third-party reports, 2026-08; not yet on YouTube's help page"}]}
```

- `ypp_readiness.bar_on(day)` returns the bar in force on `day`.
- `ops ypp` prints today's bar and, before 2027-02-01, the next one with its date and source.
- The constants stay as today's values for the old callers. New code reads `bar_on`.

**Done when:**

| day | bar |
|---|---|
| 2026-10-28 | 4,000 / 10M |
| 2027-02-01 | 8,000 / 20M |
| 2027-03-01 | 8,000 / 20M |

The report names the source of the 2027 bar.

### 2. #1824 B10.3 - engaged Shorts views

**Now:** `analytics/youtube_metrics.fetch_ypp_numbers` sums `views` by traffic source and content
type (`_by_source_and_type(service, start, end, "views")`), leaving out `PAID_SOURCES`.

**Build.**
- A second query on the same two dimensions with the metric `engagedViews` gives
  `out["shorts_engaged_90d"]`, organic only.
- When the API refuses the metric, the field is absent and `ops ypp` says "engaged views not
  available" - never zero.

**Fixture:** a fake service whose `reports().query().execute()` returns rows like
`[["SHORTS", "YT_SHORTS", 1500], ["SHORTS", "ADVERTISING", 900], ["VIDEO_ON_DEMAND", "YT_SEARCH", 40]]`,
in the order `_by_source_and_type` reads them (check its column order in the code).
- Expected: `shorts_engaged_90d` == 1500.
- A refused metric (an `HttpError` 400) gives no key.

### 3. #1697 B05.1 - organic subscribers

**Build.**
- Organic = YouTube's subscriber count minus every ads campaign's subscribers in the spend ledger
  (`core/money/ledger`, `set_result(..., subscribers=)`).
- `ops ypp` and `ops status` print "organic subscribers N (YouTube N, campaigns N)".
- Any ads entry without a result adds "at most - a campaign has no count entered".

**Fixture:**
- 134 total, results of 27 and 2, and a third ads entry with no result gives
  "organic subscribers at most 105".
- With all results entered, the "at most" is dropped.

### 4. #1825 B10.4 - the race clock

**Build.** `ypp_readiness.race_clock(numbers, *, today)` gives:
- the days to 2027-02-01;
- for each path, what it needs a day before that date under today's bar and after it under the new
  one, against the last 28 days' pace (`shorts_views_28d`, the hours pace).

**Fixture:** today 2026-10-28, `shorts_views_90d` 3,852, `shorts_views_28d` 2,817,
`long_hours_365d` 10.2.

| result | value |
|---|---|
| days left | 96 |
| Shorts per day under today's bar | (10M - 3,852) / 90 = 111,068 |
| Shorts pace now | 101 a day |

The line ends "not reachable at this pace" when the need is over 100x the pace.

### 5. #1822 B10.1 - the bridge scoreboard

One block in `ops status` and the weekly report, after the existing YPP line:
- organic subscribers (#1697);
- engaged Shorts views in 90 days (#1824);
- qualified long-form hours in 365 days;
- money earned outside YouTube (`ops spend` income, wave 136 - "not tracked yet" until then);
- for each: the last 28 days' pace and the days to today's bar at that pace;
- the race clock line.

**Done when:** with the fixtures above it prints all four rows with a pace; an absent number
prints "not measured", never 0.

### 6. #1797 B09.1 - cost per 1,000 organic views

**Build.**
- A run's cost (its stored estimate in the run's features - the "Est. run cost" the render prints)
  divided by its organic views at 7 days, per video.
- A weekly line: the week's spend on runs over the week's organic views at 7 days.

**Fixture:** runs costing $0.39, $0.27 and $0.08 with 7-day organic views 325, 0 and 23 give
$1.20, "no views" and $3.48 per 1,000. The week is $0.74 over 348 views, $2.13 per 1,000.

### 7. #1728 B06.7 - the hours ledger

**Build.**
- Per long video, qualified hours a week from the synced per-video `estimated_minutes_watched`
  (organic).
- In `ops ypp`: hours this week, the weeks to 4,000 and to 8,000 at the 4-week pace.

**Fixture:** three long videos with 240, 90 and 30 minutes this week give 6.0 hours. A 4-week pace
of 6.0 a week puts 8,000 at about 1,332 weeks; the line says so plainly.

### 8. #1827 B10.6 - experiments with stop dates

`core/experiments` gains a `stop` date per experiment (`start_experiment(..., days=)`, default 14).
The weekly report lists the open ones: lever, arms, days left, and the verdict once stopped.

**Fixture:** one started 2026-10-25 with `days=14` on 2026-11-09 reads "stops today".

### 9. #1836 B10.15 - the wave scorecard

**Build.**
- `config/waves.json` holds `{wave, shipped, lane, metric}` rows. A wave adds its own row when it
  ships (the next-five skill's docs step).
- At 14 days the weekly report prints the metric's 14 days after against the 14 days before.

**Fixture:** wave 133 shipped 2026-11-08 with lane views, metric "organic views a day". On
2026-11-22 it prints "wave 133 (views): 412 a day after against 251 before - up 64%".

### 10. #1832 B10.11 - a toast for a breakout

When the daily sync finds a Short past 1,000 organic views within 24 hours of publishing, the worker
raises one toast for that video (`core.win_notify.toast_daily`, keyed by video), naming it and
pointing to a follow-up (#1601's rule).

**Fixture:**

| organic views | hours since publishing | toast |
|---|---|---|
| 1,200 | 20 | yes |
| 900 | 20 | no |
| 1,500 | 30 | no |

A second run of the pass the same day raises nothing.

## LOCAL checks - for the PC session

- `py -m scripts.ops ypp --channel tapin` after a real sync: the engaged-views row is there, or says
  it is not available.
- The operator's Oct 8 campaign entered (`ops spend add`, then `ops spend result`), so "organic
  subscribers" loses its "at most".
- `config/waves.json` has the rows for waves 132 and 133 with their real ship dates.

## When the wave is done

The next-five skill's order:
1. backlog ticks;
2. this page archived, naming what was built;
3. the calendar's targets read against the first real scoreboard;
4. the planning log;
5. the handoff slot last.
