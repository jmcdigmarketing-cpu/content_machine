# Content OS — roadmap

> **Class:** plan · **Status:** living · **Reviewed:** 2026-10-13

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

### The stage: ship (2026-10-11 to 10-25)

**Operator, 2026-10-10:** videos going public, not new features. All 43 videos are public
(#1128). **As of 2026-10-13 nothing can go out:** the YouTube sign-in expired that evening and
no upload task is installed. Where each target stands:

1. **Sign in, and stop it expiring weekly** - `py -m youtube.oauth_setup --channel tapin`, then
   publish the Google consent screen (it is in Testing, which ends a sign-in after 7 days).
2. **Uploads go out on their own** - `py -m scripts.ops worker-task --install` (one line, the
   operator's; #1130). Run 132 has been queued since 10-10.
3. **Videos ready each morning** - overnight renders up to 2 clean drafts, queued unlisted;
   `py -m scripts.ops morning` is the morning (#1140). On 10-13 it rendered two and both were
   wrong (a game written as won before it was played; a preview rendered two days late). Both
   were pulled and the causes are fixed (#1148-#1152, wave 83): a game draft renders before
   its game or waits, a flagged title waits, and overnight stops at 3 finished videos waiting.
4. **The week against 3-5** - on the header.
5. **Click-through flowing** - `ops doctor`'s `reach` row prints the link (#1123). Still off.
6. **The intro test on** - `INTRO_TEST=alternate` in `.env`.

**Where the channel stands** (`ops ypp`, numbers of 10-11): 69 of 1,000 subscribers; 1,797
organic Shorts views in 90 days against 10,000,000 (147 a week against 777,778); 10 long-form
hours against 4,000. The 43 videos brought 2 subscribers. The near goal is the first 1,000
subscribers, not the Partner Programme.

During the stage only a defect a live run exposes gets built. **MoneyWise is parked** (#1134).
Operator calls open: runs 92 and 119 are public with a flagged claim never confirmed (#1136);
the competitor shortlist (`ops competitors suggest`, then `add --name`); the ad campaign
YouTube is counting (4,544 paid Shorts views) is not entered - `ops spend add --kind ads`.

### Recommended next five (non-app)

**2026-10-16.** #1215, #514, #418, #463 and #545 are done. The list is the five the
operator queued after those. **#1221** a neutral headline made a gaming best bet.
**#1227** junk correction URLs. **#1228** the fast-cut timeout. **#1229** one draft per
child process. **#1043** footage tagged by team (run 155 cut four untagged Madden clips).
Finished output changed: hook-motion frames are pre-scaled, and an intro with audio fades
out over its last quarter second.
`roadmap-index` after Cursor's five, with Claude's uncommitted #1230-#1232 already ticked:
open 297, done 965, numbered open 245, highest open #1229.
Claude's waves 81-90 closed #1137-#1193 (the detail is in [planning_log.md](planning_log.md)):
your own idea's script, the morning screen, game previews, corrections checked against their
own page, TikTok and Instagram through Buffer's API (§54), two games of five best bets (§55),
the overnight videos in `py main.py`. Offered to Cursor: **#1194** learning per platform
([initiative_cross_platform.md](initiative_cross_platform.md)). Waves 91-94 (#1200-#1214):
hand posts left alone (§57), `ops all` ends with the morning (§56), Buffer reads the bucket's
public address (§58), a draft's stance counts as a take, the review names the failing check,
`ops crosspost buffer-check`. Waves 95-98 (#1216-#1226): a crashed overnight is said, runs
record their facts, dead drafts say so first, team names stay whole, calm drafts get a beat.
Wave 99: one `ops worker` sends every due upload (#1230), a render past its window stops holding
the shelf (#1231), `ops crosspost public-url` (#1232). Wave 100: a chain's honest no-match is
not a failure (#1233), "Beats" the brand is not a result (#1234). Claude has nothing claimed.
The step-by-step: [operator_guide.md](operator_guide.md).

Not next:
#1025 (Later), #1029 (who stayed is on 39 videos since #1124 - after the ship stage), #1038 (the operator's blind listen),
#1015 (waits on PySide), #975 (waiting on a boosted video), desktop B2 (#1068, #1064).

Parked for an operator call: **#459** dead-code sweep (it would remove reddit's free backend).
**#914** (an emoji font off Windows) waits on whether renders ever leave the PC.

**Waiting on runs:** #849 fact-fit needs 5+ measured runs carrying it; #863's call prints itself at ten; #963-#965
(does a settled topic still get a paste?) needs ten runs in `ops auto-research`.

**Waiting on the operator, not on code:** the back-home tick-list (an artifact page Claude reads
back): git pull and `pip install -e ".[app]"`; in ElevenLabs lower Stability (~35-45) and raise
Style (~20-30) on the TapIn voices; `ops spend add` for what was paid; record 20-30 min of Madden /
UFC 5 gameplay (`ops footage-add`) - with stock a last resort it is what fills a video; confirm run
120's claim and run 119's with `ops verify-claim` (run 119's chapter line is fixed in Studio by hand),
then `go-public`; rerun the Chargers idea and press Enter on angle 1; hand
Cursor [cursor_brief_2026-10.md](cursor_brief_2026-10.md); read `ops promotions` on Oct 24.

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
4) sync analytics · 5) make a video from your own idea / a YouTube link

**Recommendation helpers:** `py -m scripts.ops recommend-time --channel tapin` ·
`recommend-length` · best-bet shown at startup

**Developer setup:** `pip install -e ".[dev]"` and `git config core.hooksPath .githooks`
(not `pre-commit install` — the repo's hooks live in `.githooks`); `ruff check .` ·
`ruff format .` · `py scripts/mypy_ratchet.py` · `py -m scripts.ops test --order reverse`.
Tooling config lives in `pyproject.toml`.

**Troubleshooting:** [debugging.md](debugging.md)

---

*Never commit `.env`, OAuth tokens, or `client_secrets.json`.*
