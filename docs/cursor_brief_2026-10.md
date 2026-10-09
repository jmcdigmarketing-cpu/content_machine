# Cursor brief — media first, then the app (October 2026)

> **Class:** plan · **Status:** living · **Reviewed:** 2026-10-09

The operator, 2026-10-08: *"draft up a very large run for cursor to work on"*. Asked how to
split it, they chose **both, media first**. The media phase answers what they said about the
finished videos: *"thumbnails are pretty terrible"*, *"the stock video really drives me crazy,
i would rather download a lot of uncopyrighted footage instead"*, *"is there naything we can
change about the voice to make sound better? idk less robotic?"* and *"how can clipping be
better"*. The app phase continues [desktop_app.md](desktop_app.md) Stage 3.

Every task below is a numbered item in [backlog.md](backlog.md) and a row in
[optimization_plan_2026-10.md](optimization_plan_2026-10.md); the backlog line is the spec,
this page is the order, the files and the definition of done.

---

## Rules (read first)

1. **Read [handoff.md](handoff.md) first, and write the Cursor slot as your last edit.**
   Verify the Claude slot against `git log <sha>..HEAD --oneline` and `git status --short`.
2. **Start from Claude's wave 66 commit** (the handoff slot names it). Pull first.
3. **Sign every commit** `Co-authored-by: Cursor <cursoragent@cursor.com>`. ASCII bodies.
4. **Tests first.** Write the test, watch it fail on unmodified code, then fix (the repo's
   `tdd` skill). Say in the commit how many failed first.
5. **No network in tests, no writes to `data/` or `output/`.** `py -m scripts.ops test`
   prints "Suite hygiene: data/ and output/ untouched" - it must.
6. **Done means CI passes:** `ruff check .`, `ruff format --check .`,
   `python scripts/mypy_ratchet.py` (the count may fall, never rise), the suite in default
   and reverse order (`py -m scripts.ops test --order reverse`).
7. **A live-run defect gets a case in `tests/regression_corpus.json`** (CLAUDE.md).
8. **Never** commit `.env`, `config/secrets/`, `.agents/` or `.codex/`. Never `git stash`
   (`video/backgrounds/*` are permission-locked; a stash deletes untracked files).
9. **Every new function has a production caller** - grep for it before you commit.

### File ownership while both agents work

| Cursor owns | Claude owns | Shared - leave a handoff note before editing |
|---|---|---|
| `assets/`, `video/`, `core/tts.py`, `core/chapter_shorts.py`, `desktop/` | `core/` engine (`content_engine`, `facts/`, `vault/`, `ui.py` prompts), `apis/`, `sports/` | `main.py`, `core/pipeline.py`, `config/channels.json`, `.env.example` |

---

## Phase A — the media (do these in order)

### A1 · Licensed footage, in bulk (#1040, with #424)

**Why.** Stock is now a last resort (`background_mode: local_first`, wave 66), so owned
footage is what fills a video. The Twitch, football and AI folders are empty (#786).

**Do.** A footage intake that searches CC0 / CC BY / public-domain sources (Wikimedia
Commons, Internet Archive, NASA-style public domain), checks each licence, downloads into
`video/backgrounds/<niche>/<subject>/` with a `license.yaml` per file (owner, licence,
sources, commercial_use), refreshes `data/clip_index.json`, and refuses anything without a
clear licence. Fix the bug your 2026-09-20 slot found: `footage-add` overwrites the folder's
licence string. Credits flow to the description already (#1019, `clip_credit`).

**Done.** A fixture-driven test per source (recorded JSON, no network); a licence test
that a missing or non-commercial licence is refused; the overwrite bug has a regression case.

### A2 · Stock, polished for when it is the last resort (#1041)

When stock runs: scene-matched to the script beat, never the same clip twice in a video or in
the last N videos, and labelled on the run card (the render already prints `footage_label`).

### A3 · Thumbnails v2 (#1047, #1048)

**Why.** "pretty terrible": the Flux prompt says "no text, no logos"
(`assets/flux_thumbnail.py`), the Pillow fallback is crude, and dual mode needs
`pick-thumbnail` by hand.

**Do.** A headline overlay (3-5 words from the title, brand fonts, stroke and shadow), a
subject cutout where a face or player exists, a contrast check that refuses an unreadable
result, and the scorer picks between two candidates (`pick-thumbnail` becomes the override).

**Done.** Golden-image tests on the composition (sizes, safe margins, contrast ratio), not
on pixels from a model.

### A4 · A voice that sounds less robotic (#1035, #1036, #1037, #1038, #217)

**Why.** With `TTS_CACHE` on (the default) every sentence is voiced in its own call
(`core/tts.py` `_generate_by_sentences`) and joined with a hard concat: each sentence starts
its intonation from zero. Speed is now 1.05 (wave 66).

**Do.** Voice a paragraph per call with ElevenLabs previous/next-text stitching, keep the
cache per paragraph, add a short crossfade at joins, fix caption drift (timings shifted by
the last word's end at each join), move stability/style/similarity into `tts` in
`config/channels.json`, run a two-arm A/B (experiments registry), and add a pronunciation
dictionary for names (#217).

**Done.** Tests on the request shape (previous/next text sent, settings sent), on caption
timing across a join (a synthetic 3-paragraph timing set), and on the cache key.

### A5 · Chapter Shorts that stand alone (#1053)

**Why.** `core/chapter_shorts.py` re-encodes a chapter at its timestamps - up to 180 s, no
minimum (run 120 offered a 6-second chapter), no re-hook, no end card - saves it beside the
long video, and the queue prompt defaults to No; `short_source: chapter_cut` is never read.

**Already done by Claude (wave 67, #1010/#1009 - in your file, with a handoff note):**
`chapter_shorts.SHORTS_MIN_SECONDS = 20` with an "under the 0:20 Shorts minimum" verdict, and each
chapter's title is now checked against the script (`angle_chapters.choose_chapter_title`), so a
Short's title is too. A chapter the script never wrote no longer reaches the list.

**Do.** A re-hook first line (the chapter's strongest fact as on-screen text),
an end card pointing to the long video, `output/<ch>/shorts/`, queued by default, and
`short_source` read by the growth report (#1054 is Claude's half).

### A6 · Black and frozen frame QC (#1044)

Technical QC flags a black or frozen stretch longer than 0.5 s, with the timestamp.

### A7 · #999 — a failed intro prepend is recorded as an intro

---

## Phase B — the application (after A)

| Order | Item | Done means |
|---|---|---|
| B1 | #1067 the new-video page with an intent card | type an idea; angle 1 is your idea worded for search (`apis.topic_variants.idea_angle`), the intent read (`core.angle_intent`), Enter keeps it |
| B2 | #1068 + #1064 the review room confirms claims and goes public | each flagged claim with its sources; confirm, fix or cut; `go-public` from the window. The engine half shipped in wave 67 (#1013): call `core.facts.claim_confirm` (`run_flagged_claims`, `confirm_claim`, `reject_claim`) - the same functions `ops verify-claim` uses |
| B3 | #161 the publish calendar | a week view of queued and scheduled uploads, cadence guardrail visible |
| B4 | #157 the clip librarian | search, licence, anti-repeat and per-clip performance over `data/clip_index.json` |
| B5 | #1070 settings | key *names* only (never values), channel config, voice settings |
| B6 | #451 phone approval | approve a render from a phone-sized view, with a push |

Tests: `tests/qt_support.requires_qt`; widget tests run in CI with `QT_QPA_PLATFORM=offscreen`.
PySide6 stays `<6.12` until #1015 (6.12.0 aborts at interpreter exit after a QtMultimedia
decode).

---

## When you finish a task

Tick it in [backlog.md](backlog.md) with what you measured, add a dated entry to
[planning_log.md](planning_log.md), and write the Cursor slot in [handoff.md](handoff.md).
