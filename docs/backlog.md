# Backlog — the full inventory

> Every open item, plus the shipped ones that carry evidence worth keeping. Read
> [roadmap.md](roadmap.md) for what to do now and [desktop_app.md](desktop_app.md)
> for the application programme. History lives in
> [roadmap_archive.md](roadmap_archive.md).

Sizes: `[S]` hours · `[M]` a session · `[L]` a wave · `[XL]` a programme.

---

## Unnumbered open items

*Carried over from the old thematic lists and the phase/pillar sections. Several
duplicate a numbered candidate below — noted where spotted.*

- [ ] Backtest recommender accuracy vs. realized engagement (volume-gated — **10** measured `[M]`
  run-linked videos vs the predictor's own threshold of 15)
- [ ] `instagram_figures` signal — still templated only; catalog entry `enabled: false` `[S]`
- [ ] Free-backend probe for Twitter/X, if the signal is ever worth restoring `[S]`
- [ ] Free-backend probes — TikTok/Twitter equivalents (only if the Apify bill justifies it) `[S]`
- [ ] **$0 TTS switch** — **technically unblocked 2026-08-16** (captions fixed above; a `[M]`
  full Piper render was verified end to end), now waiting on two operator calls rather
  than engineering. Local Piper meters $0 vs **$0.25–0.31/video (~91% of run cost)**.
  **Edge TTS** (`TTS_PROVIDER=edge`, 2026-08-28) is a separate opt-in **cloud** $0 path
  with SSML lexicon + WordBoundary timings; it is not this judgment and is never the
  default. Piper remains the true-offline Free floor.
  1. **Judge the voice** — `output/samples/piper_lessac_run65.mp3` vs the ElevenLabs
     render of the same script. Deliberately not decided for you.
  2. **Re-run `py -m scripts.bench_script_duration` after any flip** — Piper reads the
     same script ~20% slower (66.3s vs 55.2s), so `WORDS_PER_SECOND` and the
     learned-length loop go stale otherwise.
  Flip with `TTS_PROVIDER=piper` + `PIPER_VOICE` + `CAPTION_ALIGN_BACKEND=faster_whisper`
  ([free_mode.md](free_mode.md)); ElevenLabs remains the default and nothing was switched
- [ ] Clip-from-source (Phase R) + subject-tracked auto-reframe `[L]`
- [ ] Avatar mode, upscaling (Real-ESRGAN/RIFE), storyboard shot-lists `[XL]`
- [ ] Router vision path → multimodal rendered-video review (Pillar 2) `[L]`
- [ ] MoneyWise depth wave — earnings-calendar signal, ticker watchlist, finance brief sections `[L]`
- [ ] Third-vertical groundwork: AI Tools / Tech — channel profile + SEO + coverage audit `[L]`
- [ ] Tighten the mypy baseline *(the other half of the old combined line)* `[M]`
- [ ] C-follow-ups — LLM-proposed directives; optional auto-apply of a gate-winner behind a flag `[M]`
- [ ] Thumbnail scoring → CTR (needs impressions/CTR in the metrics sync) `[M]`
- [ ] Prompt-performance analysis; asset-effectiveness ranking from `assets` history `[M]`
- [ ] Full operator dashboard / Channel Command Center `[XL]`
- [ ] Tavily / broad web research; Bluesky direction signal `[M]`
- [ ] Multi-language (single script → localized TTS) — low priority for the gaming/UFC niche `[L]`
- [ ] Clone-this-winner into discovery — `winners()` is display-only; `best_bet` `[M]`
  already consumes the graveyard `[M]`
- [ ] Recommender simulation harness — synthetic histories so the loop is `[M]`
  validatable before n=15 `[M]`
- [ ] Hook-score vs retention calibration — 0–100 heuristic never checked against `[M]`
  `audienceWatchRatio` `[M]`
- [ ] Semantic vault fact retrieval — token overlap misses related notes `[M]`

### From the intelligence phase (H-K)

- [ ] Pillow remains fallback `[S]`
- [ ] Backtest recommender accuracy vs. realised engagement once volume grows `[M]`
- [ ] `instagram_figures` — still templated only; catalog `enabled: false` `[S]`
- [ ] **git remote** — repo initialised locally; create **private** GitHub remote and push `[S]`
- [ ] Tighten the mypy baseline (~94 errors → fix the real ones, e.g. `timings` value type) `[M]`
- [ ] Annotate/retire the remaining best-effort broad `except Exception` handlers `[M]`
- [ ] Raise test coverage on render + publish paths `[M]`

### From candidate phases O-S

- [ ] **Multi-language** — single script → translated script + localized TTS → per-language uploads. Real growth lever, **low priority** for the gaming/UFC niche; pairs with Phase Q captions. *(deferred — see Later horizons.)* `[L]`
- [ ] Ingest a long video / VOD / podcast (file or URL) → transcribe → find strong moments → cut vertical shorts with captions. `[L]`
- [ ] Reuse the scoring / hook / caption stack from Phases P–Q. `[S]`
- [ ] **Observability** — structured run traces + timing dashboard (timings already captured). *(promoted into **Pillar 1 — Run Ledger** below.)* `[M]`

### From the 2026-H2 pillars

- [ ] **Multimodal rendered-video review** `[L]` *(later)* — sampled frames +
  transcript → LLM rubric (pacing, caption readability, visual interest); the
  router vision path shipped 2026-08-20 (supporting track).
- [ ] **Clip-from-source (Phase R)** + subject-tracked auto-reframe — *not started; `[L]`
  auto-reframe seam is `core/reframe.py` (YOLO/AGPL, GPU). Deprioritized this pass.*
- [ ] **Avatar mode, upscaling (Real-ESRGAN/RIFE), storyboard shot-lists** — polish tiers. `[XL]`
  *Avatar/upscaling = seams parked (GPU + `[search github]` repos). Storyboard = build
  with the AI-video backend (its real consumer; prose hurts keyword stock search).*
- [ ] **Governor follow-ups (O12 candidates)** — YouTube units under a governor `[M]`
  scope; per-provider LLM spend in the run cost line; reliability time series
  ([credit_efficiency.md](credit_efficiency.md) O11 follow-ups).
- [ ] **Free-backend probes (optional)** — TikTok/Twitter equivalents of the `[S]`
  yt-dlp / Reddit-OAuth backends, only if the Apify bill justifies it
  ([agent_reach_evaluation.md](agent_reach_evaluation.md)).
- [ ] **MoneyWise depth wave** ([domain-expansion.md](domain-expansion.md) ROI 9.5) — `[L]`
  earnings-calendar signal (free API), ticker-watchlist tracking, finance-tuned research
  brief sections.
- [ ] **Third-vertical groundwork: AI Tools / Tech** (ROI 9.0) — new-channel playbook dry `[L]`
  run: channel profile + SEO config + signal-coverage audit. *Groundwork only, not a
  launch commitment.*
- [ ] **Engineering hygiene** — CI coverage reporting (non-blocking), mypy-baseline `[M]`
  tightening tracking, render/publish test depth (the acknowledged soft spot).

### Later horizons — Phase M multi-platform (parked)

- [ ] **TikTok publisher** — `TIKTOK_CLIENT_KEY`/`SECRET` present; `TikTokPublisher` still unimplemented (in `DEFERRED_PLATFORMS`) `[XL]`
- [ ] Instagram Reels / Meta — `META_APP_ID`/`SECRET`, `INSTAGRAM_*` (keys still empty) `[XL]`
- [ ] Per-platform caption/hashtag shaping from existing SEO + TikTok-trend signal `[M]`
- [ ] Cross-platform performance back into the learning loop (unify with YouTube engaged-rate) `[L]`

### Deferred (volume-gated)

- [ ] Thumbnail scoring → CTR `[M]`
- [ ] Prompt performance analysis (after provenance shipped) `[M]`
- [ ] Asset effectiveness ranking from `assets` history `[M]`
- [ ] Full operator dashboard + Channel Command Center `[XL]`
- [ ] Tavily / broad web research `[M]`
- [ ] Bluesky direction signal `[S]`
- [ ] Reuse scoring from `assets` history for background selection `[S]`

---

## Numbered candidates 21-480

**Candidates 21–55 (2026-08-20 afternoon — docs only; Phase M still parked)**

*None of these restates Next-up or the 20-item morning list. Volume-gated
backtest, $0 TTS voice judgment, and Instagram/TikTok publishers stay out.*

Aesthetics / on-screen

- [x] 21. Per-channel caption skin in `channels.json` (font, karaoke vs boxed, fill color) — shipped 2026-08-25; the real subtitle/ffmpeg path consumes each channel's mode and libass style `[S]`
- [x] 22. Thumbnail safe-area / YouTube chrome checker — shipped 2026-08-25; Pillow checks high-contrast detail in the bottom 20%, reports QUIET/REVIEW in render progress + booth. Boundary: conservative density heuristic, not a SAFE verdict or face/OCR detection `[S]`
- [x] 23. End-card / subscribe sting after VO, fail-open, per-channel asset `[S]` — shipped 2026-08-25 as a validated, generated per-channel card; publish renders concatenate intro → body → card, restore the body on every failure path, and persist the exact outro argv
- [x] 24. Lower-thirds for fighter/game names from the fact corpus (the names captions already get right) `[M]` — shipped 2026-08-25; the existing grounding rules select capped public labels, only labels persist, and real word timings produce escaped ASS overlays (missing timing leaves the render command unchanged). **Fixed 2026-08-25 in audit:** the burn-in path quoted the .ass path with Python `repr`, doubling the backslash `_escape_subtitle_path` puts before the drive-letter colon - real ffmpeg returned `-22 Invalid argument`, so it could never have rendered on Windows. The only test reaching it passed `lower_thirds_path=None`
- [x] 25. Channel LUT / color grade on the stock loop so TapIn and MoneyWise do not share the same ungraded look `[M]` — shipped 2026-08-25 as bounded `eq` parameters with distinct TapIn/MoneyWise values, applied after crop before every overlay in publish, preview, fallback, and extra-format commands
- [x] 26. Hook-line Ken Burns / zoom on the first caption beat only (retention cliff is already measured) `[M]` — shipped 2026-08-25; bounded per-channel zoom comes only from real word timings and returns to 1.0 after the first cue (no timing means byte-identical argv). **Fixed 2026-08-25 in audit:** it read only the ElevenLabs sidecar, so this and #24 were both dead on every local-TTS run while the captions on the same render had whisper timings. `video.subtitles.resolve_word_timings` is now the shared seam
- [x] 27. Dual thumbnail: high-contrast text-on vs face-forward, operator pick, logged as the thumbnail experiment arm `[M]` — shipped 2026-08-25 behind `thumbnail_format` or `THUMBNAIL_DUAL`; two independently fail-open labeled variants, pick-time-only assignment, persisted provider/cost evidence, booth POST controls, `ops pick-thumbnail`, and no newest-mtime publish fallback
- [x] 28. Intro/outro duration learned from the channel drop-off point instead of a fixed 2.15s TapIn sting `[M]` — shipped 2026-08-26; `learned_intro_duration` keeps 2.15s until `drop_off_ratio` has samples (honest floor = RETENTION_MIN_VIDEOS). Below that, plumbing exists and the gap is asserted rather than a fake learned value

Organization / operator surface

- [x] 29. `ops postmortem --run-id` — slowest phase, failed signals, ungrounded claims, cost, next fix; assembled from traces that already exist `[S]`
  *(2026-08-20: `core/postmortem.py`; no new I/O beyond existing traces/run row)*
- [x] 30. `ops doctor` — one command: free-doctor + feeds + oauth scopes + quota snapshot + caption/TTS readiness `[S]`
  *(2026-08-20: also CUDA probe; oauth is token-file + scopes, no refresh HTTP;
  feeds from cached `ops feeds` snapshot)*
- [x] 31. Artifact retention report: `ops artifact-retention` lists old `output/*/drafts`, `data/traces`, and `_runs/` clones; intentionally report-only, and ignores `--apply` `[S]`
- [ ] 32. Split `core/ui.py` (~1,400 LOC and growing) into prompt / display / recovery modules — the July audit’s compounding smell `[M]`
- [x] 33. `channels.json` schema ratchet in CI *(2026-08-22; gap closed 2026-08-25)* - `validate_channel` checks `ui_theme`, `persona`, and caption-skin contracts against the REAL shipped config. MoneyWise now carries the documented explanatory, non-selling persona and reaches `human_context_block`
- [x] 34. Vault note templates in-repo *(2026-08-22)* - `docs/vault_templates/` (`_operator_facts`, `_strategy`, `_sources`), each parsed in `tests/test_vault_templates.py` through the real `_parse_frontmatter` and checked against `TIER_WEIGHTS`, so a contract change breaks in CI instead of in the operator's vault
- [ ] 35. Alembic-only schema path — stop teaching two migration stories (`migrate_schema` vs Alembic) `[M]`
- [x] 36. `ops topic-clone --run-id` — seed a new draft from a winner (angles new, facts refreshed); the missing write path behind display-only `winners()` `[M]` — shipped 2026-08-26; `clone_from_run` calls `generate_draft` for real
- [x] **37. Playbook lint** *(2026-08-22)* — `ops playbook-lint`; untagged strategy-shaped bullets that also look fact-anchored warn because `load_facts` treats them as ground truth `[S]`

Efficiency

- [x] 38. **NVENC hardware encode** *(2026-08-28)* — one `video/encoder.py` helper (`video_encoder_args` + `run_ffmpeg_with_nvenc_fallback`) used by render, composite, intro, and outro; probe true selects `h264_nvenc -preset p4 -cq`, and a failed encode retries once with libx264. `NVENC=off` (suite default) emits the historical `-c:v libx264 -preset fast -crf 23` block byte-identical, asserted from the real command builder. **Verified with a real encode, not the probe:** ffmpeg listing `h264_nvenc` is a capability claim, so the full render argv was run against real inputs — 1080x1920 h264 + aac, exact 3.000s, ~1.5x faster than libx264 (larger file: NVENC `cq` is not x264 `crf`). Follow-on fix: the fallback broke #309's promise that the persisted argv is the one that SUCCEEDED — `executed_cmd` now reports the libx264 retry, so the booth cannot hand the operator an `h264_nvenc` command that failed `[M]`
- [x] 39. Draft-vs-publish render preset: `ops render-preview --run-id` writes suffixed preview audio plus a 480x854 `ultrafast` MP4; the default 1080x1920 `fast` publish path, run media row, thumbnail, and upload target remain unchanged, and the publisher rejects `_preview.mp4` `[S]`
- [ ] 40. Overlap thumbnail + TTS while the operator is still on the report-card prompt (interactive path only) `[M]`
- [x] 41. Cap discovery workers so one slow Apify actor cannot set wall-clock for every run (twitter’s lesson, still true for tiktok ~14s) `[S]`
  *(2026-08-20: `DISCOVERY_MAX_WORKERS` default 8; 0/off = one worker per source;
  explicit `max_workers=` still wins)*
- [x] 42. Shared discovery cache across `batch-drafts` topics that share a franchise anchor (GTA 6 leaks × N) `[M]`
  *(2026-08-26: `franchise_batch_cache` rewrites `build_key` to `franchise:{anchor}` inside `run_batch`; no second cache)*
- [x] **43. Script trim pass** *(2026-08-21)* — drop trailing padding sentences when over length; never clip; hard cap remains refuse `[S]`
- [x] 44. `scripts/probe_sync.py` *(2026-08-22)* - answers "is this render out of sync?" in one sentence. Verified on a real mp4: 2.207s leading pad vs the 2.15s TapIn intro -> **IN SYNC**, because `prepend_channel_intro` runs after ffmpeg. Encodes both traps that cost real time: input-seek `-ss` reports the wrong frame (uses output-seek), and `silence_start: 0` is the intro, not a defect
- [x] 45. Overnight quota-aware: skip or shrink `--count` when YouTube remaining < 1,600 or Apify breaker is in `[S]`
  *(2026-08-20: `OVERNIGHT_QUOTA_GATE` opt-in; fail-open on store errors; suite sets false)*

Long-term / intelligence

- [x] 46. UFC/NBA/game **seasonal calendar** as a $0 best-bet source (cards, earnings weeks, launch dates) — best-bet is RSS-only at startup by design `[M]`
  *(2026-08-26: `config/seasonal_calendar.json`; past dates expired; `get_best_bets` source=`calendar`)*
- [x] 47. Topic graph: franchise arcs (GTA VI week 1 → week 4) so best-bet can continue a story instead of only avoiding the graveyard `[L]`
  *(2026-08-26: JSON sidecar `data/topic_graph.json`; `get_best_bets` prefers week-N+1; graveyard still wins)*
- [ ] 48. Multi-run series (`part 1/2/3`) with a vault-backed outline; cadence still capped `[L]`
- [ ] 49. Post-publish first-hour anomaly (views or engaged-rate vs channel baseline) → webhook. Uses metrics sync, not a new API `[M]`
- [ ] 50. Learned insight-marker list: replace the hardcoded `_INSIGHT_MARKERS` from scripts that actually retained `[L]`
- [ ] 51. Channel DNA export → new-channel playbook (the AI Tools/Tech groundwork, but as a dump of what TapIn learned) `[M]`
- [x] 52. Graveyard reason codes *(2026-08-22)* - `reason_codes_for_quality` / `explain_reason_codes` derive `thin_facts` / `recap` / `weak_hook` / `ungrounded` **only** from the `quality_json` a run already persisted; a run predating quality persistence returns an honest `[]` rather than a guess
- [x] 53. Prompt-version auto-bump from a SHA-256 hash of the live `content_engine` prompt-builder sources; every generated package and prompt-eval run carries the hash suffix `[S]`
- [ ] 54. Retention-informed `scene_plan`: force a cut/stance beat before the measured channel cliff `[L]`
- [x] 55. Fact-expiry watchdog in `ops reliability` — vault notes with `expires` in the past that still rank into prompts `[S]`
  *(2026-08-20: notes already dropped from `load_facts`; watchdog flags leftovers on disk;
  no HTTP; empty vault path is a no-op)*

**Candidates 56–90 (2026-08-20 evening — viability / short-term success / real-world cost)**

*Brainstorm. Rationale: [planning_log.md](planning_log.md) 2026-08-20 evening.
None restates Next-up, the morning 20, or candidates 21–55. Phase M, volume-gated
backtest, and the $0 TTS voice judgment stay out. Grouped by the three axes; a
few items serve two axes and sit under the dominant one.*

Short-term success — the next publish happens, and it earns a data point

- [x] 56. ElevenLabs **character-quota governor** (same shape as `APIFY_MONTHLY_BUDGET_USD`) — trip to Piper or block render *before* the Creator 100k chars exhaust mid-month `[S]`
  *(2026-08-20: `ELEVENLABS_MONTHLY_CHAR_BUDGET` opt-in; persist via `quota_governor` only; check point in `tts.py`)*
- [x] 57. **Paid-signal outcome attribution** — did `tiktok_trends` / `youtube_competitors` move composite score or engaged-rate on measured runs? Drop or demote if they didn't (operating_plan §4 item 2) `[M]`
  *(2026-08-20: `ops paid-signals`; engaged-rate then composite; never writes the catalog)*
- [x] 58. Overnight **render-queue gate**: only enqueue render when report-card ≥ B *and* authenticity pass — unattended volume cannot tank the 2026 policy `[S]`
  *(2026-08-20: `OVERNIGHT_RENDER_GATE` default on; auto_generate + `job_type=render` worker; interactive `main.py` unchanged; missing grade fail-closes)*
- [x] 59. YouTube remaining units → **"N uploads left this reset"** on `ops reliability` / startup (upload ≈ 1,600 units) — cadence currently ignores the hard ceiling `[S]`
  *(2026-08-20: `uploads_remaining` / `format_uploads_left`; reliability + `main.py` startup; check point stays `youtube_quota`)*
- [x] 60. `ops channel-go-live --channel moneywise` — fail until OAuth + SEO + feeds + brand kit exist; MoneyWise is still a one-time ops footnote and the highest-RPM channel `[S]`
  *(2026-08-20; persona gap closed 2026-08-25: checklist requires tone+audience; remaining launch gaps include handle/trailer/OAuth; never reads token contents except via existing oauth helpers)*
- [x] 61. **Thin-facts abort before TTS** — if claim-support or fact-line count is below a bar, stop *before* the $0.31 voice line; drafts stay free `[S]`
  *(2026-08-20: default on, 3 lines + 50% support; verifier missing fail-opens; `--force` / interactive y overrides)*
- [x] 62. **Don't start the next video until yesterday has metrics** — optional `ops` gate so the learning loop actually feeds the next pick instead of another unmeasured draft `[S]`
  *(2026-08-20: `METRICS_BEFORE_NEXT` opt-in, empty/0/off = disabled; no yesterday upload = pass; store failures fail-open)*
- [x] 63. Skip a scheduled slot when trailing-7d **RPM < fully-loaded cost** — posting to lose money is not "staying consistent" `[M]`
  *(2026-08-20: `RPM_COST_GATE` opt-in; last 7 monetized uploads as the 7d proxy;
  no revenue fail-open; worker defers without consuming a retry)*
- [x] 64. Free-mode **"what Standard would have billed"** dry-run line — operator confidence to flip $0 without a surprise invoice `[S]`
  *(2026-08-20: counterfactual ElevenLabs TTS + paid thumbnail; does not mutate persisted cost; silent on Standard ElevenLabs runs)*
- [x] 65. **Operator minutes-per-run** timer (interactive prompts + wait) — short-term success is also human hours; the CLI currently meters APIs only `[S]`
  *(2026-08-20: in-memory wall vs `input()` wait; summary line; never writes `data/`)*

Real-world cost — meter the true bill, kill spend that doesn't move the needle

- [x] 66. **Meter Flux / Ideogram / Recraft** in `cost_meter` (~$0.04–0.05/image) — operating_plan §4 still lists this as an unmetered gap; `ops economics` cannot include it `[S]`
  *(2026-08-20: `COST_THUMBNAIL_PER_IMAGE` default $0.045; Pillow / no image = $0; TTS re-merge does not drop a stored thumbnail line)*
- [x] 67. TTS **provider experiment arm** (ElevenLabs vs Piper) on engaged-rate, same Bayesian gate as `hook_style` — the $0 flip is currently a taste judgment `[M]`
  *(2026-08-20: **report-only** — `ops tts-arms`; same Bayesian gate; never writes
  experiments.json; never auto-assigns Piper / never changes TTS_PROVIDER)*
- [x] 68. **Apify monthly true-up** — $0.02/run model vs the actual invoice; twitter already proved billed-for-nothing `[S]`
  *(2026-08-20: synthetic fixture `tests/fixtures/apify_invoice_synthetic.json`; no
  network, no real invoice, no secrets; `ops apify-trueup`)*
- [x] 69. **Subscription utilization** dashboard — ElevenLabs / Apify / YouTube / Brave unused quota as allocated $/video (generalizes item 4 of the next-5) `[S]`
  *(2026-08-20: `ops reliability` Utilization section; ElevenLabs leftover chars × plan rate; Apify cached limit; YouTube uploads left; Brave has no usage counter yet)*
- [x] 70. **Electricity / GPU-hour** line once CUDA torch is on — MusicGen/Comfy/XTTS meter $0 in `cost_meter` but not on the 4070 Ti power bill `[S]`
  *(2026-08-20: Windows-safe `core/cuda_probe.py` readiness only — no pip install,
  no CUDA download; `COST_GPU_HOUR_USD` stays 0 until CUDA torch is actually on;
  wired into `ops doctor`)*
- [x] 71. **TTS cache by script hash** — never re-synth the same script on a re-render (operating_plan §4 item 3) `[S]`
  *(2026-08-20: hash of spoken text + provider + voice; copies `.words.json` sidecar; cache hit meters TTS $0; `TTS_CACHE` opt-in so unittest discover cannot write `data/tts_cache`)*
- [x] 72. **Skip web-search** when vault + RSS already clear a density bar — Tavily/Brave $0.008 is small; the round-trip and junk-line risk are not `[S]`
  *(2026-08-20: vault distinctive facts only — no extra RSS HTTP and no cache-stat probes; default 6; 0/off disables; skip is in `register_signals` orchestration, not a second signal cache)*
- [x] 73. **Justify or `enabled: false` the remaining Apify tier** (`tiktok_trends` + `youtube_competitors`) — only two paid actors left; RSS + Data API may already cover them `[M]`
  *(2026-08-20: same `ops paid-signals` report; `disable` is a recommendation at
  n>=5 per arm, never an `apify_sources.json` write)*
- [x] 74. **Pillow-first thumbnail** until report-card ≥ B — don't pay an image API for a draft that fails authenticity `[S]`
  *(2026-08-20: `THUMBNAIL_MIN_GRADE=B`; missing letter fail-opens to the current Flux path; C/D/F skip paid APIs)*
- [x] 75. **Hard character cap before TTS** — Extended is a cost multiplier; clip the script (or refuse the preset) rather than regen-then-pay `[S]`
  *(2026-08-20: refuse, do not clip; default `TTS_MAX_CHARS=5000` ≈ Long; 0/off disables; `--force` / interactive y)*
- [x] 76. Surface **"this run escaped free-first LLM"** — O5 failover can land on a paid slug with no operator-visible flag `[S]`
  *(2026-08-20: usage record + cost line `! escaped free-first LLM` + reliability; pinned provider never flags)*
- [x] 77. Cap `output/` **by gigabytes**, not just file count — artifact retention (#31) is hygiene; this is SSD / backup cost `[S]`
  *(2026-08-20: `ops artifacts`; `OUTPUT_MAX_GB` / `OUTPUT_MAX_FILES`; dry-run
  default, `--apply` deletes oldest; never touches `data/`)*

Future viability — stay a media OS, not a GPT-wrapper that the platforms replace

- [x] **78. Intelligence-report SKU** *(2026-08-21)* — `ops intelligence-report --sku` (research + competitor pulse + authenticity notes, **no video / no TTS**) `[M]`
- [ ] 79. **Affiliate / Benable spike with a kill criterion** (2 weeks, drop if video→click→sale cannot close) — vision.md Phase G; non-ad revenue on a low-CPM niche `[L]`
- [x] 80. **YouTube inauthentic-content help-page hash canary** — weekly fetch; alert when the existential constraint moves `[S]`
  *(2026-08-20: `ops policy-canary` hashes a local fixture; reliability reads the
  snapshot only — no HTTP; `POLICY_CANARY_FETCH` opt-in for a live fetch)*
- [x] 81. **Cross-channel prior for MoneyWise cold-start** — a new channel has n=0; don't wait for 15 measured videos to recommend anything (vision challenge #6) `[M]` — shipped 2026-08-26; copies TapIn length/slot *shape* with `source=cross_channel_prior`, never gaming topics or `domain_slots`. MoneyWise's own n stays `analytics`
- [ ] 82. Optional **2-second operator-on-camera sting** (real face, fail-open) — 2026 policy punishes synthetic-and-shallow; this is cheaper than the GPU avatar stack and is not avatar mode `[M]`
- [ ] 83. **Holdout videos** (recommender off, one per N publishes) — without this the learning loop learns superstitions (vision challenge #2) `[M]`
- [x] 84. **RPM × cost by domain** — UFC vs GTA vs NBA contribution margin decides what TapIn should actually be; views-by-domain already exist `[S]`
  *(2026-08-20: `ops economics` adds RPM x cost by domain from `features.domain`)*
- [x] 85. **Weekly moat backup** — `pg_dump` + vault + `data/traces` (encrypted secrets excluded); the dataset *is* the company (operating_plan §7) `[S]`
  *(2026-08-20: `ops moat-backup` dry-run plan; `--apply --file dest` copies traces/vault;
  `.env` / `config/secrets/` / `quota_state.json` excluded; pg_dump is listed not executed)*
- [x] 86. **Prompt-eval as a CI regression** on one frozen golden topic per channel — a prompt edit that increases ungrounded claims fails the job `[M]` — shipped 2026-08-26; `config/prompt_eval_goldens.json` + heuristic `score_script` (no LLM judge)
- [x] 87. **YPP / membership readiness checklist** — watch-hours, disclosure, cadence headroom; description CTAs exist, the unlock path does not `[S]`
  *(2026-08-20: `ops ypp`; fail-open without metrics; hours OR Shorts-views path)*
- [x] 88. **Competitor-sync daily YouTube-unit cap** — competitor genome will eat the 10k/day budget (vision challenge #4); hard ceiling before "more intelligence" `[S]`
  *(2026-08-20: RSS still free; API fallback capped (`COMPETITOR_SYNC_MAX_UNITS=30`)
  and reserves one upload (`COMPETITOR_SYNC_RESERVE_UNITS=1600`); 0/off = unlimited)*
- [x] 89. **Public-safe dossier redaction** — if #78 is sold, vault notes must not leak operator facts, unpublished scripts, or key material `[M]` — shipped 2026-08-26; `redact_for_public` + SKU/export; unpublished dossiers withhold the script and persist pre/post line counts (§25)
- [x] 90. Overnight **never auto-renders** unless a human ran `main.py` / `ops` in the last 24h — autonomy vs the 2026 policy gate (vision challenge #5); drafts stay safe `[S]`
  *(2026-08-20: `HUMAN_PRESENCE_HOURS` opt-in, empty/0/off = disabled; overnight /
  daily-sync / worker do not stamp the heartbeat; drafts unchanged)*

**Candidates 91–140 (2026-08-20 late — any-way, Phase M still parked)**

*Brainstorm. Rationale: [planning_log.md](planning_log.md) 2026-08-20 late.
None restates Next-up, the morning 20, or candidates 21–90. Volume-gated
backtest, the $0 TTS voice judgment, and TikTok/Reels publishers stay out.
Pickup order for the 2026-08-20 late-night follow-on was remaining evening `[S]`
after the night wave (58/59/60/62/64/69/71/72/74/75). This 91–140 list is still
not a new sequence.*

Machine / Windows hygiene

- [x] 91. Disk-space preflight before ffmpeg (fail with GB free, not a half-written mp4) `[S]`
  *(2026-08-20: `DISK_MIN_FREE_GB` opt-in; missing `disk_usage` fail-opens; ASCII `>=`)*
- [x] **92. Windows MAX_PATH / long output paths** *(2026-08-21)* — clip filenames + optional `\\?\` prefix `[S]`
- [x] **93. FFmpeg file-lock retry** *(2026-08-21)* — Defender WinError 32 on encode + intro replace `[S]`
- [x] **94. NVIDIA driver + NVENC capability probe** *(2026-08-21)* — `ffmpeg -encoders` lists `h264_nvenc`; doctor check; does not encode `[S]`
- [x] **95. RAM/VRAM preflight** *(2026-08-21)* — `RAM_MIN_GB` / `VRAM_MIN_GB` opt-in before whisper / local TTS; ASCII `>=` `[S]`
- [x] **96. `ops secrets-doctor`** *(2026-08-21)* — keys present/missing/placeholder; values never printed `[S]`
- [x] **97. Redact API bodies from traces** *(2026-08-21)* — 402/403 payloads stripped on write `[S]`
- [x] 98. `pip-audit` in CI *(2026-08-22)* - report-only job + `[dev]` pin. **Pillow==11.3.0 / requests==2.32.4 / moviepy dropped 2026-08-26** (`AudioFileClip.duration` → existing `_probe_video_duration`). Re-run pip-audit on the new pins before treating the baseline as closed.
- [x] 99. Close the suite’s live Google HTTPS leak (audit C9 `ResourceWarning`) `[M]`
  *(2026-08-20: skip YouTube warmup in tests; `static_discovery=True` on `build()`;
  `CONTENT_FORBID_LIVE_YOUTUBE` blocks Data/Analytics clients and OAuth refresh;
  suite also forces `YOUTUBE_ANALYTICS_SYNC=false` so operator .env cannot leak)*
- [x] **100. OneDrive / `.git` hazard** *(2026-08-21)* — doctor check; operating_plan §7 `[S]`

YouTube surface (still YouTube-only)

- [x] 101. Upload a caption *track* (not only burned) — accessibility + search `[S]` — shipped 2026-08-26; `captions.insert` on the publish path, fail-open if no sibling/explicit .srt
- [x] **102. Auto-set YouTube category from `infer_domain`** *(2026-08-21)* — Sports 17 / Gaming 20 / finance 25 `[S]`
- [x] **103. Description sources block** *(2026-08-22)* — vault `source_url` + pasted http(s); `DESCRIPTION_SOURCES` `[S]`
- [ ] 104. Playlist-per-franchise via Data API (GTA, UFC cards) `[M]`
- [x] 105. Pin a comment that answers the top `youtube_comments` question `[S]` — shipped 2026-08-26; opt-in `YOUTUBE_PIN_COMMENT`; Data API has no pin, so this posts a channel `commentThreads.insert`. Profanity filter stays in front
- [x] 106. Detect Studio-deleted videos and cancel `publish_log` (re-queue path exists; detection does not) `[S]` — shipped 2026-08-26; `ops studio-deleted` + `daily_sync` hook; mocked `videos.list`
- [x] **107. `madeForKids=false` audit** *(2026-08-21)* — forced False on every insert `[S]`
- [x] **108. Default language + audio language** *(2026-08-21)* — `YOUTUBE_DEFAULT_LANGUAGE` (default `en`) `[S]`
- [x] **109. Unlisted review before public** *(2026-08-21)* — immediate public held as unlisted (`YOUTUBE_UNLISTED_REVIEW`) `[S]`
- [x] 110. Chapter timestamps for Extended `[S]`
  *(2026-08-26: `0:00` beat labels from the script; Shorts skip)*
- [ ] 111. End-screen / cards pointing at the previous franchise video (YouTube API) `[M]`
- [x] 112. **Correction dossier when post-publish facts reverse** *(2026-09-09)* - `core/correction_dossier.py`, wired into `ops corrections` and the overnight chain. Walks `publish_log.list_timed_outcomes` joined to its content run, rather than `last_trace` (one draft) as #341/#686 did. Needed three substrate fixes first, each of which had been shipping empty: `ClaimVerification.to_dict()` dropped the claim list and every `citation_line`; nothing ever set `features["source_urls"]` although `collect_source_urls` was already computed and then discarded; and `<stem>.facts.json` reads exactly those two keys, so every render wrote an empty claims and sources list. Writes a vault dossier (video, claim, changed evidence, severity, suggested correction, status) and auto-records a negative fact, which is what actually stops the claim being repeated. Never touches the published video `[M]`

Content / learning

- [ ] 113. Prediction ledger — persist “we called X” vs later outcome `[M]`
- [ ] 114. Audience-question series: cluster `youtube_comments` across runs into a mailbag `[M]`
- [x] **115. Don’t publish during a live UFC PPV window** *(2026-08-21)* — Sat 21:00–02:00 ET; UFC topics only; bumps `publishAt` `[S]`
- [x] **116. Blackout / quiet-hours calendar in `channels.json`** *(2026-08-21)* — TapIn + MoneyWise 1–8 ET `[S]`
- [x] **117. Title uniqueness vs own catalog** *(2026-08-21)* — `TITLE_UNIQUENESS=warn|block|off` `[S]`
- [x] **118. Description first-line SEO** *(2026-08-21)* — prepend title when first line is hashtags / Subscribe `[S]`
- [ ] 119. Stock-clip **watermark detector** — skip footage that shows another channel `[M]` *(only if stock remains; §26 prefers dropping stock over policing it)*
- [ ] 120. Embedding / CLIP b-roll match vs keyword stock search `[L]` *(only if stock remains — §26: more APIs are not a quality upgrade; owned gameplay first)*
- [x] **121. Stock query rewriter: never Pexels-search trademarked “UFC”** *(2026-08-21)* — rewrite to `mma` `[S]`
- [x] **122. `license.yaml` beside local clips** *(2026-08-25)* — inherited nearest-folder metadata reaches the persisted local-asset attribution; root file records owned/commercial use `[S]`
- [x] 123. Number/SSML reading rules (`29-1`, UFC 317, `$50k`) — distinct from the name lexicon `[M]`
  *(2026-08-26: TTS path only; captions keep digits)*
- [x] 124. Pause-after-hook: 200–400ms silence after line 1 `[S]` — shipped 2026-08-26; 250ms after first-line timings; skip is byte-identical argv/audio (same honesty as #24/#26)

Legal / policy / MoneyWise (not Phase M, not the #79 spike)

- [x] **125. MoneyWise finance disclaimer** *(2026-08-21)* — description line, separate from AI disclosure `[S]`
- [x] **126. Odds-derived scripts must say “market”, never “will”** *(2026-08-21)* — odds-context only; `is favored to` `[S]`
- [x] **127. Gambling/odds advertiser-safe mode** *(2026-08-21)* — strip bet-now / parlay CTAs `[S]`
- [x] **128. FTC affiliate disclosure *line*** *(2026-08-21)* — copy when `monetization_cta` is set; #79 is the tracking spike `[S]`
- [x] **129. UFC/trademark title linter** *(2026-08-21)* — warns `UFC` on a non-UFC topic `[S]`
- [ ] 130. Right-of-publicity: refuse stock thumbs that look like a real fighter’s face `[M]`
- [x] 131. Demonetization detector (`estimatedRevenue` cliff vs channel baseline) `[S]`
  *(2026-08-26: `ops demonetization`; missing revenue is unmeasured, not zero)*
- [x] 132. Policy-incident runbook (strike / Content ID / appeal template in-repo) `[S]`
  *(2026-08-26: `ops policy-runbook` prints `docs/policy_incident_runbook.md`)*

Operator product

- [x] 133. `.ics` calendar of scheduled publishes `[S]` — shipped 2026-08-26; `ops publish-ics` writes beside HTML dumps (`html_dir()`), not under `data/`
- [x] 134. n8n/email recipe for `weekly-report` (events exist; this is the recipe) `[S]`
  *(2026-08-26: `workflows/n8n/weekly_report.json` cron → `ops weekly-report`)*
- [x] **135. CSV export of `ops economics`** *(2026-08-21)* — `--csv` beside HTML dumps, not under `data/` `[S]`
- [x] 136. Vault Dataview-friendly dossier frontmatter `[S]`
  *(2026-08-26: `channel` / `run_id` / `grade` / `published` via real parser)*
- [x] 137. Wiki-links between related `_runs/` dossiers `[S]`
  *(2026-08-26: previous same-franchise stem `[[…]]` on write)*
- [ ] 138. Long-form length preset that is **not** a Short (16:9 sibling already exists) `[M]`
- [x] 139. Channel trailer / handle / banner checklist inside `channel-go-live` `[S]`
  *(2026-08-20: banner file + `youtube_handle` + trailer id/file; MoneyWise banner
  passes, handle/trailer still FAIL)*
- [x] 140. YouTube quota-increase request playbook (when 10k/day is the ceiling) `[S]`
  *(2026-08-26: `quota_increase_advice` next to uploads-left when one upload cannot fit)*

**Candidates 141–320 (2026-08-20 late-night brainstorm — UI / app / aesthetics / sibling software)**

*Brainstorm. Rationale: [planning_log.md](planning_log.md) 2026-08-20 (late-night
brainstorm). Exactly **5 `[XL]` / 25 `[L]` / 50 `[M]` / 100 `[S]`**. None restates
a shipped checkbox, Next-up, or candidates 1–140 unless reframed as a **new
product** (called out). Phase M, the volume-gated backtest, and the $0 TTS voice
judgment appear only as **PARKED** massive/larger. Evening recommended next 5
stay shipped; **Brainstorm next-5 (UI/app)** = 221, 222, 223, 224, 171.
**The post-wave-4 pickup shipped 2026-08-25:** 313 pause-overnight, 282
last-seen, 308–310 ffmpeg dump, 232 booth `.lnk`, 122 `license.yaml`. This
141–320 list is not a sequence and is not rewritten here.
Honest constants: TTS ~91% of a rendered run; YouTube upload ≈ 1,600/10k;
remaining paid Apify = `tiktok_trends` + `youtube_competitors`; Windows;
unittest; no second signal cache; breakers via `quota_governor` only.*

Massive — new product surfaces / years of work / could be different software

- [ ] 141. **Content OS Desktop** (local-first Tauri/WinUI console over `core/`) `[XL]` — *new-app.* Years of UX/packaging; Python stays the engine; never a second signal cache or a breaker bypass.
- [ ] 142. **Shorts Visual Studio** (caption/type/motion/thumbs/brand as a studio) `[XL]` — *aesthetics.* Sibling design product beside the CLI; not candidates 21–28 (those are flags).
- [ ] 143. **Portfolio Intelligence Web OS** (vision v3, multi-channel margin) `[XL]` — *viability.* Honest: premature as SaaS until the YouTube-only data moat is real; still the 12-month architecture, not a CLI restyle.
- [ ] 144. **PARKED — Distribution Sidecar** (TikTok/Reels as different software) `[XL]` — *new-app / parked.* Phase M consumes already-rendered 9:16; never Content Machine feature flags; not the next pickup.
- [ ] 145. **Moat Suite** (Vault Companion + Clip Librarian + Cost Tower) `[XL]` — *new-app / cost.* Sibling apps over vault, clips, and `quota_governor.snapshot()`; the dataset *is* the company.

Larger — multi-week systems

- [ ] 146. Windows **system-tray daemon** wrapping worker + overnight `[L]` — *new-app.* Overnight is a forgotten PowerShell window today.
- [x] 147. **Localhost FastAPI operator shell** *(2026-08-28)* — `core/operator_shell.py` + `ops shell`, bound to `127.0.0.1` and default off. GET-only over the gatherers that already exist (`/booth`, `/reliability`, `/doctor`, `/next`, `/status`) — no second cache, no spend, and `POST /` returns 405. Driven for real through `TestClient`; the `shell` extra is also in `[dev]` so CI can import it. Thin slice: not #141 Desktop, not a tray daemon, and the stdlib `ops booth --serve` still exists `[L]`
- [x] 148. **Job-queue visualizer** with drag-reorder *(2026-09-08)* — `list_active_jobs` over the existing job repo (pending/running/failed). Labels `render` / `upload` / `awaiting_quota` when pending and `"quota" in last_error`. `QueueWindow` + `ops queue-panel` / `py -m desktop --queue`. Drag writes `payload_json.sort_key`; `claim_next` orders by that key then `id`. No Alembic column. Missing PySide6: refuse, exit 2 `[L]`
- [ ] 149. **Analytics Studio** (retention / CTR / RPM local web) `[L]` — *viability.* Weekly-report ASCII cannot show curves; still honest that n≈10 is thin.
- [x] 150. **TapIn vs MoneyWise visual language packs** *(2026-09-07)* — Stage 2 QSS from #170 tokens. TapIn header `#E53935` vs MoneyWise `#81C995`; serif on MoneyWise. Fail-first: empty `styleSheet()` `[L]`
- [x] 151. **Brand-kit compiler** *(2026-09-09)* - `core/brand_kit.py` `compile_kit()` resolves design_tokens.json + channels.json + assets/branding/<channel>/ into one `BrandKit` carrying per-field provenance and a `missing` list; `channel-go-live`'s `brand_kit` check now reports kit status instead of running `os.path.isfile` over two filenames. `ops brand-kit` prints it, `ops brand-panel` / `py -m desktop --brand` shows it with swatches. Deliberately a READ path: values are pinned field-by-field against today's accessors and the renderer is NOT re-routed through it, because a compiler that quietly restyles finished video is the undisclosed-output defect rather than a fix. Found on the way: `assets/branding/tapin/` does not exist (#708) `[L]`
- [x] 152. **Thumbnail composition canvas** mechanical slice *(2026-09-08)* — `QGraphicsView` + last thumb + `inspect_thumbnail` overlay. `ops studio` / `py -m desktop --studio`. Missing PySide6: refuse, exit 2, no WARNING. Drag/snapping shipped as #692 `[L]`
- [x] 153. **Caption choreography timeline** *(built and RETIRED 2026-09-09)* — Retired by operator decision 2026-09-09: "i dont need to see the caption timing, i dont want to do that manually." Captions still come from real `.words.json` word timings, which predates this item and is untouched -- measured: the karaoke ASS for a tapin sample is byte-identical before and after removal (sha256 4ddd7116...), because with no edits sidecar the whole feature was a no-op. Removed `core/caption_timeline.py`, `desktop/captions.py`, the ops captions verb, the ops caption-timeline verb, `py -m desktop --captions`, the `apply_caption_edits` hook in `video/subtitles.py` and the now-dead `margins` parameter on `build_ass_karaoke`. `[L]`
- [ ] 154. **MSIX / Inno installer** bundling Python + ffmpeg + tray `[L]` — *new-app.* Packaging is what makes #141 software instead of a repo.
- [ ] 155. **MCP + local plugin API** over `core/` `[L]` — *new-app.* Agents scrape CLI today; contract must not add a signal cache or skip `quota_governor`.
- [ ] 156. **Vault Companion** (Obsidian-lite for facts / playbooks / dossiers) `[L]` — *new-app.* Pillar 4 dumps markdown; tier/expiry UX is sibling software.
- [ ] 157. **Clip Librarian** (search, license, anti-repeat, performance) `[L]` — *new-app.* Distinct from shipped clip-memory deque and from #120 CLIP match.
- [x] 158. **Cost Control Tower** (TTS 91% / two Apify actors / YouTube units) `[L]` — *cost.* *(2026-09-12)* Core slice in wave 9 (`core/cost_tower.gather_tower()` + `ops cost-tower`); panel in wave 10: `desktop/cost.py` `CostWindow` (Lane / Item / Used-Limit / State / Resets, note as tooltip, Refresh re-reads the stores), `ops cost-panel` / `py -m desktop --cost`. Shares `cost_tower.amount_text` with the ASCII tower, so UNKNOWN renders `?`, never `0`.
- [ ] 159. **MoneyWise earnings-floor board** (calendar/ticker UI) `[L]` — *UI / viability.* Distinct from Next-up MoneyWise *depth signals*: a board, not new APIs.
- [ ] 160. **Legal / disclosure review wizard** (AI, finance, FTC, trademark) `[L]` — *viability.* Distinct from #125–129 copy lines: a publish-blocking UX.
- [ ] 161. **Publish calendar GUI** (week view + overlays) `[L]` — *UI.* Distinct from #133 `.ics` export: a visual week, not a file dump.
- [ ] 162. **Experiment cockpit** over `experiments.json` `[L]` — *viability.* TTS arms are report-only; this UI still must not auto-assign Piper.
- [ ] 163. **Script desk** with grounding heat-map `[L]` — *UI / viability.* Numeric/record + claim verifier already compute; painting the script is the surface.
- [ ] 164. **Overnight factory monitor** (gates, progress, human-presence) `[L]` — *UI.* Overnight + render-gate + heartbeat shipped; watching them is still log-tailing.
- [ ] 165. **Notification center + DND** (history, quiet hours, click-through) `[L]` — *UI.* Broader than a single toast (#221): Action Center as a product slice.
- [ ] 166. **PARKED — Voice Judgment Booth** (Piper vs ElevenLabs A/B ears) `[L]` — *cost / parked.* Captions unblocked the $0 path; this booth never auto-flips `TTS_PROVIDER`.
- [ ] 167. **PARKED — Recommender Backtest Studio** `[L]` — *viability / parked.* Next-up backtest stays volume-gated; the studio must refuse to fit before n is honest.
- [x] 168. **Unlisted review room** *(2026-09-07, first Stage 3 panel)* — `ops review-room` / `py -m desktop --review` paints `gather_booth_context` (grade, authenticity, cost, last mp4). Approve runs the same `requeue-upload` string the HTML booth already prints. `ops booth` remains. CI constructs the window offscreen without decoding video. Live last-run play is still operator smoke (#684) `[L]`
- [ ] 169. **Channel Command Center v1** as a local single-operator app `[L]` — *new-app.* Reframe of deferred "full operator dashboard": local, no SaaS billing — first slice of #141.
- [x] 170. **Design-token pipeline** *(2026-09-07)* — `config/design_tokens.json` is what `themes.role_color` and `caption_fill_hex` both read. Shipped tapin `#FFFFFF` / moneywise `#F7E7A9`. Stage 0 `ask()`/`emit()` shipped the same wave `[L]`

Moderate — days

- [x] 171. **Last-run review booth** *(2026-08-21)* — `ops booth` (play / grade / authenticity / Approve; stdlib HTML, not FastAPI) `[M]` — *UI / new-app.* **Brainstorm next-5.** Last render only; not #168.
- [x] 172. Operator **HTML design system** *(2026-09-07)* — `themed_css()` generated from `design_tokens.json` (comment stamped in the page). Booth widget CSS stays as layout, not a second palette `[M]`
- [x] 173. Per-channel **GUI chrome** *(2026-09-07)* — `RunWindow._apply_look` swaps QSS on the shipped channel combo. Token borders disagree `[M]`
- [ ] 174. Windows **jump list** for last five drafts `[M]` — *new-app.* Taskbar right-click → open mp4 / booth, no console.
- [ ] 175. **Command palette** over `ops` subcommands `[M]` — *UI.* ~38 commands are unlistable from memory; palette is not a rewrite of `ops.py`.
- [ ] 176. Dark-mode **dossier HTML viewer** `[M]` — *UI.* Vault `_runs/` in the browser; does not change dossier schema.
- [ ] 177. Dual-channel **status wall** (TapIn | MoneyWise) `[M]` — *UI.* Two-pane health/quota/cadence; MoneyWise go-live FAILs stay visible.
- [ ] 178. **Render-progress pane** (ffmpeg % as a UI, not a spinner) `[M]` — *UI.* `CONTENT_RENDER_PROGRESS` exists; this is a window the operator can glance at.
- [ ] 179. **Authenticity visual checklist** (variation / insight / substance) `[M]` — *viability / UI.* Policy gate as boxes, not a log line.
- [ ] 180. **Report-card poster** layout (letter + cost subtitle) `[M]` — *aesthetics.* A–F as a designed artifact for review, not ASCII.
- [ ] 181. Thumbnail **A/B click-picker** that logs the experiment arm `[M]` — *UI.* Distinct from #27 dual *generation*: pick between already-rendered thumbs.
- [x] 182. **Caption overlay on a still** *(2026-09-06)* — `ops caption-still --path --file` writes `{stem}_captions.png` via Pillow + `split_script_into_lines` + shipped `caption_skin.fill_color`. Test: compositor output contains `Salkilld`, not a helper-exists assertion `[M]`
- [x] 183. **Font-pairing picker** *(2026-09-07)* — shipped `caption_skin.title_font`/`body_font`; ASS Style Title then Body. tapin Impact/Arial, moneywise Georgia/Arial `[M]`
- [x] 184. Named **motion-style presets** *(2026-09-07)* — `punch-in` vs `snap-zoom` distinct zoompan strings; `enabled: false` still `""` (same #26 contract) `[M]`
- [x] 185. Caption-vs-background **contrast auditor** *(2026-09-06)* — `inspect_caption_band` WCAG ratio vs shipped `caption_skin.fill_color`; AA 4.5:1. Wired like thumbnail safe-area (operator string + pipeline note). **Advisory only; `GRADE_VERSION` stayed v3** `[M]`
- [x] 186. Player **safe-title grid overlay** *(2026-09-08)* — `safe_title_rects` bottom 20% chrome on the review player and studio still. Distinct from #22 PIL checker `[M]`
- [x] 187. **End-card preview compositor** *(2026-09-07)* — `ops end-card-preview --path` Pillow still from shipped `resolve_end_card`. Disabled card raises. Usage without `--path` prints the require line `[M]`
- [x] 188. **Intro-sting waveform** *(2026-09-07)* — `ops intro-waveform --path`; missing file refuses with `not found`, no WARNING. Offset is `DEFAULT_INTRO_DURATION` (2.15s), not a live probe `[M]`
- [ ] 189. Brand-kit **screenshot linter** (banner vs in-video palette) `[M]` — *aesthetics.* MoneyWise handle/trailer already FAIL; this diffs colors, not file presence.
- [x] 190. MoneyWise **on-screen disclaimer** *(2026-09-07)* — ASS burn via `build_policy_overlays_ass` with shipped channel config. MoneyWise contains “Not financial advice”; TapIn argv/ASS does not `[M]`
- [x] 191. **AI-disclosure lower-third** *(2026-09-07)* — same ASS path; `AI_DISCLOSURE_ENABLED=false` omits “Made with AI”. Description extras stay a separate path `[M]`
- [ ] 192. **YPP progress UI** (`ops ypp` as a designed page) `[M]` — *viability / UI.* Checklist exists as ASCII; hours-or-Shorts-views needs a bar.
- [ ] 193. **Utilization rings** (ElevenLabs / YouTube / Apify leftover) `[M]` — *cost / UI.* Utilization section shipped; rings are the graphic.
- [ ] 194. Allocated-vs-marginal **waterfall chart** `[M]` — *cost.* ~$0.31 metered vs ~$1 allocated at 21/90 Creator-plan videos — picture, not two lines.
- [ ] 195. **Paid-signal sparklines** (`tiktok_trends` / `youtube_competitors` only) `[M]` — *cost.* Attribution report exists; this is the two-actor chart.
- [ ] 196. **Incident timeline UI** `[M]` — *UI.* `ops incidents` ranks count/(1+days); a timeline is the missing surface.
- [ ] 197. **Feed-health widget** (ok/stale/dead) `[M]` — *UI.* `ops feeds` is ASCII; Tapology-class silent death needs a traffic light on a wall.
- [x] 198. **Doctor HTML page** *(2026-08-21)* — `ops doctor --html` (CUDA / oauth / feeds / quota) `[M]` — *UI.* Still no pip install, still no secrets.
- [ ] 199. Pre-run gate as a **blocking modal** `[M]` — *short-term / UI.* Run-70 class: do not start discovery behind a wall of logs.
- [x] 200. **Thin-facts abort screen** *(2026-08-21)* — dedicated HTML when the TTS abort fires `[M]` — *cost / UI.*
- [ ] 201. Script **character-cap meter** while editing `[M]` — *cost / UI.* `TTS_MAX_CHARS` refuses; a meter would have shown Extended as a cost multiplier.
- [ ] 202. ElevenLabs **leftover-chars fuel gauge** `[M]` — *cost.* Governor is opt-in; the gauge is how the operator sees 100k/month burn down.
- [ ] 203. **Uploads-left fuel gauge** (1,600 units) `[M]` — *cost / UI.* Startup line exists; a gauge belongs on tray + booth.
- [ ] 204. RPM × cost by domain as **small-multiples** `[M]` — *cost / viability.* Domain lines shipped in `ops economics`; UFC vs GTA vs NBA needs charts.
- [ ] 205. **Human-presence indicator** in the tray `[M]` — *UI.* Heartbeat is opt-in; overnight must show "human last seen" without opening a log.
- [ ] 206. Render-queue **skip explanation card** `[M]` — *UI.* Grade/authenticity gate shipped; overnight skipped-why is currently tribal knowledge.
- [ ] 207. **Metrics-before-next lock screen** `[M]` — *viability / UI.* Opt-in gate shipped; a lock screen is why the learning loop actually waits.
- [ ] 208. Unlisted vs public **toggle in the booth** `[M]` — *UI.* Distinct from #109 implementing unlisted upload: this is the control chrome.
- [x] 209. **Keyboard-first review** *(2026-09-07)* — J back 5s / K pause-play / L forward in `core/review_keys.py`. `ReviewWindow.keyPressEvent` calls it. Helper is tested without Qt or a decode `[M]`
- [ ] 210. **Windows Hello** before marking public `[M]` — *viability / UI.* Accidental public is a 2026-policy event; biometric confirm, fail-open if Hello absent.
- [ ] 211. **Channel-picker overlay** (no `.env` editor) `[M]` — *UI.* Switch tapin/moneywise without teaching dotenv; never show secrets.
- [ ] 212. **Secrets-present dots** (never values) on a status strip `[M]` — *viability / UI.* Distinct from #96 secrets-doctor: display-only dots.
- [ ] 213. Trace **timing waterfall** (phases from existing traces) `[M]` — *UI.* Traces already on disk; twitter-class 32s floors should be a picture.
- [ ] 214. **Postmortem HTML one-pager** `[M]` — *UI.* `ops postmortem` shipped; a designed page is what you paste into a chat.
- [ ] 215. Weekly-report **magazine layout** `[M]` — *aesthetics.* Analyst markdown exists; this is typeset HTML, not a new agent.
- [ ] 216. Dossier reader with **run-id search** `[M]` — *UI.* Stable `{run_id}_{slug}.md` shipped; search is the missing index UI.
- [ ] 217. **Pronunciation lexicon editor** `[M]` — *cost / UI.* `config/pronunciations.json` shipped on the local TTS path; no UI to add "Salkilld".
- [ ] 218. Clip-memory **filmstrip** `[M]` — *aesthetics / UI.* Anti-repeat deque shipped; pictures of recent backgrounds are the point.
- [ ] 219. **LUFS meter graphic** `[M]` — *aesthetics.* `LUFS_NORMALIZE` opt-in shipped; a meter shows whether the toggle mattered.
- [ ] 220. MCP **plugin-settings pane** (read-only first) `[M]` — *new-app.* Companion to #155: what tools are exposed, none that write `quota_state`.

Small — hours / a PR

- [x] 221. Windows **toast when ffmpeg finishes** *(2026-08-21)* `[S]` — *UI / short-term.* **Brainstorm next-5.**
- [x] 222. System-tray **quota chip** *(2026-08-21)* — `ops tray` (uploads-left + TTS chars + Apify breaker) `[S]` — *cost / UI.* **Brainstorm next-5.**
- [x] 223. `ops reliability --html` themed snapshot *(2026-08-21)* `[S]` — *UI.* **Brainstorm next-5.** Zero new backend.
- [x] 224. **Thumbnail lightbox** *(2026-08-21)* — `ops lightbox` for the last Pillow thumb `[S]` — *cost / aesthetics.* **Brainstorm next-5.**
- [x] **225. Toast on upload scheduled / `publishAt`** *(2026-08-21)* `[S]` — *UI.*
- [x] 226. Toast when a **breaker trips** *(2026-08-21)* (Apify / LLM / ElevenLabs / signals) `[S]` — *cost / UI.* Notify only.
- [x] **227. Toast when overnight finishes drafts** *(2026-08-21)* `[S]` — *UI.*
- [x] **228. Balloon: N uploads left this reset** *(2026-08-21)* — tray + `main.py` startup `[S]` — *cost / UI.*
- [x] **229. Click-toast opens last mp4** *(2026-08-21)* — protocol launch `file:` URI `[S]`
- [x] 230. Taskbar **overlay badge** (queue depth) *(2026-09-08)* — integer from `list_active_jobs`; tray prints `queue N`. Not a second store `[S]`
- [x] 231. Start-menu shortcut via **pyw** *(2026-08-21)* — `ops shortcut` + `content_os.pyw` `[S]` — *new-app.*
- [x] **232. Desktop `.lnk` to the review booth** *(2026-08-25)* — `ops booth-shortcut` targets a persistent `pythonw` launcher because the localhost port is ephemeral and a literal URL would be dead `[S]` — *new-app.*
- [ ] 233. Per-channel **notification sound** `[S]` — *aesthetics.* TapIn vs MoneyWise should not share one ding.
- [x] **234. High-contrast CSS for HTML reports** *(2026-08-21)* — `prefers-contrast: more` `[S]`
- [x] 235. TapIn **swatch strip** in HTML headers `[S]` — *aesthetics.* Channel color without a full language pack.
  *(2026-08-26: shipped `end_card` bg/fg; **2026-08-27:** `booth_html` / `ops --html` now pass `channel_id`, so the swatch actually appears on the booth)*
- [x] 236. MoneyWise **serif header** on HTML reports `[S]` *(2026-08-27)* — Georgia on `body.channel-moneywise header h1`; `dump_pre` and the booth thread `channel_id`
- [x] 237. Favicon for localhost booth (channel mark) `[S]` — *aesthetics.* Browser tab literacy.
  *(2026-08-26: `rel="icon"` + `/favicon.svg` on `ops booth --serve`)*
- [x] 238. Local **poster image** for the review page `[S]` *(2026-08-27)* — `<video poster>` plus `.poster-chrome` from the last thumb; 9:16 stage, no network OG
- [x] 239. **Print stylesheet** for weekly-report HTML *(2026-09-07)* — `@media print` hides header/skip/swatch/wordmark; `main`/`pre` stay. Screen CSS unchanged `[S]`
- [x] 240. `ops status --html` *(2026-08-21)* `[S]` — *UI.* Swap for skipped #147 FastAPI.
- [x] 241. `ops economics --html` *(2026-08-21)* `[S]` — *cost / UI.* Allocated vs marginal already in the command.
- [x] **242. `ops grade --html --run-id`** *(2026-08-21)* `[S]` — *UI.*
- [x] 243. Startup **PNG wordmark** *(2026-09-07)* — `CONTENT_UI_WORDMARK=1` injects `<img class='wordmark'>` into `themed_page`. Flag off: ASCII path byte-identical. Not painted in conhost `[S]`
- [x] 244. Windows Terminal **profile snippet** *(2026-09-07)* — `config/windows-terminal/profiles.json` schemes “Content OS TapIn” (`#0B0F14`) and “Content OS MoneyWise” (`#1B2430`). Pointer in `docs/startup-powershell.md`. Not auto-imported into WT `[S]`
- [x] 245. HTML **type pairing** (Segoe UI / JetBrains Mono) `[S]` *(2026-08-27)* — body stays Segoe UI; `pre` / `textarea.md` use JetBrains Mono
- [x] 246. Blurred **9:16 poster** as booth background *(2026-09-08)* — last thumb as `.poster-chrome` `backdrop-filter: blur`. No new ffmpeg `[S]`
- [x] 247. CSS **grain/vignette preview** toggle *(2026-09-07)* — `themed_css(grain=True, vignette=True)` emits `body.grain` / `body.vignette`. `CONTENT_UI_GRAIN` / `CONTENT_UI_VIGNETTE`. Default off. Does not change the render command (#512 does) `[S]`
- [x] 248. Caption **font specimen strip** *(2026-09-08)* — three faces from shipped `caption_skin` (tapin Impact/Arial + Segoe UI). Pick writes `font_pick.txt`, not `channels.json` `[S]`
- [x] 249. Title-card mock: **2-line vs 3-line wrap** *(2026-09-08)* — `wrap_title_card` + Pillow still via `ops title-card`. Does not write `channels.json` `[S]`
- [x] **250. ASCII-safe HTML** *(2026-08-21)* — emoji/smart-punct stripped (cp1252) `[S]` — *UI.*
- [x] **251. Copy-as-markdown on the report card** *(2026-08-21)* — booth textarea + `ops grade --md` `[S]`
- [x] **252. Copy last unlisted URL** *(2026-08-22)* — booth textarea + clipboard; prefers unlisted `[S]`
- [x] 253. **Reveal mp4 in Explorer** *(2026-08-21)* — `ops reveal` (`explorer /select,`) `[S]` — *UI.*
- [x] 254. **Reveal thumbnail in Explorer** *(2026-08-21)* — `ops reveal --kind thumb` `[S]` — *UI.* Bundled with #253 (swap leftover for skipped #147).
- [x] **255. Open dossier via Obsidian URI** *(2026-08-22)* — `obsidian://open`; fail-open when vault unset `[S]`
- [x] **256. Reveal trace JSON** *(2026-08-21)* — `ops reveal --kind trace` `[S]` — *UI.*
- [ ] 257. **Drag-drop facts `.txt`** onto the booth `[S]` — *UI / short-term.* Overnight still cannot take `key_facts=`; this is intake chrome only.
- [x] 258. Paste-facts textarea + **char meter** *(2026-09-07)* — meter uses live `operator_key_fact_char_budget()` (12000 default, not the retired 4500). `"3 / 12000 chars"` `[S]`
- [x] 259. HTML **channel switcher** (tapin / moneywise) *(2026-09-08)* — booth header links. Never an `.env` editor `[S]`
- [x] 260. Keyboard **`?` cheat-sheet** overlay *(2026-09-08)* — booth aside + review-room `?` copy for J/K/L `,` `.` S H `[S]`
- [x] **261. Skip-link a11y on the booth** *(2026-08-21)* — skip to `#player`; dumps skip to `#main` `[S]`
- [x] 262. HTML5 **captions from SRT** *(2026-08-25)* — stable render-side SRT is converted to WebVTT and attached as the booth player's default English `<track>` `[S]`
- [x] 263. Playback-rate **1.25×** toggle `[S]` — *UI.* Operator minutes.
  *(2026-08-26: booth buttons; default `playbackRate = 1`)*
- [x] 264. **Loop last 3s of hook** *(2026-09-08)* — `apply_review_key("h")` clamps position into `[0, 3000]` of the loaded clip. Not a re-render `[S]`
- [x] 265. **Frame-step** with `,` / `.` *(2026-09-08)* — one frame at 30fps (33ms), not the 5s J/L step `[S]`
- [x] 266. **Save current frame** as a still *(2026-09-08)* — `S` writes `html_dir()/stills`. PNG copy or ffmpeg frame. Not a thumbnail API `[S]`
- [x] 267. **9:16 letterbox** in a landscape window `[S]` *(2026-08-27)* — `.stage` with `aspect-ratio: 9 / 16` and `object-fit: contain`
- [x] 268. **Safe-area overlay toggle** (YouTube UI chrome) `[S]` *(2026-08-27)* — default off; `toggleSafeArea` adds `.safe-on`; not the #22 PIL test
- [ ] 269. **Burned vs sidecar** caption toggle `[S]` — *UI.* Compare retext vs proportional without re-encoding.
- [x] 270. **Waveform under the player** *(2026-09-08)* — `under_player_waveform` from existing wav/mp3 (ffmpeg to wav when needed). No new TTS spend `[S]`
- [x] 271. Spoken vs **estimated duration** readout *(2026-08-25)* — booth compares ffprobe duration of the persisted spoken-audio MP3 (not the intro-bearing MP4) with the persisted word count / measured 3.3 wps estimate `[S]`
- [x] **272. Cost subtitle under the player** *(2026-08-21)* — `tts $0.31 · 91%` on the booth `[S]` — *cost.*
- [x] **273. Escaped free-first LLM red pill** *(2026-08-21)* — booth reads `llm_calls[].escaped_free_first` `[S]`
- [x] **274. Thin-facts warning banner** *(2026-08-21)* — same gate as #200, one strip `[S]`
- [x] **275. Ungrounded numeric chips** *(2026-08-22)* — record/rank/purse/date as chips `[S]`
- [x] **276. Authenticity semantic-arm bar** *(2026-08-22)* — peak cosine as `authenticity_semantic`; warn at 45% `[S]`
- [x] **277. Report-card component breakdown** *(2026-08-22)* — hook / grounding / authenticity numbers on the booth `[S]`
- [x] **278. Standard-would-have-billed line on Free runs** *(2026-08-21)* — existing dry-run on the booth `[S]`
- [x] **279. Allocated vs marginal one-liner** *(2026-08-21)* — booth footer; no new economics engine `[S]`
- [x] **280. TTS cache-hit $0 pill** *(2026-08-22)* — booth reads post-render `tts_cached` `[S]`
- [x] **281. Pillow vs Flux thumb badge** *(2026-08-22)* — label from provider / thumbnail cost `[S]`
- [x] **282. Human-presence last-seen relative time** *(2026-08-25)* — real heartbeat age in the tray, with honest off/never states `[S]` — *UI.*
- [x] **283. Render-gate blocked reason** *(2026-08-22)* — `Overnight will not render: …` `[S]`
- [x] **284. RPM-cost-gate deferred reason** *(2026-08-22)* — `Deferred: …` when the opt-in gate fires `[S]`
- [x] **285. Yesterday unsynced copy** *(2026-08-22)* — informational even when `METRICS_BEFORE_NEXT` is off `[S]`
- [x] **286. Uploads-left in booth header** *(2026-08-21)* — same figure as the tray chip `[S]`
- [x] **287. ElevenLabs chars in booth header** *(2026-08-21)* `[S]`
- [x] **288. Remaining Apify actors as pills** *(2026-08-21)* — catalog-enabled only (`tiktok_trends`, `youtube_competitors`) `[S]`
- [x] **289. Last-run signal-health dots** *(2026-08-22)* — trace `signals[].status` as ok/warn/fail/skip `[S]`
- [x] **290. Feed-stale strip** *(2026-08-22)* — cached `ops feeds` snapshot; no HTTP `[S]`
- [x] 291. Set Windows **AppUserModelID** *(2026-08-21)* — toasts group as "Content OS" (`ContentOS.Operator`) `[S]` — *new-app.*
- [x] **292. Mute toasts during quiet hours** *(2026-08-22)* — `CONTENT_TOAST_DND`, resolved machine-level over every configured channel; breaker toasts bypass it via `urgent=True`. The first cut was inert (no channel → `default` → no `quiet_hours`) and its test mocked `quiet_hours_reason`, so CI never saw it; `tests/test_toast_dnd.py` now drives the clock against the shipped `channels.json` instead `[S]`
- [ ] 293. Prototype **`content-os://open-last`** protocol `[S]` — *new-app.* One verb; hours, not a plugin platform (#155).
- [x] 294. Explorer **"Send to" facts.txt** `[S]` — *UI.* Windows send-to shortcut; overnight `--facts-file` is now wired, this is the Explorer helper.
  *(2026-08-26: `ops sendto-facts`; tests use a temp SendTo dir)*
- [x] 295. **2×2 contact sheet PNG** of last thumbs *(2026-09-07)* — `ops contact-sheet --path` Pillow collage. Empty folder: `"no thumbnail files"` exit 1, no PNG. Live: 4 thumbs `[S]`
- [x] 296. **Print stylesheet** for the contact sheet *(2026-09-07)* — `contact_sheet_html` `@media print` hides header; type size from tokens. `ops contact-sheet` writes the sibling `.html` next to the PNG (#679) `[S]`
- [x] 297. Caption fill **contrast ratio number** vs sampled frame *(2026-09-06)* — same helper as #185 returns `ratio` + pass/fail. Not persisted on quality_json (no `QUALITY_VERSION` bump) `[S]`
- [x] 298. YouTube-title **100-char meter** *(2026-08-25)* — the real booth reads the stored public title and flags overflow `[S]`
- [x] 299. Description **first-line preview card** *(2026-08-25)* — the real booth reads the stored public description and shows only its first non-empty line `[S]`
- [ ] 300. Local **tag chips** (edit in booth, apply writes the package) `[S]` — *UI.*
- [x] 301. **Phone-bezel CSS** around the 9:16 player *(2026-09-08)* — `.phone-bezel` wraps the 9:16 stage `[S]`
- [x] 302. **YouTube chrome mock** (like/comment/subscribe) as an overlay *(2026-09-08)* — `.yt-mock` Like/Comment, distinct from #186/#268 boxes `[S]`
- [x] 303. Booth **theme toggle** *(2026-09-07)* — `themed_page(..., channel_id="moneywise")` header border is the MoneyWise token, not hardcoded TapIn `#c62828` `[S]`
- [x] 304. **Reduced-chroma** mode *(2026-09-07)* — `CONTENT_UI_REDUCED_CHROMA=1` adds `body.reduced-chroma` (`filter: saturate(0.45)`). Default path unchanged. Does not retune render `color_grade` `[S]`
- [x] **305. 16px minimum type** *(2026-08-22)* — buttons/inputs/textareas join the 16px body `[S]`
- [x] **306. Sticky cost bar** *(2026-08-22)* — booth `#costbar` (TTS 91% line) `[S]`
- [x] **307. Sticky quota bar** *(2026-08-22)* — booth `#quotabar` `[S]`
- [x] **308. Collapsible raw trace JSON** *(2026-08-25)* — redacted trace rendered in native `<details>` inside the booth `[S]` — *UI.*
- [x] **309. Collapsible ffmpeg commands** *(2026-08-25)* — actual successful primary argv plus attempted intro concat persisted at render time, never reconstructed `[S]` — *UI.*
- [x] **310. Copy ffmpeg command** *(2026-08-25)* — PowerShell-safe command from the persisted argv `[S]` — *UI.*
- [x] **311. Copy last postmortem as markdown** *(2026-08-22)* — booth field + `ops postmortem --md` `[S]`
- [x] **312. Tray: open last output folder** *(2026-08-21)* — `--open-output` + `--stay` button `[S]` — *new-app / UI.*
- [x] **313. Tray action: pause overnight** *(2026-08-25)* — new operator flag checked before topic collection; tray button plus `--pause-overnight` / `--resume-overnight`. The roadmap previously claimed an existing gate file; none existed `[S]` — *UI.*
- [x] **314. Tray action: run doctor → HTML** *(2026-08-21)* — `--doctor-html` + stay-window button `[S]`
- [x] **315. Tray: last grade letter** *(2026-08-21)* — chip line `Grade: B` `[S]`
- [x] **316. Tray last domain** *(2026-08-22)* — chip line `Domain: UFC`; suite sets `CONTENT_TRAY_DOMAIN=false` `[S]`
- [x] **317. Tray: Free vs Standard mode** *(2026-08-21)* — chip line `Mode:` `[S]` — *cost / UI.*
- [x] 318. Remember **second-monitor bounds** *(2026-09-07)* — window state JSON stores `screen` name plus geometry per channel. Offscreen DPR is 1.0. A physical second monitor is not in CI (#673) `[S]`
- [x] 319. **"What's blocking publish"** *(2026-08-21)* — `ops blocking` one-sentence from existing gates `[S]` — *short-term / UI.*
- [x] 320. Tray: **local git describe** when `ops` gains commands `[S]` — *UI.* Changelog awareness without opening GitHub.
  *(2026-08-26: `git describe --dirty` timeout, fail-open; tests mock the helper)*

Run-71 correctness (2026-08-22)

- [x] 321. **Title claim check** - the title was the one operator-facing string no gate ever read `[M]` *(2026-08-22)* - `lint_title_grounding` (`core/youtube_meta.py`) reuses `verify_claims` because token grounding provably cannot discriminate the actor; wired at the `generate_title` call site so it lands on the report card before `Proceed?`. `TITLE_GROUNDING=warn|off`, fail-open
- [x] 322. **Pre-rewrite claim verdict survives the rewrite pass** `[S]` *(2026-08-22)* - `ClaimVerification.to_dict()` carries `rewritten` / `pre_rewrite_unsupported` / `pre_rewrite_total` / `pre_rewrite_support_rate`, stamped where the adopted-rewrite branch already logged both counts; keys appear only on a rewritten run. #52's graveyard codes judge a hedged run on what it asserted first
- [x] 323. **Variant ranking survives the 0-100 clamp** `[M]` *(2026-08-22; diagnosis corrected 2026-08-30 — see #651: the clamp was real but was not the cause of the tie, so this did not fix it)* - `composite_score_raw` + `best_variant_index` (one rule, shared by the menu and `run_pipeline`); `DiscoveryResult.raw_scores` sits beside `evaluated` so the 3-tuple stays as it was. The operator is told whether an all-equal list was ordered by headroom or is a genuine tie
- [x] 324. **RAWG results must be current-era, not just name-matched** `[S]` *(2026-08-22)* - `_is_current_era` drops matches older than `RAWG_MAX_AGE_YEARS` (default 15) unless the topic is itself retro; fail-open on missing/unparseable dates. Vault-side equivalent deliberately deferred
- [x] 325. **`Proceed?` distinguishes decline from unrecognised** `[S]` *(2026-08-22)* - obvious prose (>24 chars, multi-word, or multi-line) gets one re-prompt pointing at the Fact prompt's `paste` mode; `n`/`N`/`no`/Enter and every menu key resolve on the first ask exactly as before. **Superseded 2026-08-29 (run 74):** too narrow — the line that ended run 74 was the single word `by`, which no prose detector catches. `Proceed?` now stops only on `n`/`N`/`no`/Enter; everything else re-prompts, and buffered stdin is drained before the gate is asked

Audit of the 2026-08-26 wave (all three were GREEN in CI)

- [x] 326. **Install the dependency wave that was only declared** *(2026-08-27)* - installed; then measured, which corrected the plan: 11.3.0 still carried **25** advisories and only 12.x fixes them, so the pin is now **Pillow 12.3.0** (0 advisories; tree 75 -> 48). Verified by `PIL.__version__`, not the file, and the pin test gained an installed-vs-declared assertion. Original finding: `[S]` - *security.* `pyproject.toml` reads `Pillow==11.3.0` / `requests==2.32.4`; the environment runs **9.5.0 / 2.32.3**, so all 26 Pillow CVEs are still live on the machine that parses untrusted stock-footage and thumbnail bytes. CI installs fresh and now runs a **different Pillow major** than the operator, and the upgrade's whole risk ("does the render still work on a new Pillow") is untested because nothing has run on 11.3.0. Fix is `pip install -e .` + one real render, not a code change. moviepy 1.0.3 is also still installed though nothing imports it
- [x] 327. **`spoken_numbers` mangles ranges on every render** *(2026-08-27)* - reuses `fact_grounding._RECORD`'s verb cue, so the two modules now agree on what a record is; three-part records spell properly too. Original finding: `[M]` - *quality.* `_RECORD_RE` matches any two-digit hyphenated pair, so `expand_spoken_numbers` - which runs unconditionally in `generate_audio` for every channel - turns "5-10 years" into "five ten years", "10-15%" into "ten fifteen%", and "9-5" into "nine five". Worst on **MoneyWise**, which is made of ranges and percentages and has just been given its own voice. `core/fact_grounding.py:47` already solves the identical ambiguity by requiring a verb cue (`is|now|went|record of`) - reuse that guard. The three shipped tests use no range and no percent. **No env gate exists**, so it cannot be turned off without a code change
- [x] 328. **One bad match silently disables all number expansion** *(2026-08-27)* - out-of-range event numbers return their digits instead of raising; a test asserts a purse and a record in the same script still expand alongside one. Original finding: `[S]` - *visibility.* `_UFC_RE` accepts 2-4 digits but `_event_number` indexes a 20-entry tuple with `n // 100`, so `UFC 2000` raises `IndexError`. The call site wraps the whole pass in `try/except ... logger.debug`, so at the default WARNING level the operator sees nothing and *every* expansion stops for that script, not just the bad match. decisions §24 shape: fail-open but not fail-visible, at the wrong granularity
- [x] 329. **Subject relevance without hand-tagged franchises - P0–P4** *(2026-08-27)* - the competing-franchise fix over-corrected: requiring a shared *franchise anchor* also dropped notes about the people and companies in the story (measured - "Rockstar Games confirms the leak investigation" vanished from a GTA topic naming Rockstar, silently, on `core/ui.py`'s vault prompt). Both the good and bad cases produce an EMPTY anchor set, so anchors cannot separate them. **P0:** such bullets are surfaced marked `uncertain` ("N confident, M uncertain") instead of dropped. **P1:** `core/vault_evals.py` + `ops vault-eval`; baseline precision/recall **0.667**. **P2:** additive scorer `vault_relevance_v1` (entity-in-corpus + corpus cosine + tier + anchors as a feature). **P3:** holdout from live runs 66+70 scored precision **and** recall **1.0**; shipped `default_mode` flipped to `scored`. **P4:** extract-tier tiebreak exists, **default off** (`VAULT_RELEVANCE_TIEBREAK`); residual uncertain band was 4/14. Two-stage discovery skips `web_search` with `STATUS_SKIPPED` only *after* a non-web corpus. `_GAME_ANCHORS` remain for topic-graph. Design: planning_log 2026-08-27; decisions §27
- [x] 330. **Crossfade at the hybrid join** *(2026-08-27)* - decisions §26's one surviving MoneyPrinterTurbo borrow. The xfade was already in and ffmpeg accepted it, but it **shortened every background by exactly the fade**: an xfade output runs `offset + len(second input)` and the stock segment was never extended, so a 6.000s request produced 5.500s against real ffmpeg. The render loops the background, so it never raised - it wrapped early and showed a jump. Now exact at 6.000s and 30.000s; the test asserts the *sum* across six durations and five ratios so the arithmetic cannot drift again

**Candidates 331–480 (2026-08-27 — docs only; no pickup order)**

*None of these restates an open checkbox or the shipped list. Weighted toward
grounding, reliability, and analytics rigor — the two 2.5/5 dimensions in
[assessment.md](assessment.md) plus the n≈10 learning-loop problem — because the
open backlog is already dense in operator UI. Inventory, not a wave: Phase M,
the XL apps (#141–#143), and the volume-gated backtest stay parked. Where an
idea sits beside an existing one, the line says how it differs.*

Grounding & fact quality

- [x] 331. **Per-fact "as of" clock** *(2026-08-27)* — `stamp_as_of` prefixes packed vault notes older than 7 days (`as of last week/month`); `load_facts` and interactive `vault_accepted` both stamp. A 20-day UFC fact is labeled; operator paste without `verified_at` is not. The finished script is not regex-rewritten `[S]`
- [x] 332. **Disputed-fact surface** *(2026-08-27)* — `features_from_conflicts` stamps `disputed` + losing claims; `display_fact_engine_report` prints **DISPUTED**; pipeline copies into features; `ops grade` note. Operator vs stale source: dropped line gone from the corpus, flag remains `[S]`
- [x] 333. **Negative-fact store (what is *not* true)** *(2026-09-07)* — `record_negative("gta", "GTA 6 leaked for a June 2025 release")` then `matching_negatives` hits that script and misses a UFC champion line. `ops negative-fact`. Store isolated in the suite `[M]`
- [ ] 334. **Entity disambiguation ledger** — `entity_extractor.py` re-resolves "Jones" / "Rockstar" every run. Resolve once to a canonical id, reuse across runs and channels `[M]`
- [x] 335. **Source-diversity floor on dated topics** *(2026-09-07)* — news-shaped claims whose URLs collapse to one registrable domain (espn.com + espn.com/story2) are moved out of verified into context. ESPN + MMAFighting passes. Evergreen "how does the offside rule actually work" does not fire. Wired in `_build_prompts` via `collect_source_urls` (operator paste + vault `source_url`). No sixth `input()` gate `[S]`
- [x] 336. **Wikipedia last-revision recency tripwire** *(2026-09-09)* — `_fetch_last_revision` on the same article; signal `data.last_revision`; health line `UFC_250 edited 2h ago`. Fail-first: `status_detail` had no `edited`. Network mocked; existing pageview tests now patch the revision fetch so they cannot hit wikipedia.org `[S]`
- [x] 337. **Numeric plausibility bands per domain** *(2026-09-08)* — `find_plausibility_outliers` flags a 10x purse even when the span is in the facts. Advisory on quality; `GRADE_VERSION` stayed **v3** `[S]`
- [x] 338. **Quote-attribution gate** *(2026-09-07)* — deterministic, no extra LLM. Invented quote flags; `Dana White told ESPN "…"` in facts passes; `"GTA 6"` does not fire. Nested quotes `known_gap=True`. Pre-rewrite flag persisted if the script changes (§25). `GRADE_VERSION` stayed **v3** `[M]`
- [ ] 339. **"Unconfirmed" as a first-class script mode** — today the choice is assert or drop; saying "this is not confirmed yet" is more honest *and* more authentic under the 2026 policy `[M]`
- [x] 340. **`.facts.json` sidecar beside the mp4** *(2026-08-28)* — `write_render_sidecars` at the pipeline finalize site writes claims/sources/disputed from already-persisted quality; fail-open, and a missing mp4 writes nothing `[S]`
- [x] 341. **Retraction watch 24h post-publish** *(2026-09-07)* — `ops retraction-watch` re-fetches last-trace source URLs; a body containing `RETRACTION` or missing the stored claim is a hit. *(2026-09-08)* 24h toast is #686. #112 correction dossier still does not auto-fire `[M]`
- [ ] 342. **Learned per-source trust weights** — `grounding_tiers.py` tiers are hand-assigned. Demote a source that keeps being corrected; promote one that never is `[M]`
- [ ] 343. **Cross-run fact cache keyed by entity+date** — franchise batches share discovery (#42) but still re-verify identical facts per topic `[M]`
- [x] 344. **Channel-clock resolution of relative time** *(2026-09-08)* — `resolve_relative_clock` maps tonight/this weekend onto TapIn ET (`publish_windows` tz). Stamped on quality when the script uses those phrases `[S]`
- [x] 345. **Claim-type taxonomy with per-type thresholds** *(2026-09-16, wave 18)* - the verifier now types each claim (result / award / stat / date / schedule / rumor / opinion / other) and `core/claim_types.py` gives each its bar: an unsupported result/award/stat/date always blocks (run 77's GOTY claim), a rumor blocks unless the script hedges it (reportedly, according to, ...), an opinion never blocks unless it carries a number, an untyped claim stays strict. `gate_blocks`, `override_features` (+ `grounding_override_types`), the publish list and the claim display all read it `[M]`
- [x] 346. **Rumor-labeling rule** *(2026-08-27)* — `apply_rumor_language` after odds in `generate_content_package`. Bare "GTA 6 is delayed to 2027" on a leak topic is softened; a Tapology result line is left; "reports to EA" is employment not a hedge. Known gap: outlet is required *in the script*, not inferred from the corpus `[S]`
- [x] 347. **`ops vault-decay`** *(2026-08-27)* — wraps `fact_expiry.expired_notes` (no second scanner). Temp vault with a past `expires:` lists it; empty vault prints an honest empty line and emits no WARNING `[S]`
- [x] 348. **Operator fact-intake linter** *(2026-08-28)* — `lint_fact_intake` on `core/ui.py`'s paste path, before `capture_facts_to_vault`. URL-only lines, duplicates, and vault contradictions warn; an empty paste is silent `[S]`
- [ ] 349. **Screenshot → facts via OCR** — the operator's fastest fact source is a stat card on screen; clipboard image → parsed lines into the facts block `[M]`
- [x] 350. **Grounding regression corpus in CI** *(2026-09-06)* — `config/grounding_corpus.json` 20 frozen `{script, facts, expect_ungrounded}` replayed by `ops grounding-corpus` via `find_ungrounded_entities` (no LLM). Not folded into `run_eval_corpus` because that listing test requires every row `scored=False`. Loosening a token rule fails a frozen case `[M]`

Learning loop & analytics rigor

- [ ] 351. **Confidence intervals, not just sample counts** — `recommender_confidence.py` reports n; an interval is what tells the operator that 30.6% +/- 22 is noise `[M]`
- [ ] 352. **Bayesian shrinkage toward the channel mean** — "ufc averages 30.6% across 2 videos" should shrink to the baseline until it earns its own estimate. Fixes volume-starved learning without waiting for volume `[M]`
- [x] 353. **Minimum-detectable-effect check before an arm is proposed** *(2026-08-28)* — `start_experiment` refuses a lever with more arms than measured videos. The test reads the arm count from `experiment_levers.arms()`, so a lever gaining an arm cannot pass a hardcoded number `[S]`
- [ ] 354. **Sequential-testing stop rule for title/thumb arms** — peeking and stopping on a good look is exactly how the loop learns superstitions `[M]`
- [x] 355. **Per-video surprise score (actual minus predicted)** *(2026-08-28)* — residual persisted when metrics sync lands; surfaced beside the grade `[S]`
- [ ] 356. **Store the retention *curve*, not just `drop_off_ratio`** — #28's learned intro reads one number; the shape is where the cliff actually is `[M]`
- [ ] 357. **Feature-importance report over `run_features.py`** — dozens of features are recorded and none is ever tested for correlation with outcome `[M]`
- [x] 358. **Counterfactual log of operator overrides** *(2026-09-08)* — `record_override` fail-open JSON. `ops log-override`; overnight records when explicit topics skip the best-bet. Suite isolates the store `[S]`
- [ ] 359. **Cold-start priors from the nearest existing domain** — a third channel should inherit TapIn's shape, not library defaults; unblocks the AI-Tools groundwork `[M]`
- [x] 360. **Separate day-of-week from hour in post-time learning** *(2026-08-28)* — Saturday 9pm and Tuesday 9pm are separate buckets; two fixtures prove they no longer average together `[S]`
- [ ] 361. **Comment sentiment as a secondary target** — `youtube_comments_signal.py` already pulls the text; engaged-rate cannot tell a good reaction from a pile-on `[M]`
- [x] 362. **Subscribers-gained as its own objective** *(2026-09-09)* — `_build_entries` now sets `subscribers_gained` from `youtube_metrics`; analytics rationale is `gained 12 subscriber(s)` for six 2-sub nba rows. Zero subs does not invent a conversion line. Fail-first: rationale had no `subscriber` `[S]`
- [ ] 363. **Title-embedding clustering across the catalog** — detect that the channel has quietly made the same video five times `[M]`
- [x] 364. **Topic saturation index** *(2026-09-09)* — `topic_saturation` counts matching competitor titles inside 48h (fixture: 2). Prompt: `1 competitor covered this in 48h`. `build_quality` persists it; dossier prints `7 competitors covered this in 48h`. Fail-first: helper missing `[S]`
- [x] 365. **Recency-decay weighting in every recommender** *(2026-09-08)* — `recency_weight` half-life 90 days; `get_best_bet` averages with it. Six-month-old 90% loses to last week's 20% `[S]`
- [x] 366. **Anomaly detector on the metrics sync itself** *(2026-08-28)* — `metrics_sync_incident` reaches `ops reliability`; a stalled sync is an incident, a fresh one prints no warning `[S]`
- [x] 367. **Calibration drift over time in `analyst_accuracy.py`** *(2026-09-08)* — `drift_line` compares two windows; getting worse is a summary line, not a silent skip `[S]`
- [ ] 368. **"Would this have been picked?" replay** — run the current scorer against past winners; a scorer change that would have skipped every hit is a regression `[M]`

Cost & quota

- [x] 369. **Per-run projected-cost gate** *(2026-08-27)* — `PROJECTED_COST_MAX_USD` unset = off (zero new warnings). When set, `guard_before_discovery` raises `CostModeBlocked` from `run_pipeline` *before* `run_discovery`; uses `estimate_run_cost(script="", rendered=True)`, never post-run actuals. Rates/breaker trip points untouched `[M]`
- [x] 370. **Cost per 1k views, not per video** *(2026-08-28)* — `ops economics` prints `$ / 1k views` only when views > 0, so zero-view runs produce no scare number `[M]`
- [x] 371. **Pre-spend TTS char forecast vs actual** *(2026-08-27)* — `forecast_tts` runs in `generate_audio` before synth; `record_tts_actual` stamps chars + delta; `run_media` merges both onto features. Fail-open; healthy run: no new WARNING `[S]`
- [x] 372. **Cache-hit dollars saved** *(2026-08-27)* — `ops reliability` multiplies Apify-prefix hits × `COST_APIFY_PER_RUN`. `$` line only when hits > 0; zero hits is not a scare WARNING. Display only `[S]`
- [x] 373. **Audit that no path bills TTS before script approval** *(2026-08-28)* — audit-and-lock, no product change: the pipeline seam plus every draft call site (`main.py`, `auto_generate`, `batch_generation`) is pinned to `proceed_video=False` in `tests/test_no_tts_before_approval.py`. Proved failable by flipping the flag in `main.py` `[S]`
- [ ] 374. **Premium tier for the hook only** — the first two sentences carry the retention cliff; the rest can run cheap-tier through the existing router `[S]`
- [ ] **Ollama model pull (optional)** — `ops doctor` ollama FAIL stays until `ollama pull …`. Ollama is still free/local (not a billed API); Standard already uses DeepSeek/OpenRouter. Do not un-tick the shipped router item. `[S]`
- [ ] 375. **Ollama warm-pool across a batch** — the free path loses on cold-start latency, not quality `[M]`
- [ ] 376. **YouTube unit budget planner** — split the ~1,600 units across upload / analytics / captions for the day instead of first-come-first-served `[M]`
- [ ] 377. **`ops economics --month` close-out** — reconcile metered estimates against real vendor invoices; decisions §22 meters from the plan but never checks itself `[M]`
- [x] 378. **Free-tier expiry calendar** *(2026-09-10)* - `config/free_tiers.json` + `core/free_tier_calendar.py` + `ops free-tiers`, which exits non-zero once a window has actually lapsed. Three states kept distinct: **due** inside the notice period, **closed** (stays on the calendar rather than dropping off), and **unknown** where a provider publishes no date - unknown is not the same as safe. Says out loud that the dates are hand-maintained and not a live reading `[S]`
- [x] 379. **Spend-anomaly toast** *(2026-08-28)* — `maybe_toast_spend_anomaly` at 3x the trailing median from the last 20 runs; a cheap run is silent, and one unreadable history row no longer costs the median `[S]`
- [ ] 380. **Apify cost per *usable fact*** — cost-per-call is not the decision metric; a cheap actor returning nothing is worse than a dear one that grounds the script `[S]`
- [x] 381. **`PAID_CALLS=off` master kill-switch** *(2026-08-27)* — aliases `resolve_cost_mode` onto Free (same `apply_and_guard` path). `ops doctor` `paid_calls` check fails when the env is set but `FREE_MODE_STRICT` is not armed; unset leaves Standard unchanged `[S]`
- [x] 382. **Disk growth projection for `output/` + `data/traces`** *(2026-08-28)* — `project_days_until_full` on `ops artifact-retention`; an empty dir reports honest empty, not a warning `[S]`

Reliability & signals

- [x] 383. **Nightly synthetic canary run** — exercise every signal with zero LLM/TTS spend so a dead source is found before a real run needs it (Tapology-class silent death) `[M]` — **shipped 2026-09-05** as `core/signal_canary.py` + `ops signal-canary`, modelled on `core/feed_health.py`. Two safety properties, both asserted: it calls signal functions **directly** rather than through `_fetch_one`, so it cannot answer from cache (a warm cache proves nothing about liveness — that is how Tapology stayed 'fine' for 33 days) and cannot trip the persisted breaker (which would disable a signal for the operator's *next live run*); and paid signals are skipped via `_APIFY_PAID_SIGNALS` itself, not a second hand-list. **A first cut got the classification backwards** and reported 15 of 33 dead — most were healthy sources with no match for a UFC probe topic. Corrected to the signal-contract vocabulary: `STATUS_INACTIVE` is a source answering, not a dead one. Measured: **27 answered, none broken**. Honest cost note: zero dollars, ~101 YouTube *quota* units
- [ ] 384. **Per-signal SLO + error budget** — `reliability.py` shows incidents; a budget turns "flaky" into a decision to retire (decisions §19) `[M]`
- [ ] 385. **Response-schema pinning per API** — a vendor field rename degrades into empty facts, not an error; `sortVideosBy` and `scrape_enabled` were both this shape `[M]`
- [ ] 386. **Offline replay harness from recorded traces** — traces are on disk; a signal bug should be reproducible without touching the network `[M]`
- [ ] 387. **Deterministic run mode** — fixed seeds + recorded fixtures end-to-end, so "it did something different this time" is answerable `[M]`
- [ ] 388. **Backoff jitter + per-host concurrency caps** — the discovery pool can stampede one host; #41 caps total workers, not per-domain `[S]`
- [x] 389. **Serve stale cache on failure, visibly flagged** *(2026-08-28)* — live `unavailable`/`error`/`auth`/`rate_limited` (not honest `inactive`) serves an expired entry ≤48h with `STALE cache, age Nh`, score 0, `stale_served` not a hit. >48h keeps the live failure. Eligible stale is not overwritten. `STALE_CACHE_MAX_AGE_HOURS=0` restores drop-expired. Default on. `[S]`
- [ ] 390. **Signal dependency graph** — short-circuit a chain whose upstream already failed instead of paying for every leg `[M]`
- [ ] 391. **One HTTP client across `apis/`** — timeouts, retries, and UA are re-implemented per module; the single seam where 385/388/396 all land `[M]`
- [ ] 392. **Vendor status-feed check in `ops doctor`** — distinguish "we broke it" from "they are down" before debugging `[S]`
- [ ] 393. **Network-vs-API preflight** — one probe that says the internet is down, so seven signal failures read as one incident `[S]`
- [x] 394. **Auto-quarantine on empty-but-200** *(2026-08-27)* — three connected `STATUS_INACTIVE` with no skip-detail session-disable the signal (Tapology "no event match"). Wikipedia no-page and "Not an MMA topic" do not count. **Not** persisted to `quota_state.json` (decisions §6). One inactive does not trip `[M]`
- [x] 395. **Free-backend parity tests** *(2026-08-28)* — `SIGNAL_BACKEND=free` youtube_competitors + reddit assert `make_signal()` keys and status; no second cache added `[S]`
- [ ] 396. **Record real rate-limit headers into the governor** — `quota_governor.py` guesses resets that vendors publish; decisions §13b wants the *real* reset `[M]`
- [ ] 397. **Local mirror of slow-moving reference data** — rosters, rankings, and tickers change monthly and are fetched hourly `[M]`
- [ ] 398. **Chaos test in CI** — randomly fail k signals; the run must still produce a grounded script or refuse honestly `[M]`

Script, voice & TTS

- [ ] 399. **Hook bank with performance history** — `hook_score.py` scores against a heuristic; nothing remembers which hook *shapes* actually retained `[M]`
- [ ] 400. **Measured words-per-second per voice** — `script_length.py` assumes one rate; each voice reads differently, which is why lengths drift `[S]`
- [ ] 401. **Prosody / pause markup for local TTS** — the flat Piper read is a real part of why the $0 flip is blocked on ears `[M]`
- [x] 402. **Sentence-level TTS cache** *(2026-09-06)* — after #658's `synthesize_to_path` seam. Multi-sentence scripts synth per sentence, ffmpeg-reencode concat, offset `.words.json`, and `render_cost_lines(tts_cached=0.9)` bills 10% not $0. Whole-script cache still hits first. Piper mix stays off the per-sentence loop. Concat failure falls back to whole-script synth `[L]`
- [x] 403. **Voice-consistency check across segments** *(2026-08-28)* — `voice_mix_warning` warns once when the body TTS provider and the intro/outro path disagree; a single provider is silent `[S]`
- [ ] 404. **Breath and dead-air trim on generated audio** — a cheap duration win before any length gate fires `[S]`
- [x] 405. **Script diff: LLM draft vs post-gate rewrite** *(2026-08-27)* — adopted rewrite stamps `script_pre_rewrite` / `script_post_rewrite` on the verification dict, quality, dossier, and booth. A clean run omits the keys (same shape rule as #322) `[S]`
- [x] 406. **Per-persona style linter** *(2026-08-28)* — post-script, fail-open warn against the shipped persona. Pattern-catch held: MoneyWise ranges and percentages are not flagged (#327 class) `[S]`
- [x] 407. **Opener-pattern check** *(2026-09-10)* - `core/opener_patterns.py`, printed by `display_hook_score` at every verdict, not only `weak`: the score nets out, so a bonus elsewhere could hide a weak opener entirely. Reuses `hook_score`'s own `_WEAK_OPENERS` / `_CURIOSITY` / `_STAKES` tables so the two cannot drift. **Labelled editorial judgment, not prediction** - a test forbids the words retention / % more / will perform / predicted / increase, because n around ten cannot support a causal claim `[S]`
- [ ] 408. **Domain-aware number reading beyond `spoken_numbers`** — tickers, currency, and percentages are MoneyWise's entire vocabulary (#327's neighborhood, not its fix) `[M]`
- [ ] 409. **Per-channel brand-safety lexicon** — advertiser-safe mode (#127) is odds-specific; a general list is one file `[S]`
- [ ] 410. **Two-take TTS, pick by pace** — generate twice, keep the read closest to target duration; only worth it on the free path `[M]`
- [ ] 411. **Per-channel music bed + ducking** — `core/music.py` exists and no channel uses it; silence under VO is part of why the result looks thin `[M]`
- [x] 412. **Auto-append operator pronunciation corrections** — **superseded 2026-08-28 by Edge TTS.** The append-to-JSON workaround was rejected: a dictionary is a patch for a voice that cannot be told how to say a word. `TTS_PROVIDER=edge` is opt-in cloud $0 in `_ALT_TTS`, wraps the lexicon as SSML `<sub>`/`<phoneme>`, writes WordBoundary sidecars, meters $0, is **not** local, and is never the default. Piper stays the true-offline Free floor. `[S]`

Render & visual craft

- [ ] 413. **Deterministic render fingerprint** — same inputs, same bytes, so a render regression is a diff instead of an argument `[M]`
- [x] 414. **Post-render frame QA** *(2026-09-09)* - `core/technical_qc.py` `blackdetect` + `freezedetect` + A/V duration mismatch on the finished file. Real ffmpeg fixtures: black video is not reported clean; frozen non-black (`color=c=red`, 2.5s) files a frozen-interval issue; missing ffmpeg is `unavailable` with `passed=False`. Dossier prints the advisory `[M]`
- [x] 415. **Render smoke test in CI on a 2s synthetic input** *(2026-09-09)* — CI `apt-get install -y ffmpeg`; `smoke_render_synthetic` runs a 2s lavfi clip through `build_render_ffmpeg_command`. Local duration 1.5–3.5s. Missing ffmpeg under `CI=true` raises. Guard strips comments so a commented install cannot pass `[M]`
- [x] 416. **Scene-beat cuts from owned gameplay** *(2026-09-07, mechanical slice)* — `try_owned_beat_background` maps `clip_index` paths onto `plan_scenes` beats and concats when the files exist; empty or missing index keeps the current single loop. **Not** CLIP matching; `SCENE_MATCHED_BROLL` stays off (decisions §26). HUD-aware pick is still impossible while ingest stores `hud: null` (#683) `[L]`
- [x] 417. **Owned-footage ingest + index** *(2026-08-28, mechanical slice)* — `ops ingest-clips` (dry-run default; `--apply` remuxes muted H.264) matches capture filenames into `video/backgrounds` via existing folder routing + a short alias table. Unmatched files are listed, never dumped into `gaming/`. `data/clip_index.json` records ffprobe duration/size/codec; **HUD is persisted `null`** (no detector). Hand-tagging skipped. Scene-beat cuts remain #416 `[L]`
- [ ] 418. **Zoom resampling validation** — verify #26's Ken Burns does not soften 1080x1920 detail; a bounded zoom can still cost sharpness `[S]`
- [x] 419. **Caption line-break optimizer** *(2026-08-28)* — a lone final word is rebalanced on BOTH caption paths. The first cut only touched `split_script_into_lines` (the estimated-timing fallback), so on a normal ASR-timed run it did nothing — `group_into_lines` now rebalances too, moving the word with its own start/end. Rebalancing is per sentence: the running-list version merged two sentences into one cue, which `test_sentence_boundaries_not_crossed` has forbidden since long before 419 `[S]`
- [x] 420. **Verify loudness + true peak *after* encode** *(2026-09-09)* - post-encode `loudnorm=print_format=json` reads `input_i` / `input_tp` / `input_lra`. A real 1.5s A/V fixture reports all three; `passed` is false when analysis is unavailable. Peak-over-target uses the same `LUFS_TARGET_TP` as the loudnorm filter (retargeting the env for a hot-peak fixture also retargets the filter, so that case is not a separate fixture) `[S]`
- [ ] 421. **Render time budget with progressive fallback** — degrade the preset rather than run long when the queue is deep `[M]`
- [ ] 422. **Thumbnail text auto-fit with hierarchy rules** — Pillow thumbs currently pick a size and hope `[M]`
- [ ] 423. **Generate contrast-safe palettes from channel tokens** — makes #185's auditor largely unnecessary by construction `[M]`
- [ ] 424. **B-roll license ledger with expiry** — which clip, which license, which videos it appears in. A licensing question has no answer today `[M]`
- [ ] 425. **Vertical-crop scoring for 16:9 sources** — the scoring half of Phase R, shippable long before clip-from-source `[M]`
- [x] 426. **Render artifact manifest (input hashes) on the run row** *(2026-08-28)* — mp4 + script hashed at the same finalize site as #340 `[S]`

Publish, SEO & policy

- [ ] 427. **Per-domain description template engine with slot validation** — description assembly is concatenation across #118/#125/#128 and grows a branch per policy line `[M]`
- [ ] 428. **Hashtag performance tracking** — tags are generated and never evaluated `[S]`
- [ ] 429. **Scheduled pinned comment + its performance** — `youtube/pin_comment.py` posts; nothing times it to the traffic peak or measures it `[S]`
- [x] 430. **Community-post drafts from the weekly report** *(2026-09-09)* - `community_post_draft` turns `next_actions` into vault `{date}_community-draft.md` via `write_report_note`. Weekly-report `main()` writes it. YouTube client is never constructed. Fail-first: `ImportError` for the helper `[S]`
- [x] 431. **Verify chapter timings against real word timings** *(2026-09-09)* - `chapter_block(..., word_timings=)` + `refine_run_chapters` from `pipeline.py`. The extras test asserting `0:20`/`0:40` cannot fail: that is also the equal-span fallback for three sentences over 60s. New guard uses 5s/12s starts; ignoring timings produces `0:20`/`0:40` `[S]`
- [x] 432. **Publish dry-run that prints the exact API payload** *(2026-08-28)* — `ops publish-dry-run` / `PUBLISH_DRY_RUN=1` prints the real `videos().insert` body with tokens redacted, and never calls insert `[S]`
- [x] 433. **Cross-channel duplicate-upload guard** *(2026-08-28)* — same franchise/topic **and** same `infer_domain` lens (real scorer: GTA review = gaming, Take-Two stock = finance). Pipeline aborts before `generate_content_package`; publish + `ops next` backstop. `CROSS_CHANNEL_DUP=block|warn|off`; suite forces `off` like `TITLE_UNIQUENESS`. Same-channel titles stay #117. `[S]`
- [ ] 434. **Content-ID pre-check heuristics** — a claimed video is a monetisation event; stock and music are the exposure `[M]`
- [ ] 435. **Policy-page diff watcher** — the 2026 authenticity rules are existential and the project tracks them by hand `[M]`
- [ ] 436. **Strike / appeal evidence bundle from the run ledger** — `policy_runbook.py` documents the process; the ledger already holds the evidence it asks for `[M]`
- [x] 437. **One-command publish rollback** *(2026-09-09)* — `ops rollback-publish` unlist + correction description + vault dossier. Dry-run default; `get_youtube_service` is never constructed unless `--apply` and `YOUTUBE_UPLOAD_ENABLED`. Fail-first: `rollback-publish` not in `COMMANDS` `[S]`
- [ ] 438. **Per-channel audience-language / region targeting** — #108 sets language; targeting is a separate lever that is never set `[S]`
- [x] 439. **Shorts-eligibility validator before upload** *(2026-08-28)* — `shorts_refuse_reason` on the publish path refuses landscape and over-60s with a sentence; a missing file is fail-open `[S]`
- [x] 440. **Immutable 24h / 7d performance snapshots** *(2026-09-09)* - `merge_metric_snapshots` nests `snapshots.24h` / `7d` inside `metrics_json` on first capture; a later sync updates live totals and cannot rewrite an existing bucket. `render_dossier` prints both. Fail-first: dossier omitted `24h snapshot` `[S]`

Operator surface

- [ ] 441. **`ops explain --run-id`** — one narrative of every decision the run made and why. The postmortem covers failures; this covers choices `[M]`
- [x] 442. **`ops next`** *(2026-08-27)* — thin `@_register`: projected-cost line, then vault-decay warnings, then `blocking_publish_sentence`. One printed action. No second scanner `[S]`
- [x] 443. **`ops diff-runs A B`** *(2026-08-28)* — joins grade, cost, ungrounded, and disputed for two run ids; missing ids exit without mutating `[S]`
- [x] 444. **Minutes-per-published-video trend** *(2026-08-28)* — persisted to its own sidecar on publish (never `quota_state`), surfaced as a one-liner; tests isolate the file `[S]`
- [ ] 445. **Resume an interrupted run from the ledger** — an abort after TTS currently means re-spending it `[M]`
- [ ] 446. **Undo for destructive `ops` commands** — retention, requeue, and clone paths have no back-out `[M]`
- [x] 447. **Config diff vs the last good run** *(2026-09-07)* — `ops config-diff` compares `channels.json` sha256 to `channels_sha256` on the last trace (`write_run_trace` now stamps it). *(2026-09-08)* `.env` shape is leftover-closed as #687 `[S]`
- [x] 448. **`ops why-slow`** *(2026-09-07)* — ranks last-trace `timings`; a 32s `signals_and_variants` phase is named first. *(2026-09-08)* `word_count` / length keys are not ranked as phases `[S]`
- [ ] 449. **Batch approve queue** — review five drafts in one pass instead of five interactive runs `[M]`
- [ ] 450. **Voice-note fact intake** — record a memo on a phone, transcribe to key facts; whisper is already installed `[M]`
- [ ] 451. **Phone-sized booth layout** — review a 9:16 Short on the device it will be watched on `[S]`
- [x] 452. **Weekly operator digest** *(2026-09-09)* — `operator_digest` caps `next_actions` at 3; `ops digest` + weekly_report `main()` write `{date}_digest.md`. Six actions keep 0–2, drop 5. Not-ready writes nothing `[S]`

Engineering hygiene

- [ ] 453. **Property-based tests for the signal contract** — `make_signal()`'s shape is load-bearing for every signal and is tested by example `[M]`
- [ ] 454. **Golden-file tests for ffmpeg argv on every path** — #24 and #330 were both argv-arithmetic bugs that a golden file catches instantly `[M]`
- [x] 455. **Shared test fixture isolating `data/quota_state.json`** *(2026-09-07)* — `tests.isolation.IsolatedQuotaStore`. `GovernorCase` subclasses it. Writes land in the temp file; path is not repo `data/quota_state.json` `[S]`
- [ ] 456. **Import-time side-effect audit + import-cost budget** — CLI startup is slow and nobody knows which module does work at import `[S]`
- [ ] 457. **Lockfile + reproducible install** — #326 was the environment silently disagreeing with `pyproject.toml`; a lockfile makes that class impossible, not just detectable `[M]`
- [x] 458. **Generate the ops command reference from `ops list`** *(2026-08-28)* — `ops command-ref` writes `docs/ops_commands.md` from the live registry, and a test fails when the doc drifts from `COMMANDS` `[S]`
- [ ] 459. **Dead-code sweep after signal retirements** — `reddit` and `twitter` are `enabled: false`; their code is still in the tree `[S]`
- [ ] 460. **Typed settings object over scattered `os.getenv`** — dozens of env reads with inline defaults, none of them visible to the type checker `[M]`
- [ ] 461. **Env-var registry validated at startup** — every flag with its default and meaning, checked before a run rather than at first use (the run-70 shape) `[M]`
- [ ] 462. **run_id correlation in every log line** — traces carry run ids, logs do not, so the two cannot be joined `[S]`
- [ ] 463. **Wire `scripts/bench_*.py` into CI with thresholds** — the benchmarks exist and nothing fails when they regress `[S]`
- [ ] 464. **VCR-style recorded API fixture library** — the enabling asset for 386, 387, and 398 `[M]`
- [ ] 465. **Alembic up/down test against a real snapshot** — two migration stories (#35) is a problem; neither is verified `[M]`
- [ ] 466. **Generate the open-items index from the checkboxes** — this list is maintained by hand and the header count is already load-bearing in the docs lint `[S]`

Strategy & bigger bets

- [ ] 467. **Second operator seat** — the run ledger assumes one human; the first collaborator is a schema question, not a UI one `[L]`
- [ ] 468. **Fact engine as a standalone surface** — the grounding stack is the most differentiated code in the repo and is welded to video `[XL]`
- [ ] 469. **Sponsored-brief run type** — a run driven by a brief, with disclosure and claim limits enforced by the gates that already exist. First non-ad revenue path that is not #79 `[M]`
- [ ] 470. **Newsletter from the same fact corpus** — the research brief is already written; a second distribution costs no new research `[M]`
- [ ] 471. **Audio-only distribution from existing TTS** — the mp3 exists and is discarded after render `[M]`
- [ ] 472. **Evergreen re-cut program** — republish measured winners after N months with refreshed facts; `topic_clone.py` is the write path that already exists `[M]`
- [ ] 473. **Forward franchise calendar** — `seasonal_calendar.py` reacts; UFC cards and game launches are known months ahead and should be planned against `[M]`
- [ ] 474. **Audience-question intake into topic scoring** — comments and community polls as a discovery signal, not only a mailbag (#114) `[M]`
- [ ] 475. **Competitor gap map** — topics the tracked channels cover that we systematically never do `[M]`
- [ ] 476. **Portfolio allocator across channels** — where the next 10 videos should go for expected RPM, given cadence caps `[L]`
- [ ] 477. **Per-channel break-even model** — at what RPM and volume does a channel cover its ~$1/video allocated cost `[M]`
- [ ] 478. **White-label channel kit** — spin up channel #3 from a template in a day; #51's Channel DNA export is the input, this is the consumer `[L]`
- [ ] 479. **Restore drill for `moat_backup.py`** — a backup that has never been restored is a hypothesis `[S]`
- [ ] 480. **Open-source the signal contract as positioning** — the narrowest genuinely reusable piece; costs nothing strategic and is the cheapest credibility asset the repo has `[M]`

---


---

## Numbered candidates 481–656 (2026-08-28 — docs only; no pickup order)

*None restates an open item. Weighted toward the two things the desktop programme
does not cover: **video craft**, which survives every toolkit change and is burned
into each video forever, and **the terminal**, which is the daily driver for the
16–19 waves the app will take. Items ending in a measurement name a real number
taken from this machine.*

Terminal & TUI craft

- [x] 481. **Pinned status line** *(2026-09-07)* — formatter calls real `format_uploads_left`; `emit()` refreshes it. CSI pin is TTY-only and off under `NO_COLOR` (no new WARNING). CI does not have a real Windows Terminal `[M]`
- [x] 482. **Collapse the mascot after the first run of the day** *(2026-09-06)* — day-key stamp (`CONTENT_UI_MASCOT_STAMP` / suite temp path, never operator `data/`). Second startup same day skips the panel; `--art` / `CONTENT_UI_ART=1` forces it; next calendar day shows it again `[S]`
- [ ] 483. **Redraw signal health in place** — discovery reprints the whole 15-line block each pass instead of updating it `[M]`
- [x] 484. **`Ctrl+C` at a prompt returns to the menu** *(2026-09-06)* — `KeyboardInterrupt` in `_run_new_video_flow` / idea intake / intelligence prints "Cancelled — back to the menu" and does not `SystemExit`. Test: `input()` raising at the topic prompt never reaches discovery `[M]`
- [x] 485. **Persist discovery so a re-entered topic skips the refetch** *(2026-09-06)* — `cache_manager` prefix `discovery::{channel}`, TTL 90m. Hit skips `generate_variants`, prints `Reused discovery from cache`. Empty `evaluated` is not stored. tapin vs moneywise isolated; TTL expiry refetches `[M]`
- [x] 486. **Colour-blind-safe palette variant** *(2026-09-07)* — `CONTENT_UI_COLORBLIND=1` uses token `colorblind_roles` (success ansi256 33, error 208). `plain` stays empty of color `[S]`
- [x] 487. **`NO_COLOR` and non-TTY detection** *(2026-09-06)* — non-TTY and `CONTENT_UI_COLOR=false` already disabled color; `NO_COLOR` (any non-empty value) now does too. TTY + `NO_COLOR=1` → `paint()` returns plaintext `[S]`
- [x] 488. **Terminal-width awareness** *(2026-09-06)* — fact preview / grounding / links go through `fact_display_width()` (`terminal_width(maximum=160) - 4`). Banner max stays 100. Patch width to 140: a 120-char fact prints fuller than 90; `_elide` still adds `… (+N chars)` `[S]`
- [ ] 489. **Single-key menu mode** — press `1`, no Enter, for the high-frequency prompts `[S]`
- [x] 490. **Progress ETA from measured history** *(2026-09-06)* — `DiscoverySpinner._load_typical_timings` median over last 20 traces with `signals_and_variants` / `variant_scoring` (≥5s). Fixtures 20/40/60 → hint ≈ 40, not 20. Empty store stays silent `[S]`
- [x] 491. **Spinner frames respect the active theme's glyph set** *(already shipped; ticked 2026-09-06)* — `DiscoverySpinner` uses `active_theme().spinner_frames`; `tests/test_themes.py` asserts pokemon frames on the live spinner `[S]`
- [ ] 492. **Up-arrow recall for topics** — retyping a long topic after an abort is the common case `[S]`
- [ ] 493. **`--quiet` run mode** — gates and the report card only, no narration `[S]`
- [ ] 494. **`--replay <run-id>`** — reprint a past run's console output from its stored trace `[M]`
- [ ] 495. **Bell or flash when a gate needs an answer** — discovery is long enough to walk away from `[S]`
- [ ] 496. **OSC 8 terminal hyperlinks** on run ids, file paths and YouTube URLs `[S]`

Video & render craft — permanent, survives every toolkit change

- [ ] 497. **Per-channel LUT files** instead of #25's three `eq` scalars — a real grade, not brightness/contrast/saturation `[M]`
- [x] 498. **Loudness *range* check**, not only integrated LUFS *(2026-09-09)* - measured `input_lra` vs `LUFS_RANGE_MIN`. A real sine fixture with the floor raised to 20 LU files `loudness range ... is below` and `passed=False`. Unavailable analysis is not a pass `[S]`
- [ ] 499. **Silence-trim the VO head and tail** before the render rather than after `[S]`
- [ ] 500. **Beat-matched cut points** when a music bed is present `[L]`
- [ ] 501. **Automatic hook re-cut** — when the first 3s scores low, re-render that segment only `[L]`
- [x] 502. **Safe-area guides burned into the draft preset only** *(2026-09-06)* — draft filter graph appends two `drawbox` overlays after subtitles; the publish argv from the same helper has none `[S]`
- [ ] 503. **Per-channel caption entrance animation** (pop, slide, none) `[M]`
- [ ] 504. **Emoji in captions** — libass drops them silently today `[M]`
- [x] 505. **Two-line caption balancing** *(2026-09-06)* — `two_line_split_index` in both `split_script_into_lines` and `group_into_lines`. Eight words at max 5: 4+4, not greedy 5+3. `#419` orphan + `test_sentence_boundaries_not_crossed` stay on three-line / two-sentence cases `[S]`
- [ ] 506. **Speaker-adaptive caption colour** when a line is an attributed quote `[M]`
- [ ] 507. **Do not burn captions over on-screen text** in the background clip `[L]`
- [ ] 508. **Thumbnail face-crop bias** using the existing Pillow stack — no new image API (§26) `[M]`
- [ ] 509. **Thumbnail A/B on text variants**, not only #27's image variants `[M]`
- [ ] 510. **Chapter thumbnails** for the 16:9 sibling `[M]`
- [ ] 511. **Five-second vertical teaser** cut from the finished video, for community posts `[M]`
- [x] 512. **Grain and vignette as real ffmpeg filters** *(2026-09-07)* — `look_filter_fragment("tapin")` emits `noise=alls=8` + `vignette=` from tokens; moneywise grain 4. Absent `channel_id` keeps the old graph. Not visually graded on a live encode (#672) `[M]`
- [x] 513. **Reject a black or frozen first frame** *(2026-09-06)* — Pillow luma/frozen check on the finished mp4 after intro offset (output-seek). Pre-upload / pipeline advisory (`ADVISORY` / `not a publish block`); does not skip upload. Synthetic images in tests `[S]`
- [ ] 514. **Duck the intro sting** where it overlaps the first caption `[S]`

Desktop application — Qt specifics

- [x] 515. **`ask()` backend contract test** *(2026-09-07)* — ScriptedBackend `["y","3"]` and AskBridge submit the same pair; both return `[True, "3"]` on the live AUTH_PROMPT + Choose 1-5 strings `[M]`
- [ ] 516. **Crash-safe run journal** — `input()` held the run in memory by accident; a Qt crash must not lose it `[M]`
- [ ] 517. **Panel registry** — a panel is one class, discovered rather than wired into the window `[M]`
- [ ] 518. **One Qt model over the run ledger**, shared by the queue, analytics and review panels `[M]`
- [ ] 519. **Background-thread policy** — exactly one worker, cancellable, never on the UI thread `[M]`
- [ ] 520. **Cancel mid-discovery and keep what was already fetched** `[M]`
- [ ] 521. **Command palette over all 92 `ops` verbs** (#175) as the Qt entry point `[M]`
- [ ] 522. **Per-panel keyboard maps** with a discoverable `?` sheet `[M]`
- [x] 523. **Persist window state per channel** *(2026-09-07)* — `save_window_state` / `load_window_state`. TapIn DISPLAY2 vs MoneyWise DISPLAY1 do not clobber. Suite uses `CONTENT_WINDOW_STATE` `[S]`
- [ ] 524. **Toast → in-app notification bridge** so #165 is one history rather than two `[M]`
- [x] 525. **Drag a `.txt` or a URL onto the window** *(2026-09-07)* — `facts_from_drop` reads the txt and keeps `https://example.com/card`. Window accepts drops `[S]`
- [ ] 526. **"What changed since I last looked"** panel driven by the run ledger `[M]`
- [x] 527. **High-contrast and reduced-motion Qt themes** *(2026-09-07)* — `build_qss(..., high_contrast=True)` stamps `/* high-contrast */`; reduced_motion sets `animation-duration: 0ms`. `CONTENT_UI_HIGH_CONTRAST` / `CONTENT_UI_REDUCED_MOTION` `[M]`
- [ ] 528. **Live log tail with level filtering**, replacing terminal scrollback `[M]`
- [ ] 529. **Screenshot any panel to the clipboard** for the planning log `[S]`
- [ ] 530. **Panel-level error boundary** — one broken panel must not take the window down `[M]`
- [ ] 531. **First-run wizard** that writes `.env` and validates keys before the first run `[M]`
- [ ] 532. **In-app changelog** fed by `git log` since the last launch `[S]`

Content engine & angles

- [x] 533. **Angle intents beyond reaction** — explainer, tier-list, tutorial, debunk; `core/angle_intent.py` is built for exactly this `[M]` — **detector + angle tables shipped 2026-09-05** (the slice `roadmap.md` prescribed; run 75 showed this half is what pays). `core/angle_intent.py` grew from `reaction|default` to explainer / list / tutorial / comparison / retrospective, and `apis/topic_variants.INTENT_ANGLES` gives each one a table where **no frame asks what is broken** — every pre-existing non-reaction table contained `controversy`. `lens_examples` and the freshness/CRITIQUE block are now intent-conditional, and the detected mode finally prints on the **main generation flow**, not just the intelligence report (the module's promise that the operator can see it was half true). Cues are deliberately narrow so `GTA 6 meta breakdown` keeps the staleness pivot — pinned by a test. Measured on real seeds: run 62's `COD Bo2 ... better or worse than back in the day?` now reads `comparison`, not critique. Remainder: **#659**, **#660**
- [x] 534. **Pin an angle phrase** that must survive into the generated title *(2026-09-13, wave 15)* - run 76 selected the criterion angle and `generate_title` returned the GameSpot drones fact. A pin list from the angle (`will it be the best`, `criterion`) now repairs a miss to the angle string. Fail-first: mocked complete returning the drones title; output kept Criterion `[S]`
- [ ] 535. **Reject an angle that repeats one used in the last N videos**, by embedding rather than string match `[M]`
- [ ] 536. **An editable outline step** before prose generation `[M]`
- [ ] 537. **Per-section regeneration** — rewrite the hook without re-running the body or re-billing it `[M]`
- [ ] 538. **Generate two hooks in one run** and keep both for the thumbnail experiment `[M]`
- [ ] 539. **Reading-level target per channel**, measured and enforced `[S]`
- [x] 540. **Sentence-length rhythm check** *(2026-09-07)* — five 3-word sentences flag; a long/short mix does not. Warn-only, features `sentence_rhythm`. `display_fact_engine_report` prints the hits (#679 / #540) `[S]`
- [x] 541. **Per-channel ban-list of LLM tells** *(2026-09-07)* — `lint_persona_script("In today's video we delve...")` hits both phrases. MoneyWise `5-10 years` still clean. `config/llm_tells.json` shared phrase `here's the kicker` is not in `_FILLER_PHRASES`; emptying `ROOT_DIR` drops the hit (#679 / #541) `[S]`
- [x] 542. **Cut the summary paragraph** models insert before a CTA *(2026-09-07)* — drops `In summary...` immediately before `Like and subscribe`. Env `CTA_SUMMARY_STRIP` (default on). Persists `pre_paragraphs` / `post_paragraphs` (§25) and prints them in the fact-engine report before Proceed (#680) `[S]`
- [x] 543. **Quote the operator verbatim** *(2026-09-15, wave 17)* - typed thoughts are the brief since run 77. `idea_intake.operator_quotes` pulls first-person opinion sentences (i think / my take / imo); `_build_prompts` emits an OPERATOR'S OWN WORDS block the script must carry in quotation marks; `quote_survived` re-checks the final script after every rewrite pass and the run records `operator_quote_used`. Warn-only, like persona lint - no new gate `[M]`
- [ ] 544. **Script memory** — never reuse the same opening construction twice in a week `[M]`
- [ ] 545. **A "what I got wrong last time" beat** when a correction exists for the franchise `[M]`
- [ ] 546. **Script length learned from retention** rather than the fixed preset table `[M]`

Grounding & truth

- [ ] 547. **Inline provenance** — which source each script line came from, shown at review `[M]`
- [ ] 548. **Confidence per fact**, not only per source tier `[M]`
- [x] 549. **Script-vs-title contradiction check** *(2026-09-09)* - `check_title_script_consistency` was already called from `content_engine.py` and persisted; `display_fact_engine_report` had no reader (rule 21). A `failed` check now prints and returns needs-review; `unavailable` is printed and is not a pass. Fail-first: report returned `needs_review=False` with no "title vs script" line `[M]`
- [x] 550. **Refuse superlatives without a source** *(2026-09-07)* — `first ever` flags when facts omit it; passes when facts name it. `not only` does not fire `[S]`
- [ ] 551. **Date arithmetic check** — "18 months since" must match the actual dates in the facts `[M]`
- [ ] 552. **Number-unit sanity** — "80 hours" against a source that said minutes `[M]`
- [ ] 553. **Entity-role check** — developer vs parent company in the sentence that names them; run 71 shipped exactly this error `[L]`
- [x] 554. **Flag a fact only one source carries** *(2026-09-07)* — `singleton_source_claims` flags the ESPN-only Topuria line and leaves the two-host PPV line; `_build_prompts` appends `SINGLE-SOURCE` to context (no sixth `input()` gate) `[S]`
- [ ] 555. **Vault deduplication** — the same fact from three ingests should be one fact `[M]`
- [ ] 556. **Fact editor** — correct one pasted line without re-pasting the block `[M]`
- [x] 557. **Fact age at the prompt** *(2026-09-07)* — `stamp_as_of` on a 21-day `FactRecord` prints `as of last month` through `display_fact_preview` `[S]`
- [ ] 558. **Auto-expire notes about events that have now happened** `[M]`

Analytics & learning rigor

- [ ] 559. **Record the prediction at publish time** — fixes #355, whose residual is currently recomputed on every sync `[M]`
- [ ] 560. **A hold-out set the recommenders never see**, for honest error bars `[M]`
- [ ] 561. **Report the loop's own accuracy** on the report card, beside its advice `[M]`
- [x] 562. **Distinguish "no data" from "data says no"** *(2026-09-09)* - length with 0 samples now says `no engagement analytics yet`; 4 samples still say `N more measured video(s)`. Fail-first: both used the `more measured` template (`6 more` vs `2 more`). Learned post-time with an empty slot names `0 measured posts` instead of the no-analytics line `[S]`
- [ ] 563. **Time-to-first-100-views** as a faster signal than 7-day engaged rate `[M]`
- [ ] 564. **Exclude the operator's own views** from every metric `[S]`
- [ ] 565. **Retention-curve diffing** between two videos on the same franchise `[M]`
- [ ] 566. **Title-pattern lift against the channel baseline**, not the raw average `[M]`
- [ ] 567. **Publish-hour experiment that actually randomises** inside a safe window `[M]`
- [x] 568. **Flag a recommendation that flips week to week** *(2026-09-09)* - `note_week_flip` stamps ISO-week length / post-time picks under isolated `recommend_pick_{channel}.json`. A new week that disagrees prints `last week recommended X; this week Y`. Same week is silent. Corrupt stamp logs WARNING and prints `could not compare`. `display_recommended_length` / `display_recommended_time` are the readers `[S]`
- [x] 569. **Sample count beside every dashboard number**, unavoidably *(2026-09-09)* - `confidence_note` used to return `""` at n>=8. High-confidence now appends `(8 samples)` without the caveat wording. Fail-first: `'8 sample' not found in ''` `[S]`
- [ ] 570. **Archive the analytics snapshot per run** so a later code change cannot rewrite history `[M]`

Cost & efficiency

- [ ] 571. **A cost ceiling that degrades instead of refusing** — draft preset and cheap tier rather than a hard stop `[M]`
- [x] 572. **Show cost before the expensive step**, not after it *(2026-09-09)* — `features["projected_cost"]` is `estimate_run_cost(..., rendered=True)` before `proceed_video=False` returns. `display_fact_engine_report` prints `Projected cost if you proceed` with `tts $0.2700`. Fail-first: Proceed? report had no `0.27` `[S]`
- [ ] 573. **Cache the research brief across variants** of the same topic `[M]`
- [ ] 574. **Skip a signal whose data never reaches the script** `[M]`
- [ ] 575. **Measure which signals actually contribute facts** and retire the rest (decisions §19) `[M]`
- [ ] 576. **Batch TTS across a `batch-drafts` run** to amortise connection overhead `[M]`
- [ ] 577. **Reuse the existing render when only the description changed** `[M]`
- [ ] 578. **Cost per finished minute of video**, not per run `[S]`
- [ ] 579. **Warn when a run costs more than the channel's measured RPM returns** `[M]`
- [x] 580. **Free-mode cost report** *(2026-09-09)* — `free_mode_cost_proof` prints `billed $0.0000` or `not $0`. `ops free-cost` reads last-run persisted `cost`, not a fresh estimate (fail-first: last-run $0 re-estimated `$0.1725`). `[S]`
- [x] 581. **Track Edge TTS availability** *(2026-09-07)* — `_try_alt_tts_provider` calls `mark_tts_paid_fallback`; `display_summary` prints `edge failed — fell back to ElevenLabs` `[S]`
- [ ] 582. **Per-provider latency budget** — a slow provider is a cost too `[M]`

Signals & reliability

- [x] 583. **`trendingnow.games` fails DNS on every run** `[S]` *(2026-08-29)* - retired per decisions §19 in `apis/signals_bootstrap.RETIRED_SIGNALS`, with the reason and date recorded at the point of disablement and the module kept for revival. `SignalRegistry.unregister` makes the retirement an explicit call rather than a mutation of registry internals. §19's kill switch (`config/apify_sources.json`) only covers paid actors; this is the free-signal equivalent
- [x] 584. **YouTube RSS 404 on `UCq-Fj5jknLsUf-MWSik4vhQ`** *(2026-09-09)* — id removed from shipped `config/competitors/tapin.json`. `get_competitor_channels("tapin")` does not include it or a McAfee label. Health helper still accepts the id as a fixture `[S]`
- [ ] 585. **Per-signal contribution score** in the health block — "active" is not the same as "useful" `[M]`
- [ ] 586. **Signal result diffing between runs** on the same topic `[M]`
- [ ] 587. **A retry budget per run**, shared across signals, rather than per call `[M]`
- [ ] 588. **Detect a signal returning identical payloads every time** — a frozen cache reads as healthy `[M]`
- [ ] 589. **Fall back to a second search provider** when the first returns nothing `[M]`
- [x] 590. **Rate-limit headroom shown before discovery** *(2026-09-10)* - `core/discovery_headroom.py`, emitted from `build_registry` immediately before the ThreadPoolExecutor. Names the signal count, remaining YouTube units and uploads, LLM spend today, and per-purpose Apify usage. An unreadable store reports **unknown**, never zero - a fresh machine has full quota and printing "0 units" would read as exhaustion. Flags a pool that cannot finish on the units left. Measured 0.8ms steady per call `[S]`
- [ ] 591. **Signal timing histogram** to replace the hardcoded estimate in the spinner `[S]`
- [ ] 592. **Cache warming for the franchise anchors** this channel covers weekly `[M]`
- [x] 593. **Show domain gating in the health block** *(2026-09-07)* — `display_signal_health(..., topic=, ask=False)` prints gated `live_scores`/`odds` for a UFC topic on tapin; `main.py` passes topic `[S]`
- [ ] 594. **Offline mode** — run from cache only, no network, for script editing `[M]`

Publish, policy & channel ops

- [x] 595. **Dry-render the description exactly as YouTube will show it**, including the fold *(2026-09-09)* — `fold_preview` splits at ~100 chars; above <= 110; `ops desc-fold`. Short copy has nothing below `[S]`
- [x] 596. **Detect a title that duplicates a competitor's word for word** *(2026-09-08)* — `verbatim_competitor_advisory` over `list_recent_competitor_titles`. Advisory string on quality `[S]`
- [ ] 597. **Generate the community post from the finished video** `[M]`
- [ ] 598. **Track scheduled vs immediate uploads** and how each performed `[S]`
- [x] 599. **Verify the thumbnail actually applied** after upload *(2026-09-09)* — after `thumbnails.set`, `videos.list`; default-only is `unverified`; `maxres` is `set`. Fail-first: MagicMock list was treated as custom; non-dict payload is now unverified `[S]`
- [ ] 600. **Re-check monetisation status 48h after publish** `[M]`
- [ ] 601. **Playlist auto-assignment by franchise** (#104) driven from the fact corpus `[M]`
- [x] 602. **End-screen placement that avoids the caption safe area** *(2026-09-07)* — `end_card_text_y(80)` stays in `[0.12h, 0.80h]`. ffmpeg graph is not `y=(h-text_h)/2`. Preview PNG uses the same helper `[M]`
- [ ] 603. **Surface a Content-ID claim** from the API rather than finding it in Studio `[M]`
- [ ] 604. **Localise the description's first line** per audience region `[M]`
- [x] 605. **Publish dead-man's switch** *(2026-09-09)* — `PUBLISH_DEADMAN_DAYS` opt-in. Stale 10d heartbeat with limit 7 blocks `YouTubePublisher.publish` before `get_youtube_service`. Unset env does not block. Import failure WARNs `[S]`
- [ ] 606. **Per-channel upload checklist** that must be green before the button enables `[M]`

Performance & startup

- [x] 607. **Defer `elevenlabs.client` past import** *(2026-09-07)* — `core.tts` no longer imports the SDK at module load. `_elevenlabs_client` constructs it on the first paid synth. Piper/edge do not pay the import. Tests still patch `core.tts.ElevenLabs` `[S]`
- [x] 608. **Defer `googleapiclient.discovery` and `sports.espn`** *(2026-09-07)* — `apis.youtube_api` and `apis.live_scores_api` import with those modules absent; `build` / `get_scoreboard` load on first live call `[S]`
- [x] 609. **Startup budget test** *(2026-09-08)* — `measure_import` / `measure_import_fresh`; `core.chrome` ratchet 5.0s. Clock is injectable; no network. `ops doctor` prints the budget `[S]`
- [ ] 610. **Lazy-import the 92 `ops` verbs** so running one does not load all of them `[M]`
- [ ] 611. **Parallelise the render's independent ffmpeg passes** `[M]`
- [x] 612. **Cache Pillow font objects** *(2026-09-07)* — `load_font("arial.ttf", 24) is load_font("arial.ttf", 24)`; size 32 is a different object. End-card preview and caption overlay call it `[S]`
- [ ] 613. **Profile `core/ui.py`** — 1,783 lines of display code runs around every prompt `[M]`
- [ ] 614. **Stream the LLM script** so the operator reads while it generates `[M]`
- [ ] 615. **One HTTP session across signals**, pairing with #391's single client `[M]`
- [ ] 616. **Measure and cap peak render memory**, which the packaged app will be judged on `[M]`

Data model & storage

- [ ] 617. **Run every Alembic revision against a real snapshot** in CI `[M]`
- [ ] 618. **Retire `migrate_schema`** once Alembic is the only story (#35) `[M]`
- [x] 619. **Stamp a schema version on every run-ledger row** *(2026-09-08)* — `persist_quality` and `write_run_trace` stamp Alembic head (`0004`). No history backfill `[S]`
- [ ] 620. **Soft-delete runs** so a mistaken purge is recoverable `[M]`
- [ ] 621. **Export a run as one portable folder** — mp4, script, facts, trace `[M]`
- [ ] 622. **Import that folder back**, for moving between machines `[M]`
- [x] 623. **Database size and vacuum report** *(2026-09-07)* — `reliability.gather()["store"]` prints sqlite bytes (or `database n/a`). VACUUM is leftover #688 `[S]`
- [ ] 624. **Separate the operational store from the analytics store** before the app reads both `[L]`

Testing & ops hygiene

- [x] 625. **Audit every test double against its target's real signature** *(2026-09-07)* — `audit_known_doubles()` checks `_full_one(url, log)`, edge `Communicate(..., boundary=)`, and dated `tags: [facts]` fixtures. Dated the two undated notes in `test_description_sources.py` `[M]`
- [ ] 626. **Contract tests generated from each signal's recorded payload** `[M]`
- [ ] 627. **Mutation testing on the gate modules** — do the tests actually detect a broken gate `[L]`
- [ ] 628. **Flaky-test detector** across repeated CI runs `[M]`
- [x] 629. **Test-time budget** *(2026-09-08)* — `measure_callable` with injectable clock; cousin of #609. CI-failing threshold helper, no network `[S]`
- [x] 630. **ops selftest** - run the safety gates against fixtures and report *(2026-09-13)* - `core/selftest.py` + `ops selftest`: eight gates (authenticity, grounding, negative-fact veto, thin facts, over-length, metrics, unattended render, publish dead-man) each get a fixture that must block and one that must pass, run with the gate armed and the env restored after. Fixtures are passed in, so no store is read (a test refuses every store). `authenticity.blocks_render` puts `main.py`'s stop rule in one place so the selftest tests the same decision. Real run: **8/8 work; 4 are not armed on this machine** (#735). `armed here` is shown, never failed `[M]`
- [x] 631. **Coverage reporting for `core/` only**, non-blocking, to find untested gates *(2026-09-13)* - the CI unit-test job runs the suite under `coverage run` and prints `coverage report --include="core/*" --sort=cover` as a report-only step (`continue-on-error`). `coverage` is not in the local env, so the table exists only in the CI log. Guard reads the live steps; removing either goes red `[S]`
- [x] 632. **Size-tag the 49 open items that carry none** *(2026-09-07)* — `untagged_open_items()` uses the same backtick `SIZE_RE` as `ops roadmap-index`. 49 unnumbered early-backlog rows had `[S]`-style tags on a continuation line or none; they now carry `` `[S]` `` / M / L / XL on the `- [ ]` line. Index untagged **0** `[S]`
- [x] 633. **A docs test that every `ops` verb named in a doc exists** *(2026-09-07)* — `verbs_named_in_docs()` vs `COMMANDS`; `` `ops review-room` `` is in the set. Flags (`--html`) and unbuilt names written as prose are not verbs `[S]`
- [x] 634. **Run the docs lint in pre-commit**, not only ruff *(2026-09-08)* — local hook `ops-command-ref` calls `check_command_ref()` (the existing registry vs `docs/ops_commands.md` check) `[S]`

Security & privacy — local

- [x] 635. **Redact the vault path and username** from every HTML dump *(2026-09-07)* — `redact_operator_paths` replaces vault with `[vault]` and `USERNAME` with `[user]`. `themed_page` runs it. Traces are a leftover (#674) `[S]`
- [x] 636. **Prove no secret reaches `data/traces`** *(2026-09-13)* - `core/run_trace.py` redacted by key name only, so a secret inside a value (an LLM error echoing the key, a `?api_key=` source URL, a topic, `menu_path`) was written verbatim; the fail-first test wrote all four. `_scrub_secrets` now replaces current env values of *KEY*/*TOKEN*/*SECRET*/*PASSWORD*/*AUTH* vars (>= 8 chars, so `true` never scrubs text) and strips secret-named URL params on write. `ops trace-secrets-scan` checks what is on disk without printing a value: 28 real traces, 0 hits `[M]`
- [ ] 637. **Encrypt `config/secrets/` at rest** with a machine-bound key `[M]`
- [x] 638. **`SPORTSDATA_API_KEY` and `STEAM_API_KEY` are declared in `.env.example` and read nowhere** *(2026-09-07)* — Steam storesearch appends `STEAM_API_KEY` when set. SportsData was unread: deleted from `.env.example` and `config/data_sources.json` `[S]`
- [x] 639. **An `.env` linter** for keys read but undocumented and documented but unread *(2026-09-13)* - `core/env_lint.py` + `ops env-lint`: literal reads through `os.getenv` / `os.environ.get` / `os.environ[]` / `flag_enabled` / `_flag` / `_f` / `_env_*` against `.env.example` keys including commented `# FLAG=` lines. Measured: **326 read, 273 documented, 73 undocumented** (including both Apify credentials, `APIFY_CONTENT_MACHINE_KEY` and `APIFY_BENABLE_BOT`), 20 documented but unread, 27 dynamic reads (a stated blind spot). The filed 392 came from a looser grep. `config/env_lint_baseline.json` freezes the 73: a new undocumented key fails `tests/test_wave11.py`, and so does a baseline key that is no longer read `[M]`
- [x] 640. **Audit what a packaged app would ship** - no keys, no vault, no `data/` *(2026-09-13)* - `core/package_audit.py` + `ops package-audit` build the wheel and sdist from the working tree into a temp dir and flag, by member name only, forbidden paths (`.env*`, `config/secrets/`, runtime `data/` / `output/`, keys, token JSON), members containing a current secret env value, and members containing an operator path. `config/secrets/` holds three real OAuth files on disk; none ships. Real run: wheel 373 files, sdist 378, **0 hits** - after replacing the operator's real Windows username, hardcoded as a fixture in `tests/test_stage2_html.py:134-146`, that had been shipping in the sdist. The build removes only the `build/` / egg-info directories it created. A PyInstaller bundle does not exist yet (Stage 5) `[M]`

Loopholes found 2026-08-28 — shipped, green, and inert

- [x] 641. **Six ANSI themes are unreachable** *(2026-09-06)* — shipped `ui_theme`: tapin=`dbz`, moneywise=`plain`, default=`plain`. `set_channel_theme()` now has a channel value to resolve `[S]`
- [x] 642. **`tts_voice_pool` is unset on both channels** *(2026-09-06)* — `tts.voice_pool` set on tapin, moneywise, and default `[S]`
- [x] 643. **`local_tts_voice` / `local_tts_voices` unset on both channels** *(2026-09-06)* — Piper `.onnx` paths from `config/voices.json` `local.piper` now per channel. Side effect: `test_piper_without_voice_model_returns_none` had to clear the profile — the live tapin pool was a real file `[S]`
Run-74 follow-ups (2026-08-29) — filed while fixing the abort chain

- [x] 645. **The report card does not weight length** — run 74 shipped 277 words against a 300-word floor and graded **A (87)**. `_relength_after_postprocessing` now re-checks after the passes that shorten a script, but nothing scores the outcome. Deferred deliberately: adding a component changes the meaning of every historical grade, so it needs a migration story `[M]` — **shipped 2026-09-05**. The deferral was a migration story, and the mechanism for one did not exist: `GRADE_VERSION` was a string **nothing read, wrote or compared**, while `core/grade_calibration.py` re-grades every stored run with today's code — so the three components that moved on 2026-08-30 were already silently re-scoring history. Now: `VideoGrade.version` is stamped and `GRADE_VERSION` is **v2** covering both changes; `QUALITY_VERSION` is **v3** for the new `word_count`/`min_words`/`max_words` keys; and `_length_score` derives from the same floor comparison `format_length_report` already shows the operator, so two components cannot disagree (#653's lesson). A row without length keys renormalises over what it has and its score is **unchanged**. Measured on run 74's real components: **A 86.8 -> B 82.8** at 277 words against a 300 floor, in-range still A 88.1
- [x] 646. **`scripts/auto_generate.py` does not get scored fact selection** *(2026-09-06)* — `select_headless_facts` ranks file lines as `TIER_LINK` and `--fact` as pinned operator. Overnight `generate_draft` packs through it. Run-74 scaffolding lost to "Six Wanted Stars" on a 420-char budget `[M]`
- [x] 647. **Tune the fact-selection weights against real traces** *(2026-09-06)* — `measure_weight_split` on two fixtures (run-74 GTA strings + UFC). Current split beat insertion and equal weights -> `WEIGHT_MEASUREMENT["verdict"] = "held"`. Operator `data/traces` was empty; tests never read that store `[M]`
- [x] 648. **`_SCAFFOLDING_MARKERS` is a hand-built list** *(2026-09-06)* — structural deixis (`this/the article|page|wrap-up|roundup|…`) adds a 0.5 penalty when the phrase list misses. Furniture with no list marker loses to a detail line on a tight budget. Hard-number discount unchanged; **#647 weights not retuned** `[M]`
- [x] 649. **The claim verifier passed 12/12 on facts that were themselves truncated** *(2026-09-06)* — `verify_claims` (real, LLM mocked) prompt includes a negation tail past the old 400-char slice. `_MAX_FACT_CHARS` stays 6000. Run-74 drones/K9/hurricane script strings are **not in the repo**; known-gap test asserts that so this is not a whole-script lock `[M]`
- [ ] 650. **`read_pending_lines` is untested against a real Windows console** — the unit tests patch the backend, because CI has no tty. One manual smoke test per platform, recorded, would close the gap `[S]`

- [x] 644. **Config-coverage test** *(2026-09-06)* — `TestShippedConfigRatchet.test_no_profile_field_is_unset_on_every_shipped_channel` reads real `get_channel_profiles()`. Failed first on `local_tts_voice`, `local_tts_voices`, `ui_theme` `[M]`

Idea-quality wave (2026-08-30) — filed from [idea_quality_diagnosis.md](idea_quality_diagnosis.md)

- [x] 651. **The variant scorer does not rank** *(2026-08-30)* — `_VARIANT_REUSE_DEFAULT` pins every signal during variant scoring, so all five variants are scored against the base topic's signals, and the variant string reaches `composite_score_raw` only via `infer_domain` (same domain for five framings) and `get_historical_boost` (an exact-string lookup, so 0.0 for a fresh angle). Five angles, identical inputs, one number: run 71 tied at 100.00, run 72 at **92.14** — under the ceiling, after #323 shipped. New `core/angle_ranker.py` scores the angle *text* (distinctness / seed fidelity / specificity), deterministic and network-free, because re-fetching per variant costs 150-185s and 5x web spend and would not separate them anyway. Carried as a third dict on `DiscoveryResult` and a third key in `best_variant_index` — **not** folded into the composite, since averaging one unvalidated number into another hides both. Also fixed the three consumers that bypassed the ranking rule entirely (`intelligence_report`, `batch_generation`, `auto_generate` used `evaluated[0]`). Measured on run 72's five real angles: one number becomes four distinct ones `[M]`
- [x] 652. **The vault playbook was truncated, not ranked** *(2026-08-30)* — `load_playbook` took the first 8 bullets in file order, and `tapin/playbook.md` opens with two "Narratives that work" sections, so 8/8 bullets reaching every tapin script prompt were hot-take heuristics and 100% of that file's own "Hook rules" and "Hard rules (anti-hallucination)" were cut. Now grouped by the operator's own `##` headings (`vault_index.NoteEntry.bullet_sections`, additive) and taken round-robin, so no section spends the whole budget. `playbook_block`'s char-budget `break` became a `continue` — one long bullet used to silently discard every bullet after it. Measured on the real vault: the block now carries a narrative rule, the hook rule, the anti-hallucination rule, the voice rule and the format rule `[S]`
- [x] 653. **Gate agreement did not cover the hook scorer or the slop lists** *(2026-08-30)* — `test_gate_agreement.py` compared `_INSIGHT_MARKERS` against `_FILLER_PHRASES` and one prompt line only. Meanwhile `hook_score._CURIOSITY` paid +15 for `"nobody's talking"` (banned in `topic_variants`, slop in `title_generator`) and `authenticity` paid 35/100 for the literal `"hot take"` (which `title_generator` bans by name) — **56% of the report card rewarding what the rest of the system forbids**. Extended to all four ban lists with a multi-line extractor (the single-line trick silently dropped `"my hot take"`), phrase-boundary matching so bare words like "nobody" are not false positives, and vacuity guards so a scrape that finds nothing fails instead of passing. Removed the offending reward terms, added a banned-template guard to `score_hook`, and fixed the script prompt teaching `"This changes everything for the division."` — a hook `_clean_title` discards `[S]`
- [x] 351. **Confidence intervals, not just sample counts** *(2026-08-30)* — `confidence_interval` / `interval_note` in `core/recommender_confidence.py`, consumed by best-bet, length and post-time. `None` below two samples rather than 0.0, because n=1 is where the loop's priors actually live and a zero-width interval reads as certainty. `_slot_engagement` now returns its sample vector (it was the only recommender discarding the spread). Reported in points, not percent: "30.6% +/- 22%" invites reading the 22 as relative. Run 71's cited figure now prints `30.7% across 3 video(s) +/- 28pp` `[M]`
- [x] 654. **Best-bet ranks on the shrunk rate but prints the raw mean** — `_adjusted_domain_rates` empirical-Bayes-shrinks for `_domain_priority`, then the rationale prints the unshrunk average. Now that #351 puts an interval next to that number, the two disagree in public `[S]` — **shipped 2026-09-05**: `_ranked_on_note` appends the empirical-Bayes-shrunk figure that `_domain_priority` actually sorted on, at the caller's own precision, and stays silent when shrinking changed nothing. The raw mean stays the headline because #351's interval is computed over that same raw vector - swapping the point estimate without the interval would trade one quiet disagreement for another. Fixed in `get_best_bet` and `_emit_fresh`; deliberately **not** in `_emit_hist`, which prints one run's own rate and would be comparing two different quantities. Measured: `nba averages 11.0% ... +/- 0pp (ranked on 12.6% shrunk toward the channel mean)`
- [x] 655. **`confidence_note` emits `⚠`, which is not cp1252-safe** *(2026-09-06)* — note now uses ASCII `!`. `encode("cp1252")` of the note no longer raises `[S]`
- [x] 656. **A hook built on a banned template earns no bonus but takes no penalty** *(2026-09-06)* — `score_hook` applies -20 `"banned template"` after skipping curiosity/stakes bonuses. Run-style slop `"Nobody's talking about the GTA 6 map size."` dropped below a neutral hook. Same `GRADE_VERSION` v3 bump as #660 `[S]`

Next-five wave (2026-09-05) — filed while shipping #654 / #645 / #383 / #533

- [x] 657. **A TTS cache hit billed characters it never synthesized** *(2026-09-05)* — found while scoping #402. `record_tts_actual` ran *before* `tts_cache_lookup` in `generate_audio`, so a cached render stamped a full script's worth of "actual synth chars" and `core/pipeline.py` persisted it as `tts_actual_chars` into the run ledger — the number the operator and the analytics layer read. Same class as the run-71 verifier defect: a measurement reporting clean while measuring the wrong thing. Actuals are now recorded after the cache decision, `0` on a hit. The test also exposed that `_last_cache_hit` is a module global no test reset, so an existing "no hit yet" assertion was really asserting alphabetical test order `[S]`
- [x] 658. **`generate_audio` needs a per-segment synthesis seam before #402 can land** *(2026-09-06)* — `synthesize_to_path` owns alt / Piper-quota / timestamps / plain / mix / voice-retry / cache store. `generate_audio` owns lookup + `record_tts_actual`. Cache hit does not call the seam `[M]`
- [x] 659. **Carry the detected intent into the research brief** *(2026-09-06)* — explainer seed -> `explainer` format, no Controversy block. Cache key is `channel::topic::intent` `[M]`
- [x] 660. **Make the script prompt's take block intent-conditional** *(2026-09-06)* — explainer prompt lacks `TAKE A SIDE`; `_maybe_inject_insight` is a no-op for `CALM_INTENTS`. `GRADE_VERSION` **v3** with #656 `[L]`
- [x] 661. **Two independent intent classifiers disagree** *(2026-09-06)* — `classify_angle` calls `detect_angle_intent` first. `"GTA 6 looks amazing!!!"` is `reaction`. `FEATURE_VERSION` **v2** `[M]`
- [x] 662. **`grade_calibration` mixes rubric versions** *(2026-09-06)* — mixed `grade_version` sets `grade_correlation` to None and says so. `build_quality` stamps `grade_version` `[M]`
- [x] 663. **Nothing runs the signal canary** *(2026-09-06)* — overnight `_probe_signals` after pause; `all-checks` inventory does not include it. `_FAILED` is the only non-zero exit `[S]`
- [x] 664. **Option 5 idea is only a search seed** *(2026-09-06)* — `creative_brief_for_run` always populated; YouTube search=title, brief=OUR take; candidate 0 in `display_variants`; `chosen_variant(..., -1)` keeps `input_topic` `[M]`
- [x] 665. **Traces cannot say which menu path or intent produced a run** *(2026-09-06)* — optional `menu_path` / `angle_intent` on `write_run_trace`; omitted stays absent. Option 5 passes `"5"` `[M]`

Review of the 2026-09-06 wave (Claude, 2026-09-06)

- [x] 666. **A sentence-TTS concat failure still double-bills** *(2026-09-06)* — `ffmpeg_concat_ready()` (PATH + memoized `libmp3lame`) gates `_generate_by_sentences`. Preflight fail → one `synthesize_to_path` of the whole script, never N segments. `TTS_CACHE=true` + `which`→None: seam called once, billed chars = one script `[S]`

Stage 0 + leftover craft (2026-09-07) — filed on the way

- [x] 667. **Pinned-status CSI is untested against a real Windows Terminal** *(2026-09-13, wave 14)* — run 76 PowerShell bled `~1,600)` onto every line because pin defaulted on for any TTY. On `win32`, `pin_enabled()` is now off unless `CONTENT_UI_PIN=1`. Fail-first: `sys.platform` patched to `win32` (not the operator's real platform). CSI save/restore itself is unfixed if opted in `[S]`
- [ ] 668. **The Windows Terminal profile snippet is not installed** — `config/windows-terminal/profiles.json` is checked in; nothing merges it into the operator's WT `settings.json` `[S]`
- [x] 669. **`ops intro-waveform` offset is the TapIn constant, not a probe** *(2026-09-07)* — `intro_offset_seconds` reads `channels.json` (`tapin` 2.15, `moneywise` 0.0); waveform uses that, not `DEFAULT_INTRO_DURATION` alone `[S]`

Stage 1 run window (2026-09-07)

- [x] 670. **Stage 1 has no CI Qt** — `pip install -e ".[app]"` is optional; CI does not install PySide6. Bridge tests always run. The offscreen widget test skips without the extra. A live topic-to-mp4 in the window is still an operator smoke `[S]` — **closed 2026-09-07 (Claude review)**: CI installs `.[shell,app]` and runs with `QT_QPA_PLATFORM=offscreen`, and the typecheck job now includes `desktop`. Measured first: masking PySide6 at `sys.meta_path` (what CI saw) gave **23 ran, 3 skipped**; headless offscreen gives **23 ran, 0 skipped**, and mypy over `desktop` adds **zero** new errors (144 held, 291 -> 296 files). Cursor had structured the tests well — only widget construction was guarded — so this was two lines, not a rewrite
- [x] 671. **Angle variants are not a visual list** *(2026-09-07)* — `display_variants` posts titles on `AskBridge.set_choices`; the run window shows a `QListWidget`. Click/Enter submits `1`–`5`. CLI `ask_choice` is still a string. Guard: deleting `set_choices` leaves the list empty `[S]`

Stage 2 look + 20 (2026-09-07) — filed on the way

- [x] 672. **Grain/vignette ffmpeg is argv-only** *(2026-09-07)* — `measure_look_noise` encodes a flat frame with TapIn `noise=` and asserts `with_look` stddev > `plain`. `ops grain-grade` is the operator path. A still from a *real render* (not a 64px fixture) is still operator smoke `[S]`
- [ ] 673. **Second-monitor restore is untested on a second physical display** — state stores `screen` name; offscreen DPR is 1.0. Same class as #650 / #667 `[S]`
- [x] 674. **Trace JSON is not passed through `redact_operator_paths`** *(2026-09-07)* — `write_run_trace` walks string values through `chrome.redact_operator_paths`. Test patches `Path.home()` / `USERNAME` / `USER` to `/home/ciuser` so this box's username cannot make it pass. #636 (secrets in traces) is still open behind it `[S]`

Claude review of the Stage 0-2 waves (2026-09-07)

- [x] 675. **A shipped test would have failed on CI** *(2026-09-07)* — `tests/test_stage2_html.py`'s `themed_page` assertion was dedented **out of** its `patch.dict` block, so it ran with no `OBSIDIAN_VAULT_PATH` (`tests/__init__.py` forces that empty suite-wide anyway). It passed only because this developer's home directory contains the username, so the *home* rule removed the name the *vault* rule was meant to. Simulated ubuntu-latest: the username survived into the page and the assertion failed — every CI job runs ubuntu. Re-indented, `Path.home` pinned away from the fixture, and `[vault]` asserted so a pass proves the vault branch ran. Self-refuting to ship in the same commit as #625, whose whole subject is tests that pass for environmental reasons `[S]`
- [x] 676. **Stage 2's token CSS lost the cascade to the legacy palette** *(2026-09-07)* — `html_report.py` emitted the generated CSS *before* `_CSS`, which redeclares `html, body`, `header`, `pre`, `table`, `.card` and `a` at equal specificity, so the later block won. Measured on a rendered page: token background at offset **311**, legacy at **1894** — every HTML dump still rendered the old colours while `desktop_app.md` claimed dumps share the generated CSS. Order swapped; `_CSS` is now the structural base and tokens override. The guard test named `test_html_dump_uses_generated_css_not_a_second_palette` could not fail (it asserted token hexes were *present*, and one already appears in `_CSS`), so it gained a cascade-order assertion `[S]`
- [x] 677. **Closing the run window mid-render abandoned the run** *(2026-09-07)* — the worker is `daemon=True` and was never joined, and `AskBridge.cancel()` only unblocks a worker *currently sitting in an ask*. A worker inside ffmpeg, TTS or an upload noticed nothing and the interpreter exited without waiting: orphaned encode, half-written mp4, spent quota with no publish-log write. That is the run-73 failure `desktop_app.md` cites as the reason Stage 1 exists. `desktop.session.shutdown_worker` cancels, joins with a bounded timeout, and **warns naming what is being abandoned** when a worker cannot be stopped — deliberately still closing, because trapping the operator in a window that will not close is worse. Testable without Qt, so it runs in CI `[S]`
- [x] 678. **`emit()` read the quota JSON once per printed line** *(2026-09-07)* — `emit` -> `refresh_pin` -> `format_uploads_left` -> `get_usage_summary` -> a `json.load`, on every line, including when `pin_enabled()` is False and nothing is painted. Measured: **25 formats for 25 emitted lines**. Recompute is now throttled to 1s (the pinned numbers cannot change faster) while the cached line is still repainted, so the pin stays pinned through a burst of output. `reset_pin` / `set_pin_context` / `set_pin_cost` clear the clock so a changed context never waits it out `[S]`
- [x] 679. **Three Stage 2 items shipped green but inert** *(2026-09-07)* — `#296` HTML is written next to the PNG by `ops contact-sheet`. `#540` rhythm prints in `display_fact_engine_report`. `#541` JSON-only phrase `here's the kicker` flags, and emptying the file makes the same script clean `[M]`
- [x] 680. **`#542` mutates the delivered script with no operator surface** *(2026-09-07)* — `CTA_SUMMARY_STRIP` (default on). Gate off keeps `In summary` before CTA. Gate on strips it and the printed report shows pre/post paragraph counts `[S]`
- [x] 681. **`pipeline.py` assigns two features twice** *(2026-09-07)* — duplicate `cta_summary` / `sentence_rhythm` assignments deleted. Source now contains each key once `[S]`
- [x] 682. **decisions §4 still cites the retired 4500-char fact budget** *(2026-09-07)* — §4 now matches live `OPERATOR_KEY_FACT_CHAR_BUDGET` default **12000** `[S]`

Stage 3 leftovers (2026-09-07)

- [x] 683. **HUD-aware owned beat picks** *(2026-09-07)* — `detect_hud` on a rainbow top-bar PNG is True; uniform green is False. Ingest persists that bool. `assign_owned_clips` skips `hud: True` when a clean clip exists. *(2026-09-08)* `hud: None` on a **real file** is probed; missing paths skip as #693 `[S]`
- [x] 684. **Review room decodes a live mp4 through the window** *(2026-09-10)* - `ReviewWindow` is now constructed with the committed fixture and asserted to reach `LoadedMedia` with `duration() > 0` and no player error. Two of the three new tests passed on first run, so the decode itself was already fine; **the real defect was `QAudioOutput()` built unconditionally**, which raises on any machine with no audio sink and cost the operator the video as well as the sound. Now wrapped: a failed sink logs a WARNING and plays silent. The drafted-run refusal is pinned so the audio change cannot erode it `[S]`
- [x] 685. **`hud: None` clips are still chosen** *(2026-09-08)* — `assign_owned_clips` calls `detect_hud` when `hud is None` and the file exists. Missing paths skip as #693 `[S]`
- [x] 686. **Retraction watch 24h toast** *(2026-09-08)* — overnight/tray call `maybe_toast_retractions` with a 24h debounce stamp. CLI `ops retraction-watch` still prints and does not toast. #112 correction dossier stays open `[M]`
- [x] 687. **Config diff does not fingerprint `.env`** *(2026-09-08)* — `env_fingerprint` hashes presence/shape of `.env.example` keys (`set`/`empty`/`missing`), never values. Stamped on the trace as `env_sha256` next to `channels_sha256`. `ops secrets-doctor` still never prints a secret `[S]`
- [x] 688. **`ops reliability --vacuum`** *(2026-09-08)* — `vacuum_sqlite(path)` on the caller-named file. Tests use a temp sqlite; never vacuum the operator DB from the suite `[S]`

Stage 4 leftovers (2026-09-08)

- [x] 689. **Same-run bind + refuse drafted Approve** *(2026-09-08)* — `bind_review_media` never pairs a leftover `output/` mp4 with drafted run 75. Approve disabled + on-screen reason when status is `drafted` or path empty. Fixture: live run 75 strings `[S]`
- [x] 690. **QSS must not emit `filter:`** *(2026-09-08)* — `build_qss` drops the CSS filter line (Qt does not implement it; live log was `Unknown property filter`). `themed_css` keeps `body.reduced-chroma`. Guard: QSS with `filter:` fails `[S]`
- [x] 691. **Autoplay after `setSource`** *(2026-09-08)* — `start_review_player` calls `play()` when the file exists. Fake player records the call; no live decode in CI `[S]`
- [x] 692. **Studio canvas drag / snapping** *(2026-09-08)* — one `ItemIsMovable` layer; chrome/title-safe guides stay locked. On release, clamp into `title_safe` (not chrome). Geometry tests without Qt `[L]`
- [x] 693. **`hud: None` on a missing path is skipped** *(2026-09-08)* — same skip as `hud: True` when `not os.path.isfile(path)`. Known-gap tests now expect `[]` `[S]`


Review 4 - what the four waves shipped green but inert (2026-09-08)



- [x] 694. **#365 recency decay never decayed anything** *(2026-09-08)* - `recency_weight` / `weighted_engaged_mean` were wired into `get_best_bet`, but `_build_entries` never set `age_days`, so every weight was `recency_weight(None) == 1.0` and the weighted mean equalled the arithmetic mean it replaced. The only test drove the two helpers in isolation. `age_days` now comes from `PublishLogRecord.published_at`; a 400-day 10% sample no longer ties a 2-day 40% one `[S]`

- [x] 695. **Three new `quality` keys had no reader** *(2026-09-08)* - #302 `numeric_outliers`, #596 `competitor_title_duplicate` and #367 `clock_tonight` / `clock_weekend` were persisted by `build_quality` and read by nothing: not the dossier, not the booth, not the report card. `ungrounded_numeric`, written two lines above them, has one. `render_dossier` now prints all four `[S]`

- [x] 696. **The retraction watch fetched before checking its own throttle** *(2026-09-08)* - `notify_retractions_if_due` pulled up to 12 URLs at an 8s timeout each and only then asked `maybe_toast_retractions` whether it had toasted in the last 24h; `ops tray` calls it, so an interactive command could block ~90s to decide it had nothing to say. `toast_is_due` is now consulted first. Separately, `pairs_from_trace` scraped URLs out of `json.dumps(trace)` with a pattern that stops at whitespace / `]` / `>` / `)` but not at a quote - every URL arrived as `https://x/a",`, every fetch 404'd into the blanket handler, and #341's trace path had never watched anything `[M]`

- [x] 697. **HUD probe leaked a temp directory per clip per render** *(2026-09-08)* - `detect_hud` mkdtemp'd for the extracted frame and never removed it, on a path `render_video` reaches through `assign_owned_clips` for every clip whose index entry predates #683. The directory is now removed in a `finally`, and a process-local memo keyed on (path, mtime, size) stops an overnight batch re-probing the same clips once per draft `[S]`

- [x] 698. **`.pre-commit-config.yaml` documented an install that cannot run** *(2026-09-08)* - line 1 said `pre-commit install`, but this repo sets `core.hooksPath` to `.githooks`, so git never reads `.git/hooks` and recent pre-commit refuses to write a hook that would never fire. The header now gives the two commands that do work and says why `[S]`

- [x] 699. **`_CSS` was regrowing a second hex palette** *(2026-09-09)* - d1a1895 only swapped emission order, which wins the cascade solely for selectors BOTH blocks declare; `themed_css` never declares `.phone-bezel` / `.yt-mock` / `.cheat-sheet`, so those hexes were unopposed and ordering could not reach them. No token role existed for the chrome greys at all, so a `surfaces` group was added to design_tokens.json (bg/surface/sunken/bezel/border/ink/ink_dim/ink_faint/link/danger_bg/accent_line) at the legacy values verbatim, emitted as custom properties on `:root` by `themed_css`, and all 57 non-exempt literals became `var(--...)`. The remaining sites carry `/* palette-exempt: reason */` - skip link, media letterbox, forced-contrast and print blocks, and the YouTube-chrome mock. A new scanner test fails on any unexempted hex: measured 60 offenders on 352c547, 0 now `[S]`

- [x] 700. **`PostgresJobRepository.claim_next` dropped its `LIMIT 1`** *(2026-09-09)* - now orders in SQL (coalesce(payload_json sort_key, id), id) with `.limit(1).with_for_update(skip_locked=True)`. The filed defect was the unbounded fetch; reading it found the larger one - the SELECT/UPDATE/commit carried no row lock at all, so two workers on the supported path could claim the same job. Fail-first: the emitted SQL had no LIMIT. SQLite tests prove ordering and LIMIT. **`skip_locked` is now measured on real Postgres (#704)** `[S]`

- [x] 701. **`resolve_relative_clock("this weekend")` resolved into the past** *(2026-09-09)* - measured: Saturday 20:00 ET returned Saturday 12:00. Now rolls forward to the Sunday, which is still this weekend, and takes the next Saturday only once Sunday noon has passed. It was operator-visible, not inert: #695 gave `clock_weekend` a reader in the run ledger. The existing guard pinned `now` to a Wednesday and asserted only `weekday() == 5`, which the buggy code satisfied on every day of the week `[S]`
- [x] 702. **The retraction watch's trace path is inert in production** *(2026-09-09)* - `pairs_from_trace` now reads structured `source_urls` first. `build_features` copies `content_package["source_urls"]` (already set by the engine at `content_engine.py:1371`) and `write_run_trace` persists that list. Fail-first on f8c39b2: `KeyError: 'source_urls'`. Connected path: `build_features` -> `write_run_trace` -> `pairs_from_trace`. JSON scrape kept only as legacy compatibility. `_slim_signals` still drops URLs; that is no longer the contract `[S]`
- [x] 703. **The correction scan has no throttle** *(2026-09-09)* - reuses `toast_is_due` / `write_stamp` (`{"last": ISO}`). Overnight still calls `scan_published_for_corrections(channel)` with no `force`; `ops corrections` passes `force=True`. A completed scan stamps even when `found == []`. Fail-first: unexpected keyword `stamp_path`. Wave 5 dossier tests now pass a per-vault `stamp_path` so a suite stamp cannot skip their fetch `[S]`
- [x] 704. **`skip_locked` on `claim_next` is unproven** *(2026-09-09)* - CI now runs `postgres:16` with `CONTENT_TEST_DATABASE_URL=.../content_machine_test`. Locally: holding `FOR UPDATE` on job A, `claim_next` returned job B in 0.3s; without `skip_locked` it blocked 2.16s (`claim_next blocked instead of using SKIP LOCKED`). The operator `DATABASE_URL` / `content_os` is never read. Found on the way: #709 `[M]`
- [x] 705. **A vanished claim does not file a correction** *(2026-09-09)* - after the retraction-word miss, token-overlap coverage (not substring). Explicit retraction stays `high`. A page that dropped the claim files `medium`. Ordinary rewording (`Jones beat Pereira` vs `Jon Jones defeated Alex Pereira`) does not file. Overnight still unforced; stamp still written. Fail-first: vanished body filed 0 dossiers `[M]`
- [x] 706. **`ReviewWindow.keyPressEvent` has zero tests** *(2026-09-09)* - fake `_RecordingPlayer` injected onto `window._player` with an empty mp4 path. J seeks to 7000, L to 17000, comma/period one frame, K pauses, space does not seek, `?` prints the cheat sheet, S saves a still. Fail-first with `keyPressEvent` reduced to `super()`: positions stayed `[]` instead of `[7000]`. Local PySide6 ran the tests; CI installs `.[app]` `[S]`
- [x] 707. **#684's real decode is more feasible than the item implies** *(2026-09-09)* - `QMediaPlayer` + `QVideoSink`, no `QAudioOutput`, fixture `video/intro/channel_intro.mp4`, 10s event-loop timeout, `duration() > 2000`. Measured duration **2150ms**. Does not go through `ReviewWindow` / `start_review_player`. Guard-broken assertion (`> 999000`) failed on 2150. #684's last-run play remains operator smoke `[M]`
- [x] 708. **`assets/branding/tapin/` does not exist** *(2026-09-09)* - original octagon + play-chevron `logo.svg` / `banner.svg` from shipped tokens (`#E53935`, `#0B0F14`), not a copy of moneywise (no polyline). Fail-first: `compile_kit("tapin").missing` named `logo.svg`. `ops brand-kit --channel tapin` now prints both paths and no Missing line `[S]`
- [x] 709. **`claim_next` JSON extract does not run on Postgres** *(2026-09-09)* - `payload_json` is `Text`. `type_coerce(..., JSON)["sort_key"]` emits `payload_json ->> 'sort_key'`, and Postgres raises `operator does not exist: text ->> unknown`. That blocked #704 until `_payload_sort_key` cast to `JSONB` on postgres and kept `type_coerce` on SQLite. Fail-first: live `claim_next` errored; the compile test failed with `'jsonb' not found in "jobs.payload_json['sort_key']"` `[S]`
- [x] 710. **`video/subtitles.py` kept a `_load_word_timings` alias that silently broke every patch site** *(found and fixed 2026-09-09, audit of c43c427; ticked 2026-09-09)* - alias gone; `tests/test_word_timing_seam.py` patches `video.subtitles.load_word_timings`. Guard: `hasattr(subtitles, "_load_word_timings")` is false; the seam file has no `_load_word_timings` string `[S]`
- [x] 711. **The #704 Postgres proof skips silently when CI has no database** *(guard added 2026-09-09; trigger expanded 2026-09-09)* - `TestTheProofActuallyRunsInCI` still fails the job when `CI=true` and the URL is missing. Remaining hole was `on.push` limited to `main`/`master`, so this branch never started `postgres:16`. `ci.yml` now runs on every push, every PR, and `workflow_dispatch`. Fail-first: `workflow_dispatch:` absent `[S]`
- [x] 712. **A test file named to dodge discovery is a test that does not exist** *(fixed 2026-09-09, ticked 2026-09-09)* - `tests/test_wave6_extras.py` is collected; `loadTestsFromModule` reports >=4 cases. The extras `0:20`/`0:40` chapter assertion is still equal-span-shaped; the 5s/12s guard in `tests/test_next15_wave.py` is the one that can go red `[S]`
- [x] 713. **Automatic caption placement** *(2026-09-09)* — busy bottom chroma band (`bottom >= 12 and bottom > top * 1.5`) moves karaoke ASS Alignment 8. Quiet bottom stays Alignment 2. `generate_subtitle_file` passes `background_path` from `render_video`. No operator timeline. Leftover #717: this is not a face detector `[M]`
- [x] 714. **#705's coverage check read an unreadable page as a vanished claim** *(found and fixed 2026-09-09, audit of 18ba62c; ticked 2026-09-09)* - empty body does not file. Guard in `tests/test_next15_wave2.py` re-runs that measurement so the tick cannot go vacuous `[S]`
- [x] 715. **CI concurrency group keyed on `github.ref`** *(2026-09-09)* — `cancel-in-progress: true`. Guard strips comments; commenting the block out still passed, deleting it went red. Leftover #716: push and pull_request still use different refs `[S]`
- [x] 716. **A same-repo PR runs CI once, not twice** *(2026-09-12)* - `concurrency.group` is `${{ github.workflow }}-${{ github.head_ref || github.ref }}`. `head_ref` is the branch on pull_request and empty on push, so both events share one group and cancel-in-progress keeps the later run. Operator call 2026-09-12. Guard reads the live `group:` line; putting `github.ref` back goes red `[S]`
- [x] 717. **Caption placement now reads a luminance step, not chroma** *(2026-09-10)* - chroma is no longer consulted at all. An overlay is composited, so it introduces a horizontal band whose per-row mean luma differs sharply from the footage around it; scenery varies smoothly. Two conditions, both required: spread/median >= 0.35, and one row-to-row jump carrying >= 50% of that spread. The spread gate rejects scenery, the step gate rejects gradients. Window is 3x the caption band, measured: a band-filling overlay reads 0.24 / 0.23 / 1.07 at x1 / x2 / x3, so x1 and x2 miss it. Catches a bright score bug, a flat dark lower-third and a band-filling overlay; rejects both #718 false positives, a strong in-band gradient and a flat backdrop. `ops caption-anchor --path` prints the numbers so the operator can measure their own clips. **Flag stays off - see #721** `[M]`
- [x] 718. **#713's caption placement was silently relocating captions on ordinary b-roll** *(closed 2026-09-12: its own condition met - #721 tells a horizon from an overlay, flag now defaults on)* *(found and fixed 2026-09-09, audit of 96d6d1a)* - `choose_caption_anchor` ran on every karaoke render with no flag, and its detector counts unique chroma in the bottom eighth versus the top. Measured: a flat sky over a textured lower half - the commonest b-roll composition, no HUD present - scores top=1 / bottom=87 and moved every caption to ASS Alignment 8, i.e. the top of the video. A city street over sky scored 240. Cursor's two tests use a synthetic full-frame noise PNG, which is the detector's best case, so nothing caught it. Now gated behind `CAPTION_AUTO_PLACE`, default off, which is how this repo already holds uncertain visual features (`SCENE_MATCHED_BROLL`, `LUFS_NORMALIZE`); with the flag unset the burned ASS is unchanged. **The flag flips on when #717 can tell a score bug from a landscape** `[S]`
- [x] 719. **Every ffmpeg test skips silently if CI's apt-get step breaks** *(guard added 2026-09-09; verified in CI 2026-09-12)* - #415 installed ffmpeg in CI and `render_smoke.require_ffmpeg()` raises there when it is missing, but nothing called that un-patched: the technical-QC classes and the 2s smoke are bare `skipUnless(shutil.which("ffmpeg"))`. Under `CI=true` a missing ffmpeg is now a failure; locally it still skips. Verified: CI run 34416158840 on `b99ab81` logged `test_ci_must_not_silently_skip_every_ffmpeg_test ... ok` (ran, not skipped), 2,968 tests OK `[S]`
- [x] 720. **`apis/wikipedia_pageviews_api.py` had no logger, so the revision tripwire swallowed silently** *(fixed 2026-09-09; guarded 2026-09-12)* - `except Exception: revision = None` with nothing logged, in a module with no logger. Now logs at debug (`:213`). Guard in `tests/test_wave10.py`: with the revision fetch raising, the debug line is asserted and the signal still returns. It could not be observed failing first (the fix predates it); silencing the module logger in memory turns it red `[S]`
- [x] 721. **A low horizon no longer reads as a caption overlay** *(2026-09-12)* - temporal confirmation of #717's spatial step: frames at 0s and 1s; per column, the static-pixel share (|luma diff| <= 8) in the bottom band minus the same column above. Overlay = spatial step AND excess >= 0.25, with < 0.85 of the frame above static. Measured on five real Pexels clips: flat sky pasted over 65/70/80/90% reads -0.64..+0.05; overlays composited onto both frames that clear the spatial gate +0.36..+0.77; raw clips alone reach +0.57, so temporal confirms and never replaces. Old code on an encoded horizon clip with the flag on: top; now bottom. Stills, locked-off shots and clips under 1s read `no_motion` and never move. **`CAPTION_AUTO_PLACE` now defaults on** (operator call 2026-09-12). Remainder: #726 `[M]`
- [x] 722. **`ops free-tiers` recurring dates are derived, not typed** *(2026-09-12)* - rows carry `derive: youtube|apify`, resolved by `core/reset_window.next_reset`. Measured: the typed YouTube row `resets: 2026-09-11` read CLOSED on 2026-09-12 - a daily quota reported as a lapsed free window. Underivable, or `RESET_WINDOW_AUTO_ENABLE=false` -> unknown, never safe. The Apify row carries the last recorded `/users/me` reading (no HTTP). ElevenLabs stays typed: nothing reads its subscription reset `[M]`
- [x] 723. **The headroom line prints once per process** *(2026-09-12)* - `emit_headroom` remembers the last printed line under a lock; identical repeats go to debug, a moved number prints again. The caller is unchanged, so #590's trace test still holds. Guard: without the memo it prints twice `[S]`
- [x] 724. **An unreadable ElevenLabs ledger read as 0 chars used** *(2026-09-12)* - one layer deeper than filed: `core/quota_state._load` swallowed the read error and returned an empty store, so the governor's own `except` never fired. `quota_state.read_ok()` now separates a corrupt file from a missing one; `quota_governor.elevenlabs_chars_reading()` is None when unreadable and feeds `snapshot()`, `reliability._elevenlabs_section` (render + utilization lines), `tts._elevenlabs_budget_display` and `win_notify.quota_chip_lines`, which printed the whole budget as leftover. `elevenlabs_chars_used()` stays int, so the TTS budget guard stays fail-open `[S]`
- [x] 725. **Tests that pin a date while the code reads the real clock** *(2026-09-12)* - `tests/test_next15_wave2.py:282` pinned `now` to 2026-09-09 while `get_competitor_prompt_block` read the real clock, and went red three days later (fixed in wave 9). The other 64 pinned dates are now measured, not audited by eye: `py -m scripts.ops clock-ahead --days 365` runs the suite at +0 and +365 days through `core/clock_ahead.shifted_clock` and lists tests whose result changes - **none**. Positive control: the pre-fix test from `7c57b82` passes at -3d and fails at 0 / +365 under the same harness. The throwaway harness shifted `date.today()` twice (it calls the patched `time.time`); the shipped one derives it from the real `datetime.now()`, pinned by a test `[S]`
- [x] 726. **#721 measured on real burned-in overlays, on the frame the render shows** *(2026-09-12)* - `caption_place` measured the *source* frame, but the render cover-scales and centre-crops to 1080x1920 (`video/render_video.py:229-230`), so a 16:9 clip keeps its middle ~32%: an overlay in the discarded margins could move captions (encoded-clip test: old top, now bottom). `render_crop` applies the render geometry to both frames. Real footage, old -> new: 32 NBA 2K clips 28 TOP -> 22 TOP (6 lost, see #727), 4 bottom unchanged; 12 production hybrids unchanged (2 TOP, 10 bottom). Confirmed by eye: two 2K clips and both TOP hybrids (Madden and 2K score bars) are genuine overlays - no false TOP found. Still-sky case: #728 `[M]`
- [x] 727. **Real score bars missed on the cropped frame** *(2026-09-13)* - labelled by contact sheet: 30 real NBA 2K bars, 2 non-bar 2K frames, 50 stock clips, 12 hybrids. Temporal excess 0.25 -> 0.18 finds **22 -> 26 of 30** bars with 0 new TOP anywhere; per-block spatial candidates added 5-17 stock false positives and were rejected. The same run found 2 stock false positives already live (#730), so **`CAPTION_AUTO_PLACE` is default off again** (operator call). Running `ops caption-anchor` afterwards showed it printing a typed `needs >= 0.25`; thresholds are now read from the module. The 4 remaining misses are #731 `[M]`
- [ ] 728. **An overlay under a still sky reads as scenery** - #721's column excess compares the band with the same column above; if that column is static too, the overlay shows no excess. Carried from #726: no such clip exists in `gaming/sports/2k26` or the 12 hybrids, so it is unmeasured on real footage `[S]`
- [x] 729. **Every desktop widget test skipped in CI, with a false reason** *(found and fixed 2026-09-13; proven by the CI run of this commit)* - CI installs `.[shell,app]` and downloads the PySide6 6.11.2 wheel, yet all 23 widget tests skipped as `'PySide6 extra not installed'` (run 34741028834; 17 already on `b99ab81`) while `ci.yml` claimed "23 ran, 0 skipped". Ten files turned any `ImportError` into that message, so the desktop programme had no CI proof. `tests/qt_support.requires_qt` carries the real error locally and never skips under `CI=true`; CI now installs `libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1`. Fail-first simulated locally (a forced import error under `CI=true`) `[M]`
- [ ] 730. **`CAPTION_AUTO_PLACE` moves captions on no-overlay footage** - operator rule: default on only at 0 false moves with >= 26/30 real bars. *2026-09-13, first measurement on production footage:* the 46 hybrid backgrounds in `data/tmp/hybrid_backgrounds` were labelled by eye - **23 carry a bar or HUD in the caption band** (UFC / 2K / Madden score bars, game health bars), 19 do not, 4 unclear. So with the flag off, captions sit on an overlay in about half of real renders. The current detector finds 17/23 of those and 26/30 2K bars, but moves captions on **5 of 71** no-overlay clips (stock `pexels_6265064`, `pexels_7005860`; hybrids `hy25`, `hy27`, `hy34` - two cars, a top-down court). The only zero-false-move candidate (>= 4 adjacent static columns) finds 9/30 bars and 5/23 hybrid overlays. `near_above` and a third frame were also re-measured on the larger set; none clean. Stays off `[M]`
- [ ] 731. **4 of 30 real NBA 2K score bars still missed** - after #727: three fail the full-width spatial step (`2k00`, `2k19`, `2k26` - players or a "PLAYOFFS" box add their own luma steps inside the 3x window) and one has negative temporal excess (`2k24`, -0.33). Per-block spatial recovers them only by adding stock false positives: 5-17 alone (#727), and still 4-10 of 50 when combined with #730's `near_above` < 0.6-0.8 (2026-09-13), with 3-4 hybrids changing verdict `[M]`
- [x] 732. **`env_fingerprint` (#687) ignores commented optional flags** *(2026-09-13, wave 16)* - `env_canonical` now counts `# FLAG=` lines (`ENV_FINGERPRINT_VERSION = 2`); traces stamp `env_fingerprint_version`, and `diff_against` refuses to compare hashes across versions instead of reporting drift. Toggling `CAPTION_AUTO_PLACE` changes the hash. Real `ops config-diff` on this machine: ".env shape: fingerprint scheme changed since last run (v1 -> v2), not compared". `env_example_keys`' default is unchanged, so #639's pin still holds `[S]`
- [x] 733. **Read the first CI coverage table** *(2026-09-13)* - run 34744476819: `core/` 77% of 22,422 statements, no module at 0%. Gate modules 65-95%, re-measured locally with `coverage` 7.16 (82% of 868 statements across 12 gate files). Most missed lines are fail-open `except` handlers and display code; the untested *decisions* were `render_gate.py:84-97` (missing run fails closed, unreadable store fails open), `publish_deadman.py:43,50` (no heartbeat blocks, fresh heartbeat allows) - now pinned by tests that passed on first run, stated as coverage not fail-first - and the aggregation in #734 `[S]`
- [x] 734. **Publish blockers reach the refusal list - and are fed** *(2026-09-13)* - the four append branches (`publish_blockers.py:94-128`) are now pinned (they worked; coverage, not fail-first). Tracing the *fields* found the real defect: `ops blocking` (`scripts/ops.py:1501`) and the web `/next` (`core/operator_shell.py:33`) passed only a channel id, so the render gate graded an empty dict. Measured on this machine: both printed **"report card F (need >= B)"** while tapin's last rendered run (72) grades **A** with authenticity ok. The render gate now needs run data; `publish_blockers.last_run_context` loads quality, features, `key_facts_count` and the mp4 from the last reviewable run, and `publish_status_sentence` serves both callers. The review booth now passes the fact count it never did. Real run after: "Nothing is blocking publish". TTS cap has no feeder after render: #738 `[S]`
- [x] 735. **Four safety gates were not armed on this machine** *(2026-09-13)* - operator call (decisions.md §31): `AUTHENTICITY_GATE` and `GROUNDING_GATE` default to `block`; `METRICS_BEFORE_NEXT` and `PUBLISH_DEADMAN_DAYS` stay off. Publishing now refuses an authenticity *block* verdict only - under block it refused any verdict other than ok, which would have stopped every `review` video. `scripts/auto_generate.py` uses the shared `authenticity.blocks_render`. The full suite passed with the new defaults (one test pinned the old warn default and was updated). `ops selftest` real run: authenticity and grounding now armed here `[S]`
- [x] 736. **An sdist's contents depended on a stale egg-info** *(2026-09-13)* - `core/package_audit.stage_tree` copies tracked plus untracked-but-not-ignored files into a temp dir and both builds run there, so an ignored `*.egg-info/`, `build/` or `data/` never reaches setuptools and nothing is written into the repo. Measured: with a stale `content_machine.egg-info/SOURCES.txt` listing `tests/` planted in the repo root, the sdist has **no tests/** (409 members, up from 378 because #737 ships config JSON); plant removed after `[S]`
- [x] 737. **The wheel shipped no `config/*.json` - and no repository layer** *(2026-09-13)* - worse than filed: `[tool.setuptools] packages` lists packages explicitly, so the one subpackage, `storage.repositories`, was absent too, and a wheel install could not import storage. Added it, plus `[tool.setuptools.package-data]` single-level globs for `config`, `config/competitors`, `config/seo`, `core/data` and `analytics` - none can reach `config/secrets/` (`windows-terminal/profiles.json` is a manual fragment no code reads, left out). Proof build: wheel 404 files incl. `storage/repositories/jobs.py` and `config/channels.json`, nothing under `config/secrets/`; importing from the unpacked wheel with the repo shadowed loads both **from the wheel**. The same build found the audit's token rule flagging `config/design_tokens.json`; tightened test-first `[M]`
- [x] 738. **The TTS-cap entry in the publish refusal list can never fire** *(2026-09-13, wave 15)* - `run_media_only` now persists `tts_char_count` / `tts_force` / `tts_length_choice` on the run; `blocking_publish_reasons` reads them when no full script is passed. 8,000 chars feeds "TTS character cap: 8,000"; a forced overage does not block. TTS is already paid by then; this is the publish list being honest, not a new hard stop at synth `[S]`
- [ ] 739. **Try placing captions by footage source, not by pixels** - `assets/composite.build_hybrid_concat_command` puts the local gameplay clip first, so every #730 production label (frames at 0s and 1s) came from the *gameplay* segment: 23 showed a HUD or score bar in the caption band, 19 showed none at that moment. The stock segment was never sampled. A source rule would need both measured first: how often gameplay carries a HUD across the whole segment (19 of 42 frames said not at that instant), and that stock segments never do. If gameplay HUDs are near-constant, anchoring captions for the gameplay segment needs no detector; if not, it moves captions onto clean gameplay. Needs that measurement, then per-segment ASS timing or a whole-video rule, and the operator's call `[M]`
- [x] 740. **`y` at the TTS-cap prompt still raises** *(2026-09-13, wave 14)* - run 76: 5,720 chars vs 5,000. Operator call: ~14% is non-consequential. `tts_char_cap_reason("x"*5720)` is now `None`; `tts_char_cap_warn` fires; 5,751 still hard-blocks. `run_media_only(..., force=True)` does not raise (TTS/ffmpeg mocked). Interactive `y` and `auto_generate --force` pass `force=True`. Worker stays unforced. Extended floor is `max(env, max_words * 6)` so option 4 is not a trap at 8,000 chars. **Behaviour change:** 5,001 no longer hard-blocks (15% grace). Distinct from #738 `[S]`
- [x] 741. **Fact `paste` does not enter paste mode, and chrome is pinned** *(2026-09-13, wave 14)* - `` `paste` `` is the paste command; Share / Follow Us / `ffaaa` / Like (1) / Related Tags never reach `select_facts_for_prompt` output, even tagged `TIER_OPERATOR`. Help text says two blank lines. Fail-first used the run 76 tokens `[M]`
- [x] 742. **`"best "` forces five listicles on a thesis question** *(2026-09-13, wave 14)* - run 76 seed is not `ANGLE_LIST`. `"top 5 heavyweights"` and `"ranking every GTA protagonist"` still are. Dropped bare `"best "` / `"every "`; kept `top 5` / `ranking every` / `ranked:` `[S]`
- [x] 743. **Option 1 type-your-own never sets `creative_brief`** *(2026-09-13, wave 14)* - `brief_for_typed_topic` on the run 76 thesis returns a brief containing "meeting the hype"; `_build_prompts(..., creative_brief=brief)` emits EDITORIAL ANGLE. `main.py` option 1 calls it. Related leftover: #543 `[M]`
- [x] 744. **Editorial scores of 0.54-0.58 are not a ranking** *(2026-09-13, wave 14)* - thesis-term fidelity + listicle-leftover penalty: run 76 criterion/hype outranks honourable-mention (0.4993 > 0.2223) with `llm_judge=False`. Optional `complete(tier="cheap")` judge fail-opens when cheap-tier errors; not folded into the composite; no extra signal fetch; no Anthropic on the cheap chain `[M]`
- [x] 745. **Claim and grounding gates flagged facts that were packed** *(2026-09-13, wave 14)* - verifier window is `operator_key_fact_char_budget()` (12,000); a fact past the old 6,000 cap is kept. Start / Read / Compare / Restricted are not ungrounded specifics. Title/script `unavailable` is #748; taxonomy is still #345 `[S]`
- [x] 746. **Wikipedia candidate `Gta` / Trends `Goy` from a seed typo** *(2026-09-13, wave 15)* - `_article_candidates` keeps `GTA` as an acronym and does not emit standalone `Gta` / `Goy` from the run 76 seed. Candidates are now `GTA_6_Analysis_Predictions_Best_Game`, `GTA_6_Analysis`, `GTA`. Franchise-page mapping (GTA 6 -> Grand_Theft_Auto_VI) is #749 `[S]`
- [x] 747. **YouTube autocomplete HTTP 400 on run 76** *(2026-09-13, wave 15)* - suggest query is stripped of `!?` and capped at 80 chars; HTTP 400 returns `unavailable` with "autocomplete skipped: query rejected (400)" instead of generic `http_error`. Fail-first: the run 76 seed was sent verbatim (173 chars) `[S]`
- [x] 748. **Title/script check printed `unavailable` on run 76** *(2026-09-13, wave 15)* - when `verify_claims` returns None, a deterministic `find_ungrounded_entities(title, script)` fallback yields passed/failed. Run 76 drones title vs a criterion script is failed; Jones/Jones is passed. Relational wrong-actor with the same names is still #345 `[S]`
- [x] 749. **Wikipedia candidates are token joins, not franchise pages** *(2026-09-16, wave 18)* - `_article_candidates` puts known franchise pages first, one per family, most specific first: the run 76 seed now asks for `Grand_Theft_Auto_VI` before the token joins; GTA V, UFC, Call of Duty, NBA/NFL/MLB/NHL map too. No new network call, no cache `[S]`
- [x] 750. **Extended chapters were the first eight sentences** *(found run 77, fixed 2026-09-13, wave 16)* - `core/chapters.chapter_block` labelled sentences 1-8. With word timings run 77 stored `0:00 … 0:17` (YouTube needs >= 3 chapters of >= 10 s, so it drops them); without timings it stamped those same eight labels across 4:16. Points now sit at even word fractions snapped to a later sentence start, and `youtube_chapter_lines` (shared with all-angles `chapter_lines`) keeps only chapters >= 10 s apart, or emits none below three. Run 77's real sidecar after: `0:00, 0:39, 1:14, 1:51, 2:33, 3:09, 3:47, 4:22` with the sentence actually at each time `[S]`
- [x] 751. **The upload queue got the pre-refinement description** *(found run 77, fixed 2026-09-13, wave 16)* - `refine_run_chapters` rewrites the run row after TTS, but `main.py` and `scripts/auto_generate.py` printed and enqueued the in-memory `result.description`. Both now read `core.chapters.current_description(run_id, fallback)` after `run_media_only`; an unreadable store keeps the in-memory copy `[S]`
- [x] 752. **A 293 s video was tagged `shorts`, `Forward`, `Billion`, `Opportunity`** *(found run 77, fixed 2026-09-13, wave 16)* - `config/seo/tapin.json` defaults carry `shorts`; `tags_from_topic(variant)` added lens and headline words on top of the model's 13 tags. `core.seo.drop_shorts_tags` removes Shorts tags when the preset's max duration passes 180 s (Long and Extended); topic-word tags only pad a model list of fewer than 5, from `angle_headline` `[S]`
- [x] 753. **A successful upload printed nothing** *(found run 77, fixed 2026-09-13, wave 16)* - `jobs/worker._finalize_upload_job` logged success at INFO while the operator runs `CONTENT_LOG_LEVEL=WARNING`. Now prints `Job 44 uploaded -> https://youtu.be/<id>` `[S]`
- [x] 754. **Rendering past a flagged claim still queues a public upload** *(2026-09-15, wave 17)* - `y` at the grounding gate now persists `grounding_override` + the claims on the run (both render paths); `blocking_publish_reasons` prints "rendered past the grounding gate: <claim>"; the upload prompt drops the public option and says why. Measured on run 77's claim. Original filing: - run 77: the claim verifier flagged "GTA 5 didn't win Game of the Year in 2013" (to the operator's knowledge false - GTA V won GOTY at the 2013 VGX awards), the operator answered `y` at "Render anyway?", and the video queued public (held unlisted). Nothing after render remembers the override: carry it to the upload plan (default unlisted, name the claims at Queue) and to `blocking_publish_reasons` `[S]`
- [ ] 755. **All-angles (run 78) is unmeasured on a real Extended script** - *instrumented 2026-09-16 (wave 18):* each chapter records `placed_by` (llm / keyword), and the Shorts menu plus `py -m scripts.ops chapters --run-id N` print placement, length and the 3:00 cap per chapter. What is left is the operator's first live all-angles run: paste that table and say whether each cut opens on its own hook `[S]`
- [x] 757. **Chapter Shorts had no way to reach the queue spaced out** *(2026-09-15, wave 17)* - an all-angles run makes 1 long + up to 5 Shorts against a 5-per-7-day cap, and the menu only printed a requeue command for the first. `core/spaced_queue.plan_spaced_uploads` asks `next_optimal_post_time` for one open slot per Short (each `after` the previous, so reserved times are skipped) and stops at the cap; `queue_spaced_uploads` enqueues them unlisted. Live proof at cadence 1/5 with the long video reserved: 3 slots (18th, 19th, 20th), 2 held back naming the cap `[M]`
- [x] 758. **Long-form voice is 91% of all spend** *(2026-09-15, wave 17)* - all-time cost is $14.85, of which TTS is $13.50 (run 77 alone $1.37 at 293 s). `core/tts.long_form_provider` sends presets that can pass the 3-minute Shorts cap (Long, Extended) to `TTS_PROVIDER_LONG` (default piper, $0) while Shorts keep ElevenLabs; an explicit `TTS_PROVIDER` pins every length, and an unusable local voice still falls back to paid downstream. `generate_audio(length_choice=)` carries the preset `[M]`
- [x] 759. **The mailbox read a behind-HEAD partner as a defect** *(2026-09-15, wave 17)* - the operator's second agent helps intermittently, so "5 commits behind HEAD" is the normal state. `agent_comms.behind_note` says so in `ops agents` and `docs/handoff.md` says it before the verify steps `[S]`
- [x] 760. **Unattended batch for 3-5 uploads a week** *(2026-09-16, wave 18)* - `core/batch_review.py` + `ops batch-review`: one pass over the waiting drafts (hook, authenticity, projected voice, blocking and warn-only claims), y / n / later / q; a draft with blocking claims needs `force`, which records `grounding_override`. Accepted drafts render onto their run, then `plan_spaced_uploads` spaces them. Every decision is written to `meta.json` at once, so Ctrl+C resumes; a second batch keeps an unreviewed draft under 3 days old instead of paying for it again (`batch_generation.unreviewed_draft`) `[L]`
- [x] 756. **Chapter labels are cut at 40 characters mid-phrase** *(2026-09-16, wave 18)* - `core/chapters._label` takes the first clause when it fits (>= 3 words), else a word cut with dangling words stripped: run 77's labels now read "The only reason we know anything" and "The gaming audience today" `[S]`
- [x] 761. **Five stale renders counted as work waiting** *(2026-09-16, wave 18)* - `ops status` said "5 rendered, not on YouTube": runs 1/2/4/10/59, 60-105 days old, about a UFC card and a third-place match long over. `ops retire-renders --days 30` (dry run; `--apply` marks `features.retired_at`) and `requeue_upload.list_recyclable` skips retired runs; the files stay and still queue by id. Applied on tapin: 5 retired, status line gone `[S]`
- [x] 762. **Spaced uploads landed unlisted, so the week target depended on flipping them** *(2026-09-16, wave 18)* - operator call: public at the slot. `spaced_queue.queue_spaced_uploads` defaults to public with `publishAt` (private until the slot); `slot_privacy` holds unlisted when the run, or the long video a Short was cut from, has `grounding_override`. The chapter-Shorts menu prints the privacy per slot `[S]`
- [ ] 763. **A draft reviewed days later can be stale news** - `ops batch-review` shows hook, claims and cost but not the draft's age; a UFC card or trailer draft made Monday and accepted Friday renders last week's story. Show the age and ask again past a per-domain freshness window `[S]`
- [ ] 764. **Nothing says the week is under target** - the cadence cap stops a sixth upload, but no line says "1 queued for the next 7 days, target 3-5: run batch-drafts". A status / overnight line against the 2026-09-15 target `[S]`
