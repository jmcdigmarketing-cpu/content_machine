# Content OS — roadmap

**What to do now.** The full inventory, the desktop programme, and the history live
in their own files — this one stays short enough to read at the start of every
session.

| file | what it holds |
|---|---|
| **roadmap.md** (this) | the current stage, the next five, track counts |
| [desktop_app.md](desktop_app.md) | the Windows application programme — stages 0–7 |
| [backlog.md](backlog.md) | every open item, numbered 21–656 plus unnumbered |
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

**Just landed** — the run-73 defect wave (reaction angles, web-search recency,
yt-dlp quiet, fact budgets) and this reorganisation.

**Next: Stage 0 — Seams.** One wave, no window. The `ask()` seam over `main.py`'s
15 blocking prompts, the `emit()` output sink, and design tokens (#170). It is the
keystone: every later stage is cheap because of it, the terminal keeps working
byte-identically forever, **and the Craft wave below reads those tokens** — so it
genuinely goes first. Detail: [desktop_app.md](desktop_app.md).

**Then, in order:** Stage 1 the run window (2 waves, ends the PowerShell
dependency) → Stage 2 look → Stage 3 panels → Stage 4 studio → Stage 5 packaging
→ Stage 6 portfolio → Stage 7 efficiency.

### The Craft wave — after Stage 0, before Stage 1

Pulled forward so it is finished rather than stranded. The sorting rule is **what
survives the desktop app**:

- **Video craft is permanent.** It is burned into every video and no toolkit
  change touches it, so it outranks everything else here:
  **#185** contrast auditor · **#297** the hours-version contrast number ·
  **#505** two-line caption balancing · **#184** motion presets · **#182** caption
  overlay on a still · **#183** font pairing · **#187** end-card compositor ·
  **#188** intro-sting waveform · **#190** MoneyWise disclaimer bug · **#191**
  AI-disclosure lower-third · **#513** reject a black first frame.
- **Terminal is the daily driver for the 16–19 waves the app will take**, so
  polish pays off across all of them: **#484** `Ctrl+C` returns to the menu
  (run 73 lost two whole runs) · **#485** keep discovery on re-entry · **#488**
  width-aware wrapping · **#481** pinned status line · **#490** measured ETA ·
  **#491** themed spinner glyphs · **#243** PNG wordmark · **#244** Windows
  Terminal profile.
- **Three loopholes, config-only**, that make already-shipped features real:
  **#641** six ANSI themes no channel can reach · **#642** empty voice pool ·
  **#643** unset local-TTS voices. Plus **#644**, the test that would have caught
  all three.
- **Booth: only the cheap ones**, since Stage 3 replaces it — **#303** theme
  toggle, **#304** reduced-chroma for night review, **#296**/**#239** print CSS.
  Everything else booth-shaped stays in the backlog and dies there, deliberately.

Alongside the app, roughly one item per wave from the tracks below, so the
pipeline keeps improving while the surface is built.

### Recommended next five (non-app)

**The 2026-09-05 wave shipped four and a half of the previous five** — #654, #645,
#383 and **#533's detector + angle tables**. #402 was not shipped: scoping it
confirmed the `[L]` and produced #658 (the seam it needs) plus #657, a real
billing defect found on the way. Why, and what each one measured:
[planning_log.md](planning_log.md) 2026-09-05.

1. **#662 grade_calibration mixes rubric versions** `[M]` — caused by the last two
   waves and now visible: four grade components have moved, and calibration still
   re-grades all history with today's code before correlating against engagement.
   `VideoGrade.version` now exists, so this is finally fixable rather than just
   nameable. Do it before trusting any calibration number again.
2. **#658 a per-segment synthesis seam in `generate_audio`** `[M]` — the blocker
   under #402, which is 91% of run cost. Extract one "synthesize this text to this
   path" core from four provider branches, pin their behaviour, and #402 becomes a
   loop over it instead of a rewrite of the most cost-critical function in the repo.
3. **#659 carry the detected intent into the research brief** `[M]` — #533's next
   half and the cheapest remaining one. Mind the cache key: it omits intent, so an
   intent-aware brief would serve a stale pre-intent one for three hours.
4. **#647 tune the fact-selection weights against real traces** `[M]` — still
   calibrated on run 74's own 54 facts, and the idea-quality diagnosis leans on
   that ranking. Measure it against `data/traces/*.json` before trusting it further.
5. **#661 two independent intent classifiers disagree** `[M]` — `angle_intent`
   (generation) and `run_features.classify_angle` (analytics, persisted) can label
   the same topic differently; #533 widened one of them and not the other.

**Also small and worth grabbing:** **#663** — nothing actually *runs* the signal
canary yet; it belongs in the overnight chain, not in `all-checks` (CI has no
network and would fail every build).

**Dropped from this list** (both stay open): **#333 negative-fact store** — parked
across four `HANDOFF_SYNOPSIS.md` waves, needs an operator decision on precedence
against decisions §4, and its trigger #341 does not exist. **#416 scene-beat cuts**
— `[L]`, parked, and blocked on data: `ops ingest-clips --apply` has never run, so
`data/clip_index.json` does not exist and there is nothing to cut to.

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
