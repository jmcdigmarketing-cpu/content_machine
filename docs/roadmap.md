# Content OS — roadmap

> **Class:** plan · **Status:** living · **Reviewed:** 2026-10-22

**What to do now.** The full inventory, the desktop programme, and the history live
in their own files — this one stays short enough to read at the start of every
session.

| file | what it holds |
|---|---|
| **roadmap.md** (this) | the current stage, the next five, track counts |
| [desktop_app.md](desktop_app.md) | the Windows application programme — stages 0–7 |
| [backlog.md](backlog.md) | every open item, numbered from 21 to the highest `ops roadmap-index` reports, plus unnumbered |
| [roadmap_archive.md](roadmap_archive.md) | completed waves and historical phases |

Direction: [vision.md](vision.md) · pace and cost: [operating_plan.md](operating_plan.md)
· decisions: [decisions.md](decisions.md) · honest state:
[assessment.md](assessment.md) · session state: [handoff.md](handoff.md) ·
brainstorming: [planning_log.md](planning_log.md).

**This is a private, local, single-operator tool.** Nothing here is published or
shared, which is why several "product" items were retired outright rather than
deferred — see [desktop_app.md](desktop_app.md).

---

## Now

**Just landed** - 2026-10-09 wave 66, built so the operator's run 124 idea ("How the 0-4 chargers
can turn it around this year") runs as intended: **#1016** your idea stays yours (angle 1 is your
idea worded for search, Enter keeps it, no take pushed onto it); **#1001 #1002 #1005 #1004** the
subject read right; **#1003** NFL records and next games from ESPN; **#1012 #1017** pasted junk and
unrelated vault facts kept out; **#1018** hooks on solid ground; riders **#1000** (a flagged render
never goes public at its slot), **#1019** CC BY credits, **#1020** stock only as a last resort, voice
speed 1.05. The next 100: [optimization_plan_2026-10.md](optimization_plan_2026-10.md); Cursor's run:
[cursor_brief_2026-10.md](cursor_brief_2026-10.md).

**Before that** - wave 65: **#996 #992 #998 #997 #994** · wave 64: **#988 #987 #959 #989 #977** ·
wave 63: **#985 #986 #984 #978 #979** · wave 62: **#980 #981 #982 #983 #976**. Earlier:
[roadmap_archive.md](roadmap_archive.md) and [planning_log.md](planning_log.md).

### The five weaknesses - where each stands (2026-10-03, after wave 53)

The operator's list from [assessment.md](assessment.md). Every row has shipped its main fix; what
is left is below.

| weakness | shipped | still open |
|---|---|---|
| 1 recency | key facts + vault, claim verifier + title check, grounding gate, thin-facts stop, "no champion from memory", future-date drop, single-source flag, auto-research, **#895** guard, **#899** event research, **#558** past-event previews retire, **#589** second provider on an empty answer, **#860** facts room + **#548** confidence per fact, **#910** links read at once, **#911** confidence in the dossier, **#342** corrections lower a source's weight, **#917** conflicts name the section that lost, **#551** elapsed-time arithmetic (**#978** titles and descriptions too), **#339** unconfirmed mode, **#977** checked against later runs, **#1003** NFL from ESPN, **#1004** news searches the subject, **#1002** lowercase teams, **#1012** pasted junk out, **#1017** uncertain vault facts must name the subject | **#1011** a stale signal record · **#1022** every league + injuries · **#1024** stale best bets |
| 2 API fragility | fail-visible handlers, breakers + quota governor, `ops reliability`, nightly signal canary, seven dead signals retired (**#854**), discovery deadline + cancel, **#385** + **#906** all 18 JSON signals pinned, **#626** contract tests, **#905** `ops record-payloads`, **#908** incidents say why, **#386** `ops replay` from saved signals, **#575** + **#588** `ops signal-audit`, **#921** no network in the suite, **#585** usefulness at discovery, **#574** skips you approve, **#591** seconds per signal, **#586** `ops signal-diff`, **#930** the suite never reads your keys | record real payloads on the PC (operator) |
| 3 relevance | RAWG current-era + relevance, Twitch/fan-out hygiene, domain from the topic, **#896** sports teams, **#897** odds, **#931** a lowercase overview seeds on known names, **#946** athlete names read as their sport, **#1005** no who's-who for common words, **#1016** your idea stays yours, **#1008** stale angles dropped before the menu, **#1014** angles scored without a per-angle fetch, **#1084** your stance kept - neutral by default, a take only when asked, **#1090-#1094** your idea heard once and kept, **#1089 #1095 #1096** slang read, research for the stance, two asks | **#1007** award races · **#1021** angle-pick learning · **#1006** video games read as gaming · **#1098** corrections become cue words |
| 4 visuals | **#1105-#1107** footage from the right folder and owned before stock, word-timed karaoke, auto-placed, ~2.5 s cuts from owned gameplay, clip bands, multi-voice, **#506** second-voice colour, **#411** ducked music bed, **#503** entrance (TapIn pop, MoneyWise fade), **#504** emoji drawn from an emoji font, **#955** footage matches the topic or stays out, **#1020** stock only as a last resort, **#1019** CC BY credits | thumbnails **#1047**, the voice **#1035**, licensed footage **#1040** (Cursor) · #786 your footage (operator) |
| 5 volume | sample counts, 95% intervals, confidence tags, recency weighting, shrinkage in all three recommenders (**#352**), **#559** prediction frozen at publish, **#113** `ops predictions`, **#357** `ops feature-report`, **#909** + **#913** every best-bet pick scored, **#915** scheduled videos counted, **#916** + **#912** the used slot scored and an off-slot test, **#560** forward-only error bars, **#563** time to 100 views, **#918** young videos synced, **#564** views floor, **#598** scheduled vs immediate, **#919** an experiment per kind, **#920** one labelled measure, **#566** title lift, **#428** tag lift, **#565** retention diff, **#579** cost vs return, **#567** a randomised publish hour, **#570** `ops analytics-diff`, **#927** seeded history deduped and out of post time, **#929** every measured run counts, **#934** a views goal and its pace, **#935** your verdicts against the views, **#938** the recommenders aim at 7-day views, **#940** comparable views per video, **#954** organic only - ads out of every number, **#951** stayed / feed share and CTR, **#957** organic engaged rate, **#49** first-day alert, **#945** views prediction, **#985** which openers held viewers, **#988** the intro measured, **#959** what each ad campaign bought, **#992** paid subscribers, **#998** after the ads | #975 the organic rate on a real boosted video · more measured videos |

### The stage: the bridge (from 2026-10-27, decision 82)

**Operator, 2026-10-27:** *"all changes being in race to monetization or big views for low cost."*
Every item names its lane - views, organic subscribers, long-form hours, money outside YouTube,
cost - or is parked (`- [-]`); `tests/test_bridge.py` holds the gate. The plan, the measured state
and 300 ideas (#1597-#1896): [bridge_plan.md](bridge_plan.md). Paid promotion stopped: Google does
not count its subscribers or hours toward YPP.

**Where the channel stands** (`ops ypp`, 10-27): 134 subscribers, about 4 of them from the videos;
3,852 organic Shorts views in 90 days; 10.2 long-form hours; ~250 organic views a day. The bar
reportedly doubles on 2027-02-01 (20M Shorts views or 8,000 hours, with 1,000 organic subscribers).
GTA 6 launches 2026-11-19 - the bridge's first time-critical window (B11). **MoneyWise is parked.**

### Recommended next five

**2026-10-28 (Claude, wave 132 - the first five).** The 10-25 session's defects: a spoken "..."
ended the hook and the swap stranded a fragment (#1587; 6 of 60 stored scripts carried one);
previews read as explainers from their own brief (#1588, a `preview` intent now); another game's
lines as sources (#1589); donation asks as facts (#1590); a flagged title retried (#1591). Next:
**#1847** the GTA 6 countdown (it should start 10-29); **#1595** the topic gate; **#1594**
headlines told as the story; **#1593** one marquee preview a night; **#1592** the 5-8 minute
Week in Review (Monday 11-02). #1596 (verdicts) waits a wave - it moves no number this week.
**2026-10-28 (Claude, the bridge).** Decision 82: waves 132-136, each with a brief ([133](cloud_brief_wave133.md) [134](cloud_brief_wave134.md)
[135](cloud_brief_wave135.md) [136](cloud_brief_wave136.md)), dated in [bridge_calendar.md](bridge_calendar.md) - [bridge_plan.md](bridge_plan.md).
**2026-10-25 (Claude, wave 131).** Measured first: runs 185 and 186 were held for a claim
until their game started and nothing pushed them - a held preview now toasts within 6 hours of
its game (#1582); the captions spelled numbers as the voice said them on 5 of 12 renders - they
show the script's digits (#1583). With the operator's calls (decision 80): one YouTube search per
topic per run (#1579); 9 of the 11 playlists made, the worker finishing the last two (#1584); the
menu's domains by organic views per video (#1448). Also long sentences split (#1360), why drafts
wait recorded and counted (#1585), the Oct 13 drafts as fixtures (#1339), #1353 pinned; #1586
filed - NFL brings 32 organic views a Short. Yours: publish the Google app before Fri 10-30;
#1586's call on NFL previews (answered, decision 81). Next: wave 132 from
[cloud_brief_wave132.md](cloud_brief_wave132.md) - the hook splice, previews read as explainers,
sources, a 5-8 minute Week in Review, one marquee preview a night, headlines told as the story.
Waves before 114 (the 10-17 grand audit, waves 103-113): [planning_log.md](planning_log.md).
**2026-10-19 (Claude, wave 114).** Two of wave 113's own defects first: the sync tried a channel with no sign-in (#1518), and a video moved on YouTube kept its old slot so Buffer was sent a day early (#1519, #1520 - run 154's posts removed with your yes). Then: Shorts read against Shorts (#1491 - the softening was one long video; GREEN), subscribers per 1,000 views (#1323), compilation hours (#1314), a stop rule (#354, #1423, #1507), one more render for an empty day (#1428), re-cuts of winners (#1057, #1521), a lockfile (#457). `roadmap-index`: open 243, done 1511, numbered open 234.
**2026-10-19 (Claude, wave 115).** Uploads stopped at 4 - captions took 1,200 units: a caption file now only with quota (#1525); the AI line appended at upload and added to the compilation with your yes (#1524); the sync's scope (#1523); the sign-in date, the worker's pass and overnight's start in `ops status` (#1437 #1402 #1372); a 2+-subscriber flag (#1325); a toast for a failed Buffer send (#1399); Shorts link the compilation (#1317); #1422's card not shipped - the headline already shows the hook. `roadmap-index`: open 235, done 1523, numbered open 226.
**2026-10-19 (Claude, wave 116).** A held upload named its reset instead of "overdue" (#1526); the queue listed three public videos, so the next slot was Sat - now Fri, every time in one zone, the two weeks at a glance (#1527 #1429); run 161 off run 156's minute with your yes; the lapsed sign-in holds uploads, a toast a day before, the console page and the mode (#1439 #1438 #1445 #1443); the last line and run-ons in the script check (#1334 #1352); a failed Buffer send retried once (#1400). `roadmap-index`: open 227, done 1533, numbered open 218.
**2026-10-20 (Claude, wave 117).** Overnight ran 11 h late because the PC was shut down, and the morning now says so from the event log (#1528 #1380), with a doctor wake check (#1371), a Tonight line and an 8 PM toast (#1337); the day-5 sign-in line keeps its date (#1529); `ops agents` reads the slots again (#1530); a follow-up draft for a video that brought subscribers (#1452); a toast when a video goes public (#1404); a schedule read back (#1392); cadence by its own rule (#1435). `roadmap-index`: open 220, done 1543, numbered open 211.
**2026-10-20 (Claude, wave 118).** None of today's 3 drafts rendered: "hard to say" now warns only (#1535) and its rewrite keeps a correct split (#1531); one splitter that respects "Oct." and "No." (#1532, run 176 repaired); the Tonight line reads the shelf pause (#1534); the deadline names its day (#1533); a Yours today line (#1407); chapter Shorts for an empty week (#1430); #1378 met, #1432 not needed. `roadmap-index`: open 216, done 1552, numbered open 207.
**2026-10-21 (Claude, wave 119).** With your yes before the lapse: 168 and 170 public, 171 retired - overnight renders again. A follow-up names the original's date and one that says "since" waits (#1536, run 179's last-season seed); "Yours today" says sign in again after the lapse (#1537); a crash keeps its log and the week counts them (#1466 #1463); each video's drop-off second (#1494); a cheap second read before an unattended render (#1341); "you typed / it wrote" (#1343 #1342). `roadmap-index`: open 210, done 1560, numbered open 201.
**2026-10-21 (Claude, wave 120).** The lapse landed and "Yours today" says sign in again. Health names its runs, its dates and each line's source (#1474 #1476 #1471 #1395); the weekly report counts the drafts a claim held (#1381); the privacy sync says what it checked (#1389); `ops retention` gives each video's first 3 seconds (#1426); `ops ypp` a monthly card (#1320); the compilation's title names its biggest subjects (#1316); #1386 met by #1083. `roadmap-index`: open 202, done 1570, numbered open 193.
**2026-10-22 (Claude, wave 121).** The next ten from the latest main, in two batches. The roadmap's five: the share who stayed beside the 3-second number (#1538), whole research names (#1539, and the news search's), "unknown" instead of RED (#1472), health history a line a day (#1475), Studio edits read back (#1390). Five neighbours: the thresholds in one versioned table (#1479), cost from the spend you entered (#1478), NE read as New England (#1487), the crash's Python line in the morning (#1469), every mention read in the title check (#1486, in place of #1391 - the API cannot say which thumbnail is live). Filed #1540 #1541. `roadmap-index`: open 193, done 1581, numbered open 184.
**2026-10-22 (Claude, wave 122).** A defect first: the metrics sync had stored nothing after a video's first day since 10-05 (#1542). Then the five: a team gazetteer for NHL, MLB and the Premier League in the title check (#1481); the script checked for a broken name and caption cues that never end inside one (#1482); team names whole on the thumbnail (#1483); a beat each minute so the morning and `ops status` say when overnight died (#1468); each health line read back from what production writes (#1473). Filed #1543 #1544. `roadmap-index`: open 190, done 1587, numbered open 181.
**2026-10-22 (Claude, wave 123).** The System32 pop-ups were ours: the overnight task's `cmd` window and ~16 console windows per 15-minute worker pass - now none (`hide_child_windows`, the task on `pythonw scripts\ops_task.pyw`). The cloud's five: painted thumbnail words (#1544), 76ers/49ers/Brighton whole (#1485), a memory check, a smoke render and a disk check before renders (#1465 #1467), a weekly fields audit (#1480). C: had reached 0 GB free. `roadmap-index`: open 186, done 1593, numbered open 177.
**2026-10-23 (Claude, wave 124).** Measured first: run 181, a Cavaliers-76ers preview, was still queued a day after its tip-off and nothing would have stopped it (#1547), and run 176, the UFC 333 preview, read "past its window" the day before the card (#1548) - both fixed. With the operator's calls: the hook score out of the grade and overnight's order (#1499, decision 70) and a power-on run is normal (decision 69). The five and two neighbours: `ops hooks` - each opener trait against who stayed, the first 3 s and TikTok (#1500 #1501 #1506) and length (#1505: longer held more, r=+0.36); why a curve is missing (#1546); the GPU driver in `ops doctor` (#1470); `roadmap-index` by shortfall (#1510). Filed #1549 #1550. `roadmap-index`: open 180, done 1603, numbered open 171.
**2026-10-23 (Claude, wave 125).** UFC 333 first: run 184 named the card by number and matched no event, so it was queued for Sun noon (#1551), and nothing re-checked a queued job against its event (#1552); with the operator's yes run 180 went to Fri 10:45 PM EDT and run 179 (last season's seed) off the schedule through a new `ops unschedule` (#1555). Captions wait for queued uploads (#1553), the weak-hook hold is lifted (#1549, decision 72), the lapse is dated (#1554). The five: ten best-held openers and settled notes in the prompt (#1504), one of three hooks at review (#1503), a render per process (#1464), `ops shortfalls` weekly (#1517) - and the hook rewrite, which had adopted nothing on 17 of 18 runs, writes calls again (#1557). `roadmap-index`: open 175, done 1615, numbered open 166.
**2026-10-23 (Claude, wave 126).** A phantom slot first: run 186, held by the grounding gate and so never public at a slot, held Sat noon - the slot run 184's UFC 333 preview needed before the card (#1558); the pass line said "Sent" for passes that sent nothing (#1559). With the operator's yes run 175 is set for Sun 10 PM EDT. The five: hook variants ranked by measured traits (#1556), the rewrite on/off as an experiment (#1502), the thumbnail confirmed by thumbnails.set's answer (#1540), the idea-expiry date (#1509), open items per public video (#1515). `roadmap-index`: open 170, done 1622, numbered open 161.
**2026-10-24 (Claude, wave 127).** Caught up with the cloud's decision 74 (`f2d7897`). The PC was shut down at 1:00 AM, so run 184's UFC 333 preview missed the card - and Friday's pass had uploaded two that could wait before it: a preview due soon is now claimed first (#1563). A dropped connection is an outage, not a broken signal (#1562); google's notice is out of the logs (#1561). With the operator's calls: a preview needs a call (#1367) and is read for a stated result before its event, bouts included (#1361), live games leave the ideas (#1364), Shorts' titles read who stayed (#1409); `ops thumbnail-check` (#1541) and the weekly mix (#1365). Decision 70's r corrected to -0.08 on healed numbers. #1560 filed after its first diagnosis was wrong. `roadmap-index`: open 167, done 1631, numbered open 158.
The step-by-step: [operator_guide.md](operator_guide.md).

Not next:
#1025 (Later), #1038 (the operator's blind listen),
#1015 (waits on PySide), #975 (waiting on a boosted video). Next app item is #161. #1067, #1064 and #1068 are done.

Parked for an operator call: **#459** dead-code sweep (it would remove reddit's free backend).

**Waiting on runs:** #849 fact-fit needs 5+ measured runs carrying it; #863's call prints itself at ten; #963-#965
(does a settled topic still get a paste?) needs ten runs in `ops auto-research`.

**Waiting on the operator, not on code:** the back-home tick-list (an artifact page Claude reads
back): git pull and `pip install -e ".[app]"`; in ElevenLabs lower Stability (~35-45) and raise
Style (~20-30) on the TapIn voices; `ops spend add` for what was paid; record 20-30 min of Madden /
UFC 5 gameplay (`ops footage-add`) - with stock a last resort it is what fills a video; confirm run
120's claim and run 119's with `ops verify-claim` (run 119's chapter line is fixed in Studio by hand),
then `go-public`; rerun the Chargers idea and press Enter on angle 1; hand
Cursor [cursor_brief_2026-10.md](cursor_brief_2026-10.md); November gets one $20 ads test (decision 74) - enter it with `ops spend add --kind ads` when it starts.

**Still the operator's, unchanged:** review the 05:00 drafts (`ops batch-review`); one OAuth
consent then `ops playlists --apply`; gameplay files for the empty niches (#786). After the first
live TTS run, check that `ops reliability` reports TTS-cache hits rather than `0/3`.
`ARTIFACT_RETENTION_APPLY` stays unset unless you want overnight to delete.

**Dropped from this list** (stay open): **#730** (operator call) · **#728** (no clip) ·
**#628** · **#731** · #952's direct APIs (Buffer instead) · Ollama. **#739 is closed, not dropped** - measured and rejected.

Closed-wave notes for waves 8-30: [roadmap_archive.md](roadmap_archive.md).

---

## Tracks

Every open item belongs to exactly one. Counts come from
`py -m scripts.ops roadmap-index`, never from hand-counting.

| track | what it covers |
|---|---|
| `app` | the desktop programme — see [desktop_app.md](desktop_app.md) |
| `engine` | angles, script, facts, grounding, claim verification |
| `video` | render, captions, assets, owned footage |
| `signals` | discovery sources, reliability, breakers, caching |
| `cost` | TTS, Apify, YouTube units, unit economics |
| `publish` | YouTube API, policy, scheduling, disclosure |
| `analytics` | the learning loop and its statistical honesty |
| `ops` | CLI, tests, docs, packaging hygiene |
| `parked` | deliberately not now — direct TikTok/Instagram APIs (Buffer instead), volume-gated studios |

---

## Still not happening

Direct TikTok/Instagram publishing APIs stay parked - Phase M goes through Buffer (#968). No SaaS, no web product, no
second operator seat, no standalone fact-engine surface — all retired on the
private/local constraint. The CUDA torch wheel is uninstalled by choice until
Stage 7; `ops doctor` reports `cuda` FAIL by design and it gates nothing.

---

## Operator checklist

**Fast path:** `py -m scripts.ops all-setup --channel tapin` then `py main.py`

1. `py -m storage.migrate_layout`
2. `py -m storage.migrate_schema` (until Alembic baseline replaces ad-hoc DDL)
3. `py -m analytics.seed_tapin --channel tapin`
4. `py -m config.validate_channels --channel tapin`
5. `py -m youtube.check_setup --channel tapin`
6. Add clips to `video/backgrounds/` for hybrid mode
7. `YOUTUBE_UPLOAD_ENABLED=true` + `py -m jobs.worker --loop 30`

**`py main.py` menu:** 1) new video · 2) queue manager · 3) intelligence report ·
4) sync analytics · 5) make a video from your own idea / a YouTube link ·
6) overnight videos and drafts · 7) watch and publish

**Recommendation helpers:** `py -m scripts.ops recommend-time --channel tapin` ·
`recommend-length` · best-bet shown at startup

**Developer setup:** `pip install -e ".[dev]"` and `git config core.hooksPath .githooks`
(not `pre-commit install` — the repo's hooks live in `.githooks`); `ruff check .` ·
`ruff format .` · `py scripts/mypy_ratchet.py` · `py -m scripts.ops test --order reverse`.
Tooling config lives in `pyproject.toml`.

**Troubleshooting:** [debugging.md](debugging.md)

---

*Never commit `.env`, OAuth tokens, or `client_secrets.json`.*
