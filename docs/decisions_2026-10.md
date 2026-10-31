# Decisions, continued (2026-10 onward)

> **Class:** reference · **Status:** living · **Reviewed:** 2026-10-13

[decisions.md](decisions.md) reached its size ceiling at decision 39 (docs_standard.md §7).
Decisions 40 onward are here, numbered on. Same rules: code says *what*, this says *why*.
Keep entries short.

---

## 40. Overnight may render, up to a number the channel sets (2026-10-11)
**Decision:** `ops overnight` renders up to `overnight.renders` drafts (tapin: 2; default 0) and
queues each one **unlisted**. It takes only a draft nothing is flagged on: no unsupported claim,
an `ok` authenticity verdict, no conflicting facts, no ungrounded name, no weak hook, no label
in the title, still inside its freshness window. It never queues public; the operator watches
and runs `go-public`. `OVERNIGHT_RENDERS` overrides the channel and the suite pins it to 0.
**Why:** this reverses "overnight stays render-free" (wave 27). That rule kept unattended runs
from paying for a voice; it also meant 69 runs stopped at a draft, because the morning review
that was meant to render them was not being run. The operator chose it: "yes, up to 2 a night".
**Consequence:** a night can spend ElevenLabs characters for two videos with nobody watching.
The checks above are the whole guard - loosen one and say so here.

## 41. A parked channel stays set up and out of the way (2026-10-11)
**Decision:** `"parked": true` in `channels.json` takes a channel out of the picker and takes its
own feeds out of `ops doctor`; `--channel <id>` still reaches it and deleting the flag restores
it. MoneyWise is parked. **Why:** it had made no video, and its dead finance feed was failing
the doctor for the channel that is worked. Nothing is deleted, so nothing has to be rebuilt.

## 42. A clean script is three things, and what cannot be backed is cut (2026-10-11)
**Decision:** a script is clean when it keeps the operator's idea and stance on every sentence,
says nothing the facts do not back, and uses the operator's typed points. A sentence still
unsupported after the one rewrite is **cut and named** on the review screen, as long as the
script keeps its length (`CUT_UNSUPPORTED`, at most two sentences). The whole check is stored
on the run as `script_clean`, and overnight renders only a script it calls clean.
**Why:** the operator's words - "my idea and stance rule", "nothing unsupported", "my typed
thoughts, used closely", and for a sentence that cannot be backed, "cut it, tell me which".
Hedging it ("reportedly") was the alternative and was not chosen.
**Consequence:** a script can come out shorter than it was written. A cut is never silent.

## 43. The mix of niches stays (2026-10-11)
**Decision:** no lean toward UFC in what gets drafted. **Why:** the operator's call. UFC's
median was 185 seven-day views over 10 videos against gaming's 90 over 30 - a difference, on
ten videos. Asked again when either side has thirty.

## 44. The morning has its own command (2026-10-11)
**Decision:** `ops morning` is the morning review (sync, what overnight rendered, the shelf,
the drafts). `ops all` stays the weekly batch and does not call it. **Why:** the operator asked
why the morning review was not in `ops all`; it was in no batch at all. A daily step inside a
weekly batch would either run weekly or make the weekly one ask a yes per draft.

## 45. A game draft renders before its game or waits (2026-10-13)
**Decision:** a draft written from a schedule pick carries its game's start (`event_at`).
Overnight leaves it for a person once the game has started, when its title or script states a
result for a game not yet played, and when its start is not known - a topic named like a
fixture ("A at B") with no time waits too. **Why:** on 10-13 overnight rendered two game
drafts and both were wrong - run 139 called a Thunder win hours before tip-off, run 136
previewed a Texans game two days after it was played. The operator chose "render only before
the game" over never rendering them and over not drafting them. **Consequence:** a result is
read by words ("win over", "dissected") with history ("last season", a year) and what is still
to come ("will", "if", a question) left out. It misses a result said another way; the claim
check and the title check are still behind it.

## 46. Overnight stops at three finished videos waiting (2026-10-13)
**Decision:** `OVERNIGHT_SHELF_MAX` (default 3; 0 = no limit). Overnight renders nothing while
that many finished videos are not public, and stops mid-run when a render reaches it.
**Why:** four were waiting on 10-13 with no upload task installed and an expired sign-in;
decision 40 would have added two a night and spent the voice characters for each. The
operator's call. **Consequence:** rendering resumes on its own when the shelf drops - a video
goes public, or is retired.

## 47. The research brief is not evidence (2026-10-13)
**Decision:** the claim check is not shown the research brief as a fact it can cite. The brief
still frames the script. **Why:** the brief is written by a model from the same facts. When it
restated them, the checker cited the brief as the plainest line, and the rule that a brief
"backs nothing strict on its own" (#966) then called every one of those claims unsupported -
5 of 5 on a replay of run 137, with the sources two lines away. That, not thin facts, is most
of why drafts were blocked. **Consequence:** a claim only the brief carries is unsupported, as
#966 intended. When the brief is the only text there is, it is still shown and still backs
nothing strict.

## 48. One model writes the whole script (2026-10-13)
**Decision:** `SCRIPT_BODY_TIER` defaults to `premium` again: one call writes the hook and the
body. `cheap` restores the split of #374. **Why:** the operator's call, on the measurement.
From run 134 a free-tier model wrote every body - a local 8B model on runs 136-138, 136 being
the one rendered (a fact told twice, a garbled last line). A run cost about a cent before the
split and about a cent after it. **Consequence:** roughly $0.002 more per script. This
reverses a default the other agent set; the split is one setting away.

## 49. An unbacked sentence is cut even when the script ends a little short (2026-10-13)
**Decision:** the cut of #1139 may leave a script at 85% of its minimum length. The stored
check says how many words short it is, and the review line prints it. Cuts made for stance or
repetition keep the strict minimum. **Why:** run 141's one cut left 148 words against 150 and
was refused, so the draft waited with the sentence in it. The operator chose a clean script
two words short over a flagged one. **Consequence:** a video can run a few seconds under its
length preset. Never by more than 15%.

## 50. A typed idea is drafted as angle 1 and kept (2026-10-13)
**Decision:** `ops script-check --idea` writes the idea the way angle 1 does in `main.py` -
the idea's own wording, no generated angle, no experiment directive - and saves it as a draft
that `batch-review` can render. **Why:** the command had passed the first *generated* angle
and three scripts were reported to the operator as "your ideas" that were not written from
them. A proof that does not take the operator's path proves nothing about it.

## 51. Old drafts are set aside, not kept waiting (2026-10-14)
**Decision:** at the start of each overnight run a waiting draft past twice its
freshness window (2 days for news, 7 for the rest) is marked `expired` in its own record
and leaves the waiting count. Nothing is deleted; `ops batch-review --expired` lists them.
`OVERNIGHT_EXPIRE_DRAFTS=false` keeps every draft waiting. **Why:** the operator's call;
the waiting count grew every night with drafts that would never render. **Consequence:**
the first run sets aside about 20 of 35 - more than the 6 "past their window" the question
named, because a draft blocked for a claim was counted under the claim, not its age.

## 52. A scheduled game is drafted as a preview (2026-10-14)
**Decision:** the schedule stays in the overnight batch as it is (the operator's call, "keep
as is"). A schedule pick whose game is ahead is drafted from a brief that says the game has not
been played, names the day, and asks for the matchup and what to watch - never plays or a
score. The brief goes to the angles and to the script; it is not counted as the operator's
points. **Why:** 9 of 9 batch drafts since 10-11 were schedule games, and the 10-14 three came
back as recaps of games two days away; the title check held them, but each cost a run.
**Consequence:** a generated angle that still narrates the game is held by the title check, as
before. The first draft under the rule (run 152, Ravens at Browns, game on 10-18) is a preview.

## 53. The morning shows open corrections and offers the sign-in (2026-10-14)
**Decision:** `ops morning` lists each open correction note once - video, claim, page - and,
when the YouTube sign-in has ended and a person is at the console, asks whether to sign in now
(Google's page opens; the sync runs after). Both are the operator's calls. A correction is
checked only against a page that names the claim's subject, retractions included. **Why:**
32 notes sat in the vault's `_reports` folder that no screen showed, and none of them was about
its claim: 4 of 5 pairs had been read against pictures, the fifth against an article about
someone else. The sign-in had been dead two days with the fix printed each morning.
**Consequence:** the older notes are counted on the morning screen, not listed, and not
rewritten. A nameless retraction notice no longer files - it was pinned on the run's first
claim and recorded that claim as reversed.

## 54. TikTok and Instagram go out through Buffer once a video is public on YouTube (2026-10-14)
**Decision:** with `BUFFER_API_KEY`, the R2 keys and the Buffer channel ids set, each video
made public on YouTube is scheduled on TikTok and on Instagram (a Reel shared to the feed)
through Buffer's API, automatically, one post a day per platform at the suggested slot, the AI
label on. Only videos made public after it is first set up; the 43 already public are left.
R2 hosts the video because Buffer fetches media from a link. **Why:** the operator's calls -
"once public on YouTube" (the watch-before-public that pulled two wrong videos on 10-13 then
covers these platforms too), "new videos only", "automatic from the start". **Consequence:**
nothing goes to TikTok or Instagram until a video goes public on YouTube; a video taken down
on YouTube has its scheduled Buffer posts deleted; `CROSSPOST_AUTO=false` stops it all.
The manual Buffer pack (#968) stays for a video sent by hand.

## 55. At most two of five best bets are games (2026-10-14)
**Decision:** this week's games come after the headline and channel-history picks, at most
`BEST_BET_SCHEDULE_MAX` (2) in five; more only when nothing else is left. The overnight batch
drafts from the same list, so its three take one game. **Why:** the operator's call - "ideas are
only game previews": #1023 put the games first and five NFL fixtures filled the start menu and
9 of 9 overnight drafts. **Consequence:** this changes the batch mix kept "as is" earlier the
same day (§52 stands: a game drafted is drafted as a preview). `BEST_BET_SCHEDULE_MAX=0` keeps
games out unless typed.

## 56. `ops all` ends with the morning (2026-10-15)
**Decision:** `ops all` is the weekly checks, analytics and review **and** the morning, each
step once, the draft review last; `ops morning` stays as the morning alone. **Why:** the
operator - "is morning ... included in script ops all??? that is what i want". It reverses the
10-11 choice (#1140) of keeping `all` weekly. **Consequence:** `ops all` from a console ends by
walking the waiting drafts; from a scheduled task or a pipe it skips them, as `morning` does.

## 57. A video posted by hand skips that platform (2026-10-15)
**Decision:** before scheduling, the automatic round reads the channel's recent Buffer posts; a
post that opens with the video's own words, made after it was rendered, means that platform is
done by hand and is left. The other platform still goes. `ops crosspost done --run-id N` marks a
video done by hand on both. **Why:** the operator posts some videos in Buffer themselves
(Topuria, Chargers, Minecraft, Rakhmonov) - "skip that platform only".

## 58. Buffer reads each video from the bucket's public address (2026-10-15)
**Decision:** R2 serves the video at the bucket's public address (`R2_PUBLIC_BASE_URL`: its
r2.dev URL or a custom domain), under a name with a random part; no presigned links. **Why:**
the live draft check (approved in the plan) - Buffer refused a presigned link, "Video could not
be read from its URL": the link downloads but answers HEAD with 403, and Buffer fetches again
when the post goes out. Buffer's hosting guide says the same. This corrects §54's mechanism, not
its rule. **Consequence:** the operator turns on public access for the bucket; the copy is still
removed once Buffer reports the post sent.

## 59. Games compete like any idea, and only marquee NFL and NBA games are ideas (2026-10-16)
**Decision:** a game on this week's board is an idea only when it is an NFL or NBA game on
national TV, carries a headline note (a London game), or is a game of a team the channel made a
video of its own about - a bare game name the old board drafted does not count. It says when,
where and the records ("Sun Oct 18 3:25 PM · Chargers, a team you made videos about · Chargers
0-5 at Chiefs 4-0"), and a game that has started is not offered. It takes its league's slot like
a headline or a past winner - after that league's fresh headline, one per league in the first
pass - with no reserved slot and no backfill: a thin day shows fewer ideas, not more games.
`BEST_BET_SCHEDULE_MAX` is retired. **Why:** the operator - "why do we get video ideas that are
just the names of sporting events, and then have those be the only ideas that show up?". ESPN's
board put 40 unplayed games in that night (16 college football, 13 NFL), two of five slots were
held for them and they filled every slot the other sources left; Oct 11 drafted three games and
nothing else. The plan's answers: "NFL + NBA, marquee games only" and "Compete like any idea".
**Consequence:** this reverses §55's mechanism; its reason stands. College, NHL and MLB games are
still read from the board, so a draft about one keeps its game-day window, but they are not
suggested. §52 stands: a game drafted is drafted as a preview.

## 60. An overnight render waits for the operator (2026-10-17)
**Decision:** a video rendered overnight is queued unlisted with no publish time and stays
unlisted until the operator makes it public - `ops go-public`, "now" in the watch-and-publish
pass, or the app's Go public button. Nothing goes public by itself, not at its post time
either. **Why:** the operator - "keep overnight renders waiting for me" (the answer to #1255;
since Oct 1, 4 videos rendered overnight and 1 went public). **Consequence:**
`tests/test_grand_audit.py` holds both halves: the overnight queue's privacy and publish time,
and the list of modules that may call `apply_go_public`. A new caller has to be an operator's
action and join that list.

## 61. TapIn and MoneyWise keep their colour grade (2026-10-17)
**Decision:** both channels render with their `color_grade` (TapIn: saturation 1.18, contrast
1.08, brightness 0.01 - the look of every published video). The `color_lut` setting and
`lut3d` path stay in the code; a `.cube` file goes in only once it reproduces the look it
replaces. **Why:** the grand audit found `bef5a56` (#497) had swapped the grades for 2-point
files that are nearly flat - TapIn's next videos would have come out duller. The operator:
keep the current look.

## 62. mypy checks the Windows build, on any machine (2026-10-17)
**Decision:** `[tool.mypy] platform = "win32"`, and `types-beautifulsoup4` is not a dev
dependency (bs4 4.14 ships its own types). The ratchet's count is then the same on this PC and
in CI. **Why:** CI had failed the type check on every push since 2026-10-11 (`adbc3c7`):
checked as Linux, `msvcrt`, `windll` and `CREATE_NO_WINDOW` were errors, and the 4.12 stubs
overrode bs4's types - CI counted 25 more than this PC, and the baseline had been lowered from
this PC's count. The product runs on Windows; a Linux-only path is behind a `sys.platform`
check that mypy reads.

## 63. TikTok and Instagram posts are not spaced (2026-10-17)
**Decision:** a video made public on YouTube is scheduled on TikTok and Instagram at the
channel's suggested time, however many posts that day already holds; a game preview goes before
its game (its draft's `event_at`), and one whose game has started is skipped. **Why:** the
operator - "bypass this always and lets actually just erase this rule. volume is a struggle
right now we do not have the volume or consistency to govern ourselves by that". The one-a-day
spacing of §54 had put run 155's Titans preview nine hours after kickoff. **Consequence:** this
reverses §54's "one a day per platform"; the rest of §54 stands (after YouTube is public, the AI
label on). The YouTube cadence guardrail (`MAX_VIDEOS_PER_WEEK`) is a separate rule and is
unchanged.

## 64. TikTok and Instagram post the same evening, and Reels run to 3 minutes (2026-10-17)
**Decision:** until a platform has its own learned hours (4 posts), a crosspost goes at the next
10 PM in the channel's time zone - always within a day of the video going public. Instagram
takes videos up to 180 seconds (`INSTAGRAM_MAX_SECONDS`). **Why:** the operator's answers.
Run 157 (UFC) went public on Saturday and its TikTok post was given YouTube's learned UFC slot,
Thursday 3:00 AM; Instagram skipped it at the 90 s cap. Both were moved: run 157 posts with
runs 126 and 155 on Saturday at 10 PM.

## 65. No YouTube cadence cap unless one is set (2026-10-17)
**Decision:** `MAX_VIDEOS_PER_WEEK` unset means no cap: the start menu shows no cadence line
(only the weekly floor when short of it), health's cadence is green, and no upload is blocked
and no slot skipped for volume. Setting it brings the cap back as it was. **Why:** the
operator - "Remove it"; "volume is a struggle right now". **Consequence:** the cap was the
volume half of the 2026 "mass-produced" guardrail; the variation half (the authenticity check)
is unchanged and still holds each script. The per-video Shorts spacing (#1055) stays.

## 66. Ten ideas: five ideas and five previews/predictions (2026-10-17)
**Decision:** the start menu shows five ideas (headlines, past winners, the follow-up, the
mailbag) and five previews/predictions (marquee NFL/NBA games, UFC cards of the next two weeks
from ESPN's UFC calendar, awards, then the other NFL and NBA games; one of each kind in turn;
nothing started, nothing already covered, nothing an idea on the menu already names).
Overnight drafts from both, an idea then a preview. `BEST_BET_OPTIONS` (5) and
`BEST_BET_PREVIEWS` (5) set the two sizes. **Why:** the operator - "need to work on idea
generation, maybe expand it to 10? 5 ideas 5 previews/predictions?"; the plan's answer: "10 = 5
ideas + 5 previews". **Consequence:** this reverses §59's "games compete like any idea" - games
have their own five places again - and keeps its marquee rule (§59) for which games lead.

## 67. Hook learning uses the last 90 days, and the rewrite's rules stay until n settles (2026-10-18)
**Decision:** `analytics/hook_learning` learns from videos made in the last 90 days
(`HOOK_LEARN_DAYS`). The default-on hook rewrite (#1018) gets the three recent openers that held
viewers best and the trait gaps, except a learned note its fixed rules contradict - it asks for a
number, a name, 12 words or fewer, a contradiction or stakes, and bans questions and weak openers
- which waits until n reaches the n that settles the correlation. **Why:** the operator, asked
how the rewrite should use the data once #1287 fed it: "90 days, rules stay". All 41 videos made
the three best openers June 4's first batch; over 18 recent videos questions held 38% vs 20% and
numbers 20% vs 26%, on 4 and 8 videos. **Consequence:** new videos' openers change - the prompt
quotes the recent best openers. At n=21 (today's settling n) the held-back notes go in.

## 68. The backlog ceiling is 300, for the 22 shortfalls' ideas (2026-10-18)
**Decision:** the backlog may hold up to 300 open items (`tests/test_docs_lint.py`), and wave
113 files ten ideas for each of the Content OS Story's 22 shortfalls as numbered items
(#1314-#1517; 16 slots cite an item already open). The 2026-10-18 audit rule
"a wave closes at least as many items as it files" is waived for wave 113 only; rules 1, 3, 4
and 5 stand. **Why:** the operator, asked where 220 ideas should go when the ceiling was 130:
"All 220 as numbered items" (the idea bank outside the ceiling was the other choice).
**Consequence:** open items rise from 59 to about 250; an idea with no measurement after 90
days is retired with the reason (#1509), and a merge sweep runs past 250 (#1514).

## 69. Overnight at power-on is fine - no Sleep ask (2026-10-23)
**Decision:** overnight keeps its 5:00 AM start and its wake for the nights the PC sleeps; a night
the PC was shut down, it runs at the next power-on (StartWhenAvailable), and that is normal. The
morning, `ops overnight-last`, the doctor, the Tonight line and the 8 PM toast say when it ran or
will run; none asks for Sleep. **Why:** 3 of 4 nights were shutdowns (10-19 8:49 PM, 10-21 9:02
PM, 10-22 9:51 PM) and each run started about 6 minutes after power-on; the operator, asked: "Power-
on is fine". **Consequence:** on a shutdown night the drafts come 15-60 minutes after the PC is on,
not by morning, and a preview of that evening's game can be too late (run 181, #1547).

## 70. The hook score is shown, not counted (2026-10-23)
**Correction (2026-10-24, decision 75):** the r = -0.48 below was read on the day-one numbers
#1542 had frozen; on the healed sync it is r = -0.08 over 28 (no relation either way). The score
stays out - it does not predict.
**Decision:** report card v6 counts the hook score at 0 and shows it; overnight renders a game
first by kickoff, then the newest clean draft - not the highest hook score. **Why:** over 22
measured videos the score ran against the share who stayed (r = -0.48, past p<0.05 at n=16); the
operator, asked: "Out of grade and order". It replaces wave 112's "no retune before n of about 85"
for the grade. **Consequence:** a card with a weak hook grades higher (#1550); the weak-hook hold
still reads the score (#1549); `ops hooks` measures each trait on its own.

## 71. Run 179 off the schedule; run 180 before the card (2026-10-23)
**Decision:** run 179, the Pistons follow-up, goes back to private with no publish time - its
script says "Since then, Detroit clinched the No. 1 seed" (last season) - and the file stays. Run
180, the UFC 333 main-event preview, goes public at the next free slot before the card (Fri
10:45 PM EDT). **Why:** asked, the operator took "Take it off the schedule" and "Yes, before the
card". **Consequence:** `ops unschedule` exists (#1555); Sat noon EDT goes to run 184, the other
UFC 333 preview, once the worker moves it before its event (#1552).

## 72. The weak-hook hold is lifted; a short script may keep its A (2026-10-23)
**Decision:** a "weak" hook verdict no longer holds an overnight render (it is still shown at
review), and report card v6 is unchanged for length. **Why:** the verdict reads the score decision
70 took out (r = -0.48 over 22 videos); the operator: "Lift the hold" and "No change".
**Consequence:** #1549 done, #1550 closed; `ops backlog`'s own gate still reads the verdict.

## 73. Hooks by measured traits, the rewrite tested, run 175 public (2026-10-23)
**Decision:** once the channel has learned traits, the hook rewrite ranks its variants by them
alone - no hook-score threshold (#1556); overnight drafts alternate the rewrite on and off, so
the experiment report (`py -m core.experiments`) can say whether it holds viewers (#1502); run 175 goes public at its next free
slot; the PC stays asleep tonight so run 184 reaches Sat noon. **Why:** the operator, asked, took
"Measured traits", "Yes, alternate", "Public at the next free slot" and "Leave it asleep tonight".
**Consequence:** half of the overnight drafts keep their first-draft opener while the test runs;
run 175 is set for Sun 10 PM EDT (Sat noon is kept for the UFC 333 preview).

## 74. November gets one $20 ads test (2026-10-24)
**Decision:** one YouTube ads campaign in November, capped at $20 (`ADS_MONTHLY_CAP=20`), entered
with `py -m scripts.ops spend add --kind ads --video <id>` on the day it starts, ended with `ops
spend end`, and its Studio result entered with `ops spend result` - so `ops promotions` can split
paid from organic, which it could not for October's campaign (never entered). **Why:** the Oct 24
reminder (set Oct 6); asked, the operator took "One $20 test in November". The record: one $40
campaign, stopped Oct 8; 64-65 subscribers in 28 days, 62 of them while it ran, the videos 2-4 -
about $0.65 a subscriber if the ad brought them; whether organic views lifted with it is not
measured. **Consequence:** the test is judged on subscribers per 1,000 paid views against organic,
cost per subscriber, and whether the non-promoted videos' organic views rose; entering the October
campaign as well lets `ops promotions` read both.

## 75. Previews need a call, live games are no idea, Shorts' titles read who stayed (2026-10-24)
**Decision:** a preview whose script makes no call waits for the operator instead of rendering
overnight (#1367); a game ESPN shows in progress leaves the idea list (#1364); a Short's title
patterns rank by the share who stayed, a long video's by engaged rate (#1409); and the hook score
stays out of the grade with decision 70's numbers corrected. **Why:** the operator, asked, took
"Hold it for me", "Leave it off", "Stayed share for Shorts" and "Keep it out". **Consequence:** fewer
unattended previews render, each with a call; the hook findings of waves 124-125 shrink on the
healed numbers (12 words or fewer 27% vs 28%, a number 28% vs 27%; a question 42% vs 25% on 3).

## 76. A finished game is what it means, with a call; sport scrapers stay in their sport (2026-10-24)
**Decision:** a video about a game ESPN calls final is written as what the result means - the
final in one sentence, then what it changes for each side (record, standing, next game) - and ends
on a call about the next game, never a play-by-play (#1362); its facts lose the lines dated before
kickoff that state a result between the two sides (#1363). The MMA scrapers (`ufc_context`,
`tapology`) no longer run on NBA or NFL topics, and the soccer API (`api_sports`,
v3.football.api-sports.io) runs on soccer topics only (#1566). **Why:** the operator, asked, took
"What it means + next call" and "Skip them". Measured over 60 runs: `ufc_context` ran on all 9 NBA
runs and fed nothing; `api_sports` fed German soccer clubs ("Kickers Offenbach") into 4 NBA runs as
raw JSON and nothing on 14 NFL runs. **Consequence:** a recap ends on a call, as a preview does
(decision 75) - recording it for grading is not part of this; discovery on a team-sport topic runs
fewer signals; `ops signal-audit` shows the per-domain numbers this rests on.

## 77. A chapter Short of a public video goes out by itself (2026-10-25)
**Decision:** an unlisted chapter Short cut from a video that is already public is scheduled public
at its free noon or 10 PM slot by the upload worker, without a review; a claim-held one waits. New
overnight renders still wait for the operator (decision 60), and chapter Shorts keep YouTube's own
frame - no thumbnail of ours is set (#1569). **Why:** on 10-25 four finished videos waited for the
operator - runs 190 and 191, cut from run 92, which the operator approved and which is public, and 185-186,
held for claims - so the shelf stopped overnight's renders and nothing was scheduled after Sunday;
asked, the operator took "Chapter Shorts only" and "Leave YouTube's frame". **Consequence:** the
shelf frees itself of chapter Shorts within a worker pass of their upload; `apply_schedule_public`,
once an operator-only call, now has the worker as its second caller (#1571).

## 78. A preview due soon pushes a toast; a clean render left unanswered goes out (2026-10-25)
**Decision:** a game draft whose decide-by time is within 3 hours raises a toast, once (#1572); a
render overnight made - it passed every check - that waits unlisted 24 hours unanswered, or a
preview whose event is within 30 hours, is scheduled public at its slot by the upload worker
(#1574), unless the operator set it aside or a claim holds it. Overnight's shelf cap is 5 while
fewer than 3 videos are scheduled in the next 7 days (#1434). A dull opener - no number, name or
call in three sentences - is a warning at review, not a hold (#1357). Previews rotate three shapes
as an experiment (#1366). **Why:** over the two weeks to 10-25, 18 of 46 drafts expired undecided
and only 4 of 14 game drafts went public before their game; asked, the operator took "Toast, then
clean renders go", "5 when the week is empty", "Warn at review" and "Rotate as an experiment".
**Consequence:** decision 60 now has two exceptions, chapter Shorts of a public video (77) and an
unanswered clean render; a draft held by a check still waits for the operator.

## 79. The intro goes; gaming keeps two ideas; previews ask for the viewer's call (2026-10-25)
**Decision:** the channel intro is dropped - renders open on the first sentence (#1581); while
gaming leads the channel's organic views, at least two of the five ideas are gaming (#1447); and a
preview that goes public gets one channel comment asking for the viewer's call (#1327). **Why:** the
intro test settled at 21% stayed with it against 44% without, and each intro render opened on 2.2 s
of silence; gaming brought 53% of organic Shorts views while the menu held one gaming idea in five;
channel comments had been built (#105) and never switched on. Asked, the operator took "Drop it",
"At least 2 of 5" and "Ask for the call on previews". **Consequence:** `CHANNEL_INTRO_ENABLED` is
off unless set; the comment is automatic (50 units each) and pinning it stays a Studio click.

## 80. One search per topic per run; the playlists made; the menu by organic views (2026-10-25)
**Decision:** the youtube and youtube_comments signals share one `search.list` per topic per
run - the shared call path keeps the result for 120 s behind a lock per query, and the second
caller books no units (#1579); the 11 franchise playlists are created and new uploads join them,
with no backfill (#1584); the menu's domains are ordered by organic Shorts views per video,
shrunk toward the channel's mean, a domain under five videos at the mean (#1448). **Why:**
comment reads cost 312-527 units a day, most of it a second 100-unit search for a topic the
youtube signal had just searched; every upload logged "no playlist yet"; the menu ranked domains
by engaged rate while organic views per video ran from 145 (NBA, 4 videos) to 32 (NFL, 6). Asked,
the operator took "Share it within a run", "Create + new uploads join" and "Views per video".
**Consequence:** CLAUDE.md's "no second cache inside a signal" holds - the kept search lives in
the shared call path, and each signal is still cached once by `register_signals`; the playlists
cost 50 units each, 500 so far; NFL falls to the bottom of the ideas (#1586 asks whether previews follow).

## 81. Week in Review in 5-8 minutes; one marquee preview a night; headlines told as the story (2026-10-25)
**Decision:** the weekly compilation covers every topic of the week as a short rundown, then the
top 3 by organic views in full, in 5-8 minutes (#1592); overnight drafts at most one preview a
night, and only a marquee event - a national broadcast or a league-marked game, or a numbered UFC
card (#1593, answering #1586: NFL stays, prime time only); a headline draft leads with what
happened to the biggest name and why fans care, while breakdown lenses stay for typed ideas
(#1594); an overnight story needs 3+ outlets in 48 hours or a name on the channel's marquee list
(#1595). **Why:** this week's compilation would have run 13:13 and the first had 1 view; 11
previews took a median 48 organic views against stories' 63; the best-watched Shorts told a big
story plainly (Cyclops joins Marvel Rivals 968, Topuria 631) while the default angles turned big
stories into mechanics ("How Cincinnati's tempo keeps Baltimore's young QB off balance").
Asked, the operator took "Top 3" - then revised it to "cover all topics ... as well as a deeper
dive on the top 3, maybe 5-8 mins" - "1 a night, marquee only", "The story + why fans care"
and "3+ outlets or a marquee name". **Consequence:** the story frame is not a take - #1084's
neutral-unless-asked rule stands; a thin night drafts fewer rather than pad; smaller stories and
other games stay in the menu for the operator. Specified for a cloud session in
[cloud_brief_wave132.md](cloud_brief_wave132.md).

## 82. The bridge: every change in the race to monetization or big views for little money; ads stop (2026-10-27)
**Decision:** from 2026-10-27 every change names its lane - views, organic subscribers, long-form
hours, money outside YouTube, or cost - and the number it moves; a defect that holds or breaks
publishing always passes; an item that moves no number is parked (`- [-]`, neither open nor done).
Paid promotion stops. The bridge aims at both YPP paths equally - 20M engaged Shorts views in 90
days and 8,000 long-form hours in 12 months, each with 1,000 organic subscribers - and starts money
outside YouTube now: affiliate links, a Facebook Reels crosspost, TikTok Creator Rewards as a
long-run target. **Why:** Google's Promote help page says subscribers and watch hours from ad
campaigns do not count toward YPP and promotions do not change organic reach - the Oct 26
campaigns bought ~37k views and 29 subscribers for $15.65 that count for nothing; 4 of 134
subscribers came from the videos; the bar reportedly doubles on 2027-02-01 (third-party reports).
Asked, the operator took "Stop paid promotion", "Both equally", "Affiliate links, Facebook Reels
crosspost, TikTok Creator Rewards" and "Park them"; then: "make it 300 ideas". **Consequence:** 158
open items became 63 laned, 94 parked, 1 done; 300 ideas filed (#1597-#1896) in
[bridge_plan.md](bridge_plan.md)'s twelve sections; `tests/test_bridge.py` fails CI on an open
numbered item without a lane; the backlog ceiling rises from 300 to 400 (decision 68's rule, for the same reason) and the bridge's ideas expire after 90 days like the shortfalls'; the campaigns are in the spend ledger.

## 83. The GTA 6 countdown: the stem then the story, an extra draft, held after its day (2026-10-28)
**Decision:** from 10-29 to 11-18 a daily "GTA 6: N days to launch" Short (#1847), titled
"GTA 6: 21 days to launch - <the day's story>" (the stem alone past 100 characters), drafted
overnight as an extra fourth draft on top of the night's count - even when drafts wait - and held
and retired once its day ends; the Week in Review plays the week's other Shorts as their openings
first, then the top 3 whole, counted down #3, #2, #1 (#1592). **Why:** GTA 6 launches 11-19 and
its Shorts are the channel's best (run 191, 1,030 organic views, the week's top); a countdown
published a day late states the wrong number. Asked, the operator took "Stem, then the story",
"An extra fourth" (not the recommended "One of the three") and "Rundown, then top 3".
**Consequence:** the countdown costs one more cheap script a night and one more draft to decide;
`config/series.json` holds it and `SERIES_COUNTDOWN=false` stops it; launch day is #1848's.

## 84. The GTA 6 window scheduled: three long videos after review, moments as extra drafts (2026-10-28)
**Decision:** `config/series.json` dates the GTA 6 window. Three 10-12 minute 16:9 videos -
"everything we know before launch" drafted 11-06 (public by 11-10), "the map, characters and
story explained" 11-12, "ten things to do first" 11-20 - rendered only after the operator
accepts the script; ten launch moments drafted on their dates as extra drafts; long-form
thumbnails from our own frames with GTA 6's colours, no outside image. **Why:** long-form is the
hours lane's only road (10.2 hours in 12 months) and GTA 6 is the channel's biggest subject (run
191, 1,030 organic views); a long voice costs about five Shorts. Asked, the operator took every
recommended option: "Three, dated", "After my review", "Extra drafts", "Our own frames".
**Consequence:** the brief's 11-19 "first impressions" could not be written before anyone had
played, so the launch-day Short drafted 11-18 is the unlock, size and what to do first, published
at `publish_at` (null until Rockstar states the time); first impressions move to 11-20 and the
fixes to 11-21. The review-score and sales Shorts wait for dates. Launch week can be 5-6 drafts a
night. `SERIES_DATED=false` stops it.

## 85. TapIn is gaming and sports equally; covers are our own frames with no words; AI covers off (2026-10-30)
**Decision:** TapIn's identity is gaming and sports, equally - one fan, one look, one voice, one
cover rule - while the day's mix still follows organic views per video (decisions 79-81 stand). A
video's cover is a frame of its own footage with no words; until that is built,
`YOUTUBE_THUMBNAIL_UPLOAD=off` lets YouTube show a frame of the video. The paid image providers
(Flux, Ideogram, Recraft) are off: their keys come out of `.env`, and the code paths retire with
[look_and_feel.md](look_and_feel.md) L7. Spending stays reeled back to what viewers hear or see
(the voice) and what saves the operator time; ads stay off (decision 82). **Why:** the operator,
10-30, with eight Studio screenshots ([studio_snapshot_2026-10-30.md](studio_snapshot_2026-10-30.md)):
"i dont like how each video has the same thumbnail when i submitted multiple clips for each" and
"reeling back on spent money is good given the numbers and critique". Read on `899ff58`: covers
were AI images from one prompt per genre (`assets/flux_thumbnail._build_flux_prompt`), never our
footage; a folder's clips are drawn in filename order, at most 12, with an 8-clip memory that is
off across runs unless `CLIP_MEMORY=true`; an untagged FC Barcelona menu sat behind the Kane, Real
Madrid and Man City Shorts. Asked, the operator took "Ads + AI thumbnails off", "Best frame, no
words" and "Gaming and sports equally" (not the recommended "Gaming first"). **Consequence:** the
charter pages [tapin_philosophy.md](tapin_philosophy.md) and [tapin_principles.md](tapin_principles.md),
and the plans [logistics_plan.md](logistics_plan.md), [look_and_feel.md](look_and_feel.md) and
[horizons_2027.md](horizons_2027.md); no code with this decision - the build list L1-L10 waits for
a wave and takes backlog numbers then; long-form keeps decision 84's own frames, with words a test
(#1731 without its face).

## 86. Downloaded backgrounds credited generically; organic subscribers "at most" until final (2026-10-28)
**Decision:** a background clip named like a free-to-use download, with no licence file of its own, is
third party and credited "Free to use with credit (attribution) - YouTube free-to-use gameplay
uploaders"; the organic subscriber count is YouTube's less the campaigns' entered subscribers, and
reads "at most" until every campaign's count is marked final. **Why:** the operator's 10-28 drop
of 19 YouTube downloads inherited the library's "owned" licence, so no video credited them; the
subscriber count went from 134 to 195 in a day with both Oct 26 campaigns recorded as ended at 29.
Asked, the operator took "Credit generically" (not the recommended source lookup) and "Count it as
unknown". **Consequence:** no file is written into the library and the next drop is covered; naming
each uploader is #1905; `ops spend result --entry N --subs N --final` ends the "at most".

## 87. The countdown a day ahead; only frame covers upload; the look list built (2026-10-30)
**Decision:** each night drafts tomorrow's countdown as well as today's, and every countdown renders
outside the night's limit and is uploaded private with its own noon as the publish time, so YouTube
publishes it with the PC off; `YOUTUBE_THUMBNAIL_UPLOAD=frames` - only a cover cut from the video's
own footage uploads - with the image models' keys out of `.env`; the next 15 are look_and_feel.md's
L1-L10 and wave 134's last five. **Why:** days 21 and 20 were missed (no runs on 10-29, the PC off;
on 10-30 overnight ran at 5:44 PM and its one render went to a game), and decision 85 wanted our own
frames. Asked, the operator took "Yes, post it now" (day 20, 11:08 PM ET after a sign-in renewal),
"A day ahead", "Yes, change it now" (`.env`), "Look list + scoreboard", "Yes, schedule it now"
(day 19) and "Yes, frames only" - every recommended option. **Consequence:** a countdown no longer
waits for a person; a Short's cover is a frame of its own shots, never one used before, and the Short
opens on that shot; the two experiments already running stop 14 days from their start.

## 88. Facebook from then on; the link page on R2; income beside spend (2026-10-31)
**Decision:** a Facebook Page connected in Buffer takes only Shorts made public after it is
connected - each platform keeps its own baseline, recorded the first round it is seen; the
link-in-bio page lives on the R2 bucket Buffer already reads (`tapin/links.html`), rebuilt each
night, and shows the latest long video, the week's three top Shorts and the affiliate links (with the
FTC line, once the Associates tag is set) - no profile links; income is entered beside spend and the
scoreboard's money row shows the net. **Why:** connecting a platform would otherwise send about 40
old Shorts at once; R2 needs no new account or host; the operator chose the contents. Asked, the
operator took "From then on", "On your R2 bucket" (both recommended) and "Latest long video", "The
week's top Shorts", "Affiliate links". **Consequence:** connecting Facebook in Buffer is the one step
left for Reels; the bios need the page's address pasted once; a crosspost's lateness is measured from
when Buffer got it, since decision 64's 10 PM due time is deliberate.
