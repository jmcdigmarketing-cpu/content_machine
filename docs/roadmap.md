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

**Just landed** — 2026-09-08 queue panel, studio drag, and 15 leftovers. Locked
five: **#148** queue with drag-reorder · live review-room smoke · **#692**
studio snap · **#693** missing HUD skip · **#686** 24h retraction toast +
**#688** VACUUM. Then 15 cheap leftovers (#230 badge · booth CSS · title-card
wrap · switcher · cheat-sheet · hook clamp · plausibility · clock ·
counterfactual · recency · drift · competitor title · test-time budget).
`GRADE_VERSION` stayed **v3**. CLI / `ops booth` / `ops queue-manage` stay.
`SCENE_MATCHED_BROLL` stays off. Skipped **#151 #153 #684** so they cannot
strand the wave.

**Next: remaining Stage 4/3 craft** — brand kit, caption timeline, live decode,
then the cost tower. Detail: [desktop_app.md](desktop_app.md).

**Then, in order:** Stage 4 studio → Stage 5 packaging → Stage 6 portfolio
→ Stage 7 efficiency.

### The Craft wave — leftover after Stage 0

Pulled forward so it is finished rather than stranded. The sorting rule is **what
survives the desktop app**:

- **Video craft is permanent.** Shipped 2026-09-06: **#185** contrast auditor ·
  **#297** ratio number · **#505** two-line balancing · **#182** caption overlay
  on a still · **#513** black/frozen first frame · **#502** draft-only safe-area
  guides. Shipped 2026-09-07: **#184** motion presets · **#183** font pairing ·
  **#187** end-card compositor · **#188** intro-sting waveform · **#190**
  MoneyWise disclaimer · **#191** AI-disclosure lower-third. Shipped 2026-09-07
  (Stage 2 wave): **#295** contact-sheet PNG · **#296** print CSS · **#602**
  end-card vs caption safe area · **#512** grain/vignette ffmpeg.
- **Terminal is the daily driver for the remaining app waves.** Shipped
  2026-09-06: **#485** discovery persist · **#488** width-aware wrapping ·
  **#490** measured ETA · **#487** `NO_COLOR` · **#482** collapse mascot ·
  **#491** themed spinner glyphs · **#484** Ctrl+C. Shipped 2026-09-07:
  **#481** pinned status · **#243** PNG wordmark · **#244** Windows Terminal
  profile.
- **Three loopholes, config-only — shipped 2026-09-06:** **#641** tapin=`dbz`,
  moneywise/default=`plain` · **#642** voice pools · **#643** local Piper
  voices · **#644** coverage ratchet on real `channels.json`.
- **Booth: only the cheap ones**, since Stage 3 replaces it — **#303** theme
  toggle and **#304** reduced-chroma shipped 2026-09-07; **#239** print CSS
  shipped. **#296** shipped with #295. Everything else booth-shaped stays
  in the backlog and dies there, deliberately.

Alongside the app, roughly one item per wave from the tracks below, so the
pipeline keeps improving while the surface is built.

### Recommended next five (non-app)

1. **#151 brand-kit compiler** `[L]` — fonts/palette/sting into render + GUI.
2. **#153 caption choreography timeline** `[L]` — keyframes over real word timings.
3. **#684 live review-room decode** `[S]` — J/K/L is a helper; CI still constructs
   the window offscreen without a file.
4. **#112 correction dossier** `[M]` — post-publish fact reversal still does not
   auto-write a dossier; #686 only toasts.
5. **#158 cost tower** `[L]` — next Stage 3 panel after the queue.

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

**Dropped from this list** (stay open): **#673** second physical monitor ·
Phase M · Ollama.

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
