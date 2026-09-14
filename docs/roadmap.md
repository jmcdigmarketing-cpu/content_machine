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

**Just landed** - 2026-09-13 wave 16: five defects from live run 77. **#750**
Extended chapters span the video and pass YouTube's >= 3 / >= 10 s rule (run 77
stored `0:00-0:17`) · **#751** upload queue gets the word-timed description ·
**#752** long videos lose `shorts` and topic-word tags · **#753** the worker prints a
successful upload · **#732** env fingerprint counts optional flags, versioned.

**Previously** - runs 77/78 (unnumbered): typed thoughts at the Topic prompt; all
angles in one long video with chapter Shorts. Wave 15 **#534 #748 #746 #747 #738**;
wave 14 run 76 abort **#740 #742 #741 #743 #667 #745 #744**; **#153** retired (do not
rebuild).

### Recommended next five (non-app)

Wave 16 replaced the caption measurements with what run 77 actually shipped wrong
(operator's pick). The list now follows the run: a false claim went out after
"Render anyway?", and the all-angles feature has never met a real script.

1. **#754 rendering past a flagged claim still queues public** `[S]` - run 77's
   "GTA 5 didn't win Game of the Year in 2013" reached YouTube.
2. **#755 measure all-angles on its first live run** `[S]` - chapter locator path,
   chapter lengths vs the Shorts cap, hooks per cut.
3. **#345 claim-type taxonomy** `[M]` - an award/result claim should not clear the
   same bar as an opinion.
4. **#543 quote the operator verbatim** `[M]` - typed thoughts are now the brief
   (run 77); their wording is still paraphrased.
5. **#756 chapter labels cut mid-phrase** `[S]` - "The only reason we know anything
   is".

**Dropped from this list** (stay open): **#739** · **#730** (caption measurement,
needs footage and an operator call) · **#749** · **#728** · **#731** · **#627** ·
**#628** · Phase M · Ollama.

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

**Closed 2026-09-08 (review 4):** **#694** recency decay reached the recommendation · **#695** three write-only quality keys given a reader · **#696** retraction throttle before the fetch · **#697** HUD temp-dir leak + memo · **#698** pre-commit header.

**Closed 2026-09-08 (this wave):** **#148** queue + drag · **#692** studio snap ·
**#693** missing HUD skip · **#686** 24h toast · **#688** VACUUM · **#230 #246
#249 #259 #260 #264 #301 #302 #337 #344 #358 #365 #367 #596 #629**. Live
review-room smoke (not numbered).

**Closed 2026-09-08 (previous):** honesty **#689 #690 #691**; Stage 4 slice
**#152** (mechanical) **#186 #248**; review **#266 #265 #270**; **#685** HUD
probe on real files · **#609** startup budget · why-slow skips `word_count` ·
**#687** `.env` shape · **#634** pre-commit command-ref · **#619** schema stamp.

**Closed 2026-09-07 (previous):** **#608** google/espn import defer · **#669**
intro offset from config · **#633** docs-named ops verbs · **#632** size-tag
ratchet · **#638** Steam key / SportsData deleted · **#554** singleton-source
flag · **#557** fact age at prompt · **#593** domain gating in health · **#581**
Edge TTS fallback line · **#448** `ops why-slow` · **#623** sqlite bytes ·
**#447** channels.json config-diff · **#672** grain stddev · **#683** HUD
detector · **#341** retraction-watch (last-run).

**Closed 2026-09-07 (Stage 3 honesty):** **#679 #680 #674 #681 #682**;
**#607** ElevenLabs import defer; **#335** source-diversity floor; **#671**
visual angle list; Stage 3 review room **#168+#209**; **#416** owned beat cuts.

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
