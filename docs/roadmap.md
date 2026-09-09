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

**Just landed** - 2026-09-09 next-15: prove-and-tick leftovers already in HEAD
(**#710 #712 #431 #549 #414 #420 #498**), then **#711 #708**, honesty
(**#562 #569 #568 #430 #440**), **#705** last. Title/script finally has a
Proceed? reader. CI push is no longer `main`/`master`-only. TapIn has logo and
banner on disk.

**Previously this day** - **#702-#707 + #709**; extras committed as `b9f1354`;
**#153** caption timeline built then retired on the operator's call (do not
rebuild; **#713** is the automatic-placement remainder).

### Recommended next five (non-app)

The list changed because the previous five are now measured closed. **#21** is
already `[x]` (2026-08-25) — it was a no-op pick.

1. **#713 automatic caption placement** `[M]` - a cue covering a face or score
   bug should move itself. No operator timeline.
2. **#684 last-run ReviewWindow play** `[M]` - still operator smoke after #707's
   fixture decode.
3. **#158 Cost Tower** `[L]` - the expensive dashboard, not a cheap honesty fix.
4. **#415 render smoke in CI** `[M]` - 2s synthetic; #24/#26 shipped dead on
   Windows and were caught by audit.
5. **#437 unlist / rollback** `[S]` - mutates YouTube; operator-gated on purpose.

**Dropped from this list** (stay open): **#673** second monitor - Phase M -
Ollama.

**Closed 2026-09-09 (next 15):** **#710 #712 #431 #549 #414 #420 #498 #711
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

**Dropped from this list** (stay open): **#673** second monitor - Phase M -
Ollama.

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
