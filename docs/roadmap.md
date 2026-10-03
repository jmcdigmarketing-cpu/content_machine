# Content OS — roadmap

> **Class:** plan · **Status:** living · **Reviewed:** 2026-10-03

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

**Just landed** - 2026-10-03 wave 56: **#949** `ops backlog` - fresh best bets drafted, the
ones that clear every gate rendered and scheduled over the next two weeks (news on the first
slots), the rest left for `batch-review`, `ops backlog pull` to veto; **#950** the auto-generate
task's hard-coded old path; **#953** fail-first on a HEAD worktree no longer imports new modules
from the main checkout.

**Before that** - wave 55: **#944 #938 #940 #943 #941 #942** · wave 54: **#934 #935 #936 #937 #114 #939** · wave 53: **#930-#933 #929 #591 #573 #586** (#587 closed) · wave 52: **#927 #928 #585 #574 #570 #571** · wave 51: **#921 #579 #575 #588 #567
#922-#926** · wave 50: **#920 #566 #428 #565 #578**. Earlier: [roadmap_archive.md](roadmap_archive.md)
and [planning_log.md](planning_log.md).

### The five weaknesses - where each stands (2026-10-03, after wave 53)

The operator's list from [assessment.md](assessment.md). Every row has shipped its main fix; what
is left is below.

| weakness | shipped | still open |
|---|---|---|
| 1 recency | key facts + vault, claim verifier + title check, grounding gate, thin-facts stop, "no champion from memory", future-date drop, single-source flag, auto-research, **#895** guard, **#899** event research, **#558** past-event previews retire, **#589** second provider on an empty answer, **#860** facts room + **#548** confidence per fact, **#910** links read at once, **#911** confidence in the dossier, **#342** corrections lower a source's weight, **#917** conflicts name the section that lost | - |
| 2 API fragility | fail-visible handlers, breakers + quota governor, `ops reliability`, nightly signal canary, seven dead signals retired (**#854**), discovery deadline + cancel, **#385** + **#906** all 18 JSON signals pinned, **#626** contract tests, **#905** `ops record-payloads`, **#908** incidents say why, **#386** `ops replay` from saved signals, **#575** + **#588** `ops signal-audit`, **#921** no network in the suite, **#585** usefulness at discovery, **#574** skips you approve, **#591** seconds per signal, **#586** `ops signal-diff`, **#930** the suite never reads your keys | record real payloads on the PC (operator) |
| 3 relevance | RAWG current-era + relevance, Twitch/fan-out hygiene, domain from the topic, **#896** sports teams, **#897** odds, **#931** a lowercase overview seeds on known names | - |
| 4 visuals | word-timed karaoke, auto-placed, ~2.5 s cuts from owned gameplay, clip bands, multi-voice, **#506** second-voice colour, **#411** ducked music bed, **#503** entrance (TapIn pop, MoneyWise fade), **#504** emoji drawn from an emoji font | #914 an emoji font off Windows · #786 footage and your music tracks (operator) |
| 5 volume | sample counts, 95% intervals, confidence tags, recency weighting, shrinkage in all three recommenders (**#352**), **#559** prediction frozen at publish, **#113** `ops predictions`, **#357** `ops feature-report`, **#909** + **#913** every best-bet pick scored, **#915** scheduled videos counted, **#916** + **#912** the used slot scored and an off-slot test, **#560** forward-only error bars, **#563** time to 100 views, **#918** young videos synced, **#564** views floor, **#598** scheduled vs immediate, **#919** an experiment per kind, **#920** one labelled measure, **#566** title lift, **#428** tag lift, **#565** retention diff, **#579** cost vs return, **#567** a randomised publish hour, **#570** `ops analytics-diff`, **#927** seeded history deduped and out of post time, **#929** every measured run counts, **#934** a views goal and its pace, **#935** your verdicts against the views, **#938** the recommenders aim at 7-day views, **#940** comparable views per video | #945 a views prediction · #946 fighter names read as gaming · more measured videos |

### Recommended next five (non-app)

**Wave 56 (2026-10-03)** built the backlog the operator asked for (away from the PC, videos keep
publishing). The operator set the order after it: **packaging, then Phase M** (direct APIs,
#952). The next five:

1. **#951 packaging** (with #948) `[M]` - what YouTube reports for the feed and for clicks; titles and thumbnails judged on it.
2. **#946 fighter names read as gaming** `[S]` - skews every recommender's domain counts.
3. **#947 the view-curve backfill re-fetches small videos forever** `[S]` - `ops all` runs it weekly.
4. **#49 a first-day alert** `[M]` - a video far under the channel's 7-day baseline says so on day one.
5. **#945 a 7-day-views prediction** `[M]` - beside the engaged-rate one.

Then **#952 Phase M**: TikTok (inbox mode until the audit) and Instagram Reels.

Parked for an operator call: **#459** dead-code sweep (it would remove reddit's free backend).
**#914** (an emoji font off Windows) waits on whether renders ever leave the PC.

**Waiting on runs:** #849 fact-fit needs 5+ measured runs carrying it; #863 needs ten.

**Waiting on the operator, not on code:** before time away, `py -m scripts.ops backlog --dry-run`, then `backlog`, then `worker` (#949). `py -m scripts.ops all` once a week (it runs `backfill view-curve --apply`, which the 7-day views target needs; `RECOMMEND_TARGET=engaged` switches the recommenders back) (#944 #938). Set your numbers in `config\goals.json` (the committed ones are placeholders), then `ops sync-metrics`, `ops scoreboard`, and `ops review-week` once a week (#934 #936); `ops mailbag` (#114); `ops winners` shows what the script prompt now sees (#937). `git pull` then the suite - it no longer reads your `.env` (#930). `ops signal-diff <A> --run-id <B>` on two runs of the same topic (#586). `ops dedupe-seed` then `--apply` - every past `all-setup` added the 44 seeded videos again (#927). `ops signal-audit --skip <name>` once a signal has fed nothing in 10+ runs (#574). After your next run, `ops analytics-diff <run>` (#570). `ops signal-audit` - which signals ever feed the script, and which return a frozen payload; retiring any is your call (#575 #588). `py -m core.experiments start post_time` now flips a coin per upload and moves off-slot ones a random hour (#567). `ops sync-metrics` then `ops predictions` - scheduled videos now sync and count (#915); `ops backfill view-curve --apply` for past videos' time to 100 views (#563); `py -m core.experiments start post_time` only if you want the off-slot test (#912); `ops source-trust` (#342); `ops weekly-report` for scheduled vs immediate (#598); `ops tag-report`, `ops title-patterns`, `ops retention-diff` (#428 #566 #565); `ops predictions` names how many videos sit under 50 views - set `MIN_OUTCOME_VIEWS=50` only if that looks right (#564). Render one video whose script has an emoji to see it drawn (#504); after your next run, `ops replay <run>` (#386) and `ops predictions` (the best-bet row, #909). `ops record-payloads` then `--apply` if the diff looks right (#905, real API shapes into the tests); on the next run in `py -m desktop`, use the facts room and time the key-facts step against run 98's 7.9 min (#860); `ops incidents` after a few runs says what YouTube's "unavailable" is (#908). Render one video per channel to see the caption entrance (#503; `"entrance": "none"` in `caption_skin` turns it off) and run `ops vault-decay` to see which preview lines stopped being used (#558). Drop royalty-free tracks into `assets/music/tapin/` and
`assets/music/moneywise/` (#411), then render one debate video to hear the bed and see the second
colour (#900); on a just-happened topic, watch what the key-facts prompt finds (#899). `ops vault-retier` to see which old notes hold scraped
lines, then `--apply` if the list is right (#857); the next run on a just-happened event should stop
before TTS unless facts are pasted - say if it stops a run it should not (#895). Listen to the next
render (about 5% slower; `TTS_SPEED=1.0` undoes it), one debate and one quotes run (#889), then
`ops backfill` to see what history is behind.

**Still the operator's, unchanged:** review the 05:00 drafts (`ops batch-review`); one OAuth
consent then `ops playlists --apply`; gameplay files for the empty niches (#786). After the first
live TTS run, check that `ops reliability` reports TTS-cache hits rather than `0/3`.
`ARTIFACT_RETENTION_APPLY` stays unset unless you want overnight to delete.

**Dropped from this list** (stay open): **#730** (operator call) · **#728** (no clip) ·
**#628** · **#731** · Phase M · Ollama. **#739 is closed, not dropped** - measured and rejected.

**Closed 2026-09-20 (wave 30):** **#817 #818 #822 #739 #823**. Filed open: **#824 #825 #826**.
Two items closed *without* a behaviour change because the measurement said not to (#822, #739);
#817 closed because its filed text was wrong. `ops backfill-quality` applied on the operator's
call - 87 rows, and backfilled grades are stamped so calibration cannot read them as evidence
the rubric held.

**Closed 2026-09-20 (wave 29):** **#808 #805 #561 #803 #811**, plus wave 28's **#813 #814 #815
#816**. `QUALITY_VERSION` v3 -> v4; **`GRADE_VERSION` unchanged at v4**. `DISCOVERY_DEADLINE_S`
unset by default. Style recurrence report-only (#821).

**Closed 2026-09-20 (wave 27):** **#806 #807 #810 #812 #802**. igdb/steam 1/33 is a documented
known gap, not a §19 zero. Hedge density remains grade-only. Authenticity gate stays binary.
Overnight stays render-free. Retention apply stays off unless the env is set.

**Closed 2026-09-20 (wave 26):** **#799 #800 #801 #809 #804**. `GRADE_VERSION` v3 → v4.

**Filed 2026-09-20 (wave 25, documentation):** **#799 #800 #801 #802 #803** (script) - **#804
#805 #806 #807 #808** (grading) - **#809 #810 #811 #812** (resources).

**Closed 2026-09-19 (wave 24):** **#792 #793 #795 #796 #797 #798**. Narrowed **#788**.

**Closed 2026-09-19 (wave 23):** **#785 #787 #600 #789 #790 #791**. Narrowed **#786**; filed open **#788**.

**Closed 2026-09-19 (wave 22):** **#782 #783 #784 #601 #781**. Filed open: **#785 #786**.

**Closed 2026-09-18 (wave 21):** **#779 #771 #780**. Filed open: **#781**.

**Closed, waves 8-20 (2026-09-10 to 09-17):** waves 20 **#775 #776 #770 #773 #774 #777** · 19
**#755 #627 #769 #763 #764 #766 #765 #767 #768 #772** · 18 **#760 #762 #761 #345 #756 #749** · 17
**#754 #757 #758 #543 #759** · 16 **#750 #751 #752 #753 #732** · 15 **#534 #748 #746 #747 #738** ·
14 **#740 #742 #741 #743 #667 #745 #744** (archive: [run_76.md](run_76.md)) · 13 **#734 #735 #736
#737** · 12 **#733 #630 #640** · 11 **#729 #631 #636 #639 #727** · 10 **#719 #720 #724 #725 #726
#158** · 9 **#716 #723 #722 #721 #718**. Full detail in
[roadmap_archive.md](roadmap_archive.md).

**RETIRED 2026-09-09 — #153 caption choreography.** Operator: *"i dont need to
see the caption timing, i dont want to do that manually."* Karaoke ASS hashed
identical with no sidecar. **Do not rebuild the timeline UI.**

**Closed 2026-09-09 (defect + kit wave):** **#701** weekend clock - **#700**
`claim_next` - **#699** `surfaces` - **#112** correction dossier - **#151**
brand-kit.

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
| `parked` | deliberately not now — Phase M, volume-gated studios |

---

## Still not happening

Phase M multi-platform (TikTok/Reels) stays parked. No SaaS, no web product, no
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
