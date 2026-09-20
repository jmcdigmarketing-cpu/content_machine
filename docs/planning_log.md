# Planning log

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-09-20

A durable record of planning/brainstorming sessions so ideas aren't lost when the
ephemeral plan files (`~/.claude/plans/*.md`) are cleared. **Newest first.** Each entry
captures the prompt, the brainstorm/decisions, and what actually shipped — the tactical
backlog itself lives in [roadmap.md](roadmap.md).

> Convention: when a planning session happens (plan mode, or a substantial "what should we
> build" discussion), append a dated section here with the options considered, the
> decision, and — once built — the outcome. See [../CLAUDE.md](../CLAUDE.md).

---

## 2026-09-20 - Grand audit + master plan + docs standard

**Prompt:** "Brainstorm and plan plan plan big audit and master plan moving forward,
future more docs standardize etc etc." Planning/structure session — no feature work.

**Audited from scratch** (nothing carried from an earlier doc — that habit was itself a
finding): ~89k lines of Python, 254 test files, 46 docs / ~114k words, ruff, mypy, the
full suite, the doc link graph and the git history. Written up in
[audit_2026-09.md](audit_2026-09.md).

**The finding that mattered.** `tests/test_run69_fixes.py` passes **13/13 alone** and
**fails 5 in the full suite**. `core/llm_router._ollama_probe_cache` is a hand-rolled
module global (not `lru_cache`); `test_run_mode.py` and `test_free_doctor_probe.py`
reset it by hand and `test_run69_fixes.py` does not, so once any earlier test warms it,
patching `ollama_installed_models` stops doing anything. The five tests that stop
guarding are the ones pinning the run-70 outage (Free mode advertising an empty Ollama).
Green does not currently mean that guard holds, and the suite's verdict depends on
discovery order. This is decisions §18 — *reports healthy while broken* — applied to the
test suite itself, and it is M0 of the plan.

**Other measured findings.** mypy 136 errors / 89 files (June tracked ~94 — a
non-blocking baseline with nothing ratcheting it grows). Ruff pinned 0.8.4 consistently
across CI, `pyproject.toml` and pre-commit but ~9 months old; current ruff reports 28
lint + 28 format findings, i.e. a deferred bill, not a break. 627 broad `except
Exception` against "~18 silent" tracked in June. `core/` is 149 flat modules, 55% of
source. A partial install yields 263 errors (221 `ModuleNotFoundError`) instead of skips,
which is how two collateral failures (`test_engagement`, `test_seo_tags`) looked like
logic bugs and were not.

**Docs findings.** No index existed. Five files were 48% of the corpus, `roadmap.md`
1,774 lines with a single 1,084-line section. Eight roadmap-shaped docs, four
audit-shaped. 15 docs untouched since the repo's first commit. **Twelve different live
test counts** (363 … 2160) — `assessment.md` carries two of them in one file. Five
filename conventions, three product names, two orphans.

**Decided — the structure, not just the prose.** Class/status taxonomy
(`index`/`charter`/`reference`/`runbook`/`plan`/`snapshot`/`log` ×
`living`/`frozen`/`archived`), a one-line doc card on line 3 of every doc, `snake_case`
naming with dated snapshots, and the rule that resolves the count drift: **a number that
changes is either generated or dated** — bare counts are banned from `living` docs and
correct in `frozen` ones. Rejected: YAML front-matter (renders oddly, and the repo's
style is prose), and a docs/ subdirectory tree (the index solves navigation without
breaking 28 inbound links to `roadmap.md`).

**Shipped:**
- [docs_standard.md](docs_standard.md) — the conventions; [README.md](README.md) — the
  index that did not exist; [master_plan.md](master_plan.md) — canonical forward plan,
  M0–M5, every wave with an exit criterion that is a command.
- `tests/test_docs_standard.py` — 11 checks, written first and observed failing on
  unmodified docs (46 missing cards, no index). CI-blocking, sibling of the existing
  `test_docs_lint.py`.
- Doc cards applied to all 46 docs. Four superseded plans marked `archived` with
  successors (`content_intelligence_roadmap`, `groundwork_2026Q3`, `intelligence_phase`,
  `scope_feature_store_and_research_v2`). `audit.md` → `audit_2026-08.md` with inbound
  links rewritten. Volatile test counts removed from the four `living` docs that carried
  them.
- Pointers updated: `CLAUDE.md`, `AGENTS.md`, `ROADMAP.md` now route through the index.

**Deliberately not done:** the ten `LEGACY_NAMES` renames, the product-name sweep, the
`roadmap.md`/`HANDOFF_SYNOPSIS.md` splits and the `decisions.md` rewrap — all sequenced
as M1/M2 rather than bundled into a structure commit, so each lands reviewable. No
feature work, no behaviour change.

**Honest leftover:** M0 is not fixed, only diagnosed — the suite is still order-dependent
as of this commit. The `Reviewed: 2026-09-20` date on all 46 cards is truthful about the
audit pass, not about a line-by-line re-read of every body; M1.3 is where the 15
never-revised docs actually get read.

---

## 2026-08-27 - Vault relevance engine finished (P2–P4)

**Prompt:** finish the vault relevance engine (public-corpus crash, two-stage web skip,
measured P3 flip, conditional P4). Do not restart P2; do not mix Fortnite clip-picker
work; do not demote `_GAME_ANCHORS` from topic-graph.

**Measured (`ops vault-eval --no-save`):** holdout from live runs 66 and 70, both labels,
scored precision **1.0** and recall **1.0** vs P1 baseline **0.667**. Overall on the
14-case set: 4 uncertain / 3 confident / 7 reject. The encoded P3 gate passed, so
`config/vault_relevance.json` `default_mode` flipped to `scored`.

**Shipped:**
- Public `Sources:` accept `relevance_corpus`; headless loads with `relevance_policy=public`;
  already-chosen URLs skip a corpus-less vault reload (`generate_content_package` no longer
  TypeErrors).
- Two-stage discovery: fetch non-web, score vault, then `_fetch_one("web_search")` or
  `STATUS_SKIPPED`. Scorer failure fails open to web and logs a warning. Legacy keeps the
  pre-fetch density skip. No second cache inside the signal.
- Operator pick indexes match the printed `1. …` numbers; near-threshold rejects are
  inspect-only and never auto-attached.
- P4 extract-tier JSON tiebreak (`VAULT_RELEVANCE_TIEBREAK`, default off) for
  operator-facing uncertain rows only. Cache key = topic + bullet + corpus hash + scorer
  version. Pre- and post-tiebreak bands persist on `FactRecord` and the run audit (§25).
  Never called from public Sources: or web-search skip.

**Not done:** P4 is not turned on. 4/14 uncertain is a real residual band, which is why
the code shipped; an extra extract-tier call on every operator vault scan is still an
operator opt-in.

---

## 2026-08-27 - Next 5 shipped; the POA for subject relevance

**Prompt:** "review cursor, edit as needed, and roadmap next 5", then: "what about
changing the scoring matrix itself? its not perfect isnt good enough ... brainstorm a
way to do so even if its the long route".

**Shipped:** 326 (install the declared deps, and 12.3.0 not 11.3.0), 327/328
(spoken-number ranges + the IndexError), 329 P0+P1 (surface anchor-less notes, and the
eval harness), 330 (the crossfade duration bug). 2160 tests green.

### Reviewing Cursor

Rule 6 worked end to end: it closed the run-71 vault gap **and** inverted the documented
gap test exactly as that test's docstring instructed. Marvel Rivals and SEGA genuinely
no longer attach to a GTA topic, and still do not.

The fix over-corrected. Requiring a shared *franchise anchor* also dropped notes about
the people and companies in the story - "Rockstar Games confirms the leak investigation
is ongoing" vanished from a GTA topic that names Rockstar, silently, on the interactive
vault prompt. `_GAME_ANCHORS` is a hand-kept list of **games**, so companies are invisible
to it.

### The POA: change the scoring matrix, not the filters

The operator's framing was right and it is the architectural answer.
`load_fact_records` is a **chain of boolean gates** - token overlap `and` distinctive
tokens `and` anchor family. A chain of ANDs can only get stricter, so every fix trades a
false positive for a false negative, and strong evidence on one axis can never
compensate for weak evidence on another. "Rockstar Games confirms..." has high corpus
similarity and zero anchor family; the chain kills it on the anchor gate and never sees
the similarity.

**This repo already solves this class of problem correctly elsewhere** -
`apis/topic_scorer.composite_score` is a weighted evidence model with
`core/opportunity.signal_breakdown` explaining the result. The vault path is the odd one
out. Make it match.

**Measured on run 71's real five bullets, against run 71's real corpus:**

| Axis | GOOD Rockstar | GOOD subpoena | BAD Wolverine | BAD Marvel | BAD SEGA |
|---|---|---|---|---|---|
| Entity-in-corpus (bullet) | **1/1** | 0/0 | **0/1** | **0/3** | 0/0 |
| Entity-in-corpus (note) | - | **1/2** | **0/0** | - | - |
| Corpus cosine (bullet) | **0.309** | 0.000 | 0.143 | 0.063 | 0.000 |
| Corpus cosine (note) | - | **0.296** | **0.000** | - | - |

No single axis separates all five; together they do. Entity-less bullets are decided at
the **note** level. And decisively: against the **topic** the bad Wolverine bullet
*beats* the good one (0.286 > 0.154) because the topic itself says "Wolverine"; against
the **corpus** the ordering is right at 2.2x. **The corpus is the disambiguator, not the
angle.**

Every input already exists - `fact_grounding.specific_entities` / `mentions`,
`authenticity._content_tokens` / `_cosine`, `fact_store.TIER_WEIGHTS`. No new dependency,
no model, **no hand list**. `_GAME_ANCHORS` becomes one weighted feature among six, so it
can shrink or retire without a cliff, and `topic_graph.py`'s second hand list stops being
load-bearing.

**Getting past "not perfect isn't good enough": make it a number.** P1 shipped
`core/vault_evals.py` (`ops vault-eval`), frozen labelled cases, deterministic rubric,
no LLM judge - **baseline precision 0.667, recall 0.667**. P2 has to beat that, measured.

**Phases:** P0 stop the silent drop (done) - P1 harness + baseline (done) - P2 scorer
behind a flag - P3 flip on a measured win, demote `_GAME_ANCHORS` - P4 optional
extract-tier tiebreak for whatever band remains. Never silent: the score and its
breakdown surface in the fact prompt.

**Limits recorded:** ALL-CAPS acronyms are not extracted as entities, so SEGA scores 0/0
on that axis; a short corpus weakens every axis; six fixtures is indicative, not
conclusive - grow the set from real runs before trusting a tuning decision.

### Worth not relearning

- **A manifest edit is not an applied upgrade.** The whole dependency wave was declared
  and never installed; the pin test now asserts installed-vs-declared.
- **11.3.0 was not the safe choice.** It still carried 25 advisories - all fixed only in
  12.x, and all in font/PDF/JPEG2000/TGA parsers, i.e. the untrusted-bytes surface.
- **A filter graph ffmpeg accepts can still be wrong.** The crossfade ran clean and
  shortened every background by the fade; only a real render with `ffprobe` showed it.

---

## 2026-08-26 - Next 20 (1L / 4M / 15S) implemented

**Prompt (step 2):** implement the mixed wave on `main` after PR #37. Same
exclusions (Phase M, #141–#147 FastAPI/tray/XL, Edge TTS, NVENC, CUDA torch,
`SCENE_MATCHED_BROLL` on TapIn, Coverr-as-quality, do not flip
`background_mode` to `local`).

**Shipped in order:**

1. **#47 topic graph `[L]`** — JSON sidecar; `get_best_bets` continues week-1 →
   week-2; graveyarded follow-up excluded; empty graph fail-open.
2. **§26 hybrid xfade `[M]`** — TapIn `hybrid_local_ratio` 0.70 (still hybrid,
   not local); `xfade` at the local→stock join. MoneyWise ratio unchanged.
3. **#46 seasonal calendar `[M]`** — `config/seasonal_calendar.json`; frozen
   `now=`; no HTTP.
4. **#123 spoken numbers `[M]`** — TTS path expands `29-1` / UFC 317 / `$50k`;
   captions keep digits.
5. **#42 franchise batch cache `[M]`** — same `build_key`/`_fetch_one` cache,
   franchise key inside `run_batch` only.
6–20. DATABASE_URL suite blanking; real PDF fixture; wolverine-only vault gap
   closed; Extended chapters; demonetization detector; policy runbook ops verb;
   n8n weekly-report cron; Dataview dossier keys; wiki-links; quota-increase
   playbook; booth favicon; 1.25× playback; Send-to facts.txt; tray git
   describe; TapIn swatch strip.

**Honesty:** Edge TTS Wave B still parked (LGPL-3.0). `background_mode` is still
`hybrid`. `origin/claude/docs-optimization-review-a4l104` stays unmerged.

---

## 2026-08-26 - Stock-footage preference + MoneyPrinter hyper-compare (docs)

**Prompt (step 3 of the four-step session):** note that the operator does not
like taking that much unnecessary stock footage — it is often unrelated, and a
cut from gaming to live-action reality with no transition is disorienting. Also:
what does MoneyPrinter actually do for video clips, and which project is better.

**Two different MoneyPrinters.** Do not conflate them.

- **MoneyPrinterV2** (`FujiwaraChoki`) — AGPL-3.0, ~30k★, velocity/cost play
  (gpt4free, KittenTTS). Pattern-borrow only; never clone near this repo.
- **MoneyPrinterTurbo** (`harry0703`) — MIT, the Aug-25 Wave A source. Same
  commodity generator shape as ShortGPT: topic → LLM script → stock clips →
  TTS → MoviePy/FFmpeg. **No fact engine, no claim verifier, no YouTube
  learning loop.**

**What Turbo does for clips** (read from `app/services/material.py`, not from
marketing):

1. After the script, an LLM emits a list of search terms (default **5**).
2. For each term it searches **one** configured source: Pexels, Pixabay,
   Coverr, or `local` (a folder). Exclusive — not a hybrid mix.
3. It downloads until summed `min(max_clip_duration, clip.duration)` covers
   VO length. Default **max clip = 5s**. Concat mode **random** (shuffle) or
   **sequential**. Optional transitions: none / fade / slide / shuffle.
4. `match_script_order` can keep term order; otherwise random shuffle is the
   default. Coverr: `GET https://api.coverr.co/videos` Bearer + `urls=true`.
5. Separate path: **WaveSpeed** on-demand AI clips (paid, stop when duration
   is filled) — closest analogue to our parked ComfyUI/LTX slot, not to Pexels.

**What we do:** TapIn ships `background_mode: hybrid` at `hybrid_local_ratio:
0.45`. `get_background_asset` takes one local gameplay clip and one stock
clip (Pexels → Pixabay → Coverr). `build_hybrid_concat_command` hard-concats
local then stock with **no fade**. Keyword rewrite + abstract-tag skip exist;
they do not make live-action "GTA" footage. `SCENE_MATCHED_BROLL` (opt-in) is
one stock clip per beat — more of the same problem.

**Verdict:** Content OS is the better *media OS* for TapIn/MoneyWise
(grounding, loop, compliance, cost meter, YouTube ops). Turbo is the better
*stock-b-roll concatenator* (transitions, 5-term LLM search, clip duration).
For the operator's actual complaint, **Turbo would make it worse** — more
live-action cuts per Short. The useful borrow is a crossfade at our hybrid
join, not Coverr-as-quality and not enabling scene-matched stock. Owned
gameplay (`background_mode: local` or a higher local ratio) is the fix; that
config was not flipped this session.

**Recorded as:** [decisions.md](decisions.md) §26,
[moneyprinter_vs_content_os.md](moneyprinter_vs_content_os.md). No production
render change.

---

## 2026-08-26 - Next-20 mixed S/M wave (implemented, not committed)

**Prompt:** user said "next 20" — implement the approved 20-item wave
(`new_repos_next_20_3a743bff.plan.md`) as Step 2 of a four-step session. No
commit. No Step 3 audit. No Step 4 commit.

**Shipped (in order 1→20):**

1. Original `/tdd` skill at `.claude/skills/tdd/SKILL.md` + Cursor copy (fail-then-fix; never mock the function under test; not a third-party copy).
2. Coverr stock provider (`GET https://api.coverr.co/videos`, Bearer, `urls=true`); registered; both channels + settings default; no-key fail-open, no healthy-run warning; prefer no-face tags.
3. Thumbnail composition arms `subject_scale` / `text_negative_space` / `hard_light` in our own words; kind stays `thumbnail`.
4. Wave C public-apis shortlist in `docs/agent_reach_evaluation.md` — no keyless candidate displaces `tiktok_trends`; `youtube_competitors` already has a free backend.
5. In-repo eval-corpus fixture `prompts/eval_corpus/invented_release_date.md` (gitignore exception); runner lists it with EVAL_CORPUS_LLM off.
6. Overnight `--facts-file` through existing `run_batch(..., key_facts=)`; `--file` remains topics.
7. Pillow==11.3.0, requests==2.32.4, drop moviepy; duration from `_probe_video_duration`.
8. #101 `captions.insert` on the publish path; fail-open if no track.
9. #124 250ms pause after line 1; skip is byte-identical.
10. #36 `ops topic-clone --run-id` calls `generate_draft` for real.
11. Vault competing-franchise gate (run-71 Marvel Rivals/SEGA vs GTA); remaining gap is a wolverine-only bullet with no franchise string.
12. #86 frozen golden scripts per channel on heuristic `score_script` (no LLM judge).
13. #89 `redact_for_public` + unpublished dossier withhold + SKU; pre/post line counts (§25).
14. #81 MoneyWise TapIn length/slot shape prior; never topics or `domain_slots`.
15. #28 learned intro duration; keep 2.15s until drop-off samples exist.
16. Expert Panel second original persona `shorts_pacing`; persist on the run; ops grade/booth when enabled; default off.
17. #105 opt-in channel comment (Data API has no pin); profanity first.
18. #106 Studio-deleted detection cancels `publish_log`; `ops studio-deleted` + daily_sync.
19. #133 `.ics` beside HTML dumps; `ops publish-ics`.
20. Tests that actually call `enabled_publish_platforms` / `publishers_for_channel` / `is_upload_configured`.

**Honest remaining gaps:** YouTube Data API cannot pin a comment; Coverr face filter is tag-based not vision; intro learning needs RETENTION_MIN_VIDEOS curves; wolverine-only vault bullets still attach; pins upgraded in files, local venv not reinstalled in this step.

**Parked:** Phase M, #141–#145, #146 tray daemon, #147 FastAPI, clip-from-source/avatar, volume-gated backtest, auto-flip TTS_PROVIDER, Benable #79, Edge TTS Wave B, CUDA torch, NVENC (#38).

---

## 2026-08-25 - Ten small tasks, production-complete wave (shipped)

**Prompt:** implement the documented MoneyWise persona plus #53, #298, #299,
#271, #262, #22, #21, #39, and #31 end-to-end on the current branch.

**Decisions and boundaries:**

- The persona is the exact finance-safe text documented in the 2026-08-23
  planning entry, including the schedule-backed Week Ahead recurring segment.
- Prompt versions are `content_engine_v7-<12 hex>` from SHA-256 over every
  content-engine function that constructs or repairs an LLM prompt. This catches
  silent source edits without hashing run-specific facts, dates, or topics; the
  source-unavailable fallback hashes stable code fields, never object addresses.
- Review metadata comes from the persisted content-run row, not a display
  fixture. Spoken duration comes from ffprobe on the persisted MP3 (not the
  intro-bearing final MP4); estimate uses persisted word count and the measured
  3.3 words/second constant.
- The burned-caption path now preserves a sibling SRT even for karaoke output.
  The booth converts that SRT to WebVTT because HTML5 `<track>` does not
  reliably consume SRT directly.
- #22 is deliberately a conservative Pillow visual-density check over the
  bottom 20%. It catches risky high-contrast composition but does not claim
  face or OCR detection, and reports QUIET/REVIEW rather than SAFE.
- `ops render-preview` writes `_preview.mp4` at 480x854 / ultrafast / CRF 30,
  uses a separate `_preview.mp3`, skips intro, extra formats, thumbnails,
  media-row updates, and asset records. The publisher blocks `_preview.mp4`.
  Default publish rendering remains 1080x1920 / fast / CRF 23.
- `ops artifact-retention` is a report, not a job yet. It lists old drafts,
  traces, and vault `_runs` clones, ignores `--apply`, and has no delete call.
  The older `ops artifacts --apply` output-cap command remains a separate,
  explicitly destructive pre-existing surface.

**Behavioral proof:** the initial red run recorded 11 tests (3 failures, 8
errors); the completed first pass had 13 wave tests. The audit added 3 more
behavior tests and observed 7 failures/errors before the fixes. The 16-test
module now exercises shipped config/persona, deterministic source-hash drift,
stored booth metadata and spoken-audio duration, escaped SRT-to-WebVTT,
thumbnail risk detection through the production caller, caption skin in the
real render caller, isolated preview output plus upload rejection, and
report-only retention.

**Operator proof:** shipped MoneyWise validation reached the real config path
(persona warning gone; the expected missing local OAuth-token warning remains);
`ops artifact-retention` printed `DRY RUN ONLY` against a temp root and selected
zero files; `ops booth --channel moneywise` wrote `booth.html` under a temp
HTML directory; `ops render-preview --run-id 999999` returned the explicit
`No content run` guard without writing media.

**Still out:** no dependency upgrades, no real paid TTS/ffmpeg preview render,
no OCR/face model, and no retention deletion mode. Those are materially larger
or require operator media/cost approval.

**Final verification:** `ruff check .` and `ruff format --check .` passed;
the full isolated suite ran **1,985 tests OK** (up from 1,969), and
`git status --short data/` was empty.

---

## 2026-08-25 - Post-wave-4 operator pickup (shipped)

**Prompt:** take the next five roadmap pickups, plan them, then implement them
without committing. The five work units were #313, #282, #308-310 together,
#232, and #122.

**Two roadmap assumptions were false when traced through production:**

1. #313 said the tray action would use an "existing opt-in gate file". No
   overnight pause file or check existed. The wave added one
   (`core/overnight_pause.py`) and checks it at the start of `run_overnight`,
   before topic collection or batch generation.
2. #232 described a Desktop link to the booth URL. `serve_booth` binds an
   ephemeral port and the server dies with its process, so a literal URL would
   be a dead shortcut. `booth_os.pyw` starts the server, opens the browser, and
   keeps the process alive; `ops booth-shortcut` installs that launcher.

**Shipped:**

- **#313:** tray pause/resume button and CLI flags. The paused batch returns an
  explicit result and performs no topic collection.
- **#282:** deterministic `Human: just now / Nm / Nh / Nd ago`, plus honest
  `heartbeat off` and `never` states on the real tray chip.
- **#308-310:** the successful primary ffmpeg argv is captured at render time;
  a music-bed failure replaces it with the VO-only retry argv. The separate
  intro-concat argv is captured too. Both persist in the existing redacted run
  trace. The booth renders native collapsible trace/command sections and copies
  a PowerShell-safe command. Nothing is reconstructed from incomplete paths.
- **#232:** persistent Desktop booth shortcut via `pythonw`, reusing the proven
  WScript.Shell installer rather than adding a second shortcut mechanism.
- **#122:** root `video/backgrounds/license.yaml` records owned/commercial use.
  A nearer folder sidecar overrides it; `LocalAssetProvider` carries the
  resolved metadata into `AssetResult.attribution`, and the existing asset
  recorder persists it.

**Behavioral proof:** `tests/test_next_five_pickups.py` failed against the
unmodified implementation with 2 failures + 6 errors (missing pause module,
formatter, callback/persistence, booth kwargs, shortcut, and attribution).
After wiring, the full isolated suite ran **1,969 tests OK**. `ruff check .`
passed; formatting was applied to the two files identified by
`ruff format --check`.

**Operator proof:**

- Pause -> `ops overnight --count 1` printed `Overnight paused by operator
  flag` and drafted nothing; resume removed the temp override flag.
- `ops booth --channel tapin` wrote the real last-run booth, whose HTML contains
  the redacted raw trace section. That historical run predates command capture,
  so ffmpeg details will first appear after the next render.
- `ops booth-shortcut` installed
  `C:\Users\jonma\Desktop\Content OS Review Booth.lnk`.

**Still out:** MoneyWise persona config, the Pillow/requests/MoviePy dependency
wave (needs a real thumbnail/render), FastAPI #147, tray daemon #146, Phase M,
and the operator's Piper voice judgment.

---

## 2026-08-23 - MoneyWise persona + the Pillow decision (docs only)

**Prompt:** "give moneywise a persona, then how would we deal with pillow?
different software or cut entirely, update? document and answer only, no loc"

---

### 1. MoneyWise persona

**Why it was missing:** candidate 33's `channels.json` ratchet found it on its first
run. Every prior test built its own dict, so the *shipped* config was never validated
and the gap sat there unseen. `moneywise` is the higher-RPM channel and it was
publishing with no human-context block at all.

**What consumes it:** `core/channel_persona.py` reads `perspective`, `tone`,
`audience`, `recurring_segment`, `signoff` (in that order, extras appended) and folds
them into an advisory prompt block. `core/channel_go_live.py:81` requires **`tone` +
`audience`** at minimum to report the channel ready.

**The constraint that shapes it:** finance content cannot sound like advice. The
description already carries "Not financial advice. For informational purposes only."
(#125), and the script prompt forbids personalised recommendations. A persona that
reads as a stock picker would fight both. So the point of view is deliberately
*explanatory* - the person who reads the filing and translates it - not predictive.
That is also the honest differentiator against the "5 stocks to buy now" tier the
2026 authenticity policy is aimed at.

**Ready to paste into `config/channels.json` under `moneywise`:**

```json
"persona": {
  "perspective": "someone who reads the filing, the print, or the fine print before having an opinion - and says plainly what it means for a normal paycheck",
  "tone": "calm, plain-spoken, mildly sceptical of hype - explains, never sells",
  "audience": "working adults who want to understand the money story behind the headline, not be told what to buy",
  "recurring_segment": "Week ahead: the two or three numbers that actually move things, and why",
  "signoff": "Numbers first. Opinions after."
}
```

Notes on the choices:

- **`recurring_segment`** maps to the schedule that already exists in the config -
  Sunday 18:00 ET is the "week ahead" slot, alongside weekday 08:30 pre-market and
  Saturday 10:00 evergreen. A recurring segment the schedule cannot support would be
  invented continuity, which is the thing the persona is meant to prevent.
- **Deliberately ASCII.** The persona text flows into prompts, logs and cp1252
  PowerShell output; `tapin`'s em dash is fine in the file but there is no reason to
  add more (candidate 250's ASCII-safe rule).
- **Tone contrasts with TapIn on purpose** ("high-energy, confident, a little
  irreverent"). Two channels sharing one voice is exactly the templated-at-scale
  pattern the policy penalises.
- Not written into `channels.json` this pass - the prompt was document-and-answer.
  Dropping it in is a config edit, after which `py -m config.validate_channels
  --channel moneywise` should report 0 warnings (it currently warns on the gap).

---

### 2. Pillow: update. The blocker was not real.

**Answer to "different software or cut entirely, update?" - update, and it is
unblocked today.** Pillow is 26 of the 75 known vulnerabilities that candidate 98's
pip-audit baseline found, the worst single package by a wide margin.

**Correcting the record:** this was previously written up as "pinned for moviepy 1.0.3
compat", which is wrong and had been the reason to defer. Measured:

```
moviepy 1.0.3 requires: decorator, imageio, imageio_ffmpeg, tqdm, numpy,
                        requests, proglog          <- no Pillow at all
imageio    2.37.3  ->  pillow>=8.3.2               <- floor
goose3     3.1.21  ->  Pillow                      <- unbounded
torchvision        ->  pillow!=8.3.*,>=5.3.0       <- no ceiling ([providers] only)
matplotlib         ->  pillow>=9                    <- floor ([providers] only)
```

**Nothing in the tree caps Pillow.** `pyproject.toml:26` is a bare `Pillow==9.5.0`
with no rationale comment. The constraint was folklore.

**The API surface is four calls**, none removed in Pillow 10, 11 or 12:

| Call | File | Status |
|---|---|---|
| `Image.new("RGB", ...)`, `ImageDraw.Draw`, `ImageFont` | `assets/flux_thumbnail.py:425` | stable |
| `Image.open`, `ImageStat` | `assets/thumbnail_scorer.py:63` | stable |

No `Image.ANTIALIAS`, no `draw.textsize`, no `font.getsize` - the three removals that
break most Pillow 10 upgrades. Verified by grep across `assets/`, `video/`, `core/`.

**Recommendation:** bump to **Pillow 11.3.0**, not 12.x. 11.x clears all 26 CVEs and
is the conservative choice while 12 is new; the four calls above are identical in
both, so 12 is a later no-op bump if wanted. Verify with one real render (thumbnail
generation is the only consumer) plus `py -m scripts.ops all-checks`.

**"Cut entirely" is the wrong question for Pillow, and the right one for moviepy.**
`moviepy` appears in exactly one line of production code:

```python
video/render_video.py:4    from moviepy.editor import AudioFileClip
video/render_video.py:220  audio_clip = AudioFileClip(mp3_path); duration = audio_clip.duration
```

One import, to read a duration. **The same file already has an ffprobe duration
helper** - `_probe_video_duration` at `video/render_video.py:63`, which uses
`format=duration` and works on audio containers too. So moviepy (and its decorator /
tqdm / proglog / imageio chain) is carried for a call the file can already make.
Cutting it is a genuine simplification independent of the security question - and
ffmpeg is already a hard requirement, so it adds no new dependency.

**Also worth noting:** the remaining 49 vulnerabilities are concentrated in the
optional `[providers]` extra - `torch` (8), `transformers` (5) - plus `setuptools`
(7), which is build tooling, not runtime. Only Pillow, `requests` (a trivial
2.32.3 -> 2.32.4 bump) and `cryptography` are in the core runtime path. That reframes
"75 vulns" considerably: the core install is a much smaller problem than the number
suggests.

**Suggested wave order:**

1. `Pillow==9.5.0` -> `11.3.0` + `requests` 2.32.3 -> 2.32.4. Verify with a real
   render and a Pillow-fallback thumbnail.
2. Drop `moviepy` from `pyproject.toml`; swap the one `AudioFileClip` call for
   `_probe_video_duration`. Verify the rendered mp4 duration matches.
3. Leave `[providers]` alone until a provider is actually in use; pin `setuptools`
   only if CI starts flagging it.

Both items need a **real render** to verify, which is why they stay their own wave
rather than riding along with a correctness pass.

---

## 2026-08-22 — Honesty + leave-the-terminal wave 4 (shipped)

**Prompt:** "back to work roadmap back to work" — resume the roadmap. Implement a
coherent wave of leftover `[S]` then `[M]`. Do not commit or push. Prefer
honesty / leave-the-terminal / operator-safety. Skip #147 FastAPI, #146 tray
daemon, caption skin (#21), thumbnail safe-area (#22), Phase M, volume-gated
backtest.

**Swap vs numerical next:** did **not** pick 21 caption skin, 22 thumbnail
safe-area, 31 artifact retention, 101 caption track, 146 tray daemon, 147
FastAPI, or 172 HTML design system. Ranked leftover `[S]` that (1) keep the
next *public* honest (playbook lint, vault sources in the description,
ungrounded numeric chips, authenticity semantic bar, grade breakdown,
overnight-render / RPM / yesterday-unsynced copy), (2) surface TTS 91% /
quota on the booth (cache-hit $0, Pillow vs Flux, signal dots, feed-stale,
sticky cost + quota, 16px type), (3) leave PowerShell (copy unlisted URL,
Obsidian dossier URI, postmortem markdown, quiet-hours toast DND, tray last
domain). **#147 still skipped.** No #141/#142/#143/#144/#145, no Phase M, no
volume-gated backtest, no auto-flip Piper.

**Shipped (20):** 37 playbook lint, 103 description sources, 252 copy unlisted
URL, 255 Obsidian dossier URI, 275 numeric chips, 276 semantic-arm bar, 277
grade breakdown, 280 TTS cache-hit $0, 281 Pillow vs Flux badge, 283
overnight-render plain English, 284 RPM deferred reason, 285 yesterday
unsynced copy, 289 signal-health dots, 290 feed-stale strip, 292 mute toasts
in quiet hours, 305 16px min type, 306 sticky cost bar, 307 sticky quota bar,
311 postmortem markdown, 316 tray last domain.

**Knobs:** `DESCRIPTION_SOURCES`, `CONTENT_TOAST_DND`, `CONTENT_TRAY_DOMAIN`.
Suite forces `CONTENT_TRAY_DOMAIN=false`. Playbook lint and yesterday-unsynced
copy have no kill switch (read-only / informational).

**Out:** Phase M, volume-gated backtest, $0 TTS voice judgment, FastAPI host,
`.env` / secrets / `data/` / `output/`. Leftover next: 313 pause-overnight,
282 human-presence last-seen, 308–310 collapsible/copy ffmpeg, 232 booth
`.lnk`, 122 `license.yaml`. Live-run 71 docs (already dirty) left as
documentation-only.

---

## 2026-08-21 — Honesty + leave-the-terminal wave 3 (shipped)

**Prompt:** implement **20 more** roadmap items on top of unpushed `7c243b0`,
commit, do not push / amend / PR. Advising allowed. Prefer `[S]` then `[M]`.

**Swap vs numerical next:** did **not** pick 21 caption skin, 22 thumbnail
safe-area, 31 artifact retention, 101 caption track, 146 tray daemon, 147
FastAPI, or 172 HTML design system. Ranked leftover `[S]` that (1) keep the
next *public* honest (UFC PPV window, quiet hours, SEO first line, UFC
stock-query rewrite, odds "favored" not "will", gambling-safe CTAs, FTC
copy), (2) surface TTS 91% / quota on the booth (escaped-LLM pill,
Standard-would-have-billed, allocated vs marginal, uploads + ElevenLabs
header, Apify pills, thin-facts banner), (3) leave PowerShell (click-toast
opens the mp4, high-contrast CSS, skip-link, copy-as-markdown, tray doctor
HTML + last grade). **#147 still skipped.** No #141/#142/#143/#144/#145, no
Phase M, no volume-gated backtest, no auto-flip Piper.

**Shipped (20):** 115 UFC PPV blackout, 116 quiet hours, 118 description
SEO first line, 121 UFC stock-query rewrite, 126 odds market voice, 127
gambling-safe CTAs, 128 FTC affiliate line, 229 click-toast opens mp4, 234
high-contrast CSS, 251 copy-as-markdown, 261 skip-link, 273 escaped-LLM
pill, 274 thin-facts banner, 278 Standard-would-have-billed, 279 allocated
vs marginal one-liner, 286 uploads-left booth header, 287 ElevenLabs chars
header, 288 Apify remaining pills, 314 tray doctor HTML, 315 tray last
grade.

**Knobs:** `UFC_PPV_BLACKOUT`, `QUIET_HOURS`, `DESCRIPTION_SEO_FIRST_LINE`,
`FTC_DISCLOSURE`, `ODDS_MARKET_VOICE`, `GAMBLING_SAFE`,
`STOCK_QUERY_UFC_REWRITE`, `CONTENT_TOAST_OPEN_MP4`, `CONTENT_TRAY_GRADE`.
Suite forces PPV/quiet/odds/gambling/SEO/tray-grade off.

**Out:** Phase M, volume-gated backtest, $0 TTS voice judgment, FastAPI
host, `.env` / secrets / `data/` / `output/`.

---

## 2026-08-21 — Honesty + leave-the-terminal wave 2 (shipped)

**Prompt:** implement **20 more** roadmap items on top of unpushed `48a062f`,
commit, do not push / amend / PR. Advising allowed. Prefer `[S]` then `[M]`.

**Swap vs numerical next:** did **not** pick 21 caption skin, 22 thumbnail
safe-area, 23 end-card, 146 tray daemon, 147 FastAPI, or 172 HTML design
system. Ranked leftover `[S]` that (1) keep the next publish honest
(category / kids / language / unique titles / UFC lint / MoneyWise
disclaimer), (2) stop doomed Free-mode sessions (RAM/VRAM, NVENC *probe*
not encode, secrets-doctor, OneDrive), (3) surface TTS 91% and quota
outside PowerShell (booth subtitle, economics CSV, scheduled/overnight/
uploads-left toasts, tray folder + Free/Standard). **#147 still skipped.**
No #141/#142/#143/#144/#145, no Phase M, no volume-gated backtest, no
auto-flip Piper.

**Shipped (20):** 94 NVENC capability probe, 95 RAM/VRAM preflight, 96
secrets-doctor, 100 OneDrive/.git hazard, 102 YouTube category from
`infer_domain`, 107 madeForKids audit, 108 default language, 117 title
uniqueness, 125 MoneyWise finance disclaimer, 129 UFC title lint, 135
economics `--csv`, 225 scheduled-upload toast, 227 overnight-drafts toast,
228 uploads-left balloon, 242 `ops grade --html`, 250 ASCII-safe HTML, 256
reveal trace, 272 booth TTS 91% subtitle, 312 tray open-output folder, 317
tray Free vs Standard.

**Knobs:** `RAM_MIN_GB`, `VRAM_MIN_GB`, `YOUTUBE_DEFAULT_LANGUAGE`,
`TITLE_UNIQUENESS`, `UFC_TITLE_LINT`, `FINANCE_DISCLAIMER`. Suite forces
`RAM_MIN_GB=0`, `VRAM_MIN_GB=0`, `TITLE_UNIQUENESS=off`.

**Out:** Phase M, volume-gated backtest, $0 TTS voice judgment, FastAPI
host, `.env` / secrets / `data/` / `output/`.

---

## 2026-08-21 — Leave-the-terminal wave (shipped)

**Prompt:** implement the **Recommended next 20 (2026-08-20 night)**, commit,
do not push. Advising allowed: prefer 20 *working* operator-visible pieces
over a half-done FastAPI shell.

**Swap:** skip **#147** FastAPI operator shell (`[L]` — would swallow the
wave; booth uses stdlib `http.server` via `ops booth --serve` instead). Slot
20 is **#240** `ops status --html`. **#254** reveal-thumb ships on the same
`ops reveal` helper as #253 (the two `[S]` leftovers named in the prompt).
Did **not** start Content OS Desktop #141, Shorts Visual Studio #142, or
Phase M.

**Shipped (20 + bundled 254):** 223 reliability `--html`, 222 tray quota
chip, 291 AppUserModelID, 226 breaker toast, 221 ffmpeg toast, 224 lightbox,
253 reveal mp4, 241 economics `--html`, 92 MAX_PATH, 93 FFmpeg lock retry,
109 unlisted-before-public, 319 blocking-publish sentence, 43 script trim,
97 trace redaction, 231 pyw Start Menu shortcut, 171 last-run booth, 200
thin-facts abort screen, 198 doctor `--html`, 78 intelligence-report SKU,
240 status `--html`. 254 bundled.

**Knobs:** `CONTENT_TOAST`, `CONTENT_HTML_OPEN`, `YOUTUBE_UNLISTED_REVIEW`,
`SCRIPT_TRIM`, `WIN_MAX_PATH`, `WIN_LONG_PATHS`, `FFMPEG_LOCK_RETRIES`.
Suite forces toast/HTML-open/unlisted-review off.

**Out:** Phase M, volume-gated backtest, $0 TTS voice judgment, FastAPI
host, `.env` / secrets / `data/` / `output/`.

---

## 2026-08-20 (night) — Recommended next 20 pickup order

**Prompt:** produce the **next 20** roadmap items in pickup/importance order
after PR #35 (live-run wave) and PR #36 (candidates 141–320). Ranking + docs
only — no features, no commit, no push, no `.env` / secrets / `data/` /
`output/`. Rank by the cycle’s three axes (**future viability**, **short-term
success**, **real-world cost**) plus the operator’s last theme (**get out of
the terminal / UI / aesthetics / app**) without unparking Phase M. Do not
re-list shipped 20 Aug waves or F1/F2/F3. Brainstorm next-5 (221, 222, 223,
224, 171) is a hint, not a cage. Prefer `[S]` then `[M]`; at most one `[XL]`
as item 20 with a warning — none used. PARKED items out unless labeled, never
as #1.

**Ranking rationale**

1. **The cost/honesty CLI wave is largely shipped.** Remaining pickup is not
   another ASCII dashboard; it is *surfacing* what already exists (reliability,
   economics, quota, gates) outside PowerShell — then the leftover Windows /
   leak / policy `[S]` that can still kill the next publish.
2. **Brainstorm next-5 does not survive as 1–5.** All five stay *in* the 20;
   the order changes. A ffmpeg-finished toast is operator minutes; a **breaker
   toast** and a **browser reliability dump** prevent doomed sessions and
   silent disablement (the cycle’s actual failure shape). **AppUserModelID
   (#291)** sits before the toasts so they group as Content OS, not
   `python.exe`. The **review booth (#171)** stays `[M]` at #16 — after HTML
   dumps, Explorer reveal, and unlisted-before-public — not as the first
   “app.”
3. **Leftover 1–140 still beats decorative CSS.** `#92` MAX_PATH and `#93`
   Defender file-lock can waste a render after you left the terminal. `#43`
   script trim still moves TTS (~91% of a rendered run). `#97` trace redaction
   and `#109` unlisted-before-public are honesty/policy, not chrome. Phone
   bezels, grain toggles, and magazine layouts stayed out.
4. **Viability still gets a slot.** `#78` intelligence-report SKU (no video,
   no TTS) is #19 so the UI theme cannot erase operating_plan §6.2.
5. **No `[XL]` in the 20.** `#147` FastAPI shell is item 20 with an `[L]`
   warning — thinnest host for the booth, not Content OS Desktop (#141).
   Phase M, volume-gated backtest, and the $0 TTS *voice judgment* stay out
   (not even as labeled PARKED pickups).

**The 20** (id · title · size) — detail + surfaces in
[roadmap.md](roadmap.md) **Recommended next 20 (2026-08-20 night)**:

1. **223** `ops reliability --html` `[S]`
2. **222** System-tray quota chip `[S]`
3. **291** Windows AppUserModelID `[S]`
4. **226** Toast when a breaker trips `[S]`
5. **221** Toast when ffmpeg finishes `[S]`
6. **224** Thumbnail lightbox (last Pillow thumb) `[S]`
7. **253** Reveal mp4 in Explorer `[S]`
8. **241** `ops economics --html` `[S]`
9. **92** Windows MAX_PATH / long output paths `[S]`
10. **93** FFmpeg file-lock retry `[S]`
11. **109** Unlisted review before public `[S]`
12. **319** “What’s blocking publish” one-sentence `[S]`
13. **43** Script trim pass `[S]`
14. **97** Redact API bodies from traces `[S]`
15. **231** Start-menu shortcut via pyw `[S]`
16. **171** Last-run review booth `[M]`
17. **200** Thin-facts abort screen `[M]`
18. **198** Doctor HTML page `[M]`
19. **78** Intelligence-report SKU `[M]`
20. **147** Localhost FastAPI operator shell `[L]` — warning: not the next hour; not #141.

**What stayed out**

- Shipped evening next-5 (pre-run gate, oauth tests + coverage extra,
  pronunciation lexicon, allocated vs marginal, numeric/record grounding) and
  the 20 Aug follow-on waves / F1–F3.
- PARKED: Phase M, volume-gated recommender backtest, $0 TTS voice judgment
  (including #144 / #166 / #167). Not in this 20.
- Massive **141–145** (Desktop, Visual Studio, Portfolio Web OS, Distribution
  Sidecar, Moat Suite). Item 20 is `#147` `[L]`, not an `[XL]`.
- Clip-from-source, avatar, storyboard, `instagram_figures`, MoneyWise *depth
  signals* (a board is #159 `[L]`, not this wave).
- Decorative CSS / aesthetics-only hours (phone bezel, grain, magazine
  layout, 2×2 contact sheets) until HTML dumps exist.
- Full review room **#168**, tray *daemon* **#146**, HTML design system **#172**
  (themed `--html` is enough until several dumps exist), file-count retention
  **#31** (`ops artifacts` already caps GB).

**Rejected this session:** implementing any of the 20; restoring Phase M;
auto-flipping Piper; rewriting July docs; overwriting the 141–320 candidate
lists; touching `.env` / secrets / `data/` / `output/`. No commit.

**Canvas:** `roadmap-next20-night.canvas.tsx` in the Cursor canvases folder
(grouped UI/app vs cost vs honesty vs ops).

---

## 2026-08-20 (late-night brainstorm) — 180 ideas (UI / app / aesthetics / sibling software)

**Prompt:** brainstorm **180 unique** ideas after the 20 Aug waves on `main`
(operator: PR #35), persist them, and leave a readable ranking. Counts must
hit exactly: **5 massive / 25 larger / 50 moderate / 100 small.** Cover
future viability, short-term success, and real-world cost (the house ranking
used all cycle) **and** more aesthetics/UI, application development / getting
out of the terminal, and expansion of this project **or different software**
beside it. Honest about YouTube-only and Phase M parked. Planning only — no
features, no commit, no push, no `.env` / secrets / `data/` / `output/`.

**Constraints honored:** skip anything already `[x]`; do not restate shipped
items (pre-run gate through F3 keyhash clear, including the 20 Aug night /
evening / follow-on waves); skip Next-up duplicates and candidates **1–140**
unless reframed as a *new product* with a new number; Phase M, the
volume-gated recommender backtest, and the $0 TTS *voice judgment* may appear
only as massive/larger labeled **PARKED**. TTS remains ~91% of a rendered
run; YouTube upload ≈ 1,600/10k units; remaining paid Apify is
`tiktok_trends` + `youtube_competitors`; Windows/PowerShell; unittest; no
second signal cache; breakers via `quota_governor` only.

**How ranked**

1. **Did not overwrite** the 2026-08-20 evening **Recommended next 5** — those
   five are already marked **shipped** (night wave). A new **Brainstorm next-5
   (UI/app)** sits beside them so the house ranking stays the historical
   record.
2. **House axes still bind:** future viability, short-term success, real-world
   cost. This pass *covers* them; it does not pretend the CLI cost/honesty
   work is unfinished.
3. **Operator themes this prompt asked to cover** (not 100% one theme):
   aesthetics/UI, leaving the terminal (desktop, web, tray, canvas, operator
   console), expansion **or sibling software**. Massive ideas are new product
   surfaces / years of work; small ideas are hours / a PR.
4. **Short-term UI/app pickup** is five *small/moderate* items that help the
   next publish (see the toast, leave a doomed run unstarted, review without
   scrolling `main.py`) **without** restarting Phase M.
5. PARKED items are labeled in-title. Sibling apps are called out as *not
   this CLI*.

**Lists:** [roadmap.md](roadmap.md) **Candidates 141–320 (2026-08-20 late-night
brainstorm)** — Massive 141–145 `[XL]`, Larger 146–170 `[L]`, Moderate
171–220 `[M]`, Small 221–320 `[S]`. **Brainstorm next-5 (UI/app)** is under
Next up, below the shipped evening five.

**Brainstorm next-5 (UI/app)** — small/moderate, short-term, no Phase M:

1. **221** Windows toast when ffmpeg finishes `[S]`
2. **222** System-tray quota chip (uploads-left + ElevenLabs chars + Apify
   breaker) `[S]`
3. **223** `ops reliability --html` themed snapshot `[S]`
4. **224** Thumbnail lightbox for the last Pillow thumb `[S]`
5. **171** Last-run review booth (localhost play / grade / approve) `[M]`

**The 5 massive (full)**

1. **141 — Content OS Desktop (local-first operator console)** `[XL]`
   The operator's bottleneck is no longer a missing governor; it is living in
   PowerShell. A Tauri or WinUI shell over existing `core/` (discovery,
   review, job queue, publish, reliability, economics) is years of UX, a11y,
   packaging, and Windows integration. Python stays the engine: same
   `make_signal()` shape, same `quota_governor` façade, no second signal
   cache. This is different software that *hosts* Content Machine, not a
   prettier `main.py`.

2. **142 — Shorts Visual Studio (aesthetics as a product)** `[XL]`
   Look today is a stock loop, Pillow/Flux thumbs, burned captions, and ANSI
   `ui_theme` skins. A sibling design app — type, motion, brand kits,
   thumbnail composition, caption choreography, shared design tokens with
   any future GUI — is a years-long product sitting *beside* the CLI.
   Distinct from candidates 21–28 (JSON skins, PIL checkers, one Ken Burns
   beat): those are flags; this is a studio.

3. **143 — Portfolio Intelligence Web OS** `[XL]`
   Vision v3 ("operate media businesses"): multi-channel margin, opportunity
   scanner, channel launch, holdouts, YPP. Honest: operating_plan still says
   **don't go SaaS** until the YouTube-only data moat is real (~10 measured
   vs a 15-sample recommender gate). This is the 12-month architecture as a
   product surface, not a CLI dashboard restyle, and it stays YouTube-only
   until Phase M is unparked.

4. **144 — PARKED — Distribution Sidecar (TikTok / Reels)** `[XL]`
   Phase M as *different software* that consumes an already-rendered 9:16 —
   never as Content Machine feature flags, never as the next pickup. Live
   constraint remains YouTube Data API (upload ≈ 1,600 of 10k/day). Parked
   by operator choice; listed so the idea isn't lost and so it cannot
   masquerade as a small YouTube tweak.

5. **145 — Moat Suite: Vault Companion + Clip Librarian + Cost Tower** `[XL]`
   The dataset *is* the company (operating_plan §7). Three sibling apps —
   facts/playbooks/dossiers with tier/expiry UX; licensed clip memory with
   anti-repeat and performance; spend control for TTS (~91% of a rendered
   run), the two remaining paid Apify actors, and YouTube units — that
   outlive any one renderer. Not this CLI; they read traces, vault, and
   `quota_governor.snapshot()` only.

**Rejected this session:** implementing any of the 180; restoring Phase M as
a near-term YouTube checkbox; auto-flipping Piper; treating clip-from-source /
avatar / Instagram figures as "next"; rewriting July docs; merging
`docs-optimization` branches; touching `.env` / secrets / `data/` / `output/`.
No commit.

**Canvas:** `brainstorm-141-320-ui-app.canvas.tsx` in the Cursor canvases
folder for this workspace.

---

## 2026-08-20 (follow-on 4) — Next 20 after night + evening + wave 3

**Prompt:** complete the next 20 roadmap candidates in pickup/importance order on
top of the three uncommitted waves, then audit.

**Pickup:** no new "Next 20" list after wave 3. Ranked previously skipped-but-eligible
items (C9, 68 fixture, 70 diagnostic, 67 report-only) then remaining evening `[S]`,
morning leftover `[S]`, and afternoon `[S]` for operator safety / suite hygiene.
Parked: Phase M, volume-gated backtest, $0 TTS *voice judgment* (no auto-flip Piper).

**Skipped:** none of the 20. **67** shipped report-only (no auto-assign). **70**
shipped as a CUDA readiness probe (no pip install / no kWh meter until CUDA torch
is actually on). **68** used a synthetic fixture in `tests/fixtures/` (no real
invoice, no network).

**Shipped:**

1. C9 Google HTTPS leak (99) — skip YouTube warmup in tests; `static_discovery=True`.
2. Apify monthly true-up (68) — synthetic invoice vs $0.02/run; `ops apify-trueup`.
3. CUDA / GPU diagnostic (70) — `core/cuda_probe.py`; no install; `ops doctor`.
4. TTS provider Bayesian report (67) — `ops tts-arms`; never writes experiments.json.
5. Cap `output/` by GB (77) — `ops artifacts`; dry-run default; `--apply` deletes oldest.
6. Inauthentic-content hash canary (80) — snapshot-only on reliability; no HTTP.
7. RPM x cost by domain (84) — `ops economics` domain lines.
8. Weekly moat backup (85) — dry-run plan; secrets excluded; pg_dump listed not run.
9. YPP checklist (87) — `ops ypp`; fail-open without metrics.
10. Per-stage LLM cost — `complete(..., stage=)`; script/brief/title tagged.
11. Docs metric lint in CI — `tests/test_docs_lint.py` + CI step; relative links.
12. Stable vault dossier paths — `{run_id}_{slug}.md`; date-prefix clones unlinked.
13. Audio LUFS — `LUFS_NORMALIZE` opt-in; default ffmpeg command unchanged.
14. Background clip anti-repeat — in-process deque; `CLIP_MEMORY` file opt-in.
15. `ops postmortem --run-id` (29) — traces already on disk.
16. `ops doctor` (30) — free stack + cached feeds + oauth file + quota + CUDA.
17. Cap discovery workers (41) — `DISCOVERY_MAX_WORKERS` default 8; 0 = unlimited.
18. Overnight quota-aware (45) — `OVERNIGHT_QUOTA_GATE` opt-in; skip/shrink count.
19. Disk-space preflight (91) — `DISK_MIN_FREE_GB` opt-in; ASCII `>=`.
20. Fact-expiry watchdog (55) — vault leftovers; `load_facts` already drops them.

**Audit (same pass):** warmup/live YouTube client forbidden in the suite. Overnight
quota / disk / LUFS / clip-file / policy fetch stay opt-in so leftover env cannot
abort tests or write `data/`. Policy canary and fact-expiry do not HTTP from
`reliability.gather()`. Artifact retention never deletes without `--apply` and
never walks `data/`. Moat backup never copies `.env` / `config/secrets/` /
`quota_state.json`. TTS arm report cannot start a lever. Nested tries on doctor
optional imports. Residual C9 leak: Analytics `HttpError` for `abc123` when
operator `.env` had `YOUTUBE_ANALYTICS_SYNC` on — `get_youtube_*_service` now
returns None under `CONTENT_FORBID_LIVE_YOUTUBE` before `load_credentials`,
OAuth refresh is skipped, competitor-sync API-key `build()` is gated, and the
suite forces `YOUTUBE_ANALYTICS_SYNC=false`.

**Deferred:** afternoon leftovers (31 file-count retention as a separate job,
caption skin, schema ratchet, …); remaining `[M]`/`[L]` in 78–89 and 91–140
except 91/99.

---

## 2026-08-20 (follow-on 3) — Next 10 after night + evening waves

**Prompt:** complete the next 10 roadmap candidates in pickup/importance order on
top of the two uncommitted waves, then audit.

**Pickup:** no new "Next 10" list after the evening ship. Ranked remaining
evening leftovers (now including skipped `[M]`s) plus morning/late `[S]` that
the evening wave deferred. Parked: Phase M, volume-gated backtest, $0 TTS voice
judgment.

**Skipped:** **67** TTS provider Bayesian arm (would auto-assign Piper; same
shape as the parked voice judgment). **70** CUDA/electricity (no GPU torch
install). **68** Apify invoice true-up (no invoice fixture in-repo).

**Shipped:**

1. Operator minutes-per-run (65) — `core/operator_timer.py`. Wall vs `input()`
   wait; summary line; in-memory only.
2. Human-presence unattended render (90) — `HUMAN_PRESENCE_HOURS` opt-in;
   overnight/daily-sync/worker do not stamp; drafts unchanged.
3. Competitor-sync YouTube-unit cap (88) — RSS free; API fallback capped + one
   upload reserved. Suite sets both knobs to 0.
4. Paid-signal outcome attribution (57) — `ops paid-signals`; engaged-rate then
   composite. Catalog untouched.
5. Justify remaining Apify (73) — same report; `disable` at n>=5/arm is a
   recommendation only.
6. RPM < cost skip slot (63) — `RPM_COST_GATE` opt-in; last 7 monetized uploads;
   worker defers without consuming a retry.
7. Channel-go-live trailer/handle/banner (139) — MoneyWise banner passes;
   handle/trailer still FAIL.
8. Integration incident ledger — rank count/(1+days); persist on `ops
   reliability` / `ops incidents`, not inside the signal pool.
9. `signal_facts` earnings ratchet — symbol/date/days/EPS, not JSON dump.
10. Competitor-channel health — RSS probe in ops; snapshot-only on reliability;
    McAfee UC flagged unverified, not auto-replaced.

**Audit (same pass):** heartbeat is a no-op on the default path unless
`HUMAN_PRESENCE_HOURS` is on (a first-pass `ops.main()` in the suite had written
`data/operator_heartbeat.json` — deleted, gate-off skip added). Competitor
health does not HTTP from `reliability.gather()`. Paid-signal report never
writes `apify_sources.json`. RPM / human-presence stay opt-in. ASCII in gate
strings. C9 Google HTTPS `ResourceWarning` still present (not this wave).

**Deferred:** 67/70/68 as above; C9 HTTPS ResourceWarning; remaining afternoon
21–55 `[S]`.

---

## 2026-08-20 (late-night follow-on) — Evening remaining [S] after the night wave

**Prompt:** complete the next 10 roadmap candidates in pickup/importance order on top of
the uncommitted night wave, then audit.

**Pickup:** no new "Next 10" list was written after the night ship, so remaining evening
`[S]` items (short-term / cost / honesty / operator safety). Skipped `[M]` 57/63/67/73,
CUDA 70, operator-parked Phase M / volume-gated backtest / $0 TTS voice judgment.
Skipped **65** (operator minutes) and **68** (Apify invoice true-up) — lower leverage
than the TTS/thumbnail cost gates.

**Shipped:**

1. Overnight/unattended render-queue gate (58) — `core/render_gate.py`. Auto-generate +
   render worker; interactive `main.py` unchanged. Missing grade fail-closes.
2. YouTube "N uploads left this reset" (59) — `youtube_quota.uploads_remaining`; reliability
   + startup. Check point stays `apis/youtube_quota.py`.
3. `ops channel-go-live` (60) — OAuth/SEO/feeds/brand kit/persona. MoneyWise still FAIL on
   persona. Never reads token contents except via existing oauth helpers.
4. Metrics-before-next gate (62) — `METRICS_BEFORE_NEXT` opt-in; no yesterday upload = pass.
5. Free-mode Standard billed dry-run (64) — counterfactual ElevenLabs+thumb; does not
   mutate persisted cost.
6. Hard character cap before TTS (75) — refuse, do not clip; default 5000; 0/off disables.
7. TTS cache by script hash (71) — spoken+provider+voice; sidecar copied; cache hit meters
   $0. `TTS_CACHE` opt-in (discover does not load `tests/__init__.py`).
8. Pillow-first thumbnail until ≥ B (74) — missing letter fail-opens; C/D/F skip paid APIs.
9. Subscription utilization dashboard (69) — reliability Utilization section; Brave has no
   usage counter yet.
10. Skip web-search on vault density (72) — distinctive vault facts only (no extra RSS HTTP
    / cache-stat probes); skip in `register_signals` orchestration.

**Audit fixes in the same pass:** cache-hit TTS line is $0 (no double-bill); nested tries
on optional reliability imports; no second cache inside `web_search`; governors/gates that
can abort stay opt-in (`METRICS_BEFORE_NEXT`, `TTS_CACHE`) so leftover `RUN_COST_MODE=free`
/ `FREE_MODE_STRICT` cannot abort the unit suite, and unittest discover cannot write
`data/tts_cache`. Render-gate messages stay ASCII (`>=`) so a cp1252 console cannot
swallow a block and then render anyway.

**Deferred:** 65 operator minutes; 68 Apify invoice true-up; morning leftovers (incident
ledger, `signal_facts` ratchet, competitor-channel health); 57 paid-signal attribution.

---

## 2026-08-20 (night) — Shipped recommended next 5 + cost/honesty 56/61/66/76 + Qwen3 + oauth coverage


**Prompt:** implement the top 10 roadmap candidates in importance order, then audit for optimization, efficiency, and debug quality.

**Shipped:**

1. Pre-run completion gate — `inspect_first_calls` / `guard_before_discovery` / `apply_and_guard`. Free fail-closed (stale Readiness cannot start discovery); Standard warns. `FREE_MODE_STRICT` is the raise switch so a leftover `RUN_COST_MODE=free` cannot abort unit tests.
2. `youtube/oauth.py` tests + `coverage` extra — temp token files only; `run_interactive_oauth` skipped. `coverage>=7.6.0` in `[dev]`; command recorded under the coverage wave; not a CI % gate.
3. Pronunciation lexicon — `config/pronunciations.json` on the local TTS path only. Captions/retext keep the caller script. ElevenLabs unchanged.
4. Allocated vs marginal unit economics — `ops economics` shows both. `COST_TTS_PLAN_USD` / `COST_TTS_PLAN_CHARS`. `cost_meter` marginal rates unchanged.
5. Numeric/record grounding — `find_ungrounded_numeric` (records/ranks/dates in sports context; purses always). Warn/fail-open; does not change `GROUNDING_GATE`. Round scores like 10-9 are not records (would have fired a premium regen). Run-66 "If Netflix" intact.
6. Thin-facts abort before TTS — default on, 3 lines + 50% support; missing verifier fail-opens. Interactive prompt / `--force`. Drafts stay saved.
7. ElevenLabs character-quota governor — `ELEVENLABS_MONTHLY_CHAR_BUDGET` opt-in (empty = off, same shape as Apify). Persist via `quota_governor` only. Trip to Piper or block before ElevenLabs. Tests isolate the store.
8. Qwen3 in Free TTS readiness — `qwen` in `_LOCAL_TTS_ORDER` when `qwen_tts` + `QWEN_VOICE` are ready; does not load the 1.7B model. Piper still preferred.
9. Meter Flux / Ideogram / Recraft — `COST_THUMBNAIL_PER_IMAGE` default $0.045. Pillow / no image = $0. TTS-only re-merge leaves a stored thumbnail line alone.
10. Escaped free-first LLM — usage record + cost line + reliability. Pinned provider never flags. First-hit DeepSeek premium is not an escape.

**Audit fixes in the same pass:** restored `reliability.gather()` (had been swallowed into `_elevenlabs_section`); nested the escaped-flag read so a cost_meter import failure cannot wipe LLM breaker state; tightened fighter-record regex so 10-9/29-28 judging cards do not trigger `GROUNDING_REGEN`; ElevenLabs governor stays opt-in so tests cannot poison `data/quota_state.json`.

**Deferred:** none of 1–10. Phase M, volume-gated backtest, and the $0 TTS voice judgment stay out. Did not pull integration incident ledger, `signal_facts` formatter ratchet, or competitor-channel health.

---

## 2026-08-20 (late) — Next 5 unchanged + 50 any-way candidates (91–140)

**Prompt:** the next 5 roadmap items, plus a final 50 ideas regarding this
project in any way.

**Not built.** Pickup order is still the evening recommended next 5. Phase M
stays parked (operator choice). Volume-gated backtest and the $0 TTS voice
judgment stay out. None of 91–140 restates Next-up, the morning 20, or
candidates 21–90.

**Recommended next 5** (unchanged):

1. Pre-run completion gate `[S]`
2. `youtube/oauth.py` tests + `coverage` extra `[S]`
3. Pronunciation lexicon for local TTS `[M]`
4. Allocated vs marginal unit economics `[S]`
5. Numeric/record grounding `[M]`

**50 new candidates (91–140)** grouped on [roadmap.md](roadmap.md):

| Group | Items | Through-line |
|---|---|---|
| Machine / Windows | 91–100 | Preflights, secrets, traces, supply chain, the C9 HTTPS leak |
| YouTube surface | 101–112 | Caption tracks, category, playlists, unlisted review — still YouTube-only |
| Content / learning | 113–124 | Prediction ledger, mailbag, PPV blackout, stock watermarks, SSML numbers |
| Legal / policy | 125–132 | Disclaimers, trademark, right-of-publicity, demonetization, incident runbook |
| Operator product | 133–140 | `.ics`, CSV economics, vault wiki-links, long-form preset, quota-increase playbook |

**Rejected this session:** implementing the five; restoring Phase M; treating
clip-from-source / avatar / Instagram as "next".

---

## 2026-08-20 (evening) — Next 5 pickup order + 35 cost/viability/success candidates

**Prompt:** the next 5 roadmap items, plus 35 more ideas, all around *future
viability*, *short-term success*, and *real-world cost*.

**Not built.** Pickup order only; Phase M, volume-gated backtest, and the $0 TTS
voice judgment stay out. None of 56–90 restates Next-up, the morning 20, or
candidates 21–55.

**Recommended next 5** (existing open lines, sequenced for those three axes):

1. Pre-run completion gate `[S]` — short-term (run-70 class).
2. `youtube/oauth.py` tests + `coverage` extra `[S]` — short-term (paused
   coverage wave, last sequenced item).
3. Pronunciation lexicon for local TTS `[M]` — cost (unblocks the $0.25–0.31
   TTS line on *ears*, captions already being fixed).
4. Allocated vs marginal unit economics `[S]` — cost (~$1 allocated vs $0.31
   metered on the Creator plan).
5. Numeric/record grounding `[M]` — viability (invented ranks/dates/purses
   still pass the name-gate; 2026-policy event on a UFC short).

**35 new candidates (56–90)** grouped on [roadmap.md](roadmap.md):

| Axis | Items | Through-line |
|---|---|---|
| Short-term success | 56–65 | Next publish happens and earns a measured data point (quota, thin-facts abort, MoneyWise go-live, operator minutes) |
| Real-world cost | 66–77 | Meter the true bill (Flux, Apify invoice, GPU power, TTS cache) and stop paying for drafts that will fail |
| Future viability | 78–90 | Stay a media OS: intelligence-report SKU, holdouts, policy canary, non-ad spike with a kill criterion, backup the dataset |

**Rejected this session:** implementing the five; restoring Phase M; treating
clip-from-source / avatar / Instagram as "next" (they fail the cost and
viability tests until volume and authenticity are earned).

**Numbers this ranking used (already measured, not assumed):** TTS is ~91% of a
rendered run ($0.25–0.31 metered, ~$1 allocated at 21/90 Creator-plan
utilisation); Apify remaining paid tier is two actors; YouTube upload ≈ 1,600
units of 10k/day; recommenders still sit at 10 measured vs a 15-sample gate.

---

## 2026-08-20 — Next 5 shipped + 35 more candidates (no Phase M)

**Prompt:** close the five sequenced build items from the afternoon plan, then
append 35 new roadmap candidates. Phase M, volume-gated backtest, and $0 TTS
voice judgment stay out.

**Built (uncommitted on `fix/live-run-69-70`)**

1. **Run-70 probes.** `llm_router.ollama_probe()` is the single `/api/tags`
   helper. `_ollama_ready` already delegated; `ops free-doctor` now says **pull**
   when the daemon is up and empty (not "server unreachable"), **serve** when
   down, and names OpenRouter as throttled fallback. RUF012 gone
   (`tests/test_run69_fixes.py`).
2. **`process_one` + `_defer_for_quota` tests** — quota-exhausted claims only
   render jobs; a deferral does not consume a retry
   (`tests/test_job_worker_process.py`). No product change.
3. **`build_render_ffmpeg_command` assertions** — amix under VO, VO-only
   identity, `-t`, escaped subtitles, music-bed failure retries VO-only.
   `youtube/oauth.py` and the `coverage` extra stay for a follow-up.
4. **Semantic variation.** Stdlib content-word cosine folded into
   `_variation_check` (`AUTHENTICITY_SEMANTIC`, default-on). Paraphrase of a
   TapIn-shaped script fails; unrelated topic passes; exact duplicate still
   fails lexical first. Warn-never-block. No persisted embeddings.
5. **Router vision.** `complete` accepts OpenAI-style image parts; Anthropic /
   DeepSeek / Ollama / Groq / Doubao are skipped, not flattened. Thumbnail
   scorer uses the extract tier; Free mode heuristic + warning.
   `core/llm_client.py` deleted.

**Docs:** ticked the five on [roadmap.md](roadmap.md). Candidates **21–55**
appended (aesthetics, operator surface, efficiency, long-term). Architecture
table and decisions §14 no longer claim a `llm_client` holdout.

**Still parked:** Phase M; `youtube/oauth.py` tests; `coverage` extra; Pillar 2
multimodal review; overnight still cannot take facts; CUDA torch (`2.8.0+cpu`
on a 4070 Ti).

---

## 2026-08-20 — Post-merge orientation, 20 ideas (no Phase M), grand audit

**Prompt:** refamiliarize after committed + uncommitted work; brainstorm 20 more
roadmap ideas that are not multi-platform; then a grand audit.

**Where we actually are**

- **Branch:** `fix/live-run-69-70` at `6a6ec96` (same commit as `main` /
  `origin/main`). PR #34 merged 2026-08-19. CI green on trunk.
- **Committed since the 2026-08-15 audit:** caption retext; fail-open visibility
  (S110/S112); alembic logging fix; intro-step never loses the render; coverage
  wave paused after that; orphan-doc harvest; stale PRs #26–#32 closed; handoff
  rewritten as merged.
- **Uncommitted (important):** `core/run_mode.py` + `tests/test_run69_fixes.py`.
  Live run 70 (Cejudo, Free) died after 71s of discovery because Free mode printed
  `llm=ollama OK (local $0)` when the daemon answered `/api/tags` with **zero
  models pulled**. `_ollama_ready` was a weaker copy of `llm_router.ollama_installed_models`.
  The patch delegates. **Do not commit as-is:** (1) `ops free-doctor` still prints
  "server unreachable" whenever `OLLAMA_MODEL` is set and not ready — the run-70
  case is "pull a model"; (2) the new test's `ENV = {...}` trips **RUF012**.

**Audit headline (see [audit.md](audit_2026-08.md) 2026-08-20 + canvas):** health held
(1,433 tests committed / 1,440 with wip, 62.7k LOC, mypy 123/73 unchanged,
silent `pass` still 0). New debt is the run-70 class again (lying readiness),
thumbnail vision still silently dead on `llm_client`, overnight still cannot take
facts, and the roadmap contradicts itself in three shipped items.

**20 ideas added as not-committed candidates** on [roadmap.md](roadmap.md).
Phase M excluded. None restates Next-up (no clip-from-source, avatar, MoneyWise
depth, router vision, Instagram). Highest-leverage three if picking:

1. Finish the run-70 branch (free-doctor diagnosis + ClassVar) then commit.
2. Semantic near-duplicate authenticity — lexical `SequenceMatcher` is the live
   hole in the 2026 compliance moat.
3. Pronunciation lexicon + `CAPTION_ALIGN` default-on — what actually makes the
   $0 TTS flip survivable, now that caption *text* is fixed.

**Rejected this session:** implementing the 20; merging
`origin/claude/docs-optimization-review-a4l104` (old base, same shape as #27).

---

## 2026-08-14/15 — Six roadmap waves: the silent-failure session

**Prompt:** a sequence of *"next roadmap task"* passes, punctuated by two pasted live-run
logs (runs 64/65, then run 66). Each pass began as a normal roadmap item and turned into
the same discovery, which became the session's organising idea:

> **Things were failing quietly, and the system reported "nothing found" instead of
> "I am broken."** Nothing was crashing. Every run looked fine.

**What that pattern actually cost, once measured:**

| Source | Reported as | Truth |
|---|---|---|
| Tapology scrape | "no event match" | Cloudflare 403 for **33 days**, 10/10 empty cache |
| `twitter` signal | `inactive` | **19/19 runs, zero facts**, slowest phase (~32s), billing Apify each time |
| 11 of ~37 RSS feeds | quiet news day | 404 / 403 / 501 / dead host |
| Federal Reserve feed | 0 items | alive with 20 items — killed by a **UTF-8 BOM** parse error |
| API-SPORTS rate limit | `results: 0` | HTTP 200 **with** `errors.rateLimit` |
| `features_json.cost.tts` | `0.0` | TTS is **91% of run cost** — margin overstated ~19× |
| `"If Netflix"` | possible hallucination | sentence-initial "If"; cost the run a grade (A→B) |
| OpenRouter cheap slug | test green | retired model, **404 every day** for weeks |

**Decisions made (recorded in [decisions.md](decisions.md) §18–§22):** a dead source must
report failure, not "no match"; retire a paid signal that produces nothing rather than
repair it; derive values that can drift instead of storing them beside their source;
never pin a rotating vendor id in a test; price from the operator's real plan.

**Waves shipped:** research-intake repair + `ops feeds` monitoring · `twitter` retired ·
`youtube_comments` via the official API + O12 complete · post-render cost persisted
(+ 38 historical runs repaired) · whisper CPU caption backend · run-66 fixes.

**Deliberately stopped mid-item:** the whisper work landed its backend and measurements
but **not** the caption-text fix — whisper transcribes blind, so captions carry ASR text
("Salkilld" → "Salkal"), and fighter names are the channel's whole subject. Stopping with
the blocker written down beat shipping something that looks finished.

**Rejected / not built:** restoring Reddit (operator declined); retuning preset *word*
counts to hit their advertised durations (would change output length and break
length-label continuity in the analytics); paying down the 420 broad `except Exception`
handlers (sized in the audit, not fixed).

**Open, highest-value next:** the caption-text fix, which unblocks the **$0 TTS switch** —
the single biggest cost lever left at **$0.25/video**.

**Surprise worth acting on:** the box has an **RTX 4070 Ti (12 GB)**, but `torch` is
installed as `2.8.0+cpu`, so `torch.cuda.is_available()` is False. Every roadmap item
marked *"parked — needs a GPU box"* (WhisperX, MusicGen, ComfyUI/Wan-LTX, YOLO reframe,
avatar, Real-ESRGAN/RIFE, XTTS/Kokoro voice cloning) is blocked by a **CPU-only install,
not by hardware**. See [audit.md](audit_2026-08.md).

## 2026-07-24 — Pillar 7: Self-improving skills (Agent Skills + SkillOpt)

**Prompt:** *"continue pillar 7 and from there advance as scheduled."* Built autonomously
(safe-by-design) rather than pausing for a fresh approval gate.

**How it maps to what already existed:** the `scripts/ops.py` `@_register` registry is a
skill catalog; `core/prompt_evals.py` is a frozen validation gate; `core/overnight.py` is the
nightly runner; the Pillar 4 vault `playbook_block` is the "ship" surface. Pillar 7 just names
and closes those loops.

**Shipped:**
- **C1 — Ops-as-skills** — `core/ops_skills.py` renders `skills/content-ops/SKILL.md` (Agent
  Skills frontmatter + a command table) from the live registry; `ops gen-skills` regenerates
  it so it never drifts from the CLI.
- **C2 — SkillOpt-Sleep** — `core/skillopt.py` scores the live prompts vs curated candidate
  STYLE DIRECTIVEs on the frozen `prompt_evals` rubric across the golden topics (new
  `extra_directive` seam in `content_engine`), keeps only a gate-beater
  (`SKILLOPT_MIN_MARGIN`), and writes a reviewable **proposal** record to the vault +
  `skillopt_proposal` event. Runs in `overnight` when `SKILLOPT_ENABLED=true`.

**Key safety decision:** C2 **never auto-edits live prompts**. It proposes a gate-validated
directive; the operator promotes it to a `[strategy]` playbook bullet. This delivers the full
SkillOpt "validated optimization" value with zero autonomous prompt-mutation risk. Follow-ups
(deferred): LLM-proposed directives; optional auto-apply behind a flag.

---

## 2026-07-22 — Best Bet breadth

**Prompt:** *"best bet needs more options"* — the startup best-bet picker returned too few,
too-similar topics, especially on a single-domain channel (tapin = gaming).

**Findings:** `core/best_bet.py get_best_bets()` drew fresh candidates only from RSS, capped
one pick per domain in Phase 1, applied a per-**anchor** franchise cap in Phase 2, and had
`n=3` hardcoded at `main.py:282` (prompt `[1-3]`). Hard constraint: best-bet runs at
**startup before discovery**, so any new candidate source must be **$0/keyless** and never
trigger paid Apify.

**Decision (operator, asked & answered):** build Best Bet breadth next, then Pillar 7, then
roadmap items — continuing until usage runs out; and **document every planning session in
the repo** (this file).

**Shipped:**
- **Configurable count** — `best_bet_option_count()` (`BEST_BET_OPTIONS`, default 5, clamp
  1–8); `main.py` uses it + a dynamic `[1-N]` prompt.
- **Angle multiplexing** (the core fix) — `_angle_options()` fills leftover slots with
  *distinct angles* on the dominant franchise (tier list / what's broken / meta evolution)
  reusing `_KEYWORD_ANGLE_MAP` + `_FALLBACK_ANGLES`. $0; no filler for no-anchor channels.
- **Opt-in keyless breadth** — `BEST_BET_SIGNALS` (csv, default `rss`) can add keyless
  `reddit` (hot) + `youtube` (view-velocity) candidates via `apis/free_backends`, through
  the same commerce/dedup filter, fail-open, never paid Apify. Off by default (latency).

**Not done (deliberate):** rebalancing configured slot lists; a ranked slot menu.

---

## 2026-07-22 — Scheduling mechanics

**Prompt:** *"the best times are always on a weekend which makes it useless"* + *"make the
individual just take a time input instead of minutes from now."*

**Findings:** Upload Option 3 (`core/ui.py`) took "minutes from now". The learned post-slot
picker (`analytics/post_timing.learn_slots_from_analytics`) ranked by **summed** engagement,
so the highest-volume day (already weekend-leaning) kept winning — a weekend feedback loop.

**Decision (operator):** fix the learner bias **only** — leave the configured default slots
and Option 4 untouched; the manual time input is the weekday lever.

**Shipped:** `parse_local_time_input()` (clock time / tomorrow / ISO datetime → UTC, in the
channel tz); learner now ranks by **average** engaged-rate per bucket with a min-sample
floor; `free-doctor` distinguishes "Ollama running, set OLLAMA_MODEL" from "no free LLM".
*Caveat surfaced:* learner only overrides once ≥8 timed samples exist.

---

## 2026-07 — Next-level roadmap assessment (local $0 stack → Best Bet → run-without-PC → Pillar 7)

**Prompt:** a planning-only strategy pass triggered by (1) HuggingFace model buckets
published to the operator's account, (2) real PC specs (Ryzen 7 7800X3D, 32 GB, RTX 4070 Ti
12 GB), (3) *"best bet needs more options"* + *"run without the PC?"*, and (4) a reference to
Microsoft/GitHub **"skill ops"** (Agent Skills + SkillOpt).

**Bucket verdicts:** ★ **Qwen3-TTS-12Hz-1.7B-CustomVoice** (local $0 voice cloning — WIN);
★ **Bonsai-27B-gguf** (local LLM via Ollama, ends the retired-free-model crash class; vision
unlocks rendered-video review — WIN, use the ternary variant for 12 GB); ◐ mT5 XLSum
(multilingual summariser — maybe, for multi-language); ◐ tabfm (tabular FM — maybe, data-
gated); ✗ MusaCoder-27B / LLaMA-Mesh / Bernini-R (not content-pipeline or won't fit 12 GB).

**Sequenced plan (operator-locked):** (1) **Local $0 stack** — A1 Qwen3-TTS provider
[shipped], A2 Bonsai/Ollama enablement [operator pulls the model]; (2) **Best Bet breadth**
[shipped, see above]; (3) *run-without-PC* (FastAPI panel + Tailscale + two-layer split) —
**parked**, honest reality: the GPU/render/TTS half is PC-bound, cloud/phone Claude Code is a
*dev* surface, not a *run-the-factory* surface; (4) **Pillar 7 — Self-improving skills**:
expose `scripts/ops.py @_register` as `SKILL.md` Agent Skills (C1) + a **SkillOpt-Sleep**
nightly loop in `core/overnight.py` that ships prompt/skill edits only when they beat the
frozen `core/prompt_evals.py` gate (C2) — compounds with the local frozen Bonsai into a
self-improving $0 factory.

**Excluded throughout:** multi-platform distribution (Phase M) stays parked.

---

## 2026-08-25 — Roadmap #23–27 render + thumbnail wave

**Sequence:** implemented #23, #24, #25, #26, then #27 on top of the current
uncommitted ten-task wave. No Cursor plan file, commit, push, live network call, or
real `data/` store was intentionally touched.

**Decisions and boundaries:**
- End cards are generated from validated channel config rather than requiring a
  hand-authored asset. The in-place concat uses the intro's restoration discipline:
  the body has to be restored after subprocess launch errors, non-zero exits, and
  empty outputs. Draft previews never get intro/outro.
- Lower thirds reuse `fact_grounding.specific_entities`, then require the complete
  label phrase in one supplied fact line; only capped display labels persist. Raw fact
  lines do not. Overlay ASS is emitted only when a
  label can be located in a real word-timing sidecar; proportional timing is not
  presented as measured timing.
- Color "LUT" scope is the smallest production-complete parametric equivalent:
  validated FFmpeg `eq` saturation/contrast/brightness. This avoids claiming a LUT
  file exists and propagates through every command-building path.
- Hook motion uses `zoompan` only through the first measured cue and returns exactly
  to 1.0 afterward. A missing timing sidecar leaves argv unchanged.
- `thumbnail_format` is a dual-generation experiment, unlike the existing
  single-image `thumbnail_style`. Dual mode runs only for that active experiment or
  explicit `THUMBNAIL_DUAL=true`. Text-on prefers a configured text-capable provider;
  face-forward prefers Flux; each arm has an independent, visibly distinct Pillow
  fallback. Failed paid-attempt billing is persisted as `unknown`, not silently
  priced at zero.
- Generation does not assign an experiment arm. The validated operator pick writes
  `thumbnail_pick`, creates the selected thumbnail asset, then records assignment.
  Dual-unpicked runs cannot enqueue. Resolution is run-linked only; newest-mtime
  fallback was removed.

**Initial proof:** 15 new behavioral tests were run before production edits and failed
(13 errors + 2 failures); the real FFmpeg failure added one focused font-binding
regression. The later safety audit brought focused integration to 112 tests and the
full isolated suite to 2,010 tests (up from 1,985). `ruff check .` and
`ruff format --check .` are clean. `py -m config.validate_channels` returned OK for
all three profiles with the same three pre-existing operational warnings. Operator
registry lists `pick-thumbnail`; its missing-run path returned `No content run
#999999` without mutation.

**Real temp proof:** the first FFmpeg end-card encode failed because the installed
Windows FFmpeg has no Fontconfig default. The failure restored the original body as
designed. Binding `drawtext` to installed Arial (DejaVu fallback on Linux) made the
same proof pass: a 0.6s synthetic body became a 2.133s body+card and the callback
captured the outro argv. The later audit split that callback into explicit
`outro_attempt` and `outro_success` events.

**Remaining visual proof:** no paid thumbnail call was made in this offline/no-network
wave. Run one full publish render with a temp/output override and inspect the first
cue, lower thirds, grade, and final card, then activate `thumbnail_format` for a
disposable run and pick in `ops booth --serve`.

## 2026-08-25 — Roadmap #23–27 behavior/safety audit

The audit added nine behavioral regressions; eight were observed failing before their
fixes. Confirmed defects and fixes:

- FFmpeg callbacks had only an unqualified command emitted before execution, so a
  failed intro/outro looked successful in the trace. Callbacks now emit
  `*_attempt`/`*_success`; traces retain every attempt and expose a successful command
  only after a usable output exists.
- Public lower thirds inherited the internal token-anywhere grounding rule, allowing
  two unrelated fact fragments to "ground" one display name. Public labels now require
  the exact ordered phrase in one supplied fact line.
- An explicit identity grade inserted an `eq` filter despite being the documented
  default. Identity values now produce byte-equivalent argv to an absent grade.
- Hook motion stopped at an empty/malformed sidecar row instead of finding the first
  real cue. It now skips invalid rows and uses the first finite, positive timed cue.
- Booth POST trusted a submitted run id, and the served booth used `file://` URLs that
  Chrome blocks on an HTTP page. POST bodies are bounded/strict, tied to the displayed
  run and known arms, and candidate images use fixed booth-local HTTP routes.
- Dual fallback evidence named pre/post providers but omitted their cost values.
  Candidate evidence now reports both pre- and post-fallback rates while preserving
  failed paid-attempt billing as `unknown`.
- The standalone and interactive requeue paths did not explicitly carry the picked
  thumbnail. Both now block unpicked dual runs and enqueue the validated selected path.

Proof: roadmap regressions 25/25; focused render/thumbnail/pipeline suite 112/112; full
isolated suite 2,010/2,010. Shipped config: 3 profiles valid with the same three
operational warnings. Safe operator checks: command registry listed `pick-thumbnail`;
missing `--run-id` returned 2 without mutation. No `data/` changes.
