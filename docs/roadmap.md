# Content OS — roadmap

**What to do now.** The full inventory, the desktop programme, and the history live
in their own files — this one stays short enough to read at the start of every
session.

| file | what it holds |
|---|---|
| **roadmap.md** (this) | the current stage, the next five, track counts |
| [desktop_app.md](desktop_app.md) | the Windows application programme — stages 0–7 |
| [backlog.md](backlog.md) | every open item, numbered 21–670 plus unnumbered |
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

**Just landed** - 2026-09-20 wave 27 (operator loop + resource waste): **#806** rejection
reason keystroke · **#807** fixture replay of recorded angle sets · **#810** retire true-zero
signals (igdb/steam stay, known gap) · **#812** published-path exempt + overnight retention
line · **#802** research-brief and variant-scoring wall-clock budgets.

**Previously** - 2026-09-20 wave 26 (script quality): **#799** per-pass rewrite ledger · **#800**
hedge density (closes the open §25 call; render gate unchanged) · **#801** intent replay on the
38 recorded topics · **#809** TTS cache default-on · **#804** continuous authenticity points
(`GRADE_VERSION` v4; historical letters re-grade). Gate still uses the binary sum.

**Previously** - 2026-09-20 wave 25 (documentation): ideas for **script generation**, **idea
grading** and **resource use**, each measured against the 38 recorded runs -
[engine_upgrades.md](engine_upgrades.md). Filed **#799-#812**. Wave 24: **#792** irregular 3-8 s
shots · **#796** parallel shot encodes · **#788** narrowed · **#793 #795 #797 #798**. Wave 23
**#785 #787 #600 #789 #790 #791**; wave 22 **#782 #783 #784 #601 #781**; **#153** retired.

### Recommended next five (non-app)

**Operator, 2026-09-20:** wave 27 closed the cheapest operator-loop and resource slice. The list
below is the next from [engine_upgrades.md](engine_upgrades.md). Volume framing is unchanged - a
long video is 1-2 a month; the 3-5/week target is Shorts.

1. **#808 snapshot grade inputs** `[S]` - `GRADE_VERSION` stamps that something changed, not
   what the inputs were. Store the inputs beside the scores so a re-grade is measurable.
2. **#811 a discovery deadline** `[M]` - signals run concurrently but the run waits for the
   slowest (median 58.7 s). Take the first N good results past a deadline.
3. **#803 style memory across runs** `[M]` - similarity is one previous script deep; flag
   repeated openers and sentence shapes across the last N published scripts.
4. **#805 print the report card's own hit rate** `[M]` - correlate grade and composite against
   `engaged_rate` and print `r` with `n` on the card.
5. **#50 learned insight markers** `[L]` - replace hardcoded `_INSIGHT_MARKERS` from scripts
   that actually retained. Still the next authenticity input after #804.

**Still the operator's, unchanged:** review the 05:00 drafts (`ops batch-review`); one OAuth
consent then `ops playlists --apply`; gameplay files for the empty niches (#786). After the first
live TTS run, check that `ops reliability` reports TTS-cache hits rather than `0/3`.
`ARTIFACT_RETENTION_APPLY` stays unset unless you want overnight to delete.

**Dropped from this list** (stay open): **#739** · **#730** (operator call) · **#728** (no clip)
· **#628** · **#731** · Phase M · Ollama.

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

**Closed 2026-09-17 (wave 20):** **#775 #776 #770 #773 #774 #777**. Narrowed: **#771**.

**Closed 2026-09-17 (wave 19):** **#755 #627 #769 #763 #764 #766 #765 #767 #768 #772**.
Filed open: **#770 #771 #773 #774**.

**Closed 2026-09-16 (wave 18):** **#760 #762 #761 #345 #756 #749**. Filed open: **#763
#764**; narrowed **#755**.

**Closed 2026-09-15 (wave 17):** **#754 #757 #758 #543 #759**. Filed open: **#760**.

**Closed 2026-09-13 (wave 16):** **#750 #751 #752 #753 #732**. Filed open: **#754
#755 #756**.

**Closed 2026-09-13 (wave 15):** **#534 #748 #746 #747 #738**. Filed open:
**#749**.

**Closed 2026-09-13 (wave 14):** **#740 #742 #741 #743 #667 #745 #744**. Filed
open: **#746 #747 #748**. Archive: [run_76.md](run_76.md).

**Filed 2026-09-13 (run 76):** **#740 #741 #742 #743 #744 #745**; narrowed **#667**.

**Closed 2026-09-13 (wave 13):** **#734 #735 #736 #737**. Filed open: **#738 #739**;
narrowed **#730**.

**Closed 2026-09-13 (wave 12):** **#733 #630 #640**. Filed open: **#734 #735 #736
#737**; narrowed **#730 #731**.

**Closed 2026-09-13 (wave 11):** **#729 #631 #636 #639 #727**. Filed open:
**#730 #731 #732**.

**Closed 2026-09-12 (wave 10):** **#719 #720 #724 #725 #726 #158**. Filed open:
**#727 #728**.

**Closed 2026-09-12 (wave 9):** **#716 #723 #722 #721 #718**; **#158** core slice.
Filed open: **#724 #725 #726**.

**Closed 2026-09-10 (wave 8):** **#590** headroom before the pool · **#378**
free-tier calendar · **#407** opener advisory · **#717** luminance-step caption
placement · **#684** live review-room decode + the unconditional `QAudioOutput`
behind it. Filed open: **#721 #722 #723**.

**Closed 2026-09-09 (next 15):** **#714 #715 #584 #572 #580 #595 #452 #362
#364 #336 #605 #599 #437 #713 #415**. Found: #715 comment-out guard was
vacuous; #580 ops verb re-estimated instead of reading last-run cost.

**Closed 2026-09-09 (previous next 15):** **#710 #712 #431 #549 #414 #420 #498 #711
#708 #562 #569 #568 #430 #440 #705**. Found: the extras chapter test used
stamps that equal-span also produces.

**Closed 2026-09-09 (#702-#707 + #709):** retraction `source_urls` - Postgres
`SKIP LOCKED` - correction-scan throttle - ReviewWindow keys - Qt fixture
decode - jsonb cast for Text `payload_json`.

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

**Developer setup:** `pip install -e ".[dev]"` then `pre-commit install`;
`ruff check .` · `ruff format .` · `mypy analytics apis core config storage`.
Tooling config lives in `pyproject.toml`.

**Troubleshooting:** [debugging.md](debugging.md)

---

*Never commit `.env`, OAuth tokens, or `client_secrets.json`.*
