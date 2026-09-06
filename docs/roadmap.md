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

**Just landed** — 2026-09-06 next-15 wave: idea-quality leftovers (#661/#659/#660/#656/#664/#665), honesty (#655/#663/#662), TTS seam + sentence cache (#658/#402), headless facts (#646/#647 held), Ctrl+C (#484), and the config loopholes (#641–#644). `GRADE_VERSION` is **v3**. Uncommitted until the operator asks.

**Next: Stage 0 — Seams.** Still the keystone; this wave did not start it. One wave, no window. The `ask()` seam over `main.py`'s blocking prompts, the `emit()` output sink, and design tokens (#170). Detail: [desktop_app.md](desktop_app.md).

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
  polish pays off across all of them: **#485** keep discovery on re-entry ·
  **#488** width-aware wrapping · **#481** pinned status line · **#490**
  measured ETA · **#491** themed spinner glyphs · **#243** PNG wordmark ·
  **#244** Windows Terminal profile. *(#484 Ctrl+C shipped 2026-09-06.)*
- **Three loopholes, config-only — shipped 2026-09-06:** **#641** tapin=`dbz`,
  moneywise/default=`plain` · **#642** voice pools · **#643** local Piper
  voices · **#644** coverage ratchet on real `channels.json`.
- **Booth: only the cheap ones**, since Stage 3 replaces it — **#303** theme
  toggle, **#304** reduced-chroma for night review, **#296**/**#239** print CSS.
  Everything else booth-shaped stays in the backlog and dies there, deliberately.

Alongside the app, roughly one item per wave from the tracks below, so the
pipeline keeps improving while the surface is built.

### Recommended next five (non-app)

**The 2026-09-06 wave shipped the previous recommended five plus the overnight
holes around them.** Why, and what each one measured:
[planning_log.md](planning_log.md) 2026-09-06.

1. **#485 persist discovery so a re-entered topic skips the refetch** `[M]` —
   pairs with shipped #484. Run 73 paid 38s twice; Ctrl+C no longer kills the
   process, but the signals are still thrown away.
2. **#185 caption-vs-background contrast auditor** `[M]` — video craft is
   permanent; burned captions fail on busy clips and no desktop stage changes
   that.
3. **#505 two-line caption balancing** `[S]` — sibling of #419's orphan fix;
   cheap, visible, survives the app.
4. **#350 grounding regression corpus in CI** `[M]` — a gate change that
   loosens grounding should fail CI, not a live run. Frozen verdicts, not
   another scorer.
5. **#648 scaffolding markers are a hand-built list** `[M]` — #646/#647 held
   the weights; the next furniture site will miss `_SCAFFOLDING_MARKERS`.

**Also small:** **#488** width-aware wrapping. **Dropped from this list** (stay
open): Stage 0 `ask()`/`emit()` · **#333** · **#416** (still no clip index).

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
