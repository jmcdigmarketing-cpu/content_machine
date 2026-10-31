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

**2026-10-30 (Claude, wave 135 - catch-up and the next 15).** Caught up with the cloud's plans
(decision 85). Countdown days 21 and 20 were missed - the PC off at 5 AM, one render to a game: day
20 went out by hand at 11:08 PM ET, day 19 is scheduled, and each night now drafts tomorrow's,
uploaded for its own noon (decision 87). The look list L1-L10 (#1907-#1916): every clip in rotation,
no menu behind another club, covers cut from our own frames with no words and never repeated, the
Short opening on the cover's shot, only frame covers uploaded; and the scoreboard's rest - cost per
1,000 views ($1.67), the hours ledger, experiment stop dates, the wave scorecard, a breakout toast.
Next: **#1754** Facebook Reels, **#1772** every Short crossposted within the hour, **#1750** a
link-in-bio page, **#1753** income beside spend, **#1756** TikTok that can earn.
**2026-10-28 (Claude, wave 134 - the next five).** Your new backgrounds wired in: 19 downloads were
recorded as owned - now credited generically (decision 86); Call of Duty, Black Ops and Counter-Strike
topics reach their folders. The scoreboard: the bars as data, engaged views, organic subscribers "at
most 166" until the campaigns' counts are final, the race clock (96 days), one Bridge line in `ops
status`. Next: **#1797** cost per 1,000 organic views, **#1728** the hours ledger, **#1827**
experiments with stop dates, **#1836** the wave scorecard, **#1832** a toast for a breakout.
**2026-10-28 (Claude, wave 133 - the next ten).** The GTA 6 window is scheduled (decision 84):
three long 16:9 videos - 11-06 ("GTA 6 Release Date: Everything We Know Before Launch"), 11-12,
11-20 - drafted on their dates, rendered after your review; ten launch moments as extra drafts
(the unlock Short drafted 11-18 for `publish_at`); a 6 PM GTA slot and GTA-first drafting in
launch week; the countdown in day order in the GTA playlist; long-form titles from search and
cards from our own frames; affiliate links on long videos once your Associates tag is set; the
verdicts compare 24 ratings, not 3. Next: wave 134's scoreboard - **#1823** the YPP bars as
data, **#1824** engaged views, **#1697** organic subscribers, **#1825** the race clock, **#1822**
the scoreboard.
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
Wave 132 and waves before 127 (the 10-17 grand audit, waves 103-126): [planning_log.md](planning_log.md).
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
