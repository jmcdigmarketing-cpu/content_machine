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

**2026-11-01 (Claude, wave 144 - the next 15, S02).** Trending Shorts end on a true reason to
follow - the subject's public long video, its countdown, or the Monday Week in Review - and long
descriptions and the bio pages carry a subscribe link (decision 96). Long videos: payoff in the
first 40 words, search-term tags and chapter titles, a drop-off line. The calendar: the GTA 6
editions long video Nov 9, the trade-deadline fast lane Nov 9-11, The Game Awards Dec 11. The
same fight is never drafted twice; a leak is never titled as fact; runs 120 and 126 refiled as
Gaming. Next, with **S15** (the menu 43 points off the views): **#1866** the week-one special
Week in Review, **#1779** weekly per-platform rows, **#1713** unsubscribes a week, **#1961** the
leak rule's subject-only warning.
**2026-11-01 (Claude, wave 143 - the next five, S06).** All four public "recaps" made a call
the take detector did not know ("Here's the trap", "the real question is density"); it
learned six shapes and S06 reads 0 of 48 (decision 95). A countdown day was held for sharing
GTA 6's words with yesterday's - series days now compare on wording. GTA long videos link both
editions; a long description is a 150-250 word summary led by its title; no gambling link, ever.
#1730 is parked: YouTube's API cannot set a Short's related video. Next, with **S02** (4
subscribers from 91 videos): **#1729** deep-dive Shorts end on the full video, **#1726** keyword
chapter titles on long videos, **#1960** the same fight drafted twice, **#1733** each long
video's drop-off minute.
**2026-11-01 (Claude, wave 142 - the next five, S05).** Your verdicts tracked the views (0.65);
the grade did not - 15 of 40 measured videos in their views' third, chance 33% - so it gates
nothing now (decision 94; GRADE_GATE brings a floor back) and S05 reads it against the audience.
An NFL team named by nickname reads NFL, and 10 stored subjects were corrected (S15: gaming 67% of
the views). Amazon links carry a tracking ID per place - long videos and a link page per bio -
and the sync keeps which outside site sent a view. The captions end 450 px up, clear of
Instagram's caption rows. Next, with **S06** (4 of 48 public videos read as a recap): **#1730**
each Short's related video set to its topic's long video (GTA 6 on Nov 6), **#1749** GTA 6
edition links before 11-19, **#1741** long descriptions with the search terms, **#1764** no
gambling affiliate, ever.
**2026-11-01 (Claude, wave 141 - the next five, S01).** You set the Associates tag and turned on
the Reporting API (the report job runs; S11 now waits on YouTube's first file). S01: the two
Weeks in Review drew 4 views and 0, so the slot measured where long views come from - by
traffic source, with minutes - before writing a better one (#1315 waits). The menu offered
gaming 24% while gaming earned 59% of organic views: S15 passes within 15 points, and three
ideas of five are gaming (decision 93). Chapter Shorts now count for their parent's domain;
Cyber Monday is a long deals video drafted Nov 28; S09 counts corrections; S10 skips what you
left. Next, with **S05** (your verdicts against the audience, 54%): **#1919** the link page's
clicks, **#1752** Amazon tracking IDs per platform, **#1947** two gaming videos stored as
another domain, **#1931** Instagram's side buttons.
**2026-10-28 (Claude, the bridge).** Decision 82: waves 132-136, each with a brief ([133](cloud_brief_wave133.md) [134](cloud_brief_wave134.md)
[135](cloud_brief_wave135.md) [136](cloud_brief_wave136.md)), dated in [bridge_calendar.md](bridge_calendar.md) - [bridge_plan.md](bridge_plan.md).
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
