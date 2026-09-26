# Content OS — roadmap

> **Class:** plan · **Status:** living · **Reviewed:** 2026-09-26

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

**Just landed** - 2026-09-26 wave 33 (run 98, Claude Code): **#840** every multi-sentence
ElevenLabs render since 09-20 was billed twice (fixed) · **#841 #842** a topic's domain comes
from the topic, and football is TapIn's (`soccer`) · **#843** popularity payloads no longer pose
as facts · **#844-#846** page titles are metadata, pasted-link lines are link tier and checked
against the angle · **#847** report card v5 (topic weight 0.05). Plans: [vault.md](vault.md),
[tooling_review_2026-09-26.md](tooling_review_2026-09-26.md), the facts room **#860**.

**Before that** - wave 32: **#826 #820 #824** closed, **#821 #819** measured · wave 31
(structural): **#827 #828 #829 #833** (mypy ratchet, 129), docs standard finished · wave 30
(measurement): **#823 #824 #822 #739**. Earlier waves: [roadmap_archive.md](roadmap_archive.md)
and [planning_log.md](planning_log.md).

### Recommended next five (non-app)

**Wave 33 (2026-09-26, run 98)** fixed what the run exposed and needed no sample: double-billed
TTS, football routed as gaming, junk "facts", scraped boilerplate saved as operator facts, and
a topic weight that scored five angles identically. The list now follows the operator's two
open questions from that run - *pull everything* and *make football work* - ahead of the
structural items, which keep their order in [master_plan.md](master_plan.md) M3.

1. **#848 auto-research** `[M]` - read the web-search result pages the pipeline already has,
   filtered against the angle, at web tier. The operator asked for exactly this.
2. **#852 entity-aware signal queries** `[S]` - `api_sports` searches the raw 48-character
   topic and Wikipedia never tries "Manchester_City"; football signals stay weak until fixed.
3. **#859 soccer RSS feeds** `[S]` - no feed is tagged `soccer`; the operator names two.
4. **#850 the research brief sees the key facts** `[S]` - it can contradict them today.
5. **#836 backfill angle scores** `[M]` - gives #849 (telling angles apart) an n now.

**Waiting on the operator, not on code:** `git pull`, then `py -m scripts.ops calibration`
(per-component and today's-rubric lines) and `py -m scripts.ops backfill-quality --channel
tapin --force` (dry run, then `--apply`) to re-stamp history as v5. #821 and #819 wait on those
numbers. Structural queue unchanged: #839 · #830 · #832 · #831.

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

**Developer setup:** `pip install -e ".[dev]"` and `git config core.hooksPath .githooks`
(not `pre-commit install` — the repo's hooks live in `.githooks`); `ruff check .` ·
`ruff format .` · `py scripts/mypy_ratchet.py` · `py -m scripts.ops test --order reverse`.
Tooling config lives in `pyproject.toml`.

**Troubleshooting:** [debugging.md](debugging.md)

---

*Never commit `.env`, OAuth tokens, or `client_secrets.json`.*
