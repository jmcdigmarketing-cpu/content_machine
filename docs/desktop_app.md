# Content OS Desktop — the programme

The plan to leave the terminal permanently, for a real Windows 11 application.
**Private, local, single-operator, never published.** That constraint is load
bearing: it retires work rather than deferring it.

Current stage and the next five live in [roadmap.md](roadmap.md). Items referenced
by number are in [backlog.md](backlog.md).

---

## Why this is not an XL

The old roadmap listed **#141 Content OS Desktop `[XL]` — "years of UX/packaging"**
next to #148 job queue, #149 analytics, #152 thumbnail canvas, #156 vault
companion, #158 cost tower, #161 publish calendar, #163 script desk, #168 review
room — **twenty-one items that are each a panel inside that same app.**

Read as one XL it is unapproachable. Read as a shell plus panels added one at a
time — each already backed by data the system computes today — it is a long
project made of ordinary weeks. #141 is retired as a checkbox and replaced by the
eight stages below.

The "years" estimate was true for what #141 actually specified: a Tauri/WinUI
rewrite, meaning a JavaScript front end in a **separate process**, which
reintroduces a serialization boundary the terminal does not have. That is not what
gets built.

## The blocker, stated plainly

`main.py` has **15 blocking `input()` calls**. When Python reaches one the program
stops dead on that line, holding the entire run — 38 seconds of discovery, the
scored angles, the pasted facts — in memory, and resumes on the next line when the
operator types. That is why two `KeyboardInterrupt`s in run 73 destroyed whole runs:
the frozen process was the only copy.

A web server cannot do that; it answers and forgets. **A desktop app can** — it is
one long-running process with memory, exactly like the terminal. The only real
constraint is that a window must keep repainting, so the pipeline runs on a worker
thread and blocks there instead of on the UI thread.

So the fix is a seam, not a rewrite. See Stage 0.

## Toolkit: PySide6 / Qt

Decided 2026-08-28 after comparing against a WebView2 window.

| | Qt | WebView2 |
|---|---|---|
| #152 layer canvas, #153 timeline, #148 drag-reorder | `QGraphicsView` — built for it | bespoke JavaScript each time |
| #168 player, #209 J/K/L review | `QMediaPlayer` embeds natively | local `.mp4` needs a custom scheme; already bit the booth once |
| languages | Python only | Python **and** JS, bridge per panel |
| polish | QSS is a CSS subset, no flexbox — deliberate effort | real CSS, easier |
| size | ~150MB dep, ~250MB packaged | ~1MB dep |

The canvas and player gaps never close; the polish gap does. Qt also keeps the
codebase in one language, which matters because the operator wants to run and
modify this machine without an agent. ~250MB is irrelevant for a private local
tool.

Measured before deciding: the existing booth HTML is ~113 tags and ~182 CSS rules,
and most of `core/review_booth.py`'s 1,124 lines is Python building strings. What
carries over to Qt is the **design** — what to show, how to lay it out — not the
markup. The real loss is about a week.

---

## Stage 0 — Seams · shipped 2026-09-07 · closes #170

No window. Three seams that make every later stage cheap and leave the terminal
byte-identical at the default backends.

**`ask()`** — the 15 `input()` calls became `ask_text()` / `ask_choice()` /
`ask_confirm()` over a pluggable backend. Terminal backend *is* `input()`; the Qt
backend is Stage 1. `ScriptedBackend` replays queued answers. Same call, same
place in the flow.

The five blocking gates are authenticity, grounding, thin facts, over-length,
and **metrics** (`main.py` "Start the next video anyway?") — cadence is
print-only.

**`emit()`** — `core/ui.py` display helpers default `print_fn` to a module-level
sink. Terminal writes stdout; a later Qt pane can capture without rewriting
~100 `print` sites in `main.py` / `pipeline.py`.

**Design tokens (#170)** — `config/design_tokens.json` (palette, type scale,
spacing, per-channel accent) is what `core/themes.py` and the caption/Pillow
fill both read. Shipped tapin `#FFFFFF` / moneywise `#F7E7A9`.

**Exit (met):** terminal default backends still call `input()`/`print`; `ask()`
has a scripted test backend; tokens drive ANSI plus the caption overlay.

## Stage 1 — The run window · shipped 2026-09-07

The daily driver: one window that makes a video without PowerShell.

- Channel picker, topic box, **large facts paste area** — run 73's actual injury,
  where an article got pasted into PowerShell because there was nowhere else
- Worker thread runs `main._run_new_video_flow`; `ask()` round-trips on
  `AskBridge` (no `input()`)
- Output pane from `emit()` plus a stdout tee so `print(script)` still shows
- Discovery progress via `DiscoverySpinner.report` -> the bridge
- Angle mode from `core.angle_intent` on the topic box
- The five safety gates as Override / Stop; Proceed as Approve / Regenerate / Reject

**Exit:** `py -m desktop` after `pip install -e ".[app]"`. Without PySide6 the
command refuses honestly. CI does not install the extra; the bridge tests do
not need a display. The CLI is unchanged (`py main.py` without `--gui`).

Launch: `py -m desktop` · `py main.py --gui` · `py -m scripts.ops run-window`.

## Stage 2 — Look · shipped 2026-09-07 · closes #150, #172, #173

QSS generated from Stage 0 tokens (`core.chrome.build_qss`); type scale and spacing;
dark chrome from each channel's `end_card_bg`/`end_card_fg` (#304 — reviewing happens
at night); per-channel chrome so TapIn and MoneyWise disagree on header, type, and
accent (#150, #173); SVG icon from those tokens; designed empty and error copy; DPI
is 1.0 without a screen and uses `QScreen.devicePixelRatio` when one exists.
HTML dumps share the same generated CSS (#172). High-contrast / reduced-motion /
reduced-chroma are token flags (#527). CLI is unchanged.

**Exit (met):** widget stylesheet is non-empty token QSS, not default Qt; missing
PySide6 still refuses with exit 2 and no WARNING.

Launch: `py -m desktop` · `py main.py --gui` · `py -m scripts.ops run-window`.

## Stage 3 — Panels · 5–6 waves · closes 13 items

Each panel is an existing item whose data the system already computes. Ordered by
daily value.

**Shipped 2026-09-07 — review room (#168 + #209) and the visual angle list (#671).**
`ops review-room` / `py -m desktop --review` / `py main.py --gui --review`. Qt
paints `gather_booth_context` (mp4, grade, authenticity, cost). J/K/L live in
`core/review_keys.py` so CI can call them without decoding. Approve runs the same
`requeue-upload` command the HTML booth already prints. **`ops booth` remains.**
Missing PySide6: same honest refuse as the run window, exit 2, no WARNING. Other
Stage 3 panels (cost, analytics, …) are later waves.

| # | panel | note |
|---|---|---|
| #168 + #209 | Review room — player, Approve, J/K/L | **shipped 2026-09-07**; `ops booth` stays |
| #148 | Job queue — drag-reorder render/upload/quota-defer | **shipped 2026-09-08**; `ops queue-manage` stays |
| #158 | Cost tower — TTS 91%, Apify actors, YouTube units | the number that decides if this is worth doing |
| #149 | Analytics studio — retention, CTR, RPM | must keep saying n≈10 is thin |
| #163 | Script desk — grounding heat-map | verifier computes it; painting it is the work |
| #164 | Overnight monitor — gates, progress, presence | overnight is a forgotten window |
| #165 | Notification centre — history, DND, click-through | absorbs the toast work |
| #161 | Publish calendar — week view, quiet-hours/PPV overlays | |
| #156 | Vault companion — facts, tiers, expiry, dossiers | |
| #157 | Clip librarian — the 141 owned clips, search, usage | pairs with #417 ingest |
| #162 | Experiment cockpit — arms, MDE refusals, results | report-only; never auto-assigns |
| #160 | Legal/disclosure wizard | publish-blocking, not copy lines |
| #159 | MoneyWise earnings board | last; second channel |

**Exit per panel:** reads real data, and the equivalent `ops` verb still works. The
CLI is never removed — it is the headless path and the test surface.

## Stage 4 — Studio · 3–4 waves · closes #142, #151, #152, #153

The aesthetics work, and the reason Qt was chosen.

- **#152** thumbnail composition canvas — mechanical slice shipped 2026-09-08
  (`QGraphicsView` + last thumb + overlay). Drag/snapping shipped as **#692**.
- **#153** caption choreography timeline — keyframes over real word timings, which
  now exist on both the ElevenLabs and Edge TTS paths
- **#151** brand-kit compiler — fonts, palette, sting, handle, banner compiled to
  render assets *and* GUI chrome from the Stage 0 tokens

This **is** #142 "Shorts Visual Studio" — three panels in the app that exists by
then, not a sibling product.

## Stage 5 — Packaging · 2 waves · closes #146, #154, #174, #293

PyInstaller (Nuitka if startup drags) to one `.exe`; bundle ffmpeg and Piper
voices; **#146** tray daemon wrapping worker + overnight; Start-menu entry and
**#174** jump list for the last five drafts; **#293** `content-os://` protocol;
first-run setup that checks keys and writes `.env`; an update path that does not
need git; crash reports to a local file.

**Exit:** installs and runs on a clean Windows 11 account with no Python.

## Stage 6 — Portfolio · 2 waves · closes #169, #177, #476, #478

**#169** Channel Command Center as the home view; **#177** dual-channel status
wall; **#476** portfolio allocator (where the next ten videos go for expected RPM
under cadence caps); **#478** white-label channel kit consuming #51's Channel DNA
export to stand up channel #3.

## Stage 7 — Efficiency · 1–2 waves

Last, when there is something real to measure: cold-start budget, lazy panel
construction, table virtualisation, render queue parallelism, and the **CUDA torch
wheel** finally installed so whisper alignment runs on the 4070 Ti.

**Programme total: 16–19 waves.** Stage 1 alone ends the PowerShell dependency.

---

## Every XL, decided

| # | item | decision |
|---|---|---|
| 141 | Content OS Desktop | **Becomes this programme.** Checkbox retired; Stages 0–7 replace it |
| 142 | Shorts Visual Studio | **Absorbed → Stage 4** |
| 143 | Portfolio Intelligence Web OS | **Retired** — a SaaS framing for something never published. Its useful content is #169 and #476, both in Stage 6 |
| 144 | Distribution Sidecar (TikTok/Reels) | **Stays parked** with Phase M |
| 145 | Moat Suite | **Dissolved** — a wrapper around #156/#157/#158, all Stage 3 panels |
| 468 | Fact engine as a standalone surface | **Retired** — nothing is published, so a standalone surface has no consumer. The engine keeps improving inside the pipeline |

Six open XL items become zero.

## Every L, decided

**Absorbed into the app (21):** #146 #148 #149 #150 #151 #152 #153 #154 #156 #157
#158 #159 #160 #161 #162 #163 #164 #165 #168 #169 #170.

**Engine track — kept, sequenced outside the app (5):** #48 multi-run series · #50
learned insight markers (needs #356's retention data) · #54 retention-informed
`scene_plan` · #416 scene-beat cuts from owned gameplay (unblocked by #417) ·
multimodal rendered-video review (genuinely later).

**Kept standalone (3):** #79 affiliate spike, two weeks with a kill criterion —
the only non-ad revenue path · #155 MCP/plugin API, rising in value now two agents
share the tree · #478 white-label kit, folded into Stage 6 but survives alone.

**Retired (3):** #120 CLIP b-roll matching — decisions §26 settled this in favour
of owned gameplay · #467 second operator seat — single operator, private tool ·
#143's remains.

**Parked (2):** #166 Voice Judgment Booth — Edge TTS may retire the question
entirely · #167 Recommender Backtest Studio — volume-gated, must refuse to fit on
n≈10.

---

## Rules that hold across every stage

1. **The CLI is never removed.** It is the headless path, the test surface, and
   the fallback when a panel breaks. Every panel has an `ops` equivalent.
2. **No panel invents its own data.** If a number is not already computed by
   `core/`, the panel does not show it — it becomes a backlog item first.
3. **Stage 0's seams are toolkit-agnostic** on purpose. If Qt turns out to be
   wrong at Stage 3, only the backend changes.
4. **Every stage ends in use, not in a screenshot.** Stage 1 is done when a real
   video is made without a terminal.
