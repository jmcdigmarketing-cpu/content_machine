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

**Just landed** - 2026-09-20 wave 29 (measurement): **#808** the grade is recorded beside the
inputs that produced it, so a re-grade is measurable instead of silent · **#805** the card prints
its own accuracy - **composite vs engaged-rate r=-0.15 over 12 publishes**, the first real number
on the score the selection path leans on · **#561** the recommender's 40% hit rate over 10
publishes, printed beside its advice · **#803** a repeated opener is flagged even when no single
pair trips the similarity limit (the filed premise was wrong - see the item) · **#811**
`DISCOVERY_DEADLINE_S` stops the run blocking on its slowest signal. Wave 28's review fixes
(**#813 #814 #815 #816**) are in the same commit.

**Previously** - wave 27 (operator loop + resource waste) **#806 #807 #810 #812 #802**; wave 26
(script quality) **#799** rewrite ledger · **#800** hedge density (closes §25) · **#801** intent
replay · **#809** TTS cache default-on · **#804** continuous authenticity points (`GRADE_VERSION`
v4, gate still binary); wave 25 (documentation) [engine_upgrades.md](engine_upgrades.md), filed
**#799-#812**; wave 24 **#792 #796 #788 #793 #795 #797 #798**; wave 23 **#785 #787 #600 #789 #790
#791**; wave 22 **#782 #783 #784 #601 #781**; **#153** retired.

### Recommended next five (non-app)

**Operator, 2026-09-20:** [engine_upgrades.md](engine_upgrades.md)'s list is **exhausted** -
#799-#812 are all closed. The list below is what wave 29's measurements turned up, plus the one
standing defect both agents have circled. Volume framing is unchanged - a long video is 1-2 a
month; the 3-5/week target is Shorts.

**#50 was pulled from this list and is now data-gated.** "Scripts that actually retained" means
runs carrying both a `quality_json` and a synced engaged-rate, and `tapin` has three. #561 took
the slot.

1. **#818 explain the collecting gap** `[S]` - 37 rows have a grade, 12 have an outcome, 3 have
   both. `ops calibration` will read "collecting" for months and the reason is history, not
   volume. One weekly-report line so it is not re-discovered.
2. **#817 which window the recurrence pass reads** `[S]` - #803 ships against the last 12 runs of
   any status; the item said *published*. Narrowing it also narrows the existing similarity gate,
   so it is a decision, not a patch.
3. **#822 hedging passes the gate and only costs grade points** `[M]` - #345 lets a hedged rumor
   through; #800 then docks the grade for hedging. The cheapest route past the hard gate is what
   the soft score punishes. Decide which layer owns it.
4. **#819 what the selection tie should lean on** `[L]` - composite is r=-0.15 against engagement
   over every measured publish. Until that is positive, a tie broken by composite is a coin flip.
   `angle_scores` (#807) is the candidate and is itself unvalidated.
5. **#739 place captions by footage source, not by pixels** `[M]` - unchanged from the dropped
   list, and now the largest output-quality item with a clear measurement path.

**Still the operator's, unchanged:** review the 05:00 drafts (`ops batch-review`); one OAuth
consent then `ops playlists --apply`; gameplay files for the empty niches (#786). After the first
live TTS run, check that `ops reliability` reports TTS-cache hits rather than `0/3`.
`ARTIFACT_RETENTION_APPLY` stays unset unless you want overnight to delete.

**Dropped from this list** (stay open): **#821** (held on #818's dataset) · **#730** (operator
call) · **#728** (no clip) · **#628** · **#731** · Phase M · Ollama.

**Closed 2026-09-20 (wave 29):** **#808 #805 #561 #803 #811**, plus wave 28's **#813 #814 #815
#816**. Filed open: **#817 #818 #819 #820 #821 #822**. `QUALITY_VERSION` v3 -> v4;
**`GRADE_VERSION` unchanged at v4** - no component moved. `DISCOVERY_DEADLINE_S` is unset by
default. Style recurrence is report-only (#821).

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
