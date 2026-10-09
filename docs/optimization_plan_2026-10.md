# The next 100 — optimization plan, October 2026

> **Class:** plan · **Status:** living · **Reviewed:** 2026-10-09

The operator, 2026-10-08: *"plan out the next 100 optimizations, be it within documentation,
ui, color, inner working, long term strategy, big and small, but not so small next 5's
currentl efficiency drops, I also dont want these to be so small they are smaller tasks for
the big root problem. (yes but no, yhou get what i am getting at, strategic division good,
stalling bad)"*.

So: one hundred items in fourteen epics, each an outcome a viewer or the operator would
notice, none a sub-step of another. Every item has a number in [backlog.md](backlog.md),
which holds its full text; this page holds the order. Epic E7 in the backlog points here.

**How to read a row.** *Owner*: **C** Claude (engine, `core/`, `apis/`, `sports/`), **Cu**
Cursor (media and the app, see [cursor_brief_2026-10.md](cursor_brief_2026-10.md)), **Op**
the operator. *Horizon*: **Done** shipped, **Now** waves 67-68, **Next** waves 69-75,
**Later** after that. Sizes are the backlog's: `S` hours, `M` a session, `L` a wave.

**The rule for picking.** A wave takes whole epics' next items, and the next five always
include one item the operator will *see* in the next run (a run card line, a menu, a
thumbnail), so progress is visible rather than internal.

---

## A — Your idea, read right (8)

| # | Item | Size | Owner | Horizon |
|---|---|---|---|---|
| #1016 | Your idea stays yours: angle 1 is your idea worded for search, Enter keeps it | L | C | Done (wave 66) |
| #1001 | "yes" at the seed prompt is a yes; the seed keeps the teams and the week | S | C | Done (wave 66) |
| #1002 | Lower-case team names are names | M | C | Done (wave 66) |
| #1005 | Who's-who never looks up a common word | M | C | Done (wave 66) |
| #1007 | An award race is a race, not a title | M | C | Now |
| #1006 | Game titles with a league name read as gaming | M | C | Now |
| #1008 | Angles get the date and past-event checks | M | C | Done (wave 67) |
| #1021 | Angle-pick learning: weight the frames the operator keeps choosing | M | C | Next |

## B — Live, dated data (8)

| # | Item | Size | Owner | Horizon |
|---|---|---|---|---|
| #1003 | NFL records, results and next games from ESPN | M | C | Done (wave 66) |
| #1004 | News and auto-research search the subject | S | C | Done (wave 66) |
| #1011 | A signal's stale record loses to today's facts | S | C | Now |
| #1014 | Variant scoring that is not noise (one cheap call) | M | C | Done (wave 67) |
| #1022 | One ESPN client for every league, injuries included | M | C | Next |
| #1023 | Schedule-aware topics (games, cards, award dates) | M | C | Next |
| #1024 | Best bets stop recycling stale or 0-view topics | M | C | Next |
| #1025 | Gaming release and patch calendar as dated facts | M | C | Later |

## C — Fact hygiene and verification (8)

| # | Item | Size | Owner | Horizon |
|---|---|---|---|---|
| #1012 | Lines pasted at `Fact N` pass the junk filter | S | C | Done (wave 66) |
| #1017 | Uncertain vault facts must name the subject | M | C | Done (wave 66) |
| #1009 | Chapter titles come from the script and are checked | M | C | Done (wave 67) |
| #1010 | A chosen chapter cannot go missing | M | C | Done (wave 67) |
| #1013 | Confirm a flagged claim without a re-render | M | C | Done (wave 67) |
| #1026 | Claim -> fact provenance on the run card | M | C | Next |
| #1027 | Vault anchors beyond game titles | M | C | Next |
| #1028 | A numeric-claim checker | M | C | Next |

## D — Script and hooks (9)

| # | Item | Size | Owner | Horizon |
|---|---|---|---|---|
| #1018 | Hooks on solid ground | L | C | Done (wave 66) |
| #1029 | Hook patterns learned from stayed share (with #993) | M | C | Next |
| #1030 | Recurring phrasing is a gate, not a report | M | C | Next |
| #1031 | Structure templates per intent | M | C | Next |
| #546 | Script length from the facts available | M | C | Next |
| #1032 | The closer pays off the hook | S | C | Next |
| #1033 | Channel personas rewritten from the operator's words | S | C | Now |
| #1034 | A read-aloud pass before TTS | M | C | Later |
| #54 | Pattern-interrupt pacing at the measured cliff | L | C | Later |

## E — Voice (6)

| # | Item | Size | Owner | Horizon |
|---|---|---|---|---|
| #1035 | Paragraph TTS with request stitching | L | Cu | Now |
| #1036 | Caption timing drift fixed | M | Cu | Now |
| #1037 | Per-channel voice settings with an A/B | M | Cu | Next |
| #217 | A pronunciation dictionary for names | M | Cu | Next |
| #1038 | A TTS model A/B | S | Cu | Next |
| #1039 | Delivery marks (pauses, emphasis, a faster hook) | M | Cu | Later |

## F — Footage and visuals (9)

| # | Item | Size | Owner | Horizon |
|---|---|---|---|---|
| #1020 | Stock only as a last resort (`local_first`) | S | C | Done (wave 66) |
| #1019 | CC BY footage credited in the description | S | C | Done (wave 66) |
| #1040 | Licensed footage bulk intake (with #424) | L | Cu | Now |
| #1041 | Stock last-resort polish | M | Cu | Now |
| #1043 | Clip index tagged by team, player and game | M | Cu | Next |
| #1042 | Generated stat cards and score bugs | L | Cu | Next |
| #1044 | Black and frozen frame QC | S | Cu | Now |
| #1045 | Visual variety: per-clip cap, no reuse within N videos | S | Cu | Next |
| #1046 | Caption style refresh per brand | M | Cu | Later |

## G — Thumbnails and packaging (7)

| # | Item | Size | Owner | Horizon |
|---|---|---|---|---|
| #1047 | Thumbnails v2: headline text, subject cutout, contrast check | L | Cu | Now |
| #1048 | The thumbnail scorer picks | S | Cu | Now |
| #1051 | One description builder | M | C | Next |
| #1052 | Shorts packaging (own title, own hashtags) | S | C | Next |
| #1050 | Titles checked against YouTube suggest | M | C | Next |
| #1049 | CTR -> thumbnail style learning | M | C | Later |
| #423 | A brand palette system | M | Cu | Later |

## H — Shorts and distribution (7)

| # | Item | Size | Owner | Horizon |
|---|---|---|---|---|
| #1053 | Chapter Shorts that stand alone | L | Cu | Now |
| #1054 | Shorts measured: cut vs native | M | C | Next |
| #952 | Buffer scheduling for TikTok and Instagram | L | C | Next |
| #1055 | A Shorts cadence planner | M | C | Next |
| #1056 | A first-frame text hook | M | Cu | Next |
| #429 | Short -> long linking (pinned comment, timed) | S | C | Later |
| #1057 | Re-cuts of past winners | M | Cu | Later |

## I — Learning from what viewers did (8)

| # | Item | Size | Owner | Horizon |
|---|---|---|---|---|
| #1058 | CTR into the learning loop | M | C | Next |
| #1059 | Shorts viewed vs swiped | M | C | Next |
| #356 | The retention curve, not one number | M | C | Next |
| #1060 | Post time learned per sport | M | C | Now |
| #1061 | The weekly report as three decisions | M | C | Next |
| #162 | An experiment registry and cockpit | L | Cu | Later |
| #1062 | Predicted vs actual per run | M | C | Later |
| #1063 | A competitor outlier watch | M | C | Later |

## J — Publishing safety (5)

| # | Item | Size | Owner | Horizon |
|---|---|---|---|---|
| #1000 | A flagged render never goes public at its slot | S | C | Done (wave 66) |
| #1064 | Confirm a claim and go public from the app | M | Cu | Now |
| #1065 | A pre-publish checklist gate | M | C | Next |
| #434 | A Content-ID pre-check | M | C | Later |
| #1066 | Fix a published description without a re-upload | S | C | Next |

## K — The desktop application (10)

| # | Item | Size | Owner | Horizon |
|---|---|---|---|---|
| #1067 | The new-video page with an intent card | L | Cu | Now |
| #1068 | The review room confirms claims | L | Cu | Now |
| #161 | The publish calendar | L | Cu | Next |
| #157 | The clip librarian | L | Cu | Next |
| #1070 | A settings page (key names only) | L | Cu | Next |
| #163 | The script desk with a grounding heat-map | L | Cu | Next |
| #451 | Phone approval (with a push) | M | Cu | Next |
| #1069 | A design-token colour and typography system | M | Cu | Next |
| #531 | First-run onboarding | M | Cu | Later |
| #154 | The installer | L | Cu | Later |

## L — Cost and reliability (5)

| # | Item | Size | Owner | Horizon |
|---|---|---|---|---|
| #1073 | A signal that feeds nothing is demoted | M | C | Next |
| #374 | The premium tier for the hook only | S | C | Next |
| #445 | Resume an interrupted run | M | C | Next |
| #1072 | Cost per published minute | S | C | Next |
| #1071 | Replace the two Apify actors where quality holds | L | C | Later |

## M — Engineering, docs and the terminal UI (5)

| # | Item | Size | Owner | Horizon |
|---|---|---|---|---|
| #1015 | Lift the PySide6 pin | S | C | Next |
| #1077 | The main menu redesigned (fewer prompts, status in colour) | M | C | Next |
| #1076 | One operator guide | M | C | Next |
| #1075 | mypy under 100 | M | C | Later |
| #1074 | The next `core/` sub-packages | L | C | Later |

## N — Strategy (5)

| # | Item | Size | Owner | Horizon |
|---|---|---|---|---|
| #991 | A series format | M | C | Next |
| #474 | Audience comments -> topics and corrections (with #361) | M | C | Next |
| #192 | The YPP ETA | M | C | Next |
| #1078 | A nightly unattended run to a review queue | L | C | Later |
| #1079 | A third channel, gated on a retention bar | S | Op | Later |

---

## Order of attack

1. **Wave 67 (Claude) - done 2026-10-09:** #1008, #1009 + #1010, #1013, #1014. #1007 moved to
   wave 68 (the roadmap took the five runs 119-120 exposed).
2. **Cursor phase A (media):** #1040, #1041, #1047, #1048, #1035 + #1036, #1053, #1044 -
   the operator's complaints about stock, thumbnails and the voice, in that order.
3. **Wave 68 (Claude):** #1007, #1006, #1011, #1033, #1060 - the rest of the "Now" horizon.
   Then #1024, #1022 and #1082 (numbered events beyond UFC, filed in wave 67).
4. **Cursor phase B (the app):** #1067, #1068, #1064, then #161, #157, #1070, #451.

## What this plan is not

It is not a commitment to all hundred in order: the backlog stays the inventory, and a run
that exposes a defect still jumps the queue (CLAUDE.md, the regression corpus). An item that
turns out to be a sub-step of another is merged, not split.
