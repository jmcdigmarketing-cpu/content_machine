# Cloud brief — wave 135: speed, volume, and Shorts that loop

> **Class:** plan · **Status:** living · **Reviewed:** 2026-10-28

The Shorts path needs more shots and faster ones ([bridge_plan.md](bridge_plan.md), "The math to
the bar"). Today:
- uploads go out at noon and 10 PM;
- news is hours old when it goes out;
- previews were drafted as late as 31 minutes before kickoff (run 193);
- every render ends on ~0.8 s of a dark end card, so a Short does not loop;
- 39% of drafts expire undecided.

This wave holds eleven of the bridge's top 30 ([bridge_scores.md](bridge_scores.md)). It is planned
for W5 (Nov 23-29) in [bridge_calendar.md](bridge_calendar.md). **The cloud has no `data/`,
`output/`, database or keys.**

## Start here - the prompt to paste into the cloud session

```text
You are Claude Code in a cloud session on content_machine. Build wave 135: speed, volume, loops.
1. git pull. Read docs/handoff.md (both slots), then docs/cloud_brief_wave135.md in full. Each
   item's backlog line in docs/backlog.md is its source (numbers below).
2. next-five skill and tdd: each new test fails first; say how many. Tests in tests/test_wave135.py.
3. Fixtures only; list the LOCAL checks in your handoff slot.
4. Done: ruff check . ; ruff format --check . ; python scripts/mypy_ratchet.py (92 or fewer) ;
   python -m unittest discover -s tests -t . -v ; python -m scripts.ops test --order reverse.
5. Commit (ASCII body) with your Co-Authored-By trailer, push, read CI; docs in the skill's order,
   your handoff slot last. Nothing outward.
```

## Ground rules

These are as in [cloud_brief_wave132.md](cloud_brief_wave132.md#ground-rules-for-this-wave), plus
two more:

- **Child processes.** A child Python process started from overnight or the worker runs
  `core.win_shell.hide_child_windows()` first in its `main`. `tests/test_child_windows.py` guards
  this. Without it, every ffmpeg call opens a window - the 10-28 pop-ups.
- **The operator's machine.** Nothing changes the scheduled tasks. The fast lane runs inside the
  existing 15-minute worker pass.

## The wave, in build order

### 1. #1622 B02.1 - no end card on a Short, so it loops

**Now.** `video/render_video.py` (~line 858) appends the generated end card whenever
`video.channel_outro.resolve_end_card(channel_id)` returns a card.

**Build.**
- The card is appended only to a long video: one over 180 seconds, or one rendered with the
  landscape profile.
- A Short ends on its last word.

**Fixture.**

| video | duration | profile | end card |
|---|---:|---|---|
| Short | 45 s | vertical | none (patch `append_channel_outro`, assert not called) |
| long video | 600 s | landscape | yes |

### 2. #1623 B02.2 + #1624 B02.3 - a loop line, and no sign-off on a Short

**Now.** "Tap in for more." is in 9 of the last 12 scripts; `core/script_craft._SIGN_OFF_RE`
matches it.

**Build.**
- For a Short, the script prompt asks for a last line that leads back into the first.
- A pass removes a trailing sign-off sentence from a Short's script. Long videos keep theirs.
- `unfinished_ending` (#1334) must still pass on the result.

**Fixture.**
- "Seattle held Kansas City to three points. ... If that line can't protect Mahomes, the AFC West
  tilts fast. Tap in for more." loses its last sentence, and the one before it stays whole.
- The same script with `kind: long` is unchanged.

### 3. #1670 B03.24 + #1893 B12.22 - previews drafted 24-48 hours ahead

**Now.** `core/facts/event_dates.starts_within(..., PREVIEW_MIN_LEAD_HOURS)` keeps out a game under
3 hours away, but nothing makes previews early.

**Build.**
- Overnight's preview pick (decision 81: at most one a night, marquee only - #1593) prefers a game
  24-48 hours away.
- A game under 24 hours away is taken only when nothing in the window qualifies.

**Fixture:** at 2026-11-25 05:00 UTC, with games at +20 h, +30 h and +70 h, the pick is the +30 h
game. With only the +20 h game, that one.

### 4. #1665 B03.19 - a clean news draft left undecided goes out after 6 hours

**Now.** Decision 78: `core/batch_review.schedule_unanswered_renders` schedules a clean overnight
render left unanswered for 24 hours.

**Build.** A news render (freshness window under 7 days, `freshness_window_days`) goes out after 6
hours. Games and evergreen stay at 24.

**Fixture:** a news render 7 hours old is scheduled; the same render 5 hours old is not; an
evergreen one 7 hours old is not.

### 5. #1608 B01.12 - a "more of what worked" slot

Each week, the subjects of the top 3 Shorts by organic views at 7 days get one idea each in the
next week's menu. They are matched with `apis/topic_tokens.names_any` on fresh headlines first,
else the subject's last story.

**Fixture:** the top 3 are "Modern Warfare 4", "GTA 6" and "Dana White". A headline pool with a
Modern Warfare 4 DLC story yields that story as an idea marked "more of what worked".

### 6. #1648 B03.2 - three Shorts a day, as an experiment

**Build.**
- A `slots` lever in `core/experiments` (`start_experiment(channel_id, "slots")`) with two arms:
  two `(12, 22)` and three `(12, 18, 22)`. A 14-day stop (wave 134's #1827, if built).
- `core/spaced_queue.twice_daily_slots` takes its hours from the arm in force that day.
- The weekly report reads organic views a day and per Short, by arm.

**Fixture:** with the "three" arm in force, 6 slots asked for from 2026-11-24 09:00 ET give noon,
18:00 and 22:00 on two days.

### 7. #1647 B03.1 - the breaking-news fast lane (L)

**Build** - a pass in `jobs/worker.drain_due`, at most once every 30 minutes (a stamp in its store):
1. From the idea pool (`best_bet._fresh_candidates` / `rank_by_coverage`), find a headline on
   5 or more outlets whose first outlet published under 2 hours ago. It must name a subject on
   `config/marquee.json` (#1595) and not already be drafted (`unreviewed_draft`, recent topics).
2. Draft it in the overnight draft child (`python -m core.overnight --draft-job`).
3. If the draft passes `unattended_block_reason` (the claim gate, the title check), render it in the
   render child (`python -m core.batch_review --render-draft`).
4. Queue it **public now** (#1655), not at a slot. Then call `process_one` for that job at once,
   so it does not wait for the next pass.
5. A draft held for a claim raises one toast and stops (#1667).

**Limits.** At most 2 a day. Not with under 1,600 quota units left, not on battery, and not while
overnight is running (its lock).

**Fixtures:**
- **The pool:** headlines with `outlets` 6 / published 50 minutes ago / "Mahomes" (marquee), 6 /
  5 hours ago / "Mahomes", and 7 / 30 minutes ago / "Valve" (not marquee). Only the first is
  taken.
- **A claim-held draft:** no render; one toast.
- **The cap:** two fast-lane runs already today, so nothing more.

### 8. #1649 B03.3 + #1650 B03.4 - results fast lanes

These use the same pass. A finished game or card is a story the moment it ends.

**NFL and NBA.**
- A final on a national broadcast (`best_bet._NATIONAL_TV`) becomes a result idea within 60 minutes
  of the ESPN final (`apis/live_scores_api`, `event_dates.finished_game`).
- Decision 76's framing applies: what it means, with a call.

**UFC.** A numbered card's finish headline ("UFC 334", 3 or more MMA outlets within 30 minutes)
becomes a result idea.

**Fixture.**

| final | broadcast | age | result idea |
|---|---|---|---|
| Seahawks 20, Chiefs 3 | NBC | 40 minutes | yes |
| a CBS 1 PM final | CBS | 40 minutes | no |
| the NBC final | NBC | 90 minutes | no |

### 9. #1872 B12.1, #1873 B12.2, #1875 B12.4, #1885 B12.14 - the sports calendar plans drafts ahead

**Build.**
- `core/seasonal_calendar` gives the marquee events two weeks ahead: numbered UFC cards, NFL prime
  time (TNF/SNF/MNF), the Thanksgiving games, and national NBA games.
- Overnight uses it for #1670's 24-48 hour preview.
- A UFC numbered card gets its fight-week plan: the main event on Monday, a weigh-in Short on
  Friday (on 3+ outlets), results on Saturday through #1650.

**Fixture:** the calendar for 2026-11-09 lists UFC 334 on 11-14 with the Monday item on 11-09 and
the Friday item on 11-13. For the week of 11-23, Thanksgiving's three games are on 11-26.

### 10. #1599 B01.3 - competitor outliers first

A tracked competitor's Short at 5x its channel median within 48 hours
(`best_bet._competitor_outlier_candidates`) that names a marquee subject is the first idea.

**Fixture:** an outlier at 6x naming "Topuria" ranks above a 5-outlet headline. One at 6x naming a
subject off the marquee list does not.

### 11. #1657 B03.11 - headline to public, timed

**Build.**
- A draft stores when its headline was first seen: the feed's `published`, or the draft time for a
  non-headline idea.
- The weekly report gives the median hours from headline to public, for fast-lane runs and for the
  rest.

**Fixture:** runs at 1.2, 1.6 and 0.9 hours give a fast-lane median of 1.2. Runs at 30 and 18 hours
give 24 for the rest.

## LOCAL checks - for the PC session

- The fast lane's first live run: watch one through to public, and confirm no console windows
  appear (the 10-28 fix).
- Start the slots experiment on the PC: `py -m core.experiments start slots --channel tapin`.
- Watch one Short's loop on a phone: it should end on the last word and start again at once.

## When the wave is done

The next-five skill's order:
1. backlog ticks;
2. this page archived;
3. the calendar's W5-W6 rows checked;
4. the planning log;
5. the handoff slot last.
