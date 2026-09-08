# Handoff synopsis — 2026-09-07: Stage 3 review room + defects

Use in a fresh session to continue `content_machine` without re-reading the full thread.

## Last implementation wave — Stage 3 review room + defects (2026-09-07)

Cursor wave. HEAD before this wave: `dbbd582` (Claude review 3 at `d1a1895` plus
one). `GRADE_VERSION` stayed **v3**. CLI and `ops booth` stay.
`SCENE_MATCHED_BROLL` stays off. #333 stays a veto.

- **Honesty:** #681 duplicate features gone · #682 §4 is 12000 · #674 traces
  redacted (home patched to `/home/ciuser`) · #680 CTA strip gated + printed ·
  #679 HTML/rhythm/JSON-only phrase each have a production caller.
- **Engine:** #607 ElevenLabs import deferred · #335 single-outlet news demoted
  on the tapin `_build_prompts` path.
- **UI:** #671 angle `QListWidget` · #168+#209 `ops review-room` /
  `py -m desktop --review`. Approve = booth command. J/K/L in `core/review_keys.py`.
- **#416 mechanical slice:** owned `clip_index` beats; empty index = single loop.
  HUD gap filed as **#683**. Live decode filed as **#684**.
- **Launch:** `pip install -e ".[app]"` then `py -m desktop --review`. Missing
  extra: refuse, exit 2, no WARNING.
- **Proof:** fail-first missing `set_choices` / `review_keys` / `owned_beats` /
  `desktop.review`. Guard deleting `set_choices` left the list empty. Suite
  **2,725 -> 2,751**. mypy **144** held. Backlog **398** open / **522** done,
  highest **#684**. Filed #683 #684. `data/` empty.

**Still parked:** remaining Stage 3 panels; #672 grain; #673 second monitor;
Phase M; Ollama FAIL. Next five: #148 queue · #683 HUD · #672 · #341 · #608.

## Previous wave — Stage 2 look + 20 (2026-09-07)

Cursor wave. HEAD before this wave: `7e4284c` (Stage 1). `GRADE_VERSION` stayed
**v3**. PySide6 is still the `[app]` extra; CI does not install it.

- **Look:** `core/chrome.py` QSS + HTML CSS from `config/design_tokens.json`.
  TapIn vs MoneyWise chrome. Dark from `end_card_bg`. Icon SVG. Empty/error copy.
  DPR 1.0 offscreen.
- **Window:** stylesheet, facts meter, drag-drop, per-channel geometry.
- **20 items:** #295 #296 #625 #333 #602 #527 #258 #525 #523 #515 #247 #541
  #550 #635 #612 #540 #542 #318 #512 #455.
- **Launch:** `py -m desktop`. Missing extra: refuse, exit 2, no WARNING.
- **Proof:** fail-first `ModuleNotFoundError: core.chrome`. Suite
  **2,685 -> 2,718**. mypy **144** held. Backlog **404** open / **506** done,
  highest **#674**. Filed #672 #673 #674.

**Still parked:** Stage 3 panels; #416; #670 no CI Qt; #671 visual list;
Phase M; Ollama FAIL. Next five: Stage 3 review room · #671 · #607 · #335 · #416.

## Previous wave — Stage 1 run window (2026-09-07)

Cursor wave. HEAD before this wave: `3a338e8` (Stage 0). `GRADE_VERSION` stayed
**v3**. PySide6 is the `[app]` extra; CI does not install it.

- **Bridge:** `core/ask_bridge.py`. Five gates classify as confirm. Facts paste
  answers the fact loop then `""`. `cancel()` → `KeyboardInterrupt`.
- **Window:** `desktop/window.py` `RunWindow`. Worker:
  `main._run_new_video_flow`. Output from `emit()` + stdout tee. Angle mode
  from `core.angle_intent`. Gates: Override/Stop. Proceed: Approve / + / Reject.
- **Launch:** `py -m desktop` · `py main.py --gui` · `ops run-window`. Missing
  extra: honest refuse, exit 2, no WARNING.
- **Proof:** fail-first `ModuleNotFoundError: core.ask_bridge`. Suite
  **2,673 -> 2,685**. Widget test offscreen when PySide6 is present.
  mypy **144** held. Backlog **424** open / **483** done, highest **#671**.
- Filed **#670** (no CI Qt) and **#671** (1-5 line, not a visual variant list).

**Still parked:** Stage 2 look; #296 (blocked on #295); #333/#416; Phase M;
Ollama FAIL. Next five: Stage 2 · #295 · #625 · #333 · #602.

## Previous wave — Stage 0 plus leftover craft (2026-09-07)

Cursor wave on HEAD `f6869ea`. Stage 0 seams (`ask` / `emit` / tokens **#170**)
plus leftover craft. `GRADE_VERSION` stayed **v3**. No PySide6, no Stage 1
window. Sitting 2026-09-06 wave was already committed as `f6869ea`.

- **ask/emit:** 15 `main.py` `input()` sites plus `ui.py` expand prompt.
  Metrics gate at `main.py:346` is the fifth blocker; cadence is print-only.
- **#170:** shipped caption fills agree between tokens and Pillow/ASS.
- **#481:** formatter uses real `format_uploads_left`; CSI is TTY-only.
- **#338:** deterministic quote gate; pre-rewrite flag kept if rewritten.
- **#190/#191:** on-screen ASS, not `description_extras`.
- **Proof:** `ops end-card-preview` / `ops intro-waveform` usage lines;
  scripted metrics `ask_confirm("")` is `False`.
  Suite **2,639 -> 2,673**; mypy **145 -> 144**; `data/` empty.

**Still parked:** Stage 1; #296 (blocked on #295); #333/#416; #512/#527;
Phase M; Ollama FAIL. Next five: Stage 1 · #295 · #607 · #625 · #602.

## Previous wave — craft 15 (2026-09-06)

Cursor wave on HEAD `ddce1bd`, committed as `f6869ea` after Claude's review.
Cheapest-first S-cluster then the then-roadmap five (#485 #185 #505 #350 #648)
plus #297/#649/#182. Stage 0 / #333 / #416 stayed out. `GRADE_VERSION` **v3**
(unchanged; contrast is advisory).

- **#666** preflight: missing ffmpeg → one whole-script synth, not N+1.
- **#485** `discovery::{channel}` cache; empty results not stored.
- **#350** 20 frozen grounding cases; `ops grounding-corpus` (not `run_eval_corpus`).
- **#649** whole-facts prompt lock; run-74 script strings absent (known gap).
- **#491** already shipped (`spinner_frames`); ticked only.
- **Proof:** `ops grounding-corpus` → 20/0; `ops caption-still` usage line.
  Suite **2,609 -> 2,637**; mypy **148 -> 145**; `data/` empty.

**Still parked (as of that wave):** Stage 0; Phase M; #333/#416; Ollama FAIL.

## Previous wave — next 15 (2026-09-06)

Cursor wave, **not committed** until the operator asks. Plan: honesty (#655
#663 #662) then finish #533 (#661 #659 #660 #656) then option 5 + traces
(#664 #665) then TTS (#658 #402) then facts (#646 #647 held) then #484 and
#641-#644. Stage 0 / #333 / #416 stayed out.

- **`GRADE_VERSION` v3** (#660 + #656). **`FEATURE_VERSION` v2** (#661).
- **#402 shipped** on the #658 seam; fractional TTS billing.
- **#647 held** the fact-selection weights on two fixtures.
- **Proof (pre-slot):** ruff clean. Full suite re-run after the mailbox edit.
  Do not commit `cached-strolling-popcorn.md`.

**Still parked:** Stage 0; Phase M; #333/#416; Ollama FAIL.

## Previous wave — next five + idea quality (2026-09-05)


Two waves landed as one commit at the operator's call: the 2026-08-30
idea-quality wave (#651 angle ranker, #652 playbook ranking, #653 gate
agreement, #351 intervals) had been uncommitted for six days, and the
2026-09-05 next-five wave sits on top of it.

- **Shipped 2026-09-05:** #654 (best-bet names the shrunk figure it ranked on),
  #645 (report card weights length; `GRADE_VERSION` is real and now **v2**,
  `QUALITY_VERSION` **v3**), #383 (`core/signal_canary.py` + `ops signal-canary`),
  #533's **detector + angle tables only**, and #657 (a cache hit billed chars it
  never synthesized).
- **#402 not shipped, deliberately.** `generate_audio` is ~147 lines over four
  provider branches; it needs the seam filed as **#658** first. Left open rather
  than half-shipping a cache.
- **Four grade components have now moved across the two waves.** Historical
  report-card letters are not comparable to new ones. `VideoGrade.version`
  records which rubric produced which — but `grade_calibration` still re-grades
  all history with today's code, which is **#662** and is roadmap pick 1.
- **New ritual skill:** `.claude/skills/next-five/SKILL.md` (+ `.cursor` mirror),
  the four-step session written down.
- **Proof:** suite 2,546 -> **2,573** green; ruff + format clean; mypy **148**
  (unchanged); `git status --short data/` empty; `ops all-checks` clean.
  Backlog 463 -> **465** open, highest **#663**.

**Still parked:** Phase M; #141-#146; #333/#349 (narrowed, #333 needs the
operator and its trigger #341 does not exist); #451 LAN booth; #416 scene-beat
(blocked on data - `ops ingest-clips --apply` has never run); Ollama FAIL.

## Previous wave — Piper 1/8 mix, drop Brave/BFL (2026-08-28 night)

Pickup from planning_log **2026-08-28 (Piper mix / secrets)** on the current branch.
Tests were written first and failed on unmodified code. **Do not commit unless asked.**
Do not unpark ElevenLabs ids. Do not `ollama pull` unless you do it yourself.

- **ElevenLabs add path:** elevenlabs.io (same account as `ELEVEN_API_KEY`) →
  Voices → Explore → Add to my voices → `ops voices` shows `* <id>` → move out of
  `_parked_voice_not_found`. Ids are 20 chars; a 19-char id never matches. TapIn
  is pinned to Brian (`config/channels.json`).
- **Ollama FAIL:** the app is the daemon; doctor wants `OLLAMA_MODEL` in
  `/api/tags`. `ollama pull llama3.1:8b` if you want that FAIL gone. Standard
  already uses DeepSeek/OpenRouter.
- **secrets-doctor:** dropped `BRAVE_SEARCH_API_KEY` and `BFL_API_KEY` from the
  optional list. Keys still work in web search / Flux; doctor stops listing them.
  Remaining optionals: OpenAI, Anthropic, News.
- **Piper mix:** `TTS_PIPER_MIX_EVERY=8` on Standard ElevenLabs renders when
  Piper is ready. Fail-open to ElevenLabs. Does not flip `TTS_PROVIDER`. Mix
  meters TTS $0 via `last_tts_was_piper_mix()`. Suite isolation: `TTS_PIPER_MIX_EVERY=0`.

**Still parked:** Phase M; #141–#146; #333/#349 (narrowed); #451 LAN booth;
#416 scene-beat; $0 TTS *voice judgment* (ears); Ollama FAIL; Seven ElevenLabs ids.

**Proof:** ruff clean; **2365** tests green (was 2357). `ops secrets-doctor`
lists OpenAI/Anthropic/News as optionals — no Brave/BFL lines. `git status
--short data/` empty.

## Previous wave — doctor greens (2026-08-28 night)

Pickup from planning_log **2026-08-28 (doctor greens)** on the current branch.
Tests were written first and failed on unmodified code. **Do not commit unless asked.**
Do not git-add `video/voices/*.onnx` (gitignored weights).

- **Secrets:** `ops doctor` FAILs only on required env names (DeepSeek, OpenRouter,
  Eleven, Apify, YouTube). Optional blanks (OpenAI, Anthropic, Brave, BFL, News)
  are a detail line. `ops secrets-doctor` still never prints values.
- **Sherdog:** RSS 403 — removed from `config/data_sources.json` and
  `config/seo/tapin.json`. Not an API key.
- **Piper:** four `.onnx`+`.json` in `video/voices/` (bobby/carl/eminem/patrick),
  catalog equal-weight. Doctor ready on `.onnx` only; a README path is not ready.
  `resolve_local_voice` rotates. Fallback `PIPER_VOICE=video/voices/en_US-bobby-medium.onnx`.
  Default `TTS_PROVIDER` stays ElevenLabs.
- **ElevenLabs ids:** seven operator ids parked in `_parked_voice_not_found` —
  `ops voices` did not list any of them. Add from the Voice Library, re-run
  `ops voices`, then move into a live category. 19-char id was truncated.
- **Fact intake:** paste ends on `.` / `END` / two blank lines. Long paragraphs
  already kept (~600 chars, cap 800). URLs still fetch.

**Ollama doctor FAIL stays.** Optional `ollama pull` is on the roadmap as an open
checkbox. Ollama is local/free, not a billed API. Do not un-tick the shipped router.

**CUDA (previous session, this machine):** `2.8.0+cu128`, `torch.cuda.is_available() True`,
RTX 4070 Ti. Do not `pip install` more torch this wave.

**Still parked:** Phase M; #141–#146; #333/#349 (narrowed); #451 LAN booth;
#416 scene-beat; $0 TTS *voice judgment* (ears).

Pickup: add the parked ElevenLabs voices to the account library if wanted;
`ollama pull` if you want that FAIL gone; live Piper ears vs ElevenLabs.

**Proof:** ruff clean; **2357** tests green. `ops secrets-doctor` / `ops doctor` /
`ops voices` pasted in the implementing session. `git status --short data/` empty.

## Previous wave — parked four (2026-08-28 evening)

Pickup from planning_log **2026-08-28 (evening)** on the current branch. Tests
were written first and failed on unmodified code. **Do not commit unless asked.**

- **Edge TTS** (`TTS_PROVIDER=edge`): `_ALT_TTS` + unmodified `edge-tts` in
  `[free]`. `(cloud, $0)` not `(local, $0)`. SSML lexicon. WordBoundary sidecar.
  Never default; Piper is the Free floor. decisions §28.
- **`ops ingest-clips`**: dry-run default; `--apply` muted H.264 remux into
  `video/backgrounds`. Unmatched listed, not dumped into `gaming/`. HUD=`null`.
- **#389**: live failure serves cache ≤48h flagged STALE, not a hit; >48h
  refuses; honest `inactive` does not resurrect; do not clobber.
- **#433**: same franchise/topic **and** same `infer_domain` lens. GTA review
  blocks across channels; Take-Two stock allows. Pipeline / publish / `ops next`.

**CUDA (as of that evening):** still `2.8.0+cpu`. **Later the same night:** operator
installed `2.8.0+cu128` (`cuda.is_available() True`). NVENC already shipped via ffmpeg (#38).

**Still parked:** Phase M; #141–#146; #333/#349 (narrowed); #451 LAN booth;
#416 scene-beat; the CUDA wheel; Piper *voice judgment* ($0 TTS switch).

Pickup: CUDA wheel if wanted; #333 backstop; #451 LAN bind; live Edge ears
vs Piper; `--apply` ingest-clips if the dry-run listing looks right.

**Proof (this session):** ruff clean; **2339/2339** green (was 2315). `ops
ingest-clips` dry-run listed 16 Xbox captures (15 matched, GTA Online unmatched).
`ops free-doctor` still wants Piper for Voice. Torch remains `2.8.0+cpu`.

## Previous wave — 23 items (2026-08-28)

Picked up mid-flight on `consolidate/2026-08-27`: modules and production wiring
existed, the suite did not pass (6 failures/errors in 2,296; `ruff` red; nothing
ticked; #373 not started). Now **2,315/2,315 green**, ruff clean, `data/` clean.
**Do not commit from this step unless asked.**

Shipped: **#38** NVENC encode (one `video/encoder.py` helper for render /
composite / intro / outro; `NVENC=off` byte-identical; failed encode retries
libx264). **#147** localhost GET-only FastAPI shell (`ops shell`, 127.0.0.1,
default off, `POST /` 405) — no longer "skipped", and not #141. **CUDA** doctor
is fail-visible (`ok=False` only when nvidia-smi is present AND torch has no
CUDA; no wheel installed). Plus 20 from 331–480: #340 #348 #353 #355 #360 #366
#370 #373 #379 #382 #395 #403 #406 #419 #426 #432 #439 #443 #444 #458.

**Four things the green tests did not catch** (detail: planning_log 2026-08-28):

- **#419 was inert on the shipped caption path.** The rebalance only touched the
  estimated-timing fallback; ASR-timed cues come from `group_into_lines`
  (decisions §23), which had none. Fixed on both paths.
- **#419's first cut merged two sentences into one cue**, violating
  `test_sentence_boundaries_not_crossed`. Rebalance is now per sentence and the
  pre-existing `test_proportional_timing` passes **unmodified**.
- **NVENC broke #309's argv promise** — a fallback persisted the failed
  `h264_nvenc` command as the "success" argv. `executed_cmd` reports what ran.
- **#369 (previous wave) could never fire** — it estimated from `script=""`, so
  TTS priced at $0 and a realistic $0.50 cap was unreachable. Now estimates the
  longest length preset; $0.50 refuses a ~$2.28 worst case, unset still off.

**A review pass on the diff found six issues; four are fixed.** The one that
would have bitten a GTA 6 batch: #394's empty-200 quarantine used a denylist, and
`rawg`/`odds`/`sports` all return `connected+INACTIVE` with no detail when a topic
is off their domain — three off-domain topics in one batch session-disabled RAWG,
so a later GTA topic silently got no game data. Now an allowlist (`tapology`).
Also fixed: #432's dry run omitted `selfDeclaredMadeForKids` and `publishAt`;
#382's growth line printed inside the file list. **Left open on purpose:** #355's
residual is recomputed on every sync (needs a publish-time prediction, a schema
change) and #340's sidecar has a null `ungrounded_count` (written before
`build_quality`).

**NVENC is verified by a real encode, not the probe:** full render argv against
real inputs → 1080x1920 h264 + aac, exact 3.000s, ~1.5x faster than libx264.
`cq 23` yields a larger file than `crf 23` (different scales, not a regression).
Default stays on; `NVENC=off` restores the historical CPU argv exactly.

**Skipped at the time — needs the operator:** #333 negative-fact store, #349 OCR
intake, #412 pronunciation append, #450 voice-note intake, #451 phone booth, #389
stale-cache serve, #433 cross-channel dup guard, #416/#417 owned footage, and
the **CUDA torch wheel** (multi-GB). #141–#146 and Phase M untouched.
(Parked-four wave later the same evening shipped Edge/#412, ingest-clips/#417,
#389, and #433. CUDA, #333/#349, #451, #416 remain.)

Pickup at the time: CUDA wheel, then `ops doctor`; #333 if sized. #433 shipped
in the parked-four wave.

## Previous wave — next 10 from 331–480 (2026-08-27)

Ten green-and-inert holes plus thin `#442 ops next`, on `consolidate/2026-08-27`.
Tests were written first and failed on unmodified code. **Do not commit from this
step unless asked.**

- **#332** `features["disputed"]` + losing claims; report card / `ops grade`.
- **#347** `ops vault-decay` → `expired_notes` (no second scanner).
- **#331** packed vault facts older than 7 days get `as of …`; operator paste
  without `verified_at` is not dated; script is not regex-rewritten.
- **#346** leak-topic rumor soften after odds; Tapology results and `reports to EA`
  left alone. Known gap: outlet must appear in the script.
- **#372** `ops reliability` prints Apify cache `$` saved only when hits > 0.
- **#371** TTS forecast before synth; actual + delta on run features.
- **#381** `PAID_CALLS=off` is Free; doctor asserts `FREE_MODE_STRICT` is armed.
- **#369** `PROJECTED_COST_MAX_USD` unset=off; when set, blocks before discovery
  using `estimate_run_cost`, never post-run actuals.
- **#405** `script_pre_rewrite` / `script_post_rewrite` on rewritten runs only.
- **#394** three Tapology empty-200s session-disable; Wikipedia no-page does not;
  `quota_state.json` untouched.
- **#442** `ops next` ranks cost, vault decay, then `blocking_publish_sentence`.

**Still parked / skipped (as of that wave; #147, NVENC and CUDA shipped
2026-08-28):** Phase M; the CUDA torch wheel; #389
stale-cache; #433 cross-channel dup; #416/#417 owned footage; flipping TapIn to
`background_mode: local`.

Pickup: #333 negative-fact store; #389 stale-cache (behavior change, parked);
#433 if sized as [M]; Coverr (`COVERR_API_KEY` empty = chain continues).

## Last implementation wave — vault relevance P2–P4 (2026-08-27)

Item 329 is finished. `config/vault_relevance.json` `default_mode` is **scored**
after holdout precision/recall **1.0/1.0** (live runs 66+70) beat the P1
baseline of **0.667**. Scorer version `vault_relevance_v1`. Corpus = signal
headlines + operator/link facts, never the angle.

- Public `Sources:` accept `relevance_corpus`; headless uses
  `relevance_policy=public`; already-chosen URLs skip a vault reload.
- Two-stage discovery: non-web fetch, then `web_search` once or `STATUS_SKIPPED`.
- Operator pick indexes match printed `1. …`; `n` drops all uncertain;
  near-threshold rejects are inspect-only.
- P4 extract-tier tiebreak exists and is **off** (`VAULT_RELEVANCE_TIEBREAK`).
  Residual uncertain band was 4/14. `_GAME_ANCHORS` stay for topic-graph.
- Wolverine-only vault bullets no longer attach to a GTA topic in scored mode.

**Still parked / skipped:** P4 stays opt-in; FastAPI #147; Phase M; NVENC;
CUDA torch; flipping TapIn to `background_mode: local`.

## Last implementation wave — next 20 mixed (2026-08-26)

Implemented 1→20 from the next-20 mixed plan (topic graph → TapIn swatch).
Tests were written first. **Do not treat green tests as the audit** — Step 3
still needs ruff + full suite + green-and-inert checks (topic graph moves
`get_best_bets`; xfade in argv; `DATABASE_URL` isolated). No Step 4 commit in
this pass unless asked.

- **#47** franchise arcs: `data/topic_graph.json` sidecar; `get_best_bets`
  source=`arc`; graveyard still wins; recorded on publish.
- **§26** TapIn `hybrid_local_ratio: 0.70` + `xfade` at the local→stock join.
  `background_mode` remains `hybrid`. MoneyWise ratio 0.45.
- **#46** local seasonal calendar (no HTTP). **#123** TTS spoken numbers;
  captions keep digits. **#42** franchise-anchor discovery cache via existing
  `_fetch_one` keys inside `run_batch`.
- Smalls: suite blanks `DATABASE_URL`/`DATABASE_KEY`; real PDF fixture;
  wolverine-only vault notes no longer attach to GTA; Extended chapters;
  `ops demonetization` / `policy-runbook` / `sendto-facts`; n8n weekly-report
  cron; Dataview + wiki-links on dossiers; quota-increase playbook beside
  uploads-left; booth favicon + 1.25×; tray `git describe`; TapIn swatch.

**Still parked / skipped:** Edge TTS Wave B, Phase M, #141–#147 FastAPI/tray
daemon/XL apps, NVENC, CUDA torch, `SCENE_MATCHED_BROLL` on TapIn, Coverr as a
quality lever, flipping TapIn to `background_mode: local`, merge of
`origin/claude/docs-optimization-review-a4l104`.

Pickup: Coverr (`COVERR_API_KEY` empty = chain continues, no warning); overnight
`--facts-file`; `ops topic-clone` / `studio-deleted` / `publish-ics`; caption track
and opt-in pin comment on publish; Studio-deleted cancel in daily_sync; MoneyWise
cross-channel prior; learned intro duration plumbing; Expert Panel `shorts_pacing`
persisted when `EXPERT_PANEL_ENABLED`; frozen prompt-eval goldens; public-safe
SKU/dossier redaction; eval-corpus `invented_release_date` fixture; `/tdd` skill.

**Honest leftover:** Data API has no comment pin (channel `commentThreads.insert`
instead); intro duration does not pretend to learn below `RETENTION_MIN_VIDEOS`;
Pillow/requests pins updated in lockfiles — reinstall the venv before a real
render. **#147 FastAPI, #146 tray daemon, Phase M, NVENC, CUDA torch still skipped.**

## Last implementation wave — next 20 (2026-08-26)

Implemented in order 1→20 on top of uncommitted prior waves. **Do not commit from
this step.** Tests were written first and observed failing on unmodified code.
No Step 3 full audit and no Step 4 commit in this pass.

**Visual constraint (2026-08-26, decisions §26):** do not pull more unrelated
stock. Hybrid TapIn is ~55% live-action after a hard concat; that cut is
disorienting. Coverr is not a quality lever. Compare:
[moneyprinter_vs_content_os.md](moneyprinter_vs_content_os.md). Prefer owned
gameplay / `background_mode: local` / a higher local ratio; do not enable
`SCENE_MATCHED_BROLL` on TapIn.

Pickup: Coverr (`COVERR_API_KEY` empty = chain continues, no warning); overnight
`--facts-file`; `ops topic-clone` / `studio-deleted` / `publish-ics`; caption track
and opt-in pin comment on publish; Studio-deleted cancel in daily_sync; MoneyWise
cross-channel prior; learned intro duration plumbing; Expert Panel `shorts_pacing`
persisted when `EXPERT_PANEL_ENABLED`; frozen prompt-eval goldens; public-safe
SKU/dossier redaction; eval-corpus `invented_release_date` fixture; `/tdd` skill.

**Honest leftover:** Data API has no comment pin (channel `commentThreads.insert`
instead); intro duration does not pretend to learn below `RETENTION_MIN_VIDEOS`;
Pillow/requests pins updated in lockfiles — reinstall the venv before a real
render. Vault relevance default is scored (see top of this file) — wolverine-only
bullets no longer attach. **#147 FastAPI, #146 tray daemon, Phase M, NVENC, CUDA
torch still skipped.**

## Last implementation wave — roadmap #23–27 (2026-08-25)

Implemented in strict order without a commit or push, on top of the uncommitted
ten-task wave. The initial 15 behavioral tests were observed red first; the real
FFmpeg proof added one Fontconfig regression test. The full isolated suite is now
**2,010 tests** after the behavior/safety audit below.

- **#23:** generated validated per-channel end card, publish-only after the existing
  intro/body, robust in-place restoration, exact outro argv persisted and shown.
- **#24:** grounded public-safe lower-third labels persist without raw operator facts;
  real word timings generate escaped ASS. No timings means an honest skip and unchanged
  command shape.
- **#25:** bounded per-channel `eq` grade after crop/before overlays. TapIn and
  MoneyWise ship distinct values across publish, preview, fallback, and extra formats.
- **#26:** bounded first-cue zoom from the real word-timing sidecar only, propagated
  through every render variant. No timing means no motion filter.
- **#27:** dual `text_on` / `face_forward` thumbnails only under the
  `thumbnail_format` experiment or `THUMBNAIL_DUAL`; up to two configured paid
  providers may run, each independently falls back to a distinct Pillow layout, and
  provider/cost evidence persists. `ops pick-thumbnail` and booth POST controls make
  the pick; publish is blocked while unpicked; assignment occurs only at pick time;
  main/requeue/YouTube use the selected path and never guess by mtime.

Audit proof: focused render/thumbnail/pipeline integration **112 tests**; full suite **2,010**;
`ruff check .` and `ruff format --check .` clean; shipped channel config validates.
The audit fixed eight confirmed gaps: exact-phrase public grounding; identity-grade
no-op; first-valid-cue motion; attempted-vs-successful FFmpeg trace evidence; bounded
booth POST run binding; HTTP-served dual images; pre/post fallback cost evidence; and
picked-thumbnail propagation through both requeue paths.
A real temporary FFmpeg proof caught this Windows build's missing Fontconfig default;
the card now binds to installed Arial/DejaVu. The retry produced a **2.133s**
intro-free body+card from a 0.6s body and captured the outro argv (the audit now records
separate attempt/success events). Full visual
inspection of grade/motion/lower thirds remains the next operator proof.

## Last implementation wave — ten small production-complete units (2026-08-25)

The requested coherent `[S]` wave is implemented without a commit or push.
Behavioral tests were written and observed failing before production edits.
**#147 FastAPI still skipped.**

Shipped: documented MoneyWise persona; content-engine prompt-source hash;
booth title meter, description first line, duration comparison, and HTML5
caption track; Pillow bottom-20% thumbnail checker; channel caption skins;
isolated 480p draft preview preset; and report-only artifact retention. Detail:
[planning_log.md](planning_log.md) 2026-08-25.

**Boundary:** thumbnail safe-area checking is a conservative Pillow visual-density
heuristic, not OCR/face detection. Artifact retention is intentionally dry-run only.
`render-preview` refuses a stored script truncated at 2,000 characters unless the
operator supplies `--file`; preview audio/video are suffixed, never update upload media,
and the YouTube publisher rejects `_preview.mp4` files.
The separate dependency wave (Pillow 11.3, requests 2.32.4, remove MoviePy)
still requires a real dependency/render pass. Still skip #147 FastAPI, #146 tray
daemon, Phase M, volume-gated backtest, and auto-flipping the $0 TTS voice.

## Last live run — 71 (2026-08-21, documented 2026-08-22)

TapIn / Standard / best-bet 3 (GTA 6 leak + Wolverine “summer of hate”). **Draft
only** — operator did not type `y` at Proceed. Full narrative:
[debugging.md — Live-run 71](debugging.md#live-run-71-2026-08-21--pasted-article-hit-powershell-not-the-cli).

- `all-setup` OK; YouTube READY; discovery ~58s; est. **$0.028**; no MP4.
- Facts: MSN URL headline-only; one typed Take-Two sentence; vault mixed in
  Marvel Rivals / SEGA lines. Article body never entered the fact window.
- After *Stopped before render*, pasted IGN/ad/store text went to **PowerShell**
  (`Fast` / `Sponsored` / `user(s)` as commands). Re-enter via `py main.py`;
  use key-facts **`paste`** for the article if you continue this topic.

## Branch / PR

- **Branch:** `docs/brainstorm-141-320`; this implementation wave follows the
  MoneyWise/Pillow documentation commit `b26ce23`. The earlier stack
  **merged 2026-08-19 via
  [PR #34](https://github.com/jmcdigmarketing-cpu/content_machine/pull/34)** (24 commits,
  merge commit `6389e87`); CI is green on `main`. 20 Aug added the run-70 Ollama
  probe, worker/ffmpeg coverage tests, semantic authenticity, and router vision
  (`core/llm_client.py` gone).
- **Suite:** 2,010 tests · **Pre-commit:** `ruff check .` · `ruff format .` · `python -m unittest discover -s tests -t .`
- **Pickup order:** real visual render proof for #23–27 / dependency wave, then
  candidate 28 and 56–90 under Next up.
- History carries: morning (free backends, batch/A/B, webhooks, O11), Pillars 1–3,
  **Pillar 4** (Obsidian knowledge OS), **Pillar 5** (agent layer: `ops health` /
  `analyst` / `overnight`), **Pillar 6** (provider seams + local TTS + voice variety),
  **Pillar 7** (Agent Skills + SkillOpt).

### Unmerged work on these two branches (2026-08-14 session)

`feat/trade-validation-default-on` (6 commits):

1. **Trade validation default-on** for NBA/NFL topics (domain-gated; UFC excluded —
   `signed` false-positives). `infer_domain(key_facts=)` so pasted NBA facts on the
   gaming channel resolve correctly.
2. **Vault fact contamination fixed** — `core/ui.py` was re-saving *borrowed* vault
   facts into a note titled with the new topic, laundering them into "operator facts"
   for every later run. 131 borrowed bullets cleaned from 31 notes (0 distinct facts
   lost). Grounding false positives fixed (`_MONONYM_SKIP` discourse adverbs,
   30 generic tokens added to `_GENERIC_TOKENS`).
3. **Test-suite vault isolation** — `tests/__init__.py` forces `OBSIDIAN_VAULT_PATH=""`;
   the suite had been writing into the operator's real vault for weeks.
4. **O12 part 1** — per-provider LLM cost line + cross-run dead-model persistence.
5. **Alembic baseline + `0004` content_run FKs** — `publish_log`'s legacy `0` sentinel
   became `NULL` (836 of 870 rows preserved); `migrate_schema` finishes through Alembic.
   Reddit signal retired (`enabled: false`) + Apify actor-failure memory.

`feat/research-intake-repair` (5 commits, this session's later waves):

1. **Research intake repair + source health** — Tapology retired (Cloudflare 403),
   11 dead RSS feeds replaced (37/37 live), BOM parser fix, `ops feeds` monitoring.
2. **`twitter` signal retired** — 19/19 runs, zero facts, slowest phase (~32s).
3. **`youtube_comments` + O12 complete** — official-API signal; YouTube units under the
   governor + reliability time series.
4. **Post-render cost persisted** — the ledger was missing TTS on every render;
   `ops economics` went from $0.02 to $0.31/video, 38 historical runs repaired.
5. **Whisper local CPU backend** — landed with measurements; caption-text fix still open
   (see the section below, and "Open (roadmap next)").

**Triaged 2026-08-17 — see the block further down.** Both branches are now in PR #34.
All seven stale PRs (**#26–#32**, not the "#29–#32" earlier notes claimed) are **closed
and their branches deleted**, after harvesting five orphan docs that existed nowhere else.
`claude/trade-validation-default-on` is gone: it was superseded *and* still carried the
expired `"2026-07-25 18:00"` at `tests/test_ui_length_and_recovery.py:144` that #33 fixed,
so merging it would have turned CI permanently red.

---

## Shipped 2026-08-14 (research intake repair + source health)

**The finding:** TapIn's research intake had been silently dead for over a month and
nothing reported it. Verified live, not inferred:

- **Tapology is Cloudflare-403'd** ("Just a moment... Enable JavaScript"), direct *and*
  via the r.jina.ai reader proxy. All 10 cached results were empty across ~33 days.
  It reported the block as `STATUS_INACTIVE` "no event match", so no breaker or
  dashboard ever saw a failure. Its query builder also hardcoded `"Topuria Gaethje"`
  into *every* numbered-event search.
- **11 of ~37 configured RSS feeds were dead** (404s, a 403, a 501, ESPN's
  `202`-with-empty-body, a dead host).
- **The Federal Reserve feed was alive but invisible** — valid RSS with 20 items,
  dropped because `_parse_feed_xml(resp.text)` chokes on a UTF-8 BOM and the bare
  `except ET.ParseError` swallowed it.

**The fix:**

1. **Parser** — `apis/rss_feeds.decode_feed_bytes()` (`utf-8-sig` → latin-1 fallback);
   parse failures now log at warning with the feed URL.
2. **Feeds** — every dead URL replaced with a live-verified one. **37/37 ok.**
   MMA went from 1 working source to 5 (Sherdog, MMA Fighting `/rss/index.xml`,
   Bloody Elbow, MMA Weekly, UFC.com official).
3. **Honest failure** — `tapology_api` non-2xx now raises, so a 403 reports
   `STATUS_UNAVAILABLE`. Retired via `TAPOLOGY_SCRAPE_ENABLED=false` (module kept).
4. **`apis/mma_stats_api.py`** — API-SPORTS MMA host (reuses `API_SPORTS_KEY`) for
   fighter records + physicals, consumed by `ufc_context`. Guards: rate limits arrive
   as **HTTP 200 + `errors.rateLimit`** and must not read as "not found";
   `search=Topuria` returns *Aleksandre*, so `_name_matches` rejects a wrong first name.
   Free tier: 10 req/min, 100/day, `/fights` gated to 2022–2024 (so **no upcoming
   cards** — those come from RSS + NewsAPI).
5. **`core/feed_health.py` + `ops feeds`** — ok/**stale**/dead with newest-item age,
   persisted to `data/feed_health.json`, surfaced through `data_quality.warnings()`
   into `ops reliability`, and added to the `all-checks` batch.

**Watch out:** `core/signal_facts.format_signal_facts` formats **per-signal** — adding a
new key to a signal's `data` silently drops it from the prompt until a branch is added
there. That is how `fighter_stats` would have been lost.

## Shipped 2026-08-14 (paid-signal audit — `twitter` retired)

Same silent-failure pattern, but this one cost money. Measured against all 19 run
traces: **`twitter` was `inactive` on 19/19 runs from 2026-07-07 to 08-14** — it has
never once produced a fact — while being the **slowest signal at ~32s**. Signals run
concurrently with one worker each (`build_registry`: `workers = max_workers or
len(sources)`), so wall-clock ≈ the slowest signal: twitter alone set the floor for
every discovery. Next slowest is `youtube_competitors` at ~15s.

Cause: `apidojo/tweet-scraper` bills a full run and returns `10 x {"noResults": true}`
sentinel rows instead of tweets (X search almost certainly needs authenticated cookies
now). The signal only checked `if not items`, so a broken source read as a successful
empty search. The actor input was verified correct against `input_template`, so unlike
Reddit this was **not** input drift.

- `apify_client.is_no_results()` — shared sentinel detector; a run of rows carrying
  nothing but `noResults`/`error`/`message` keys is a failure, and any real row means
  the actor worked.
- `twitter_signal` reports `STATUS_UNAVAILABLE` on the sentinel, not `inactive`.
- `twitter_breaking` → `enabled: false` in `config/apify_sources.json` (the catalog
  kill-switch in `register_signals._catalog_disabled_signals` does the rest).
- `tiktok_trends` (~14s) and `youtube_competitors` (~15s) were checked and **kept** —
  both return real data.

**Remaining Apify tier:** `tiktok_trends`, `youtube_competitors`. Reddit + twitter
retired; `instagram_figures` still templated only.

## Shipped 2026-08-14 (`youtube_comments` signal + O12 complete)

**1. `youtube_comments` — audience questions as content gaps.** The catalog templated
this as an Apify actor; wired instead against the **official Data API**, which serves
the same data under the YouTube key we already hold. ~103 units/topic (one 100-unit
search + 1 per video) of a 10,000/day budget, versus billed Apify credits.

Surfaces the questions viewers are still asking under the best existing coverage —
by definition what nobody has answered. Live check on a Marvel Rivals topic returned
75 comments across 3 videos and 8 usable questions.

Three guards worth knowing about:
- `signal_facts` labels them **"AUDIENCE QUESTIONS (unverified …never as facts)"** —
  they are audience *language*, and the whole fact layer depends on not confusing the
  two.
- **Profanity filtered** (`_is_clean`) before anything reaches the script prompt; this
  is an advertiser-facing channel and comment sections are crude.
- **Pinned in `_VARIANT_REUSE_DEFAULT` + 6h TTL** — without that it re-runs per
  variant at ~103 units each.

**2. O12 complete.**
- `quota_governor.youtube_usage()` — `snapshot()` now reports apify/llm/signals/**youtube**
  together. `apis/youtube_quota` stays the counter *and* the check point (decisions §13:
  the governor unifies state + reporting, never the layered checks).
- `core/reliability_history.py` — one row per day (LLM spend, YouTube units, signals
  disabled, dead feeds, cache hit-rate), capped at `RELIABILITY_HISTORY_DAYS` (90),
  rendered as an ASCII trend under `ops reliability` and **recorded on view**, so the
  series builds itself with no job to forget. The dashboard could only answer "how is
  it now", never "is this getting worse" — which is exactly how every failure found
  this session stayed invisible while it developed.

---

## Shipped 2026-08-14 (post-render cost reaches the ledger)

Third instance of the session's pattern — something silently wrong that nothing
reported — and this one corrupted a shipped feature's headline number.

**Both operator render paths finalize the run before rendering it.** `main.py:362` and
`scripts/auto_generate.py:193` each call `run_pipeline(proceed_video=False)`, then
render separately. So the persisted cost kept `tts: 0.0` and the trace kept
`status="drafted"` on every rendered run. `main.py:512` *did* recompute the correct
cost — into a local dict, for display only, never written back.

`core/unit_economics.py:79` derives contribution margin from
`features_json.cost.total`, so **every margin was overstated by roughly the whole TTS
line** — the largest cost of a rendered run. `ops economics` reported *20 uploads,
$0.32 ($0.02/video)*; the truth was **$6.18 ($0.31/video)**.

- **`core/pipeline.run_media_only`** now persists the render lines + patches the trace.
  It is the single choke point both flows share, so one fix covers both.
- **`cost_meter.render_cost_lines()` / `merge_render_cost()`** — render lines only.
  `llm`/`apify`/`web_search` are session-metered and already persisted; recomputing them
  after the fact would overwrite good values with wrong ones.
- **`run_features.merge_features()` / `run_trace.update_trace()`** — merge helpers
  mirroring the existing `run_quality.merge_quality`.
- **`ops backfill-cost`** (`--dry-run` first) repaired 38 runs ($0.75 → $11.77) and 13
  traces. Idempotent; only touches rendered/scheduled/published rows. Flags
  `cost_estimated` when chars came from `word_count` (`script_preview` truncates at
  2000) and `cost_partial` for the 18 runs predating cost metering entirely.
- **TTS priced from the real plan**: ElevenLabs Creator $22/100k chars = **$0.22/1k**
  (was a $0.30 list-price guess). Re-derive as monthly cost ÷ quota if the plan changes.
- **`backfill-features --force` no longer wipes cost** — `build_features` has no `cost`
  block, so a forced rebuild silently destroyed it. It now carries unknown keys forward.

*Open observation, not built:* on a subscription the plan covers ~90 videos/month
against ~21 actually made, so the **allocated** cost is nearer $1/video than $0.22.
The metered marginal rate is the right fit for `cost_meter`; utilisation is a later pass.

---

## Shipped 2026-08-14 (Whisper local — CPU backend; caption text still blocked)

**Stopped deliberately mid-item.** The backend and its evidence are landed; the thing
that would make it *useful* is not, and the reason is written down rather than lost.

The roadmap said these backends were "parked — needs a GPU box". On this machine
`whisperx`, `faster_whisper` (1.2.1), `torch` (2.8.0+**cpu**), `piper` and
`ctranslate2` were **all already installed**, and the caption wiring
(`video/subtitles.py:110` → `caption_timing.words_from_caption_align` →
`core/caption_align.transcribe_and_align`) was **already complete and fail-open**.
Only a CPU-capable backend was missing.

**Landed**
- `core/caption_align.py` — `faster_whisper` backend alongside `whisperx`, plus
  `CAPTION_ALIGN_MODEL` / `_DEVICE` (auto → cpu here) / `_COMPUTE` (int8 on CPU).
  Still OFF by default and fail-open.
- `scripts/bench_caption_align.py` — accuracy against the **ElevenLabs `.words.json`
  sidecars** already sitting next to our mp3s. Real ground truth, real channel audio.

**Measured** (3 shorts, 55–58s):

| model | line-start p50 | p90 | speed (CPU) |
|---|---|---|---|
| **tiny** | **43–56ms** | 111–176ms | 12–15× realtime |
| base | 73–85ms | 142–159ms | 4–15× realtime |

`tiny` wins and is half the download, so it is the default — evidence, not instinct.
Piper synthesis of a real 1,156-char script: **5.1s**.

*Benchmark gotcha worth keeping:* grouping each transcript into caption lines
independently reported ~4s of "error" when per-word error was ~40ms — Whisper punctuates
differently, so `group_into_lines` split at different points and line N described
different words. The fix was to pair words first, then group. Don't re-introduce it.

**Why this is not finished.** The path transcribes blind, so captions carry **ASR text,
not the script**: run 65 came back with "Salkal" for "Salkilld" and "Mattius Gamarat"
for "Mateusz Gamrot". Fighter and game names are the channel's entire subject, so burned
captions would show mangled names despite ~45ms timing accuracy.

**This was fixed on 2026-08-16 — see the section below.**

Also noted: Piper renders the same script **66.3s vs ElevenLabs 55.2s** (~20% slower),
which shifts video length and feeds the learned-length loop. A voice sample exists at
`output/samples/piper_lessac_run65.mp3` for the operator to judge; **ElevenLabs remains
the default and nothing was switched.** Voice: `models/piper/` (gitignored).

---

## Shipped 2026-08-16 (fail-open made fail-visible)

All **98** silent handlers now log; **`S110`/`S112` enabled in ruff** so new ones fail CI.
Decisions §24.

**Things worth not relearning:**

- **Don't blanket-`logger.debug` them.** `CONTENT_LOG_LEVEL` defaults to **WARNING**, so
  the audit's own recommendation would have produced 93 lines nobody ever sees. The split
  is: `warning` when a *guarantee* dies (`llm_add_spend` → budget guard stops guarding;
  `write_run_trace` → `ops traces`/`dossier`/`data_quality` blind for that run), `debug`
  for enrichment, `# noqa: S110` + reason where silence is right.
- **Test the silence, not just the noise.** A warning that fires on healthy runs trains
  the operator to ignore warnings, so `tests/test_fail_open_visibility.py` asserts both.
- **`contextlib.suppress(Exception)` does not trip S110** — it's a loophole. `suppress` is
  for a narrow, expected exception type.
- **A migration used to switch off all logging.** `alembic/env.py`'s `fileConfig()`
  defaulted to `disable_existing_loggers=True`, killing the whole `content_machine.*`
  tree; `migrate_schema` calls `upgrade_head()` in a normal process. Fixed. Symptom to
  recognise: tests that pass alone and fail under `unittest discover`.
- **Entry-point scripts can't take a module-level logger.** `scripts/ops.py` and
  `scripts/auto_generate.py` import before `config.settings` loads `.env`, so a
  module-level `get_logger()` caches the level before `CONTENT_LOG_LEVEL` is readable —
  they resolve the logger at the call site instead. `main.py` defines its logger *after*
  `setup_logging()`.
- **Auto-derived log messages are worthless** ("loads skipped", "join skipped"). The
  messages were written by hand against each block; that reading is what surfaced the
  alembic defect.

## Shipped 2026-08-16 (caption text from the script — the $0 path is open)

`video/caption_retext.py`: whisper's **timings**, the script's **words**, aligned with
`difflib.SequenceMatcher`. Decisions §23.

The run-65 SRT, before and after, same audio:

| before | after |
|---|---|
| `broken, Quill and Salkal just` | `Quillan Salkilld just submitted Mateusz` |
| `submitted Mattius Gamarat and round` | `Gamrot in round one, and` |
| `with a top ten lightweight` | `a top-10 lightweight ranking.` |

**Things worth not relearning:**

- **The hard part is re-tokenisation, not misspelling.** Whisper splits (`Quillan` →
  `Quill and`), writes numerals as words (`10` → `ten`, `top-10` → `top ten`), drops
  words and invents them. A positional zip desyncs permanently at the first one. Hence
  number-words folding onto digits in the normaliser, `replace` spans shared by character
  length, `delete` runs interpolated + clamped monotonic, `insert` tokens dropped.
- **It costs nothing in timing.** Run 66 (243 words): word p50 42→43ms, line p90
  **117→117ms**, covering **243/243** script words vs the 243-of-251 whisper heard, and
  correcting **12 misheard words**. `py -m scripts.bench_caption_align` grew `+retext`
  columns and now shares its matcher with the shipped code.
- **The decline threshold is measured, not guessed.** `CAPTION_RETEXT_MIN_MATCH=0.35`:
  real audio scores **0.87**, unrelated audio ~0.0, and a worst-case 9-word
  proper-noun-dense line scores 0.44. A first guess of 0.6 sat too close to live values
  and declined on short scripts — caught by a test, not in production.
- **A rendered mp4 looks 2.17s out of sync with its SRT, and isn't.**
  `prepend_channel_intro` adds TapIn's **2.15s intro** *after* the ffmpeg render, shifting
  audio and burned captions together. Subtract it before concluding anything about drift.
- **`ffmpeg -ss` before `-i` gave unreliable frame times** when checking burned captions;
  output-seek (`-i` then `-ss`) agreed with reality.

**Not switched:** ElevenLabs remains the TTS default. The $0 flip is the operator's call
(voice sample: `output/samples/piper_lessac_run65.mp3`), and Piper's ~20% slower delivery
means `py -m scripts.bench_script_duration` must be re-run after it.

## Shipped 2026-08-15 (live-run 66 fixes)

Run 66 (GTA VI / Netflix) **confirmed the cost fix works live** —
`$0.3454 (llm $0.0043 · tts $0.3131 · apify $0.0200 · web $0.0080)`, TTS visible at 91%.
It also exposed five defects, none of which announced itself as a failure. All were
reproduced before being fixed.

| # | Defect | Fix |
|---|---|---|
| 1 | `WORDS_PER_SECOND = 2.4` vs **measured 3.32** (median of all 14 real renders) — run 66 shown "~101s", rendered **70.2s** | rate corrected; preset seconds now **derived** from word ranges so they can't drift apart again |
| 2 | `"If Netflix"` flagged as a possible hallucination → report card **A→B**, while the claim verifier said 12/12 backed | phrases no longer start on a function word |
| 3 | `youtube: ERROR — read operation timed out` (no timeout set anywhere) | bounded `YOUTUBE_API_TIMEOUT`; timeouts classify as `STATUS_UNAVAILABLE` |
| 4 | `youtube_comments` surfaced only *"What about Alaska?"* from 25 comments | questions must share a topic token; `"first"` no longer matches as a substring |
| 5 | Both cheap-tier LLM slugs dead — one probe each per 24h | OpenRouter repointed; Ollama reports unavailable when nothing is pulled |

**Things worth not relearning:**

- **Preset durations are derived, not stored.** Word ranges are the source of truth
  (`core/script_length.py`); they were deliberately *not* retuned, so a stored
  `length_preset` still means the same thing to the learned-length analytics.
  Re-check the rate with `py -m scripts.bench_script_duration` after any voice change.
- **Don't trim proper nouns on the whole `_COMMON_WORDS` list.** The first attempt did,
  and destroyed `"Black Widow" → "Widow"` and `"Season 8.5" → "8.5"`. `_LEADING_STOPWORDS`
  is deliberately a narrow function-word set, and `"the"` is excluded ("The Rock").
- **Don't pin a specific `:free` slug in a test.** OpenRouter rotates them; a test naming
  one goes green while production 404s daily. `test_openrouter_anchors_cheap_tier` now
  asserts *provider + `:free`*, not the id.
- **Picking an OpenRouter free model needs a live call, not a spec sheet.** The
  `gemma-4-*:free` models 429 on contention, and every `nemotron-*:free` leaks its
  reasoning trace into the reply ("Okay, the user just asked me to…"), which would
  corrupt short structured outputs. `poolside/laguna-s-2.1:free` returned a clean exact
  answer. A 429 is fine (fails over, O5); only a **404** means retired.
- **Ollama:** `ollama list` is empty on this box. `ollama pull llama3.1:8b` (~4.7GB) is
  the operator's call; until then the provider correctly reports unavailable.

---

## Pipeline order (operator)

```
Topic → Discovery (signals + editorial ANGLES) → pick angle → length → KEY FACTS → [fact conflicts] → script → TITLE → grounding → [trade check] → tier warnings → claim verifier → authenticity → report card → render → [vault dossier]
```

**Titles are NOT chosen at discovery.** Discovery returns short angle lines; `core/title_generator.py` writes the YouTube title after key facts + script + grounding.

**Vault mirror (Pillar 4):** when `OBSIDIAN_VAULT_PATH` is set, every drafted/rendered run writes `{channel}/_runs/{date}_{slug}-{id}.md`; `daily_sync` / `ops vault-sync` refresh dossiers with post-sync actuals. Strategy notes feed a bounded `CHANNEL PLAYBOOK` block in the script prompt (style, not facts).

---

## Key facts (operator ground truth)

| Feature | Where |
|---------|--------|
| Multi-line paste | Type `paste` at key-facts prompt |
| Vault save (all facts) | `vault/<channel>/_operator_facts/<date>_<topic>.md` (stamped `tier: operator` + `verified_at`) |
| LLM packing | Char budget default 12000 (`OPERATOR_KEY_FACT_CHAR_BUDGET`), soft 24 lines |
| Priority | manual → links → vault |
| Conflicts | Operator facts win — contradicting signal/web lines dropped pre-prompt (`FACT_CONFLICT_FILTER`) |
| Playbook | Strategy/belief notes → `CHANNEL PLAYBOOK` prompt block (NOT facts) |
| Run dossiers | `vault/<channel>/_runs/` — records of what we made, never read back as facts |
| Link scrape | Yahoo/list items OK; ESPN WAF → use `paste`; Bing search/captcha blocked; `ck/a` unwraps |
| Sports on TapIn | `infer_domain(key_facts=)` + NBA script matrix — pasted NBA facts override gaming default |
| **Headless** | `auto_generate --facts-file <paste-block.txt> --fact "..."` (repeatable) |

---

## Credit / speed

- **O1–O11 backlog complete** ([credit_efficiency.md](credit_efficiency.md)). `core/quota_governor.py`
  is the single façade over `data/quota_state.json`: Apify exhaustion + usage cache, LLM daily
  spend, persisted signal disables (key-hash invalidated), `snapshot()` for the dashboard.
- Apify 403 = auth (30m TTL), 402 = credits — persists until the real monthly cycle reset
  (`core/reset_window.py`, `APIFY_RESET_DAY`, O10)
- `SIGNAL_BACKEND=apify|free|auto` — `free`/`auto` serve `youtube_competitors` via yt-dlp and
  `reddit` via official OAuth (free script app) at $0; Twitter/TikTok stay Apify
- The claim verifier adds **one extract-tier LLM call per script** (free-first chain, §14);
  `CLAIM_VERIFIER_ENABLED=false` opts out
- Vault reads are **mtime-cached in-process** (`core/vault_index.py`) — no extra cost, big win
  for `batch-drafts` (N ideas × `load_facts` per run)
- `py -m scripts.ops reliability` — dashboard (breakers, budgets, persisted disables, resets, cache)

---

## Shipped 2026-07-17 (Pillar 6 — local-TTS voice variety + doc reconciliation)

1. **Voice variety** — `core/tts.resolve_local_voice(provider, channel_id)` mirrors the
   ElevenLabs per-channel/pool pattern for the local providers: per-channel
   `channels.json` `tts.local_voice` / `tts.local_voices` (pool rotates per run) →
   global env pool (`PIPER_VOICES` / `KOKORO_VOICES` / `XTTS_SPEAKERS`, csv) → the single
   env (`PIPER_VOICE` etc.) — so the fallback is byte-identical to before. Threaded into
   `_piper_synth` / `_kokoro_synth` / `_xtts_synth`. Optional run-seeded delivery jitter
   (`TTS_VOICE_VARIETY`, default off; `_variety_speed_factor` in a 0.94–1.06 band).
2. **Piper API fix** — the installed piper's `synthesize()` returns audio chunks and takes
   no wav file; `_piper_write_wav` now uses `synthesize_wav(text, wav_file, syn_config=…)`
   with a legacy `synthesize(text, wav_file)` fallback. This also carries the jitter config.
3. **Config** — `ChannelProfile.local_tts_voice` / `local_tts_voices` (default None; existing
   `config/channels.json` unchanged). Tests: `tests/test_tts_voice_variety.py` (21).
4. **Doc reconciliation** — roadmap Pillar 6 + `providers_runbook.md` status map now match
   git: seams wired into live paths marked so, GPU-only backends marked **parked (needs a
   GPU box)**, clip-from-source + storyboard marked not-started.

## Shipped 2026-07-08 (this branch — Pillar 6 baseline seams + goose3)

1. **Provider contract** — `core/providers.py`: `ProviderResult` + `resolve_order` /
   `selected_provider` / `flag_enabled` / `run_chain` (generalizes `signal_contract` +
   the asset chain). Every seam is env-gated OFF, lazy-imports its backend, fails open.
2. **Tool seams** (baseline, fail-open): `core/caption_align.py` (WhisperX),
   `core/music.py` (MusicGen), `core/comfy_client.py` (ComfyUI), `core/vault_ingest.py`
   (multi-source → vault note), `core/grade.py` (Expert Panel), `core/run_eval_corpus.py`
   (system_prompts_leaks), `core/avatar.py`, `core/reframe.py` (AGPL note),
   `assets/ai_video_provider.py`, + a `TTS_PROVIDER` chain in `core/tts.py` (Kokoro/XTTS).
3. **goose3 grounding (implemented)** — `core/link_facts._goose3_body_lines`: goose3
   extracts the article body from already-fetched HTML (`raw_html`, no 2nd request),
   BeautifulSoup `<p>` scan as fallback; trade-tracker pages keep the BS4 path.
   `vault_ingest.ingest_url` reuses it.
4. **Config/docs** — `goose3` in core deps; heavy backends in the `[providers]` extra;
   `.env.example` "Provider slots (ALL OFF)" block; cloned tool dirs + local corpus/
   workflows gitignored. Index: [providers_runbook.md](providers_runbook.md).
   Tests: `tests/test_providers.py` (23), `tests/test_link_facts_goose3.py` (9).

## Shipped 2026-07-09 (this branch — live-run wave 2: vault scan, claim regen, speed, UI)

From the Palworld run's pain points:
1. **Vault topic scan** — `load_facts(..., require_distinctive=True)`: facts must share a
   topic-identity token (generic "patch"/"massive" don't count; no evergreen bypass).
   `prompt_key_facts` auto-attaches relevant facts (`VAULT_FACTS_AUTO`, default on) or
   skips with one line — no more manual `n` on NBA facts for a Palworld video.
2. **Claim regen** — the verifier's verdict is now acted on: unsupported claims get one
   premium-tier rewrite (remove or attribute as "reports claim…"), adopted only if the
   re-verified count drops (`CLAIM_REGEN_ENABLED`, default on).
3. **Variant scoring 185s → seconds** — ALL signals now pin by default during variant
   scoring (`_variant_reuse()`, env per-call). **A stale `.env` override
   (`VARIANT_REUSE_SIGNALS=youtube`) was the real cause — commented out locally.**
   Also fixes per-variant Wikipedia 429s + 5× Tavily spend.
4. **Competitor pulse panel scrapped** from main.py (snapshot sync kept for briefs).
5. **IGDB 400 fixed** — the query requested the removed `popularity` field; now
   total_rating/hypes.
6. **Spinner engagement** — live variant detail, "typ ~Ns" hints from the last trace.

Known issues: YouTube RSS feed id `UCq-Fj5jknLsUf-MWSik4vhQ` 404s (stale channel id in
config — replace or remove the feed entry).

## Shipped 2026-07-09 (this branch — Pillar 6 #1: local TTS)

**The cost lever** (TTS was ~96% of run cost): `TTS_PROVIDER=piper|kokoro|xtts` now works
end-to-end — local synth → temp wav → ffmpeg transcode to the exact mp3 the render pipeline
reads (`core/tts.py` `_transcode_to_mp3`); any failure falls back to ElevenLabs (a local
provider can never break a render). `cost_meter` meters local voice at **$0**. **Piper** is
the CPU-only Windows path: `pip install piper-tts` + `PIPER_VOICE=<voice.onnx>`; Kokoro
(torch + espeak-ng) / XTTS (torch, cloning) for a GPU box. Local TTS emits no word
timestamps → captions use the proportional fallback until the Whisper-alignment phase.
Tests: `tests/test_tts_local.py` + cost-meter zero-cost case.

## Shipped 2026-07-08 (this branch — live-run quality fixes)

From a real tapin run's pain points:
1. **Script framing** — `core/content_engine._build_prompts` gained a FRAMING block: facts
   are EVIDENCE for the take (no 3+ bare-fact runs), and brief/web speculation must be
   explicitly attributed, not asserted (cuts invented-claim flags).
2. **Best-bet freshness** — `apis/rss_feeds._parse_feed_xml` now captures pubDate; `core/best_bet`
   prefers items within `BEST_BET_FRESH_DAYS` (5) and **date-seeded rotates** the pool so bets
   change daily instead of recurring for a week.
3. **Topic diversity** — best_bet caps **one pick per franchise anchor** (`_first_anchor`, most-
   general match so GTA VI + GTA 6 collapse) so gaming slots aren't all GTA; angle prompt
   (`apis/topic_variants`) forces distinct lenses.
4. **Scrape/checks** — `core/link_facts`: title-only detection + opt-in `LINK_READER_PROXY`
   (r.jina.ai) for JS-heavy pages (MSN); `core/ui.py` warns on headline-only scrapes;
   `core/claim_verifier` message explains unsupported = model-invented.
5. **Apify 403 → free** — `apis/reddit_signal` now auto-degrades to the free OAuth backend when
   Apify is disabled this session (youtube_competitors already did), so a dead key keeps Reddit
   and stops 90s actor-timeout stalls. **Operator fix:** check `APIFY_CONTENT_MACHINE_KEY`
   permissions, or set `SIGNAL_BACKEND=auto`.

## Shipped 2026-07-07 (this branch — Pillar 4)

1. **Run dossiers** — `core/vault_dossiers.py`: `{channel}/_runs/{date}_{slug}-{id}.md`
   (topic, angle, report-card grade, quality summary, cost, script, post-sync actuals +
   video URL). Written fail-open from `_finalize_run`; `refresh_dossiers()` via
   `daily_sync` + `ops vault-sync`. Weekly report → `{channel}/_reports/{date}_weekly.md`.
2. **Vault index** — `core/vault_index.py`: per-process mtime cache behind
   `load_fact_records()` — unchanged notes are `stat()`ed, not re-read.
3. **Playbook layer** — `load_playbook()` / `playbook_block()`: strategy + machine-belief
   bullets feed a bounded "CHANNEL PLAYBOOK" block in the script prompt. Fixed `[strategy]`
   tag parsing (`_tag_set`). Dossiers/reports excluded from facts (`_is_machine_record`).

## Shipped 2026-07-06 (this branch — Pillars 1–3 + morning wave)

1. **Pillar 1 — Run Ledger** — traces, `quality_json`, `ops traces`/`dossier`, data-quality
   monitor, unit economics.
2. **Pillar 2 — Video Grading** — report card, predictor, calibration, prompt evals.
3. **Pillar 3 — Fact Engine 2.0** — structured facts, tiered corpus, claim verifier,
   conflict detection, web-source capture, quality v2.
4. **Morning wave** — Reddit free backend, signal-breaker persistence, batch-drafts,
   script-lever + thumbnail A/B, webhook events, O11 governor.

---

## Best 5 terminal commands (outside `py main.py`)

1. `py -m scripts.ops daily-brief` — morning one-shot: fresh data → ideas → quota → queue
2. `py -m scripts.ops traces` / `ops dossier --run-id N` — run ledger viewers
3. `py -m scripts.ops vault-sync --channel tapin` — beliefs + dossier refresh into vault
4. `py -m scripts.ops batch-drafts --channel tapin --count 3` — unattended draft scripts (feeds A/B)
5. `py -m scripts.ops reliability` — credit/quota/breaker/cache dashboard
6. `py -m scripts.ops feeds` — RSS source health (ok/stale/dead); run monthly, feeds die quietly

Setup path (fresh machine): `py -m scripts.ops all-setup --channel tapin`.

---

## Open (roadmap next)

**Pickup:** take the Pillow/requests/MoviePy dependency wave when a real render
can verify it. Candidates **23–28** (remaining caption/thumb aesthetics) and **56–90** leftovers sit at
the bottom of Next up. Phase M stays parked. **#147 FastAPI still skipped.**

**Already done (do not re-open):**
- Ten-small-task wave (2026-08-25): MoneyWise persona; #21, #22, #31, #39,
  #53, #262, #271, #298, and #299.
- Post-wave-4 pickup (2026-08-25): #313, #282, #308–310, #232 and #122.
- Caption-text from the script (`video/caption_retext.py`, 2026-08-16). The **$0 TTS
  switch** is unblocked and waiting on two *operator* calls: judge
  `output/samples/piper_lessac_run65.mp3`, then re-run
  `py -m scripts.bench_script_duration` (Piper reads ~20% slower).
- Silent `pass` handlers (S110/S112, 2026-08-16).
- **PR #34 merged 2026-08-19** (`6389e87`), CI green on `main`. All seven stale PRs
  **#26–#32 closed**. Pre-merge check: Alembic `0004`, 4/4 FKs, 37/37 feeds, 1,433
  tests. `feat/research-intake-repair` and `feat/trade-validation-default-on` are in
  `main` and safe to delete.
- Coverage wave: `prepend_channel_intro`, `process_one` quota gate, `_defer_for_quota`,
  `build_render_ffmpeg_command` **done**. Remaining: **`youtube/oauth.py` tests**
  (never `config/secrets/`) and the `coverage` extra (report only, no CI %).
- Router vision path (2026-08-20): thumbnail scorer uses `llm_router.complete` with
  image parts; `core/llm_client.py` deleted. Pillar 2 *rendered-video* review is still
  later. Semantic authenticity (`AUTHENTICITY_SEMANTIC`) default-on, warn-never-block.
- Cheap-tier dead slugs: OpenRouter cheap repointed on live test; Ollama reports
  unavailable when nothing is pulled (run 66 / run 70). `ops free-doctor` now says
  **pull** vs **serve** vs OpenRouter throttled fallback.

**Still open:**
1. **Reinstall the venv** after the Pillow 11.3 / requests 2.32.4 / moviepy-drop
   pin change, then do a real thumbnail/render. Do not start with clip-from-source,
   avatar, #147 FastAPI, or Phase M.
2. **Pillar 6 remainder** — seams live; heavy backends wait on a **CUDA torch**
   build (`2.8.0+cpu` on an RTX 4070 Ti), not on hardware. Clip-from-source and
   storyboard still not started. [providers_runbook.md](providers_runbook.md),
   [video_creation_stack.md](video_creation_stack.md).
3. **Pillar 2 remainder** — multimodal rendered-video review (vision path now
   exists); calibration/predictor stay volume-gated (10 measured vs threshold 15).
4. **Unphased:** MoneyWise depth, AI Tools/Tech groundwork. Overnight `--facts-file`
   is wired. Vault wolverine-only bullets (no franchise string) still attach.
5. **Vault:** stable-path dossier upsert (date-prefix clones the same `run_id`).
6. **One-time ops:** re-auth `youtube.readonly` for tapin; `oauth_setup` for MoneyWise.
7. **Do not merge** `origin/claude/docs-optimization-review-a4l104` (9 commits, no
   PR, last touched 2026-07-21, old base — same shape as #27).
   `origin/feat/reddit-free-backend-and-signal-persistence` is in `main`; delete it.

**Parked / excluded:** Instagram + TikTok platform linking (Phase M) · Benable bot.

---

## Docs to read first

- `docs/decisions.md` §15 (pillar reorientation), §16 (Fact Engine), **§17b (vault OS)**
- `docs/credit_efficiency.md` — O1–O11 (all ✅)
- `docs/roadmap.md` — Pillars 1–7 ✅ (Pillar 6 backends parked on CUDA torch); post-wave-4 pickup shipped
- `docs/providers_runbook.md` — Pillar 6 tool → module → env → proof index
- `docs/debugging.md` — playbook vs facts, hallucination triage

---

## Key files

```
apis/mma_stats_api.py       — API-SPORTS MMA fighter records (replaced Tapology)
core/feed_health.py         — RSS ok/stale/dead checker behind `ops feeds`
core/signal_facts.py        — per-signal -> prompt formatting (add a branch for new data keys)
core/vault_dossiers.py      — Pillar 4: run dossiers + weekly report into vault
core/vault_index.py         — Pillar 4: mtime-cached vault parse
core/obsidian_facts.py      — load_facts + load_playbook/playbook_block
core/fact_store.py          — Pillar 3: FactRecord, tiers, freshness
core/claim_verifier.py      — Pillar 3: claim verifier + GROUNDING_GATE
core/run_trace.py           — Pillar 1: per-run traces
core/video_grade.py         — Pillar 2: pre-publish report card
core/quota_governor.py      — O11 façade
core/providers.py           — Pillar 6: provider-slot contract (ProviderResult, run_chain)
core/link_facts.py          — goose3-first article extraction (+ BeautifulSoup fallback)
docs/providers_runbook.md   — Pillar 6: tool → module → env → proof index
scripts/ops.py              — ~40 subcommands (vault-sync, traces, dossier, batch-drafts)
main.py                     — interactive flow + gates + report card
```
