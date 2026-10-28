# The bridge — the race to monetization, or big views for little money

> **Class:** plan · **Status:** living · **Reviewed:** 2026-10-27

The operator, 2026-10-27: *"start preparing for the next big phase of the project. next 100= ideas
and lets make the bridge to success starting now, with all changes being in race to monetization or
big views for low cost."* - and on the first draft: *"make it 300 ideas."*

This page is that phase. It supersedes nothing: [hands_off_plan.md](hands_off_plan.md) keeps the
22 shortfalls and how the machine runs itself; this page decides **what is worth building next**.
Its 300 ideas are numbered #1597-#1896 in [backlog.md](backlog.md) under "The bridge", each with
its lane. The four answers behind it are [decision 82](decisions_2026-10.md).

## The honest read (measured 2026-10-27, after the sync)

| | now | the bar | per day needed |
|---|---:|---:|---:|
| Subscribers | 134 total - about 4 from the videos, the rest with the ads | 1,000 **organic** | - |
| Shorts views, 90 days | 3,852 organic (+4,970 paid) | 10M today, **20M from 2027-02-01** | 111k today, 222k after |
| Long-form hours, 12 months | 10.2 | 4,000 today, **8,000 from 2027-02-01** | 11 today, 22 after |
| Money outside YouTube | $0 | - | - |
| Organic views a day | ~250 (W43: 1,389 a week, +33%) | | |

**What does not count.** Google's Promote help page: *"Watch hours & subscribers gained through ad
campaigns do not count towards YPP eligibility thresholds"*, and promotions do not change a video's
organic reach. The two Oct 26 campaigns bought about 37k views and 29 subscribers for $15.65 ($0.54
a subscriber) - none of it toward the bar. **Decision 82: paid promotion stops.** Three of the four
campaigns are in the spend ledger (`ops spend`) so paid and organic stay apart; the fourth (Oct 8)
waits for its numbers.

**The date.** Several outlets report that from **2027-02-01** new applicants need 1,000 subscribers
plus 8,000 qualified long-form hours in 12 months or 20M qualified (engaged) Shorts views in 90 days
- double today's bar. YouTube's own help page has not been found to confirm it (B10.16 checks).
Neither path is reachable before that date at today's pace; the bridge aims at the new bar on both
paths at once (the operator's answer), with money outside YouTube started now.

**The fastest views of the year.** GTA 6 launches **2026-11-19** - 23 days from this page. A gaming
channel's best organic Shorts have been big franchise stories told plainly (Cyclops joins Marvel
Rivals 968, Modern Warfare 4 325, the GTA 6 trailer reactions 305). Section B11 is that window.

**What each video costs.** A draft is a median $0.04; a render with ElevenLabs $0.20-0.40; about
$36.74 of runs so far against roughly 5,000 organic views.

## The lanes and the gate (decision 82)

Every change names its lane and the number it moves:

| lane | the number | where it is read (B10 builds what is missing) |
|---|---|---|
| **views** | organic Shorts views a day; engaged views in 90 days | `ops scoreboard`, `ops ypp` |
| **subscribers** | organic subscribers a week (YouTube's total minus the campaigns' counts) | `ops ypp`, `ops promotions` |
| **hours** | qualified long-form hours a week | `ops ypp` |
| **money** | dollars a month earned outside YouTube | `ops spend` (income, B07.7) |
| **cost** | dollars per 1,000 organic views | the weekly report (B09.1) |
| **defect** | a defect that holds or breaks publishing - always passes | - |

An open backlog item carries ` · lane: <lane>` at the end of its line; `tests/test_bridge.py`
fails CI on an open numbered item without one. An item that moves none of the numbers is
**parked** - `- [-]`, with the reason - neither open nor done (`ops roadmap-index` counts them).
On 2026-10-27 the 158 open items became 63 with a lane, 94 parked and 1 done; a parked item comes
back with a new number when a lane needs it.

## The waves, in order

1. **Wave 132** - [cloud_brief_wave132.md](cloud_brief_wave132.md), written 10-25: the hook splice,
   previews read as explainers, sources, a 5-8 minute Week in Review, one marquee preview a night,
   headlines told as the story, the topic gate. Already lane-tagged (#1587-#1596).
2. **Wave 133 - the GTA 6 window** (B11, before 11-19): the daily countdown series (B11.1), the
   "everything we know" long video by 11-10 (B11.4), Rockstar's press footage (B11.11), the marquee
   list front-loaded (B11.13), the fast lane armed for GTA 6 (B11.21), launch day planned (B11.24).
3. **Wave 134 - the scoreboard** (B10.1-B10.4, B05.1, B09.1): organic subscribers, engaged views,
   qualified hours, the 2027 bars as data, the race clock, cost per 1,000 organic views - so every
   later wave is judged on the bridge's numbers.
4. **Wave 135 - speed and volume** (B03): the breaking-news fast lane, three a day as an
   experiment, results fast lanes, Shorts that loop (B02.1-B02.3).
5. **Wave 136 - money outside YouTube** (B07): Amazon links on long-form, the affiliates map, the
   link-in-bio page, Facebook Reels through Buffer - once your sign-ups are done.
6. Then by lane share: views and hours first while both bars are far (B10.5).

## The sections

Each section's 25 ideas are in [backlog.md](backlog.md) under its heading; its last idea is the
lane's number and the command that says it is done.

### B01 Topics that travel - views (#1597-#1621)
**Now.** The best Shorts tell a big subject plainly; one-outlet small news earns 2-16 views; soccer
46 a video. **How.** A marquee list that learns, rising search terms, competitor outliers, community
heat, follow-ups on winners, release and patch calendars; small or stale stories stay in the menu.
**First:** B01.1, B01.3, B01.4, B01.5, B01.17.

### B02 The first second and the loop - views (#1622-#1646)
**Now.** Every render ends on ~0.8 s of a dark still - a Short that should loop; the closer "Tap in
for more" is in 9 of 12 scripts; TikTok viewers watch ~3 s. **How.** End on the last word, a loop
line, the subject in the first frame and first three words, a stake card, footage that matches the
story. **First:** B02.1, B02.2, B02.3, B02.5, B02.6.

### B03 Volume and speed for little money - views (#1647-#1671)
**Now.** 18 uploads in 7 days at noon and 10 PM slots; news is hours old when it goes out. **How.**
A fast lane public in 90 minutes, results within the hour, three a day tested, five drafts a night
when the gate passes them, every long video cut into Shorts. **First:** B03.1, B03.2, B03.3, B03.4,
B03.24.

### B04 Formats that travel - views (#1672-#1696)
**Now.** Formats are not recorded, so none can be ranked. **How.** Debates, rankings, quizzes,
stat-shock, "who is", "what's next", the game-ratings crossover - each recorded and rotated out
when it underperforms. **First:** B04.20, B04.1, B04.2, B04.5, B04.19.

### B05 Organic subscribers - subscribers (#1697-#1721)
**Now.** +1.0 a week from the videos. **How.** Measure organic only; a true follow reason per
format; part-2 stories; channel sections and description; replies to comments (your call first).
**First:** B05.1, B05.2, B05.3, B05.6, B05.11.

### B06 Long-form hours - hours (#1722-#1746)
**Now.** 10.2 hours; the first Week in Review has 1 view. **How.** Search-led long videos on marquee
subjects (UFC recaps, tier lists, franchise explainers), chapters and titles from search terms, an
hours ledger, Shorts that point to the long video. #1315 (a written weekly long-form) is already
open in this lane. **First:** B06.7, B06.1, B06.4, B06.9, B06.3.

### B07 Money before YPP - money (#1747-#1771)
**Now.** $0; Shorts' description links are not clickable. **How.** Affiliate links on long-form and
in bios (Amazon, game-deal partners, Fanatics), Facebook Reels, TikTok cuts over a minute for
Creator Rewards, income entered beside spend. No gambling or betting promotion, ever (B07.18).
**First:** B07.1, B07.2, B07.4, B07.8, B07.7.

### B08 Reach outside YouTube - views (#1772-#1796)
**Now.** TikTok 22 posts, 2,075 views; Instagram 22 posts, 2,304. **How.** Every Short crossposted
within the hour, TikTok-native first frames and captions, X for sports, per-platform hours, a
platform rests when it returns nothing. **First:** B08.1, B08.4, B08.7, B08.2, B08.8.

### B09 Cost per 1,000 organic views - cost (#1797-#1821)
**Now.** ~$36.74 of runs over ~5,000 organic views; the voice is most of a render's cost. **How.**
The number per video, Flux off for Shorts, a cheaper voice tested, the TTS cache on, signals judged
on the topics that won, nothing paid for a draft that will be held. **First:** B09.1, B09.2, B09.6,
B09.7, B09.13.

### B10 The scoreboard and the gate - views (#1822-#1846)
**Now.** `ops ypp` reads today's bar, counts total subscribers, and views rather than engaged views.
**How.** The four numbers with pace, the 2027 bars as data, the race clock, experiments with stop
dates, a wave scorecard. **First:** B10.1, B10.2, B10.3, B10.4, B10.15.

### B11 The GTA 6 launch window - views and hours (#1847-#1871)
**Now.** 23 days to 11-19. **How.** A daily countdown, launch-day and launch-week Shorts, three long
videos before launch and two guides after, edition links, Rockstar's press footage, the fast lane
armed. **First:** B11.1, B11.4, B11.13, B11.11, B11.24.

### B12 The sports calendar - views (#1872-#1896)
**Now.** Previews were reactive and drafted late (run 193, 31 minutes before kickoff). **How.** A
two-week calendar of marquee events - numbered UFC cards, NFL prime time, NBA national games, the
trade deadline, Thanksgiving, The Game Awards - planned 24-48 hours ahead. **First:** B12.1,
B12.2, B12.4, B12.22, B12.7.

## Yours

- **End the two Oct 26 campaigns** in YouTube Studio (Promotions), then send their final spend and
  subscribers; and show the fourth Promotions row (the $40 campaign that stopped Oct 8) - it is not
  in the ledger yet.
- **Amazon Associates** sign-up (B07.1), then the tag goes in `.env`.
- **A Facebook Page** connected in Buffer (B07.8).
- **Publish the Google app** before Fri 10-30 (sign-in).
