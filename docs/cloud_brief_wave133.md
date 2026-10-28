# Cloud brief — wave 133: the GTA 6 window (launch 2026-11-19)

> **Class:** plan · **Status:** living · **Reviewed:** 2026-10-28

The bridge's first time-critical wave ([bridge_plan.md](bridge_plan.md), decision 82): GTA 6
launches on **2026-11-19**, the biggest window of the year for a gaming channel's views and
long-form hours. Nine of the bridge's top 30 ideas are in it ([bridge_scores.md](bridge_scores.md)).
The dates around it are in [bridge_calendar.md](bridge_calendar.md). Built after wave 132
([cloud_brief_wave132.md](cloud_brief_wave132.md)) or alongside it; where it needs 132's work it
says so. **The cloud has no `data/`, `output/`, database or keys** - every fixture is below.

## Start here - the prompt to paste into the cloud session

```text
You are Claude Code in a cloud session on content_machine. Build wave 133, the GTA 6 window.
1. git pull. Read docs/handoff.md (both slots), then docs/cloud_brief_wave133.md in full: the order,
   the files, the fixtures and done-when. Each item's backlog line (#1847-#1871, #1747-#1748,
   #1616, #1725, #1731 in docs/backlog.md) is its source; decision 82 is the operator's.
2. Work it with the next-five skill and tdd: every new test fails on the unmodified code first;
   say how many did in the commit. New tests go in tests/test_wave133.py.
3. No data/, output/, database or keys: build and test from the fixtures; list the LOCAL checks
   in your handoff slot.
4. Done: ruff check . ; ruff format --check . ; python scripts/mypy_ratchet.py (92 or fewer) ;
   python -m unittest discover -s tests -t . -v ; python -m scripts.ops test --order reverse.
5. Commit to main (ASCII commit body - the hook's rule) with your Co-Authored-By trailer, push,
   read CI. Then the docs in the skill's order, your handoff slot last.
Nothing outward: no uploads, schedules, playlists edits, sign-ins.
```

## Ground rules

As in [cloud_brief_wave132.md](cloud_brief_wave132.md#ground-rules-for-this-wave): `ops regressions
<file>` before editing; a defect gets a corpus case (append in place); no `data/` writes in tests;
topic words from `apis/topic_tokens`; a new env key in `.env.example` (CRLF) and its suite value in
`tests/__init__.py`. A new module goes in a `core/` sub-package (`tests/test_core_layout.py`); a new
sub-package is listed in `pyproject.toml` `packages`. Every new backlog item names its lane.

## The wave, in build order

### 1. #1847 B11.1 - "GTA 6: N days to launch", a daily countdown series

**Pattern to copy.** "Picks, graded" (#991): `core/predictions/calls.picks_graded()` returns
`(topic, facts, rationale)`; `core/best_bet._series_idea()` turns it into a `BestBetResult(source=
"series")` that `get_idea_menu` puts first; `core/batch_generation.series_drafted(channel, topic)`
keeps it to once.

**Build.**
- A new sub-package `core/series/` (`__init__.py`, `countdown.py`), listed in `pyproject.toml`.
- `config/series.json`:

```json
{"tapin": [{"id": "gta6-countdown", "kind": "countdown", "subject": "GTA 6",
            "title": "GTA 6: {n} days to launch", "from": "2026-10-29", "until": "2026-11-19",
            "playlist": "GTA"}]}
```

- `countdown.countdown_idea(channel_id, *, now)` returns the day's idea or `None`:
  - between `from` and the day before `until`, the topic is the title with `n` = days to `until`;
  - facts are the day's headlines naming the subject, from `best_bet.idea_feeds` and
    `best_bet._fetch_feeds`, matched with `apis.topic_tokens`;
  - a day with no fresh headline still gets the idea, with facts = the days left and the date.
- `get_idea_menu` puts it first beside the "Picks, graded" idea, through the same
  `series_drafted` check on the dated topic.

**Fixtures.**

| now | topic |
|---|---|
| 2026-10-28 | `None` (before `from`) |
| 2026-10-29 | "GTA 6: 21 days to launch" |
| 2026-11-18 | "GTA 6: 1 day to launch" (singular "day") |
| 2026-11-19 | `None` (launch day is #1848's) |

**Done when:** the four fixtures hold; a second call the same day after a draft exists returns
`None` (patch `series_drafted`); `collect_topics` takes it first (ideas come before previews).

### 2. #1747 B07.1 + #1748 B07.2 - the affiliates map and the Amazon tag (long-form only)

Moved here from wave 136: the editions video (#1852) needs its links before launch. **A Short's
description links are not clickable**, so links go on long-form only.

**Build.**
- `config/affiliates.json` is `{channel: [{keys: [...], url, label}]}`, matched the way the
  playlists map is (`core/playlists._matches` - reuse it, do not copy it).
- `AFFILIATE_AMAZON_TAG` goes in `.env.example`. The suite sets it to `""`.
- An Amazon `url` gains `tag=<it>`. With no tag, no Amazon link is added at all.
- `core/description_extras`: `affiliate_lines(channel_id, title, topic, *, long_form)` - at most
  one link, only when `long_form` - goes into the "notes" block. Whenever a link is added,
  `ftc_affiliate_line` (#128) is added too.

**Fixture.**

```json
{"tapin": [{"keys": ["gta 6", "gta vi", "grand theft auto vi"],
            "url": "https://www.amazon.com/dp/B0EXAMPLE1", "label": "GTA 6 on Amazon"}]}
```

| title | long_form | tag | result |
|---|---|---|---|
| "GTA 6 - everything we know before launch" | True | `tapin-20` | one line `GTA 6 on Amazon: https://www.amazon.com/dp/B0EXAMPLE1?tag=tapin-20`, plus the FTC line |
| the same | False | `tapin-20` | nothing |
| the same | True | unset | nothing |

**Done when:** the three fixtures hold.

### 3. #1850 B11.4, #1851 B11.5, #1853 B11.7 - a long-form draft kind, 16:9

**What exists.**
- Length preset "4" Extended is 1,000-2,000 words (`core/script_length.py`).
- Chapters from angles (#1010): `chapter_angles` in `core/pipeline.py` - "A = all angles in one
  long video".
- A 16:9 cut: `video/render_profiles` "landscape" (1920x1080, suffix `_16x9`) through
  `RENDER_FORMATS`, rendered as a sibling file in `video/render_video.py` (~line 917).

**Build.**
- A draft can be `"kind": "long"` (in its `meta.json`). For it, `batch_generation.generate_draft`
  uses:
  - the Extended preset;
  - three to five chapter angles from the topic's angles;
  - a render with the landscape profile.
- The upload sends the `_16x9` file, with the chapters in the description (`core.chapters`
  already builds a block).
- Long-form topics come from `config/series.json` entries with a date:

```json
{"id": "gta6-everything", "kind": "long", "topic": "GTA 6 - everything we know before launch",
 "on": "2026-11-07"}
```

  Overnight drafts each one on its `on` date. The operator reviews it in `batch-review` as today;
  a long draft is never rendered unattended.

**Done when:**
- A `kind: long` meta gives preset "4", at least three chapters each at least 10 s long, the
  landscape profile, and an upload path ending `_16x9.mp4` (patch the render and the publisher).
- A Short's meta is unchanged.
- Overnight takes a `kind: long` entry on its date and not the day before.

**LOCAL:** the first long render on the PC, watched once.

### 4. #1856 B11.10 + #1725 B06.4 + #1616 B01.20 - long-form titles and topics from search

**Build.**
- For `kind: long`, `core/title_generator.generate_title` gets the subject's autocomplete
  suggestions (`apis/autocomplete_api`).
- The title starts with the subject within 40 characters and carries the distinctive words of the
  top suggestion.
- A long-form topic in `config/series.json` that has no suggestions is flagged in `batch-review`
  ("nobody searches this").

**Fixture.**
- Suggestions `["gta 6 release date", "gta 6 map", "gta 6 price", "gta 6 trailer 3"]` give a title
  starting "GTA 6" with "release date" in it.
- An empty list keeps today's title path.

### 5. #1859 B11.13 - GTA names on the marquee list

`config/marquee.json` (#1595, wave 132) gains `GTA 6`, `GTA VI`, `Grand Theft Auto VI`, `Rockstar`,
`Vice City`, `Lucia` and `Jason` for `tapin`. If wave 132 has not built the file yet, create it
with these names and let #1595 extend it.

### 6. #1868 B11.22 - two GTA 6 slots a day in launch week

`core/spaced_queue.twice_daily_slots` uses `_TWICE_DAILY = (12, 22)`.

**Build.** A `slots` entry in `config/series.json`:

```json
{"id": "gta6-launch-slots", "kind": "slots", "subject": "GTA 6",
 "from": "2026-11-16", "to": "2026-11-22", "extra_hours": [18]}
```

A run whose title names the subject gets the extra 6 PM slot inside those dates. Other runs keep
noon and 10 PM.

**Done when:**
- A GTA 6 title on 2026-11-18 gets slots that include 18:00.
- A UFC title that day does not.
- A GTA 6 title on 2026-11-23 does not.

### 7. #1867 B11.21 - a GTA 6 story jumps the queue in launch week

Wave 135 builds the full fast lane (#1647). Until then, inside the slots window above:
- a fresh headline naming GTA 6 on 5 or more outlets in 48 hours (`best_bet.rank_by_coverage`'s
  `outlets`) is the first idea;
- `collect_topics` drafts it first;
- its draft takes the next free GTA slot.

**Fixture:** a pool with a GTA 6 headline at `outlets` 6 and a UFC one at 7 gives GTA 6 first
inside the window, and UFC first outside it.

### 8. The launch moments, as dated entries

Covers #1848 B11.2, #1849 B11.3, #1854 B11.8, #1860 B11.14, #1861 B11.15, #1862 B11.16, #1863 B11.17,
#1864 B11.18, #1865 B11.19 and #1679 B04.8.

Each moment is a `kind: "moment"` entry in `config/series.json` with its date. Overnight drafts each
on its date, the way #1847 drafts the countdown.

| on | topic |
|---|---|
| 2026-11-12 | "GTA 6 Online - what is confirmed" |
| 2026-11-14 | "When does GTA 6 come to PC?" |
| 2026-11-17 | "GTA 6 pre-load, file size and unlock times" |
| 2026-11-19 | "GTA 6 is out: first impressions" |
| 2026-11-20 | "GTA 6 launch problems and fixes" |
| 2026-11-21 | "Players react to GTA 6" - #1679's format, the community's lines quoted on screen |
| 2026-11-27 | "GTA 6 Black Friday deals" - its long video carries the affiliate links (item 2) |
| the embargo date | the review-score roundup |
| when Take-Two announces | the sales-record Short |

The embargo and sales entries ship with `"on": null` and are not drafted until a date is set
(LOCAL); the PC question is drafted only if headlines in the week name it (otherwise skipped, with
the reason in overnight's line).

**Done when:** each entry with a date is drafted on that date only, and the `null` one never is.

### 9. #1870 B11.24 - launch day, planned

- The Nov 19 moment's draft is made and **rendered on Nov 18**, held for review like any overnight
  render.
- It is scheduled for the unlock hour set in its entry, `"publish_at"`.
- Before the publish time is set, the entry carries `"publish_at": null`, and the schedule falls
  back to the next free slot.

**Fixture:** an entry with `publish_at` `2026-11-19T05:00:00Z` gives a job due then; with `null`,
the next slot.

**LOCAL:** set the real unlock time once Rockstar states it.

### 10. #1855 B11.9 - the GTA playlist in series order

`core/playlists.add_to_playlists` adds a countdown Short to the GTA playlist at the position its day
number gives (`playlistItems.insert` `snippet.position`), so the playlist plays day 21 to day 1 in
order.

**Fixture:** a `MagicMock` service; days 21, 20 and 19 inserted get positions 0, 1 and 2.

### 11. #1731 B06.10 + #1869 B11.23 - long-form thumbnails that earn the click

A long video, unlike a Short, is chosen from its thumbnail.

**Build.**
- For `kind: long`, the thumbnail step renders a 16:9 card: the subject's face or key art, plus
  three words from the title.
- A GTA 6 long video uses the cover art's palette. That is a style entry in `config/series.json`,
  not a new image source.
- The card goes through `ops thumbnail-check`'s rules (#1541).

**Fixture:** "GTA 6 - everything we know before launch" gives a 1920x1080 card whose text is at
most three words from the title.

## LOCAL checks - for the PC session

- **#1857 B11.11 press screenshots:** only from a source the operator approves once - list
  Rockstar's press page in `config/footage_sources.json` with their yes. No download without it.
- The first `kind: long` render watched end to end; its 16:9 upload checked in Studio as long-form.
- The embargo date and the unlock time put into `config/series.json` when Rockstar states them.
- The countdown's first overnight draft (Oct 29) read before it renders.

## When the wave is done

The next-five skill's order:
1. backlog ticks;
2. this page archived (`Status: archived`, `Superseded by: bridge_plan.md`, a line on what was
   built);
3. the calendar's W2-W4 rows checked against what shipped;
4. a planning-log entry;
5. the handoff slot last.
