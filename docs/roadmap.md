# Content OS — roadmap

**What to do now.** The full inventory, the desktop programme, and the history live
in their own files — this one stays short enough to read at the start of every
session.

| file | what it holds |
|---|---|
| **roadmap.md** (this) | the current stage, the next five, track counts |
| [desktop_app.md](desktop_app.md) | the Windows application programme — stages 0–7 |
| [backlog.md](backlog.md) | every open item, numbered 21–669 plus unnumbered |
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

**Just landed** — 2026-09-07 Stage 0 + leftover craft: `ask()`/`emit()`/`#170` tokens,
pinned status **#481**, motion **#184**, MoneyWise/AI burn-ins **#190/#191**, quote
gate **#338**, title/body fonts **#183**, end-card/waveform **#187/#188**, wordmark
and WT **#243/#244**, print CSS **#239**, booth chrome **#303/#304/#486**.
`GRADE_VERSION` stayed **v3**.

**Next: Stage 1 — The run window.** The seams exist; this is the first window.
Detail: [desktop_app.md](desktop_app.md).

**Then, in order:** Stage 2 look → Stage 3 panels → Stage 4 studio → Stage 5 packaging
→ Stage 6 portfolio → Stage 7 efficiency.

### The Craft wave — leftover after Stage 0

Pulled forward so it is finished rather than stranded. The sorting rule is **what
survives the desktop app**:

- **Video craft is permanent.** Shipped 2026-09-06: **#185** contrast auditor ·
  **#297** ratio number · **#505** two-line balancing · **#182** caption overlay
  on a still · **#513** black/frozen first frame · **#502** draft-only safe-area
  guides. Shipped 2026-09-07: **#184** motion presets · **#183** font pairing ·
  **#187** end-card compositor · **#188** intro-sting waveform · **#190**
  MoneyWise disclaimer · **#191** AI-disclosure lower-third. Still open:
  **#295** contact-sheet PNG (blocks **#296**).
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
  shipped. **#296** still waits on **#295**. Everything else booth-shaped stays
  in the backlog and dies there, deliberately.

Alongside the app, roughly one item per wave from the tracks below, so the
pipeline keeps improving while the surface is built.

### Recommended next five (non-app)

**The 2026-09-07 wave shipped the previous recommended five** (Stage 0 · #481 ·
#184 · #190 · #338) **plus the leftover craft around them.** Why, and what each
one measured: [planning_log.md](planning_log.md) 2026-09-07 (Stage 0).

1. **Stage 1 run window** `[L]` — Stage 0 seams exist; this is the first Qt
   window. Detail: [desktop_app.md](desktop_app.md).
2. **#295 2x2 contact sheet PNG** `[S]` — Pillow collage of last thumbs; unblocks
   **#296** print CSS (held this wave because there is no sheet).
3. **#607 defer `elevenlabs.client`** `[S]` — 0.51s of a measured 1.89s CLI start,
   paid even when no audio is made.
4. **#625 audit every test double against its target's real signature** `[M]` —
   three drifted in one week, each passing while the real path was broken.
5. **#602 end-screen placement that avoids the caption safe area** `[M]` —
   leftover video craft that survives the app.

**Dropped from this list** (stay open): **#296** (blocked on #295) · **#333** ·
**#416** (still no clip index) · **#512/#527** (need a Qt app or #247 preview) ·
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
