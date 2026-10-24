# The hands-off plan

> **Class:** plan · **Status:** living · **Reviewed:** 2026-10-18

The forward plan from 2026-10-18; it supersedes [optimization_plan_2026-10.md](optimization_plan_2026-10.md)
("the next 100"), whose open rows the [backlog audit](backlog_audit_2026-10-18.md) merged,
retired or kept. [master_plan.md](master_plan.md) keeps the long horizons (M4 volume, M5
reach); this page is how they are worked now.

The operator, 2026-10-18, after a day of using it: *"no damn way am i posting these manually.
plan for improvement on these items, big big plan to adress these moving forward."* The items
are the Content OS Story's list of what is wrong. Since wave 113 each one is a section of its
own ("The 22 shortfalls"): where it stands, measured with the date, how it is addressed, who
acts, and the command that says it is done.

**Who acts.** **Code** - an agent ships it. **You** - a click or a decision only the operator
can make (a Google console, money, the channel's niche). Each "You" step names the exact
command or page.

**Horizons.** **H0** this week · **H1** the next two to four weeks · **H2** the quarter.
[roadmap.md](roadmap.md)'s next items are drawn from H0 and H1; the ordered lists are at the end.

---

## The 22 shortfalls

The operator, 2026-10-18: *"I would like a written description on how we will adress each one
of these alongside 10 ideas per bullet to go in the backlog."* Each section is one line of the
Story's "Where it falls short", in its order: where it stands (measured 2026-10-18), how it is
addressed, who acts, and the command that says it is done. Its ten ideas are numbered in
[backlog.md](backlog.md) under the same heading (decision 68). The 2026-10-18 tables (themes
A-E) are replaced: every row still open is under its shortfall below, and the shipped rows are
in [planning_log.md](planning_log.md) (waves 110-112).

### S01 Monetization is far

**Now.** 69 of 1,000 subscribers; 1,936 organic Shorts views in 90 days (272 a week against the
777,778 the Shorts path needs); 10 of 4,000 long-form hours (0.2 a week against 77). As of
2026-10-18, YouTube's own numbers, ads excluded.

**How.** At this size the Shorts path is not reachable by volume, so long-form hours come first:
the weekly $0 compilation (#138) makes its first video on Monday 10-19. Per-video reach (S02, S12,
S16) multiplies everything else. Longer term: a written long-form format and money that is not ads
(#79), with titles that stay advertiser-safe from the start.

**Who:** Code; you for the ad decision and the playlists. **Done when:** `py -m scripts.ops ypp` -
long-form hours a week rising from 0.2.

**Ideas:** #1314-#1321 in [backlog.md](backlog.md) under "S01", and already open: #79, #434. Built
in wave 113: #1319.

### S02 Subscribers came from ads, not videos

**Now.** +64 subscribers in 28 days, 2 of them from the 53 videos (one each from the Vanguard meta
and the GTA VI box videos). YouTube counts 4,543 paid Shorts views in 90 days; no campaign is
entered, so `ops promotions` cannot split them.

**How.** Give a viewer a reason to follow that is true - every call is graded after the game - and
measure subscribers per video and per format so the reason can be tested. Enter the October ad so
its subscribers separate from the videos'.

**Who:** Code; you for entering the ad. **Done when:** `py -m scripts.ops growth` - 10 or more
subscribers from videos in 28 days.

**Ideas:** #1322-#1331 in [backlog.md](backlog.md) under "S02". Built in wave 113: #1322, #1329.

### S03 Overnight rendered two wrong videos (Oct 13)

**Now.** Fixed: a game draft renders before its game or waits, a flagged title waits, a night
stops at 3 finished videos, and a preview now carries a call and a matchup card. None pulled
since.

**How.** Keep the gates, and check the finished video as well as the script - both Oct 13 failures
were visible in the render (a called result, a garbled last line).

**Who:** Code. **Done when:** the weekly report - 0 videos pulled before public over 4 weeks.

**Ideas:** #1332-#1341 in [backlog.md](backlog.md) under "S03".

### S04 The proof of "your own idea" was wrong (Oct 13)

**Now.** Fixed: a typed idea is drafted as the idea, not a generated angle; written from your
ideas, the three came back with 2, 1 and 1 flagged claims, each named.

**How.** Measure how closely a draft keeps the idea, so a regression shows on the review screen
instead of in a published video.

**Who:** Code. **Done when:** `py main.py, option 5` - a fidelity line on every own-idea review.

**Ideas:** #1342-#1351 in [backlog.md](backlog.md) under "S04".

### S05 Clean is not the same as good (Oct 14)

**Now.** The run-on opener and the doubled sentence are fixed; the "Denver Loss Angeles" title is
fixed (#1181, and #1211 checks old titles).

**How.** Add checks for what reads badly, not only for what is false, and keep your own rating
beside the grade so "clean" is tested against "good".

**Who:** Code. **Done when:** `py -m scripts.ops verdicts` - your 1-5 agreeing with the grade.

**Ideas:** #1352-#1360 in [backlog.md](backlog.md) under "S05", and already open: #537.

### S06 Every overnight draft was a game written as a recap (Oct 11-14)

**Now.** Fixed: a scheduled game is drafted as a preview with a call (#1169, #1301), and music and
filings signals no longer run for a football game.

**How.** Read the finished script's tense before render, and give previews more than one shape.

**Who:** Code. **Done when:** `py -m scripts.ops overnight-last` - 0 recap-tense previews over 4
weeks.

**Ideas:** #1361-#1370 in [backlog.md](backlog.md) under "S06".

### S07 Overnight runs when the PC wakes, not at 5:00 AM

**Now.** The task's WakeToRun is on and the power plan allows wake timers (checked 2026-10-18).
The last run started 10-18 at 08:04; the next 5:00 start shows whether the wake works.

**How.** Make the wake checkable and a missed run loud.

**Who:** Code. **Done when:** `data/overnight_last.json` - started at 05:0x for a week.

**Ideas:** #1371-#1380 in [backlog.md](backlog.md) under "S07". Decision 69 (wave 124, the
operator): a run at power-on after a shutdown is normal - nothing asks for Sleep any more.

### S08 Good research blocked good drafts

**Now.** Fixed Oct 13: the checker no longer calls a claim unsupported because the research brief
cited it (5 of 5 on the replay; it was most of why 15 of 31 drafts waited).

**How.** Keep the held-for-claims rate visible, and give a hold one more look before it stops a
draft.

**Who:** Code. **Done when:** `py -m scripts.ops auto-research` - under 20% of drafts held for
claims, with a replay sample confirming the holds.

**Ideas:** #1381-#1388 in [backlog.md](backlog.md) under "S08", and already open: #547, #555.

### S09 The record drifted from YouTube

**Now.** Fixed: every sync asks YouTube for each video's privacy and corrects the record (#1128).

**How.** Read more fields back, and count the corrections until there are none.

**Who:** Code. **Done when:** `py -m scripts.ops sync-metrics` - 0 records corrected for 2 weeks.

**Ideas:** #1389-#1397 in [backlog.md](backlog.md) under "S09", and already open: #464. Built in
wave 121: #1390 (Studio titles and descriptions read back, same quota); #1391 closed by
measurement - the API cannot say which thumbnail image is live (#1541 compares the image).

### S10 The last mile was manual

**Now.** Fixed: a scheduled task runs the upload worker, drafts get slots that fit them, and
Buffer sends each video as it goes public. One leftover: `ops status` still printed "Buffer this
week: 17 packed, 6 posted - mark each with ops crosspost done".

**How.** Every status line reads Buffer's own state, and a failure is said, not found.

**Who:** Code. **Done when:** `py -m scripts.ops crosspost status` - a week with no command typed
for posting.

**Ideas:** #1398-#1407 in [backlog.md](backlog.md) under "S10". Built in wave 113: #1398.
Wave 125: a queued job's slot is moved before its event (#1552), and `ops unschedule` takes a
scheduled video off YouTube's schedule (#1555).

### S11 Clicks are unmeasured

**Now.** The YouTube Reporting API is still off in the sign-in's Google project; `ops doctor`'s
only failing reach check prints the link.

**How.** You turn it on; then #1058 feeds impressions and click-through into title and thumbnail
learning.

**Who:** You, then Code. **Done when:** `py -m scripts.ops packaging` - click-through per long
video.

**Ideas:** #1408-#1416 in [backlog.md](backlog.md) under "S11", and already open: #1058.

### S12 The first second

**Now.** Every TapIn video opens on a 2.15 s channel intro. On YouTube the test stands at 1 video
without it and 5 with (INTRO_TEST=alternate). TikTok viewers watch 1.24-1.68 s on average (Buffer,
2026-10-18) - they leave while the intro is still playing.

**How.** The TikTok and Instagram copies start at the first word. YouTube keeps its test until 3
each, then you decide.

**Who:** Code; you for the YouTube intro. **Done when:** `py -m scripts.ops growth` - TikTok
average watch above 3 s; the intro split settled.

**Ideas:** #1417-#1426 in [backlog.md](backlog.md) under "S12". Built in wave 113: #1417, #1418,
#1419. Built in wave 121: #1538 (the share who stayed beside the 3-second number).

### S13 Volume

**Now.** 13 uploads in the last 7 days, 4.5 a week over 28. YouTube quota: 9,485 of 10,000 units
used on 10-17 and 6,032 on 10-18 with 2 uploads left; the ledger kept only a daily total.

**How.** Know what spends the units and keep one upload's worth back from searches, then fill the
empty slots.

**Who:** Code; you for a quota increase. **Done when:** `py -m scripts.ops growth` - 7 a week for
4 weeks, and no upload deferred for quota.

**Ideas:** #1427-#1435 in [backlog.md](backlog.md) under "S13", and already open: #1057. Built in
wave 113: #1427. Wave 125: a caption file keeps an upload's units for each upload queued (#1553).

### S14 The sign-in ends every 7 days until the Google app is published

**Now.** The policy site is built; publishing the app is your click. No sign-in reminder shows on
10-18, so either the 7 days are not up or the app is published.

**How.** You publish the app; the code warns before a sign-in lapses and holds uploads cleanly if
it does.

**Who:** You; Code for the warnings. **Done when:** `py -m scripts.ops check-youtube` - no sign-in
needed for 30 days.

**Ideas:** #1436-#1445 in [backlog.md](backlog.md) under "S14".

### S15 Every best bet was a game (Oct 14)

**Now.** Fixed: decision 66 - five ideas and five previews, ranked by how many outlets carry the
story (#1300).

**How.** Weight domains by what holds viewers on this channel (the best 7-day video is a gaming
one, Cyclops at 968).

**Who:** Code. **Done when:** `py -m scripts.ops predictions` - each week's menu mix against the
views it earned.

**Ideas:** #1446-#1453 in [backlog.md](backlog.md) under "S15", and already open: #475, #473.

### S16 Clean drafts read as recaps (Oct 15)

**Now.** Fixed: the take detector reads a stated call, and since wave 112 the first sentence must
carry the stake and the call (#1311).

**How.** Measure takes and score the ones that predict.

**Who:** Code. **Done when:** `py -m scripts.ops growth` - stayed share after #1311 against
before, at n of 10.

**Ideas:** #1454-#1462 in [backlog.md](backlog.md) under "S16", and already open: #50.

### S17 Overnight crashed, and the morning said it ran (Oct 16)

**Now.** Fixed: the morning says when overnight stopped and why, and the next native crash names
its Python line (faulthandler).

**How.** Isolate each render so one crash costs one video, and keep the evidence.

**Who:** Code. **Done when:** the weekly report - 0 crashes over 4 weeks.

**Ideas:** #1463-#1470 in [backlog.md](backlog.md) under "S17", and already open: #457, #445.
Built in wave 121: #1469 (the crash's Python line in the morning). Built in wave 122: #1468 (a
beat each minute; `ops status` and the morning say when a run died and what it was doing). Built
in wave 124: #1470 (the GPU and its driver in `ops doctor`). Built in wave 125: #1464 (each
overnight render in its own process).

### S18 Health read RED on a number nobody stored (Oct 16)

**Now.** Fixed: runs record the facts they were written from; authenticity reads 79/100 over 15.
Engagement's "recent" window is runs 109-133 (Oct 1-10), and the line does not say how old that
is.

**How.** Every health line names its source and its age, and a missing input reads unknown, not red.

**Who:** Code. **Done when:** `py -m scripts.ops health` - no line built on a missing input.

**Ideas:** #1471-#1480 in [backlog.md](backlog.md) under "S18". Built in wave 121: #1472
(unknown, never RED), #1475 (a line a day), #1478 (cost from the spend entered), #1479 (the
thresholds in one versioned table). Built in wave 122: #1473 (each line read back from what its
production writer stores), which found #1542 - the metrics sync froze a video's numbers at day 1.
Built in wave 124: #1546 (why a curve is missing, and which videos never synced).

### S19 "New England" lost its "New" (Oct 16)

**Now.** Fixed: whole team names reach the angle prompt, and a broken one fails the title check
(#1211).

**How.** Check names everywhere text reaches the viewer: captions, thumbnails, the voice.

**Who:** Code. **Done when:** 0 broken names in titles, captions and thumbnails for a month.

**Ideas:** #1481-#1488 in [backlog.md](backlog.md) under "S19", and already open: #334, #553.
Built in wave 121: #1486 (every mention read, cases for every league), #1487 (NE -> New
England), with #1539 (whole research names). Built in wave 122: #1481 (a gazetteer with NHL, MLB
and EPL for the title check), #1482 (the script and the caption cues), #1483 (the thumbnail).

### S20 Engagement is softening (Oct 17)

**Now.** 27.4% engaged over runs 109-133 against 32.3%. Nine newer videos have no rate yet -
mostly YouTube's 2-3 day lag; the sync ran on 10-18 at 10:04, and only `ops morning` or `ops all`
runs it.

**How.** Sync without you, say how old the window is, and split long videos from Shorts (run 120,
a 406 s NBA video at 11%, is most of the drop).

**Who:** Code. **Done when:** `py -m scripts.ops health` - the engagement window includes a video
from the last 7 days.

**Ideas:** #1489-#1498 in [backlog.md](backlog.md) under "S20". Built in wave 113: #1489, #1490.
Fixed in wave 122: #1542 - since 10-05 the sync stored nothing after a video's first day, so the
engagement it reads was day-one engagement.

### S21 The hook score is backwards (Oct 18)

**Now.** r = -0.42 between the hook score and stayed share over 14 videos. Wave 112 decided no
statistical retune before n of about 85 (master_plan M4.5); the first-line rule (#1311) was the
logic change, and the learned gaps steer the rewrite from n=21 (decision 67).

**How.** Measure hook features one at a time; whether the fixed score leaves the grade is your call.

**Who:** Code; you for the grade. **Done when:** `py -m scripts.ops growth` - hook r at or above
0, or the score out of the grade.

**Ideas:** #1499-#1507 in [backlog.md](backlog.md) under "S21", and already open: #1290.
Built in wave 124: #1499 - the score out of the grade and overnight's order (decision 70), which
meets "Done when"; #1500 #1501 #1505 #1506 - `ops hooks`, each trait on its own (over 22 videos
a question held 42% vs 21%, longer openers held more, r=+0.36). Built in wave 125: #1504 (ten
examples; settled notes replace the rules they contradict), #1503 (one of three hooks at review),
#1557 (the rewrite had adopted nothing on 17 of 18 runs), and the weak-hook hold lifted (#1549).

### S22 It grew faster than it shipped

**Now.** The Oct 18 audit took the backlog from 258 open to 70, and a check failed past 130; 59
were open on 10-18. That evening you asked for ten ideas per shortfall as numbered items.

**How.** Decision 68 raises the ceiling to 300 for these and waives "a wave closes as many as it
files" for this wave only; ideas expire without a measurement, and a merge sweep runs past 250.

**Who:** Code. **Done when:** `py -m scripts.ops roadmap-index` - at or under 300, and falling
after this wave.

**Ideas:** #1508-#1517 in [backlog.md](backlog.md) under "S22". Built in wave 124: #1510
(`ops roadmap-index --by-shortfall`). Built in wave 125: #1517 (`ops shortfalls` in the weekly
review).

## The rules the backlog keeps

From the 2026-10-18 audit ([backlog_audit_2026-10-18.md](backlog_audit_2026-10-18.md)):

1. An item is filed with a measurement or an operator ask - not an idea alone.
2. A wave closes at least as many items as it files - waived for wave 113 only (decision 68).
3. A duplicate is merged into the later or more precise entry on sight, and the closed one
   names it.
4. UI widgets live in [desktop_app.md](desktop_app.md)'s stages, not in the backlog.
5. A parked channel has one item (MoneyWise's depth wave).

**Done when:** `py -m scripts.ops roadmap-index` shows the open count at or under 300 and
falling. `tests/test_docs_lint.py` fails a backlog past 300.

---
## This week (H0)

Shipped in wave 113 (the operator's six): TikTok views and Buffer's own state (S10, S12; #1329, #1398, #1418), metrics synced without you (S20; #1489, #1490), advertiser-safe titles (S01; #1319), the quota by caller with an
upload reserve (S13; #1427), the earned follow line (S02; #1322), and cross-post copies that start at the hook (S12; #1417, #1419).

Yours, each one line:

1. Publish the Google OAuth app - the sign-in stops ending every 7 days (S14).
2. Turn on the YouTube Reporting API - the link is in `py -m scripts.ops doctor` (S11).
3. Enter the October ad (`py -m scripts.ops spend add --kind ads`), and decide on another by
   Oct 24 (S02).
4. The 11 playlists, if yes: `py -m scripts.ops playlists --apply --channel tapin` - 550 units (S01).

Done by you on 10-18: overnight can wake the PC - the task's WakeToRun is on and the power
plan allows wake timers (S07).

Answered 2026-10-18: NFL and NBA news join the ideas; the weekly long-form is a $0 compilation;
the first series is "Picks, graded"; 1 in 5 overnight drafts is a holdout. Answered 2026-10-18:
ten ideas per shortfall as numbered items (decision 68), and the six above.

## Next ten (H1, wave 111) - all ten shipped 2026-10-18

In order, cheapest and safest first; each batch was committed on its own (A-F).

| # | Item | Exit |
|---|---|---|
| 1 | NFL and NBA news in the ideas (#1303) | the menu's ideas include an NFL or NBA story |
| 2 | Audit corrections (#104, #1059 were shipped) and the twelve stale doc cards (#1269) | `tests/test_docs_standard.py` green; every card re-read |
| 3 | A status-only update keeps what YouTube holds (#1306) | `videos.list part=status` is the same before and after a go-public |
| 4 | A voice note's names corrected to the run's own (#1296) | "Molot" reads "Malott" |
| 5 | A test may not read the real `data/` (#1305) | `ops test` names any test that does |
| 6 | A call's why from the game itself (#1304) | a preview's why cites an injury, a projection or form |
| 7 | The calls ledger, scored (#1304) | `ops predictions` prints "Calls: N of M right"; the second menu build is fast |
| 8 | Picks, graded (#991) | the menu offers it once 3 calls are scored in a week |
| 9 | Holdouts, 1 in 5 overnight drafts (#83) | `ops predictions` compares holdouts with ranked picks |
| 10 | The weekly $0 compilation (#138) | `ops week-compile` renders the week's Shorts as one video; overnight queues it for a slot on Mondays |

## The quarter (H2, November-December 2026)

In order. Each needs H0/H1 underneath it, and each has a command that says it is done.

| # | Item | Needs | Exit |
|---|---|---|---|
| 1 | Click-through into title and thumbnail learning (#1058) | the Reporting API on (yours) | `ops packaging` shows CTR per long-form video |
| 2 | The weekly compilation every Monday, unattended (#138) | H1 #10 | `ops ypp` long-form hours rise from 10 |
| 3 | Picks, graded every week, and its own numbers (#991, #1304) | H1 #7-8 | `ops growth` shows the series' stayed share against the channel's |
| 4 | Stat cards and score bugs drawn from the facts (#1042; the record card shipped in wave 112) | - | a render with a record card; stayed share compared |
| 5 | The hook score retuned, the intro decided (#1290, #988) | n of about 85 for the score (master_plan M4.5); 3+ each side of the intro test | `ops growth`: hook r above 0, the intro split settled |
| 6 | An honest learning loop: holdouts read and a stop rule (#83, #354); the curves are stored (#356 closed) | H1 #9 | `ops predictions` holdout line with n |
| 7 | The two Apify actors replaced where quality holds (#1071) | - | `ops reliability`: $0 Apify across ten runs |
| 8 | Re-cuts of past winners (#1057) | the retention curve (#356) | re-cuts published and measured |
| 9 | The $0 voice, after your blind listen (#1038, the $0 TTS switch) | your ears | `ops tts-arms` verdict |
| 10 | The third-channel gate (#1079) | TapIn's stayed share past the bar | a decision recorded |
| 11 | The app: Stage 3 panels (the facts room first), then Stage 5 packaging | - | [desktop_app.md](desktop_app.md)'s stage exits |

**Beyond (2027):** clipping Shorts from long sources (Phase R), avatar and upscaling, a
multimodal review of the finished video, MoneyWise's depth wave once it is un-parked.
[master_plan.md](master_plan.md) M5 keeps reach last: it multiplies the quality underneath it.
