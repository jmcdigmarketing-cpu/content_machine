# Content OS — Roadmap

> **North star:** [vision.md](vision.md) — the v3 intelligence-systems vision
> ("operate media businesses," not "make videos"), a senior-level critique of it,
> and the revised 12-month architecture plan prioritized for defensibility,
> revenue, and learning advantage.
> **Operating plan:** [operating_plan.md](operating_plan.md) — pace/cost projections
> (2wk/1mo/3mo/6mo/1yr), the new-channel playbook, AI cost-per-run + reduction
> roadmap, side-income territories, ops/process hygiene, and competitive analysis.
> This roadmap is the tactical layer beneath both.
> **Planning log:** [planning_log.md](planning_log.md) — dated brainstorming/decisions
> from planning sessions (so ideas survive beyond the ephemeral plan files).

Product phase names are the source of truth. **Phases H–K** (intelligence) are specified in **[intelligence_phase.md](intelligence_phase.md)**.

Last updated: 2026-08-21 — **leave-the-terminal wave shipped** (20 working
operator-visible pieces). FastAPI shell **#147 skipped** (would swallow the
wave); swapped for **#240** `ops status --html` and bundled **#254** reveal-thumb
on the same Explorer helper as #253. Evening next-5 and Phase M stay out.
Rationale: [planning_log.md](planning_log.md) 2026-08-21.

**New verticals:** [domain-expansion.md](domain-expansion.md) — finance, anime, pop culture, music, gaming/sports depth. One domain at a time; official APIs first.

**Where we are:** the discovery → script → render → publish pipeline is complete and the **learning loop is closed** — real YouTube engagement now feeds topic, length, and post-time recommendations. Current focus is widening data intake (Apify), tightening automation, and engineering hygiene. See **Next up — all open items** below.

---

## Next up — all open items

*The single forward list — everything still open across this roadmap, grouped by area.
Detail lives in the phase/pillar sections further down. **Multi-platform distribution
(Phase M) is intentionally excluded here** — it stays parked under
[Later horizons](#later-horizons). Shipped this cycle: Pillars 1–6, the config-driven
voice catalog + honest Free-mode readiness, the **Qwen3-TTS** local voice-cloning provider,
the router/title/voice crash fixes, and the **scheduling upgrades** (clock-time upload
input + average-based learned post slots). Leave-the-terminal wave 2026-08-21.

**Recommended next 5 (2026-08-20 evening)** — **shipped 2026-08-20 night.**
Pickup order was *future viability*, *short-term success*, and *real-world cost*.
Volume-gated backtest, the $0 TTS *voice judgment*, and Phase M stay out.

1. **Pre-run completion gate** `[S]` — *short-term.* Run 70 burned 71s of discovery
   then 404'd a missing Ollama model. Readiness line ≡ applied env ≡ first LLM/TTS
   call, *before* discovery starts.
2. **`youtube/oauth.py` tests + `coverage` extra** `[S]` — *short-term.* Last
   sequenced item on the paused render/publish coverage wave. `token_has_scope`
   gates the dup-upload check; a broken token is a silent missed publish. Add
   `coverage` to `[dev]` (report only — no CI percentage gate).
3. **Pronunciation lexicon for local TTS** `[M]` — *cost.* Captions already spell
   Salkilld; Piper still says it wrong. ElevenLabs is **$0.25–0.31/video (~91% of
   a rendered run)**; the $0 flip is unblocked on captions and blocked on *ears*.
4. **Allocated vs marginal unit economics** `[S]` — *cost.* Metered TTS is
   $0.22/1k (~$0.31/video). Creator plan covers ~90 videos against ~21 made, so
   **allocated is nearer $1/video**. `ops economics` currently answers the
   engineering question, not the business one.
5. **Numeric/record grounding** `[M]` — *viability.* The name-gate catches
   invented fighters; invented ranks, dates, and purses still pass. A fake record
   on a UFC short is a 2026-policy event, not a grade ding.

**Brainstorm next-5 (UI/app)** *(2026-08-20 late-night — docs only; does not
replace the shipped evening five.)* Historical short list for *leaving the
terminal* without restarting Phase M. **Superseded as pickup order** by
**Recommended next 20 (2026-08-20 night)** below — 221/222/223/224/171 are
still in that 20, reordered. Detail: candidates **221, 222, 223, 224, 171**.

1. **Windows toast when ffmpeg finishes** `[S]` — *short-term / UI.* The
   operator currently babysits a spinner; a toast unblocks other work.
2. **System-tray quota chip** `[S]` — *cost / UI.* Uploads-left (≈1,600 units),
   ElevenLabs leftover chars, Apify breaker — so a doomed session never starts
   (run-70 class, visible without `ops reliability`).
3. **`ops reliability --html` themed snapshot** `[S]` — *UI.* Same breakers /
   utilization / incidents, opened in the browser. Zero new backend.
4. **Thumbnail lightbox for the last Pillow thumb** `[S]` — *cost / aesthetics.*
   Pillow-first already skips paid image APIs on C/D/F; the operator still
   cannot *see* the thumb without Explorer.
5. **Last-run review booth** `[M]` — *UI / new-app.* Localhost play + grade +
   authenticity + cost + Approve/Reject. Replaces scrolling `main.py` for the
   last render only (the full review *room* is larger #168).

**Recommended next 20 (2026-08-20 night)** — **shipped 2026-08-21.**
Pickup order stood; **#147 FastAPI skipped** (would swallow the wave). Slot 20
is **#240** `ops status --html`; **#254** reveal-thumb ships on the same
`ops reveal` helper as #253. No Content OS Desktop (#141), no Visual Studio
(#142), no Phase M. Detail + surfaces below.

1. **223** `ops reliability --html` themed snapshot `[S]` — *shipped.* `ops reliability --html` (themed `<pre>` over existing `gather()`).
2. **222** System-tray quota chip `[S]` — *shipped.* `ops tray` (uploads-left + EL chars + Apify breaker; toast + optional on-top chip).
3. **291** Set Windows AppUserModelID `[S]` — *shipped.* `ContentOS.Operator` on the toast/tray helper.
4. **226** Toast when a breaker trips `[S]` — *shipped.* Notify-only at Apify / signal / LLM / ElevenLabs trip points.
5. **221** Windows toast when ffmpeg finishes `[S]` — *shipped.* `run_media_only` → toast helper.
6. **224** Thumbnail lightbox for the last Pillow thumb `[S]` — *shipped.* `ops lightbox`.
7. **253** Reveal mp4 in Explorer `[S]` — *shipped.* `ops reveal` (`explorer /select,`).
8. **241** `ops economics --html` `[S]` — *shipped.* Same themed dump over unit economics ASCII.
9. **92** Windows `MAX_PATH` / long `output/` paths `[S]` — *shipped.* Filename clip + optional `\\?\` prefix.
10. **93** FFmpeg file-lock retry `[S]` — *shipped.* Defender WinError 32 retries on encode + intro replace.
11. **109** Unlisted review link before public `[S]` — *shipped.* Immediate `public` → `unlisted` (`YOUTUBE_UNLISTED_REVIEW`).
12. **319** "What's blocking publish" one-sentence `[S]` — *shipped.* `ops blocking` (existing gates only).
13. **43** Script **trim** pass `[S]` — *shipped.* Drop trailing padding sentences; never clip; hard cap still refuse.
14. **97** Redact API bodies from `data/traces` `[S]` — *shipped.* `run_trace.redact_trace_value` on write/update.
15. **231** Start-menu shortcut via **pyw** `[S]` — *shipped.* `ops shortcut` + `content_os.pyw`.
16. **171** Last-run review booth `[M]` — *shipped.* `ops booth` (stdlib HTML; `--serve` is not FastAPI).
17. **200** Thin-facts abort screen `[M]` — *shipped.* Dedicated HTML when the TTS abort fires.
18. **198** Doctor HTML page `[M]` — *shipped.* `ops doctor --html`.
19. **78** Intelligence-report SKU `[M]` — *shipped.* `ops intelligence-report --sku` (research + competitors + authenticity; no TTS).
20. **240** `ops status --html` `[S]` — *shipped (swap for #147).* Same HTML path as reliability/economics.

**Skipped this wave:** **147** Localhost FastAPI operator shell `[L]` — thinnest host is stdlib `ops booth --serve`; do not start #141.

**Data spine & storage**
- [x] **Alembic baseline + FKs** *(2026-08-14)* — `0004_content_run_fks`: real
  `content_run_id` foreign keys on `publish_log` / `jobs` / `assets` /
  `thumbnail_scores`. The blocker was `publish_log`'s legacy `0` sentinel for
  "imported, no run" (836 of 870 rows), now `NULL`; all rows preserved. Also
  reconciled the stamp/state drift — `migrate_schema` finishes through Alembic
  instead of hand-patching past it
- [~] ~~Tapology scrape~~ — **retired 2026-08-14**: Cloudflare JS challenge returns 403
  for every request (direct *and* via the r.jina.ai reader proxy), and it had reported
  itself as "no event match" rather than blocked for ~33 days. Module kept behind
  `TAPOLOGY_SCRAPE_ENABLED` for revival; fighter facts come from `mma_stats`
- [~] ~~Reddit agent-workload rate-limit-aware caching~~ — **signal retired 2026-08-14**
  (`enabled: false` in the catalog): its actor failed on 100% of live runs while still
  billing, and the free OAuth backend has no credentials configured
- [x] **Research intake repair + source health monitoring** *(2026-08-14)* — the audit
  behind this item found the intake layer had been silently dead for a month:
  **Tapology is Cloudflare-403'd** (10/10 cached results empty over 33 days, and it
  reported the block as *"no event match"*, so no breaker ever saw it), **11 of ~37
  feeds were dead**, and the Federal Reserve feed was *alive* but dropped by a UTF-8
  **BOM parse bug**. Fixed the parser, replaced every dead URL with a live-verified
  one (**37/37 ok**), made a blocked scrape report `STATUS_UNAVAILABLE`, retired
  Tapology (`apis/mma_stats_api.py` — API-SPORTS MMA — now supplies fighter
  records/physicals), and added **`ops feeds`** (ok/stale/dead + newest-item age) wired
  into `all-checks` and `ops reliability` so rot can't hide again

**Recommenders & calibration**
- [ ] Backtest recommender accuracy vs. realized engagement (volume-gated — **10** measured
  run-linked videos vs the predictor's own threshold of 15)
- [x] **Live-run 66 fixes** *(2026-08-15)* — the run confirmed the cost fix landed
  (`tts $0.3131`, **91%** of a $0.3454 run) and exposed five defects, none of which
  announced itself as a failure:
  1. **Duration estimates were 38% wrong** — `WORDS_PER_SECOND` 2.4 vs a measured
     **3.32 median across all 14 real renders**; run 66 was shown "~101s spoken" and
     rendered **70.2s**. Rate corrected and preset seconds are now **derived** from the
     word range, so the menu can't advertise a duration the preset can't hit
     ("Extended 420–900s" really produced ~300–600s). Word ranges untouched, so the
     learned-length loop keeps its meaning. `ops`-style checker:
     `py -m scripts.bench_script_duration`
  2. **A false hallucination alarm cost a grade** — `"If Netflix"` was extracted as a
     proper noun (sentence-initial `If`) and failed grounding, dropping the report card
     **A→B** while the claim verifier said 12/12 backed. Phrases no longer start on a
     function word; real inventions still flag
  3. **`youtube` reported ERROR on a timeout** — no timeout was set anywhere; now bounded
     (`YOUTUBE_API_TIMEOUT`) and `classify_exception` maps timeouts to
     `STATUS_UNAVAILABLE` (transient, retried) rather than a hard error
  4. **`youtube_comments` surfaced "What about Alaska?"** — questions must now share a
     token with the topic; also fixed `"first"` matching as a substring, which was
     discarding legitimate questions
  5. **Both cheap-tier LLM slugs were dead ends** — the retired OpenRouter model was
     **hardcoded** (so `.env` never fixed it), repointed to a live slug chosen by live
     test; Ollama had **zero models pulled**, so the router now checks `/api/tags` and
     reports unavailable instead of 404ing a model daily. Stale dead-model records cleared
- [x] **Post-render cost reaches the ledger** *(2026-08-14)* — both operator render paths
  finalize a run *before* rendering it, so `features_json.cost` kept `tts: 0.0` on every
  rendered run and the trace stayed `drafted`. `main.py` recomputed the right number but
  only into a local dict for display. Since `unit_economics` derives contribution margin
  from `cost.total`, **every margin was overstated**: `ops economics` read *20 uploads,
  $0.32 total ($0.02/video)* when the real figure was **$6.18 ($0.31/video)**.
  `run_media_only` — the one choke point both flows share — now persists
  `cost_meter.merge_render_cost()` plus a `status="rendered"` trace patch;
  `ops backfill-cost` repaired 38 historical runs ($0.75 → $11.77) and 13 traces.
  TTS is now priced from the real plan ($22/100k chars = **$0.22/1k**, was a $0.30
  guess). Also stopped `backfill-features --force` silently wiping the cost block
- [x] Promote `SEMANTIC_TRADE_VALIDATION` default-on for sports channels `[S]` — now auto-on for NBA/NFL topics (domain-gated); env still forces on/off globally

**Signals & data intake**
- [x] **`youtube_comments` signal** *(2026-08-14)* — wired, but against the **official
  Data API** (1 unit/video) rather than the catalog's `streamers/youtube-comments-scraper`,
  which would bill Apify credits for data the YouTube key already reaches (~103 units/topic
  of a 10k/day budget). Surfaces the **unanswered audience questions** on a topic's top
  videos — the content gaps competitors left — plus audience vocabulary. Labelled
  *unverified* in `signal_facts` so a viewer's guess can never become a claim, profanity
  filtered (advertiser-facing), pinned during variant scoring + 6h TTL so it can't
  re-bill per variant
- [ ] `instagram_figures` signal — still templated only; catalog entry `enabled: false`
- [x] **Live-run tuning of Apify actor inputs against real topics** *(2026-08-14)* —
  audited the paid tier against real run traces. `twitter` was **`inactive` on 19/19
  traces spanning 2026-07-07 → 08-14** — it has never produced a fact — while being the
  **slowest signal (~32s)**, which set the wall-clock floor for every discovery
  (signals run concurrently, one worker each). The actor bills a run and returns
  `10 x {"noResults": true}` sentinels instead of tweets; the input was verified
  correct against `input_template`, so unlike Reddit this was **not** input drift —
  X search now needs auth. Retired (`enabled: false`) and
  `apify_client.is_no_results()` makes the sentinel report `STATUS_UNAVAILABLE`
  instead of a quiet `inactive`. `tiktok_trends` + `youtube_competitors` verified
  healthy and kept
- [ ] Free-backend probe for Twitter/X, if the signal is ever worth restoring
- [ ] Free-backend probes — TikTok/Twitter equivalents (only if the Apify bill justifies it)

**Video creation quality (Pillar 6 remainder + Phases Q/R)**
- [x] **Whisper local — CPU backend** *(2026-08-14; caption-text blocker closed
  2026-08-16 by the retext item below)*.
  The roadmap called these backends "parked, needs a GPU box"; in fact `whisperx`,
  `faster_whisper`, `torch` (CPU), `piper` and `ctranslate2` were **already installed**
  and the caption wiring (`subtitles.py` → `words_from_caption_align` →
  `caption_align.py`) was **already complete** — only a CPU backend was missing.
  - **Shipped:** `faster_whisper` backend in `core/caption_align.py` (+ device/model/
    compute config, still fail-open and OFF by default) and
    `scripts/bench_caption_align.py`, which measures word timings against the
    **ElevenLabs `.words.json` sidecars** we already have for real channel audio.
  - **Measured** on three real 55–58s shorts: `tiny` gives **43–56ms median** caption
    line-start error (p90 111–176ms) at **12–15× realtime on CPU** — and beats `base`
    (73–85ms median) while being half the download. Default set to `tiny` from that
    evidence. Piper synthesis of a real 1,156-char script took **5.1s**.
  - **Blocker found, and since closed:** the path transcribes audio *blind*, so it
    returns ASR text, not the script. On run 65 it produced "Salkal" for "Salkilld" and
    "Mattius Gamarat" for "Mateusz Gamrot". Fighter/game names are the channel's whole
    subject, so burned captions showed mangled names despite accurate timing. Fixed by
    the caption-retext item directly below.
  - Also worth knowing: Piper renders the same script **66.3s vs ElevenLabs' 55.2s**
    (~20% slower delivery), which shifts video length and the learned-length loop.
- [x] **Caption text from the script, timing from whisper** *(2026-08-16 —
  `video/caption_retext.py`; decisions §23)*. Whisper's timings, the script's words,
  aligned with `difflib.SequenceMatcher`. `generate_subtitle_file(script, …)` already
  received the script, so nothing new had to be plumbed.
  - **Proven on the real fixture**, not asserted. The run-65 SRT went from
    `broken, Quill and Salkal just` / `submitted Mattius Gamarat and round` /
    `with a top ten lightweight` to `Quillan Salkilld just submitted Mateusz` /
    `Gamrot in round one, and` / `a top-10 lightweight ranking.` — names right,
    punctuation from the script, and the dropped `the`/`in` restored.
  - **It costs nothing in timing** (run 66, 243 words): word error p50 42→43ms,
    line p90 **117ms → 117ms**, while covering **243/243** script words instead of the
    243-of-251 whisper heard, and correcting **12 misheard words**. Retext columns added
    to `py -m scripts.bench_caption_align`, which now shares one matcher with the
    shipped retexter instead of keeping its own lookahead walk.
  - **Declines rather than guesses** below `CAPTION_RETEXT_MIN_MATCH` (**0.35**, set
    from measurement: real audio scores **0.87**, unrelated audio ~0.0) — a transcript
    that doesn't match the script has timings for different audio, so the caller falls
    back to the proportional estimate. `CAPTION_RETEXT=off` restores raw ASR.
  - **End-to-end $0 render verified** — Piper VO + retexted burned captions through
    `render_vertical_video`, checked as burned pixels. *Worth not relearning:* the
    rendered mp4 looks 2.17s "out of sync" against the SRT until you notice
    `prepend_channel_intro` adds TapIn's **2.15s intro** after the render, shifting audio
    and captions together — sync is exact once you subtract it.
  - 1411 tests green (+29): `tests/test_caption_retext.py` + wiring cases in
    `tests/test_subtitles.py`.

  *Design notes kept because they were the hard part:* the matcher must survive
  re-tokenisation, not just misspelling — whisper splits (`Quillan` → `Quill and`),
  writes numerals as words (`10` → `ten`, `top-10` → `top ten`), drops words and invents
  them. A positional zip desyncs permanently at the first one, so number-words fold onto
  their digits in the normaliser, `replace` spans are shared out by character length,
  `delete` runs are interpolated from their neighbours and clamped monotonic, and
  `insert` tokens are dropped so their time is absorbed.
  - **The real difficulty is re-tokenisation, not misspelling.** From the run-65 pair:
    numerals (script `10` / whisper `ten`; script `top-10` / whisper `top ten`), splits
    (script `Quillan` / whisper `Quill and`), plus VAD drops and inserted tokens. A
    positional zip desyncs permanently on the first one; `difflib.SequenceMatcher` over
    *normalised* tokens gives the opcode stream needed to handle each case honestly.
  - **`video/caption_retext.py`** (new, pure, no I/O):
    `retext_words_from_script(words, script) -> list[dict] | None`, returning the same
    `[{word, start, end}]` shape with **script tokens** on **whisper times**.
    Tokens via `clean_script_for_tts` (`core/utils.py`) — the same transform
    `generate_audio` applies, so we align against what was actually spoken — with
    punctuation left attached, so `group_into_lines` breaks on the *script's* real
    sentence ends. Normaliser = lowercase alphanumerics **plus a digit↔word table**
    (0–20/hundred/thousand) so `10` matches `ten`; rankings, rounds and seasons are most
    of what this channel says. Opcodes: `equal` → 1:1; `replace` (n script ↔ m ASR) →
    spread the ASR span across the script tokens weighted by character length (the
    `Quillan Salkilld` ↔ `Quill and Salkal` case); `delete` → untimed, filled by
    interpolation between known neighbours, clamped non-decreasing; `insert` → dropped,
    time absorbed by neighbours.
  - **Decline rather than guess:** below `CAPTION_RETEXT_MIN_MATCH` (0.6) of script
    tokens landing in `equal` blocks, return `None`. A transcript that doesn't match the
    script means the *timings* describe different audio too, so painting the script over
    them yields confidently-wrong captions — decisions §18's failure shape exactly. The
    caller then falls back to the proportional estimate, which at least spells correctly.
    `CAPTION_RETEXT=off` keeps raw ASR for benching; empty script ⇒ input unchanged.
  - **Wiring:** one branch in `video/subtitles.py::generate_subtitle_file` (~line 110),
    **whisper path only** — the ElevenLabs sidecar came from our own text and is already
    right. Also export `matched_pairs()` so `scripts/bench_caption_align.py` shares one
    matcher instead of keeping its own `align_sequences` walk.
  - **Proof, not assertion:** the sidecar is *both* true text and true timing, so feeding
    its text in as the "script" makes retexted output **1:1 token-aligned with ground
    truth** — per-word error with no pairing ambiguity at all. Bench gains raw-vs-retexted
    columns (line-start error must hold its ~43–56ms band); then the named regression on
    real audio (the run-65 SRT must read `Quillan Salkilld` / `Mateusz Gamrot` /
    `top-10`); then a real $0 render so captions are judged as burned pixels.
  - **Tests** (`tests/test_caption_retext.py`, pure/offline per `tests/CLAUDE.md`): the
    run-65 regression verbatim; `10`↔`ten` and `top-10`↔`top ten`; whisper drops a word
    (still timed, still monotonic); whisper inserts one (dropped, no gap); exact match
    preserves timings byte-for-byte; unrelated transcript ⇒ `None` ⇒ proportional SRT;
    sidecar path never retexts.
  - **Docs on landing:** `caption_align.py`'s "Known limitation — ASR text" block (that
    *is* the thing being fixed), `providers_runbook.md` U1, `free_mode.md` (drop the
    "not recommended yet" caveat only if the proof earns it), `.env.example` (the caption
    block still reads `none | whisperx` — stale), decisions §23 (*timing from ASR, text
    from the script; ASR text is never trusted for proper nouns*).
- [ ] **$0 TTS switch** — **technically unblocked 2026-08-16** (captions fixed above; a
  full Piper render was verified end to end), now waiting on two operator calls rather
  than engineering. Local Piper meters $0 vs **$0.25–0.31/video (~91% of run cost)**.
  1. **Judge the voice** — `output/samples/piper_lessac_run65.mp3` vs the ElevenLabs
     render of the same script. Deliberately not decided for you.
  2. **Re-run `py -m scripts.bench_script_duration` after any flip** — Piper reads the
     same script ~20% slower (66.3s vs 55.2s), so `WORDS_PER_SECOND` and the
     learned-length loop go stale otherwise.
  Flip with `TTS_PROVIDER=piper` + `PIPER_VOICE` + `CAPTION_ALIGN_BACKEND=faster_whisper`
  ([free_mode.md](free_mode.md)); ElevenLabs remains the default and nothing was switched
- [ ] Clip-from-source (Phase R) + subject-tracked auto-reframe
- [ ] Avatar mode, upscaling (Real-ESRGAN/RIFE), storyboard shot-lists
- [ ] Router vision path → multimodal rendered-video review (Pillar 2)

**Efficiency & observability**
- [x] ~~Cost / quota dashboard (O9)~~ — shipped in wave 3 (`ops reliability`); this entry was stale
- [x] Governor follow-ups (O12), part 1 — **per-provider LLM spend in the cost line**
  (`cost_meter.llm_cost_by_provider`) + **cross-run dead-model persistence**: a retired
  slug is skipped for `LLM_DEAD_MODEL_TTL_SECONDS` (24h) instead of costing a failed
  probe every run, key-hash invalidated and shown in `ops reliability`
- [x] **Governor follow-ups (O12), rest** *(2026-08-14)* — **YouTube units under a
  governor scope** (`quota_governor.youtube_usage()`; `snapshot()` now reports
  apify/llm/signals/**youtube** together, while `apis/youtube_quota` stays the counter
  and the check point per decisions §13) + a **reliability time series**
  (`core/reliability_history.py`): one row per day of LLM spend, YouTube units, signals
  disabled, dead feeds and cache hit-rate, rendered as an ASCII trend under
  `ops reliability`. Recorded *on view*, so the series builds itself. **O12 complete** —
  the dashboard could only ever answer "how is it now", never "is this getting worse",
  which is how every failure found this session stayed invisible while it developed
- [x] ~~Router follow-ups — premium→cheaper provider failover on auth/quota error~~ — already
  live as O5/O6 (`_RETRYABLE_LLM` chain failover + `_DISABLE_LLM` session breaker); entry was stale

**Growth & new verticals**
- [ ] MoneyWise depth wave — earnings-calendar signal, ticker watchlist, finance brief sections
- [ ] Third-vertical groundwork: AI Tools / Tech — channel profile + SEO + coverage audit

**Engineering hygiene**
- [x] git private remote — create + push *(done: `jmcdigmarketing-cpu/content_machine`, private)*
- [x] **Branch + PR triage** *(2026-08-17)* — the 21-commit stack is in **PR #34**
  (CI green, operator to merge). All seven stale PRs **#26–#32 closed** and their branches
  deleted; **#27** would have turned CI permanently red (superseded *and* carrying the
  expired date #33 fixed). Five orphan docs harvested first, each with a supersession
  header. *Still open:* `origin/claude/docs-optimization-review-a4l104` — **9 commits, no
  PR, last touched 2026-07-21**, on an old base, so merging it would revert code that has
  since landed; same shape as #27 and needs the same decision.
- [x] **Silent exception handlers annotated + ruff ratchet** *(2026-08-16 — decisions §24)*.
  The audit sized this at **93 bare `pass` swallows** of 420 broad handlers and called it
  "the real debt". All **98** (90 `S110` + 8 `S112`) now log, and `S110`/`S112` are
  enabled in `pyproject.toml` so new ones fail CI.
  - **Level policy, not blanket-debug.** `core/logging.py` defaults to
    `CONTENT_LOG_LEVEL=WARNING`, so the audit's own "add a `logger.debug` everywhere"
    would have produced 93 invisible lines. `warning` where a *guarantee* is lost
    (`llm_add_spend` — the daily-budget guard under-counts and stops guarding;
    `write_run_trace` — `ops traces`/`dossier`/`data_quality` go blind for that run);
    `debug` for best-effort enrichment; `# noqa: S110` + reason where silence is right.
  - **Both directions tested** (`tests/test_fail_open_visibility.py`): the warnings fire
    with useful content *and* a healthy run stays silent — a warning that always fires
    teaches the operator to ignore warnings.
  - **Found a bigger defect than any handler:** `alembic/env.py` called `fileConfig()`
    with the default `disable_existing_loggers=True`, disabling the whole
    `content_machine.*` tree. `migrate_schema` runs `upgrade_head()` in a normal process,
    so **every log line after a migration was dropped in silence**. Fixed + pinned
    (`tests/test_alembic_logging.py`). Surfaced only because the new tests passed alone
    and failed under discovery.
  - Messages were written by hand, which was the point of reading all 98: "loads skipped"
    says nothing; "Unreadable quality_json on run %s" says what was lost.
- [ ] Tighten the mypy baseline *(the other half of the old combined line)*
- [~] **Raise test coverage on render + publish paths** — *started 2026-08-17, paused
  part-way; the remaining design is written out here so it survives the break.*
  - **First, the framing is wrong in the old roadmap line.** Measured rather than
    assumed, these paths are not broadly untested: **20 test files** already touch them
    and publisher-level upload is genuinely well covered (`test_youtube_upload.py` has
    idempotency, quota block, success, pending-healed). The real gap is narrow — the
    functions **no test ever names** — and it happens to be the most dangerous code:

    | Module | Never named in a test |
    |---|---|
    | `video/channel_intro.py` | ~~`prepend_channel_intro`~~ **done** |
    | `jobs/worker.py` | ~~`process_one`~~ **done** (quota gate + `_defer_for_quota`) |
    | `youtube/oauth.py` | ~~6 of 8~~ **done** — `load_credentials`, `save_credentials`, `token_has_scope`, `oauth_scopes`, `token_path_for_channel` (`tests/test_youtube_oauth.py`; `run_interactive_oauth` skipped — needs a browser) |
    | `publishing/registry.py` | `enabled_publish_platforms`, `publishers_for_channel` |
    | `youtube/upload.py` | `is_upload_configured` |
    | `youtube/thumbnails.py` | `merge_thumbnail_into_upload_detail` |

  - **[x] Done — `prepend_channel_intro` + a real defect** (commit "Never lose the render
    when the intro step fails"). It moves the finished mp4 aside with `os.replace` before
    ffmpeg runs, and the restore was reached **only on a non-zero exit code** — so ffmpeg
    missing from PATH (subprocess raises before any exit code exists) left the render
    parked at `<path>.body.tmp.mp4` while `render_vertical_video` logged *"Channel intro
    skipped (render kept)"*. The pipeline then stored an `mp4_path` with no file behind
    it and the upload failed much later with "invalid file". Reproduced first — the test
    failed with *"rendered video vanished from its path"*. Now a `try/finally` covering
    non-zero exit, raising subprocess, empty output and Ctrl-C, plus an output
    exists-and-non-empty check before the temp is deleted. 15 tests.
  - **[x] Done — `process_one` quota gate + `_defer_for_quota`** *(2026-08-20)* —
    `tests/test_job_worker_process.py`. Exhausted quota claims only render jobs;
    a quota deferral decrements `attempts` and sets a future `scheduled_at` so
    blocked days cannot silently exhaust `max_attempts`.
  - **[x] Done — `build_render_ffmpeg_command`** *(2026-08-20)* —
    music bed mixed *under* the VO (`amix … normalize=0`, bed at `MUSIC_BED_VOLUME`),
    `music_path=None` byte-identical to the VO-only command, `-t` bounds the output,
    subtitles burned from the escaped path; `render_vertical_video` retries VO-only
    when the bed mix fails (`tests/test_render_video.py`).
  - **[ ] Next, in blast-radius order:**
    1. ~~**`jobs/worker.process_one` — the quota gate**~~ **done 2026-08-20**.
    2. ~~**`_defer_for_quota`**~~ **done 2026-08-20**.
    3. ~~**`build_render_ffmpeg_command`**~~ **done 2026-08-20**.
    4. ~~**`youtube/oauth.py`**~~ **done 2026-08-20** — `token_has_scope`,
       `token_path_for_channel`, `oauth_scopes`, and `load_credentials`/`save_credentials`
       round-tripped against a **temp** token file. Never `config/secrets/`.
       `run_interactive_oauth` still skipped (needs a browser).
  - **[x] Tooling:** `coverage` is in the `[dev]` extra. Report only — **not** a CI
    percentage gate (a ratchet is only worth it when it catches a real defect class,
    as `S110` did).
    ```
    py -m coverage run -m unittest discover -s tests
    py -m coverage report --include="video/*,publishing/*,youtube/*,jobs/*"
    ```
  - **Method that paid off and should be repeated:** write the test first and watch it
    fail. The intro defect was found by asserting the *consequence* ("the file is still
    there") rather than the implementation. Also: no test may touch the real DB, `data/`,
    `config/secrets/` or the vault — last wave a test wrote a real run row (id 67) into
    the operator's database.

**Pillar 7 — Self-improving skills (Agent Skills + SkillOpt)** *(shipped 2026-07-24 — detail in the Pillar 7 section below)*
- [x] C1 — `scripts/ops.py` commands exposed as `skills/content-ops/SKILL.md` (Agent Skills)
- [x] C2 — SkillOpt-Sleep gated proposal loop (`core/skillopt.py`, opt-in in `overnight`)
- [ ] C-follow-ups — LLM-proposed directives; optional auto-apply of a gate-winner behind a flag

**Deferred (volume-gated — do not build until publish volume supports correlations)**
- [ ] Thumbnail scoring → CTR (needs impressions/CTR in the metrics sync)
- [ ] Prompt-performance analysis; asset-effectiveness ranking from `assets` history
- [ ] Full operator dashboard / Channel Command Center
- [ ] Tavily / broad web research; Bluesky direction signal
- [ ] Multi-language (single script → localized TTS) — low priority for the gaming/UFC niche

*Excluded: **Phase M — multi-platform distribution** (TikTok/Instagram/Reels + cross-platform
learning) stays parked under [Later horizons](#later-horizons).*

**Candidate ideas (2026-08-20 session — Phase M excluded)**

*Brainstorm. Rationale: [planning_log.md](planning_log.md) 2026-08-20 and
[audit.md](audit.md). None of these restates an open Next-up line
(clip-from-source, avatar, MoneyWise depth, Instagram figures). Items 1 and 4
plus the coverage-wave and router-vision Next-up lines shipped the same day.*

- [x] Capability-probe consolidation — one SoT for Ollama/TTS readiness; teach
  `ops free-doctor` "up but empty" vs "down" (the run-70 class) `[S]`
  *(2026-08-20: `ollama_probe` shared; free-doctor pull vs serve vs OpenRouter)*
- [x] Pre-run completion gate — readiness line ≡ applied env ≡ first LLM/TTS call
  before discovery starts `[S]`
  *(2026-08-20: `inspect_first_calls` / `guard_before_discovery`; Free fail-closed,
  Standard warns; stale Readiness cannot start discovery)*
- [ ] Clone-this-winner into discovery — `winners()` is display-only; `best_bet`
  already consumes the graveyard `[M]`
- [x] Semantic near-duplicate authenticity — `SequenceMatcher` misses paraphrases;
  2026 policy targets rehash `[M]`
  *(2026-08-20: stdlib content-word cosine in `_variation_check`; `AUTHENTICITY_SEMANTIC`)*
- [x] Integration incident ledger — persist signal/provider failures; rank by
  count × recency `[S]`
  *(2026-08-20: `ops incidents` + reliability view; score = count / (1 + days);
  writes `data/incidents.json` on view, not from the signal thread pool; tests
  persist to a temp path)*
- [x] Per-stage LLM cost attribution — tag router calls by pipeline step `[S]`
  *(2026-08-20: `complete(..., stage=)`; default stage=tier; script/brief/title
  tagged; `ops` cost line `stages[...]`; cost_meter `llm_cost_by_stage`)*
- [ ] Recommender simulation harness — synthetic histories so the loop is
  validatable before n=15 `[M]`
- [x] Docs metric lint in CI — test counts, shipped checkboxes, relative links `[S]`
  *(2026-08-20: `tests/test_docs_lint.py` + CI step; relative links in `docs/*.md`;
  no network; does not rewrite July docs)*
- [x] Include Qwen3 in Free TTS readiness — runtime provider exists, `_LOCAL_TTS_ORDER`
  skips it `[S]`
  *(2026-08-20: qwen in `_LOCAL_TTS_ORDER` when `qwen_tts` + `QWEN_VOICE` are ready;
  does not load the 1.7B model)*
- [x] `signal_facts` formatter ratchet — live signals (earnings) currently JSON-dump `[S]`
  *(2026-08-20: `earnings` renders symbol/date/days/EPS; no JSON dump; unknown
  signals still snippet as JSON)*
- [x] Allocated vs marginal unit economics — Creator plan ~$1/video allocated vs
  $0.31 metered `[S]`
  *(2026-08-20: `ops economics` shows both; `COST_TTS_PLAN_USD` / `COST_TTS_PLAN_CHARS`;
  cost_meter marginal rates unchanged)*
- [x] Stable vault dossier paths — date-prefix clones the same `run_id` `[S]`
  *(2026-08-20: `{run_id}_{slug}.md`; refresh overwrites; date-prefixed clones unlinked)*
- [x] Competitor-channel health — dead Pat McAfee UC id still in
  `config/competitors/tapin.json` `[S]`
  *(2026-08-20: `ops competitor-health` RSS probe; reliability uses snapshot only
  — no extra HTTP; McAfee UC flagged `unverified`, not auto-replaced)*
- [x] Pronunciation lexicon for local TTS — captions now spell names; Piper still
  says them wrong `[M]`
  *(2026-08-20: `config/pronunciations.json` applied on the local TTS path only;
  captions/retext keep the original script; ElevenLabs unchanged)*
- [ ] Hook-score vs retention calibration — 0–100 heuristic never checked against
  `audienceWatchRatio` `[M]`
- [ ] Semantic vault fact retrieval — token overlap misses related notes `[M]`
- [ ] CUDA torch as an ops enablement — RTX 4070 Ti is in the box; `2.8.0+cpu` is
  the actual gate `[M]`
- [x] Audio LUFS normalize — ffmpeg `loudnorm` for Shorts level consistency `[S]`
  *(2026-08-20: `LUFS_NORMALIZE` opt-in; default command byte-identical; I=-14)*
- [x] Background clip anti-repeat — variation guard checks scripts, not pictures `[S]`
  *(2026-08-20: `assets/clip_memory.py` in-process deque; `CLIP_MEMORY` file persist
  opt-in; fail-open if every clip was used)*
- [x] Numeric/record grounding — gate catches names; invented ranks/dates/purses pass `[M]`
  *(2026-08-20: `find_ungrounded_numeric`; sports-context records/ranks/dates; purses
  always; warn/fail-open; round scores like 10-9 are not records; "If Netflix" intact)*

**Candidates 21–55 (2026-08-20 afternoon — docs only; Phase M still parked)**

*None of these restates Next-up or the 20-item morning list. Volume-gated
backtest, $0 TTS voice judgment, and Instagram/TikTok publishers stay out.*

Aesthetics / on-screen

- [ ] 21. Per-channel caption skin in `channels.json` (font, karaoke vs boxed, fill color) — themes already exist for the CLI, not the video `[S]`
- [ ] 22. Thumbnail safe-area / YouTube chrome checker (PIL: keep faces and title text out of the bottom 20%) `[S]`
- [ ] 23. End-card / subscribe sting after VO, fail-open, per-channel asset `[S]`
- [ ] 24. Lower-thirds for fighter/game names from the fact corpus (the names captions already get right) `[M]`
- [ ] 25. Channel LUT / color grade on the stock loop so TapIn and MoneyWise do not share the same ungraded look `[M]`
- [ ] 26. Hook-line Ken Burns / zoom on the first caption beat only (retention cliff is already measured) `[M]`
- [ ] 27. Dual thumbnail: high-contrast text-on vs face-forward, operator pick, logged as the thumbnail experiment arm `[M]`
- [ ] 28. Intro/outro duration learned from the channel drop-off point instead of a fixed 2.15s TapIn sting `[M]`

Organization / operator surface

- [x] 29. `ops postmortem --run-id` — slowest phase, failed signals, ungrounded claims, cost, next fix; assembled from traces that already exist `[S]`
  *(2026-08-20: `core/postmortem.py`; no new I/O beyond existing traces/run row)*
- [x] 30. `ops doctor` — one command: free-doctor + feeds + oauth scopes + quota snapshot + caption/TTS readiness `[S]`
  *(2026-08-20: also CUDA probe; oauth is token-file + scopes, no refresh HTTP;
  feeds from cached `ops feeds` snapshot)*
- [ ] 31. Artifact retention job: cap `output/*/drafts`, `data/traces`, old `_runs/` clones; dry-run first `[S]`
- [ ] 32. Split `core/ui.py` (~1,400 LOC and growing) into prompt / display / recovery modules — the July audit’s compounding smell `[M]`
- [ ] 33. `channels.json` JSON Schema ratchet in CI so a missing `persona` or bad `ui_theme` fails before a run `[S]`
- [ ] 34. Vault note templates in-repo (`_operator_facts`, strategy, sources) so hand-written notes always carry `tier`/`verified_at` `[S]`
- [ ] 35. Alembic-only schema path — stop teaching two migration stories (`migrate_schema` vs Alembic) `[M]`
- [ ] 36. `ops topic-clone --run-id` — seed a new draft from a winner (angles new, facts refreshed); the missing write path behind display-only `winners()` `[M]`
- [ ] 37. Playbook lint: strategy bullets that never got a `[strategy]` tag silently feed facts today in the inverse direction; warn `[S]`

Efficiency

- [ ] 38. NVENC hardware encode on the 4070 Ti (`h264_nvenc`) for render; CPU libx264 stays fallback. Render is the longest paid-adjacent wait `[M]`
- [ ] 39. Draft-vs-publish render preset: 480p `ultrafast` for operator preview, 1080p film for upload `[S]`
- [ ] 40. Overlap thumbnail + TTS while the operator is still on the report-card prompt (interactive path only) `[M]`
- [x] 41. Cap discovery workers so one slow Apify actor cannot set wall-clock for every run (twitter’s lesson, still true for tiktok ~14s) `[S]`
  *(2026-08-20: `DISCOVERY_MAX_WORKERS` default 8; 0/off = one worker per source;
  explicit `max_workers=` still wins)*
- [ ] 42. Shared discovery cache across `batch-drafts` topics that share a franchise anchor (GTA 6 leaks × N) `[M]`
- [x] **43. Script trim pass** *(2026-08-21)* — drop trailing padding sentences when over length; never clip; hard cap remains refuse `[S]`
- [ ] 44. ffmpeg `-ss` output-seek already documented; bake a `scripts/probe_sync.py` so intro-offset mistakes stop getting relearned `[S]`
- [x] 45. Overnight quota-aware: skip or shrink `--count` when YouTube remaining < 1,600 or Apify breaker is in `[S]`
  *(2026-08-20: `OVERNIGHT_QUOTA_GATE` opt-in; fail-open on store errors; suite sets false)*

Long-term / intelligence

- [ ] 46. UFC/NBA/game **seasonal calendar** as a $0 best-bet source (cards, earnings weeks, launch dates) — best-bet is RSS-only at startup by design `[M]`
- [ ] 47. Topic graph: franchise arcs (GTA VI week 1 → week 4) so best-bet can continue a story instead of only avoiding the graveyard `[L]`
- [ ] 48. Multi-run series (`part 1/2/3`) with a vault-backed outline; cadence still capped `[L]`
- [ ] 49. Post-publish first-hour anomaly (views or engaged-rate vs channel baseline) → webhook. Uses metrics sync, not a new API `[M]`
- [ ] 50. Learned insight-marker list: replace the hardcoded `_INSIGHT_MARKERS` from scripts that actually retained `[L]`
- [ ] 51. Channel DNA export → new-channel playbook (the AI Tools/Tech groundwork, but as a dump of what TapIn learned) `[M]`
- [ ] 52. Graveyard reason codes (thin facts / recap / wrong domain) so avoid-list is explained, not just a mute set `[S]`
- [ ] 53. Prompt-version auto-bump from a hash of `content_engine` prompt builders so `ops prompt-eval --compare` is meaningful after silent edits `[S]`
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
  *(2026-08-20: checklist also requires persona tone+audience; MoneyWise brand/SEO/feeds pass, persona still FAIL; never reads token contents except via existing oauth helpers)*
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
- [ ] 81. **Cross-channel prior for MoneyWise cold-start** — a new channel has n=0; don't wait for 15 measured videos to recommend anything (vision challenge #6) `[M]`
- [ ] 82. Optional **2-second operator-on-camera sting** (real face, fail-open) — 2026 policy punishes synthetic-and-shallow; this is cheaper than the GPU avatar stack and is not avatar mode `[M]`
- [ ] 83. **Holdout videos** (recommender off, one per N publishes) — without this the learning loop learns superstitions (vision challenge #2) `[M]`
- [x] 84. **RPM × cost by domain** — UFC vs GTA vs NBA contribution margin decides what TapIn should actually be; views-by-domain already exist `[S]`
  *(2026-08-20: `ops economics` adds RPM x cost by domain from `features.domain`)*
- [x] 85. **Weekly moat backup** — `pg_dump` + vault + `data/traces` (encrypted secrets excluded); the dataset *is* the company (operating_plan §7) `[S]`
  *(2026-08-20: `ops moat-backup` dry-run plan; `--apply --file dest` copies traces/vault;
  `.env` / `config/secrets/` / `quota_state.json` excluded; pg_dump is listed not executed)*
- [ ] 86. **Prompt-eval as a CI regression** on one frozen golden topic per channel — a prompt edit that increases ungrounded claims fails the job `[M]`
- [x] 87. **YPP / membership readiness checklist** — watch-hours, disclosure, cadence headroom; description CTAs exist, the unlock path does not `[S]`
  *(2026-08-20: `ops ypp`; fail-open without metrics; hours OR Shorts-views path)*
- [x] 88. **Competitor-sync daily YouTube-unit cap** — competitor genome will eat the 10k/day budget (vision challenge #4); hard ceiling before "more intelligence" `[S]`
  *(2026-08-20: RSS still free; API fallback capped (`COMPETITOR_SYNC_MAX_UNITS=30`)
  and reserves one upload (`COMPETITOR_SYNC_RESERVE_UNITS=1600`); 0/off = unlimited)*
- [ ] 89. **Public-safe dossier redaction** — if #78 is sold, vault notes must not leak operator facts, unpublished scripts, or key material `[M]`
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
- [ ] 94. NVIDIA driver + NVENC *capability* probe in `ops doctor` (distinct from #38 actually encoding) `[S]`
- [ ] 95. RAM/VRAM preflight before whisper / local TTS so Free mode does not OOM mid-run `[S]`
- [ ] 96. `ops secrets-doctor` — keys present, not obviously expired, never copied into traces `[S]`
- [x] **97. Redact API bodies from traces** *(2026-08-21)* — 402/403 payloads stripped on write `[S]`
- [ ] 98. `pip-audit` / Dependabot in CI (supply chain; report-only like coverage) `[S]`
- [x] 99. Close the suite’s live Google HTTPS leak (audit C9 `ResourceWarning`) `[M]`
  *(2026-08-20: skip YouTube warmup in tests; `static_discovery=True` on `build()`;
  `CONTENT_FORBID_LIVE_YOUTUBE` blocks Data/Analytics clients and OAuth refresh;
  suite also forces `YOUTUBE_ANALYTICS_SYNC=false` so operator .env cannot leak)*
- [ ] 100. OneDrive/`.git` hazard check in `ops doctor` (operating_plan §7; specific, not a generic doctor) `[S]`

YouTube surface (still YouTube-only)

- [ ] 101. Upload a caption *track* (not only burned) — accessibility + search `[S]`
- [ ] 102. Auto-set YouTube category from `infer_domain` (Sports vs Gaming) `[S]`
- [ ] 103. Description **sources** block from vault `source_url`s `[S]`
- [ ] 104. Playlist-per-franchise via Data API (GTA, UFC cards) `[M]`
- [ ] 105. Pin a comment that answers the top `youtube_comments` question `[S]`
- [ ] 106. Detect Studio-deleted videos and cancel `publish_log` (re-queue path exists; detection does not) `[S]`
- [ ] 107. `madeForKids=false` self-declared audit on every insert `[S]`
- [ ] 108. Default language + audio language on `videos.insert` `[S]`
- [x] **109. Unlisted review before public** *(2026-08-21)* — immediate public held as unlisted (`YOUTUBE_UNLISTED_REVIEW`) `[S]`
- [ ] 110. Chapter timestamps for Extended `[S]`
- [ ] 111. End-screen / cards pointing at the previous franchise video (YouTube API) `[M]`
- [ ] 112. Correction dossier + community-post template when post-publish facts reverse `[M]`

Content / learning

- [ ] 113. Prediction ledger — persist “we called X” vs later outcome `[M]`
- [ ] 114. Audience-question series: cluster `youtube_comments` across runs into a mailbag `[M]`
- [ ] 115. Don’t publish during a live UFC PPV window (cannibalize the niche) `[S]`
- [ ] 116. Blackout / quiet-hours calendar in `channels.json` `[S]`
- [ ] 117. Title uniqueness vs own catalog (no colliding titles) `[S]`
- [ ] 118. Description first-line SEO (search; not hashtag stuffing) `[S]`
- [ ] 119. Stock-clip **watermark detector** — skip footage that shows another channel `[M]`
- [ ] 120. Embedding / CLIP b-roll match vs keyword stock search `[L]`
- [ ] 121. Stock query rewriter: never Pexels-search trademarked “UFC” fight footage `[S]`
- [ ] 122. `license.yaml` beside local clips (we own this file) `[S]`
- [ ] 123. Number/SSML reading rules (`29-1`, UFC 317, `$50k`) — distinct from the name lexicon `[M]`
- [ ] 124. Pause-after-hook: 200–400ms silence after line 1 `[S]`

Legal / policy / MoneyWise (not Phase M, not the #79 spike)

- [ ] 125. MoneyWise finance disclaimer in description (separate from AI disclosure) `[S]`
- [ ] 126. Odds-derived scripts must say “market”, never “will” `[S]`
- [ ] 127. Gambling/odds advertiser-safe mode (strip implied betting CTAs) `[S]`
- [ ] 128. FTC affiliate disclosure *line* (copy; #79 is the tracking spike) `[S]`
- [ ] 129. UFC/trademark title linter (`UFC` vs “fight night”) `[S]`
- [ ] 130. Right-of-publicity: refuse stock thumbs that look like a real fighter’s face `[M]`
- [ ] 131. Demonetization detector (`estimatedRevenue` cliff vs channel baseline) `[S]`
- [ ] 132. Policy-incident runbook (strike / Content ID / appeal template in-repo) `[S]`

Operator product

- [ ] 133. `.ics` calendar of scheduled publishes `[S]`
- [ ] 134. n8n/email recipe for `weekly-report` (events exist; this is the recipe) `[S]`
- [ ] 135. CSV export of `ops economics` `[S]`
- [ ] 136. Vault Dataview-friendly dossier frontmatter `[S]`
- [ ] 137. Wiki-links between related `_runs/` dossiers `[S]`
- [ ] 138. Long-form length preset that is **not** a Short (16:9 sibling already exists) `[M]`
- [x] 139. Channel trailer / handle / banner checklist inside `channel-go-live` `[S]`
  *(2026-08-20: banner file + `youtube_handle` + trailer id/file; MoneyWise banner
  passes, handle/trailer still FAIL)*
- [ ] 140. YouTube quota-increase request playbook (when 10k/day is the ceiling) `[S]`

**Candidates 141–320 (2026-08-20 late-night brainstorm — UI / app / aesthetics / sibling software)**

*Brainstorm. Rationale: [planning_log.md](planning_log.md) 2026-08-20 (late-night
brainstorm). Exactly **5 `[XL]` / 25 `[L]` / 50 `[M]` / 100 `[S]`**. None restates
a shipped checkbox, Next-up, or candidates 1–140 unless reframed as a **new
product** (called out). Phase M, the volume-gated backtest, and the $0 TTS voice
judgment appear only as **PARKED** massive/larger. Evening recommended next 5
stay shipped; **Brainstorm next-5 (UI/app)** = 221, 222, 223, 224, 171.
**Pickup order** is now **Recommended next 20 (2026-08-20 night)** under
Next up — this 141–320 list is not a sequence and is not rewritten here.
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
- [ ] 147. Localhost **FastAPI operator shell** (static UI, not SaaS) `[L]` — *new-app.* **Skipped 2026-08-21** (would swallow the leave-the-terminal wave). Booth uses stdlib `--serve`; swapped this slot for #240 + #254. Not #141.
- [ ] 148. **Job-queue visualizer** with drag-reorder (render vs upload vs quota-defer) `[L]` — *UI.* Worker stalls are invisible; 1,600-unit ceiling needs a picture.
- [ ] 149. **Analytics Studio** (retention / CTR / RPM local web) `[L]` — *viability.* Weekly-report ASCII cannot show curves; still honest that n≈10 is thin.
- [ ] 150. **TapIn vs MoneyWise visual language packs** (GUI + video chrome) `[L]` — *aesthetics.* `ui_theme` is ANSI; the two channels still share one ungraded look.
- [ ] 151. **Brand-kit compiler** (fonts/palette/sting/handle/banner → render + GUI) `[L]` — *aesthetics.* `channel-go-live` checks files exist; it does not apply a kit.
- [ ] 152. **Thumbnail composition canvas** (operator drag layers) `[L]` — *aesthetics / UI.* Distinct from #22 PIL safe-area *checker*: this is an editor.
- [ ] 153. **Caption choreography timeline** (karaoke beats vs SRT) `[L]` — *aesthetics.* Distinct from #21 JSON font skin: timing and placement, not fill color.
- [ ] 154. **MSIX / Inno installer** bundling Python + ffmpeg + tray `[L]` — *new-app.* Packaging is what makes #141 software instead of a repo.
- [ ] 155. **MCP + local plugin API** over `core/` `[L]` — *new-app.* Agents scrape CLI today; contract must not add a signal cache or skip `quota_governor`.
- [ ] 156. **Vault Companion** (Obsidian-lite for facts / playbooks / dossiers) `[L]` — *new-app.* Pillar 4 dumps markdown; tier/expiry UX is sibling software.
- [ ] 157. **Clip Librarian** (search, license, anti-repeat, performance) `[L]` — *new-app.* Distinct from shipped clip-memory deque and from #120 CLIP match.
- [ ] 158. **Cost Control Tower** (TTS 91% / two Apify actors / YouTube units) `[L]` — *cost.* Allocated vs marginal already ships as ASCII; this is the dashboard app.
- [ ] 159. **MoneyWise earnings-floor board** (calendar/ticker UI) `[L]` — *UI / viability.* Distinct from Next-up MoneyWise *depth signals*: a board, not new APIs.
- [ ] 160. **Legal / disclosure review wizard** (AI, finance, FTC, trademark) `[L]` — *viability.* Distinct from #125–129 copy lines: a publish-blocking UX.
- [ ] 161. **Publish calendar GUI** (week view + overlays) `[L]` — *UI.* Distinct from #133 `.ics` export: a visual week, not a file dump.
- [ ] 162. **Experiment cockpit** over `experiments.json` `[L]` — *viability.* TTS arms are report-only; this UI still must not auto-assign Piper.
- [ ] 163. **Script desk** with grounding heat-map `[L]` — *UI / viability.* Numeric/record + claim verifier already compute; painting the script is the surface.
- [ ] 164. **Overnight factory monitor** (gates, progress, human-presence) `[L]` — *UI.* Overnight + render-gate + heartbeat shipped; watching them is still log-tailing.
- [ ] 165. **Notification center + DND** (history, quiet hours, click-through) `[L]` — *UI.* Broader than a single toast (#221): Action Center as a product slice.
- [ ] 166. **PARKED — Voice Judgment Booth** (Piper vs ElevenLabs A/B ears) `[L]` — *cost / parked.* Captions unblocked the $0 path; this booth never auto-flips `TTS_PROVIDER`.
- [ ] 167. **PARKED — Recommender Backtest Studio** `[L]` — *viability / parked.* Next-up backtest stays volume-gated; the studio must refuse to fit before n is honest.
- [ ] 168. **Unlisted review room** (player + Approve, around unlisted upload) `[L]` — *UI.* Distinct from #109 unlisted *flag*: this is the room; #171 is last-run HTML only.
- [ ] 169. **Channel Command Center v1** as a local single-operator app `[L]` — *new-app.* Reframe of deferred "full operator dashboard": local, no SaaS billing — first slice of #141.
- [ ] 170. **Design-token pipeline** (one JSON for GUI + video) `[L]` — *aesthetics.* Stops ANSI themes, Pillow thumbs, and captions drifting into three palettes.

Moderate — days

- [x] 171. **Last-run review booth** *(2026-08-21)* — `ops booth` (play / grade / authenticity / Approve; stdlib HTML, not FastAPI) `[M]` — *UI / new-app.* **Brainstorm next-5.** Last render only; not #168.
- [ ] 172. Operator **HTML design system** (type, density, buttons) `[M]` — *aesthetics / UI.* Shared chrome for every `--html` dump so they do not look like five blogs.
- [ ] 173. Per-channel **GUI chrome** (TapIn neon vs MoneyWise editorial) `[M]` — *aesthetics.* Smaller than language packs #150; header/type/accent only.
- [ ] 174. Windows **jump list** for last five drafts `[M]` — *new-app.* Taskbar right-click → open mp4 / booth, no console.
- [ ] 175. **Command palette** over `ops` subcommands `[M]` — *UI.* ~38 commands are unlistable from memory; palette is not a rewrite of `ops.py`.
- [ ] 176. Dark-mode **dossier HTML viewer** `[M]` — *UI.* Vault `_runs/` in the browser; does not change dossier schema.
- [ ] 177. Dual-channel **status wall** (TapIn | MoneyWise) `[M]` — *UI.* Two-pane health/quota/cadence; MoneyWise go-live FAILs stay visible.
- [ ] 178. **Render-progress pane** (ffmpeg % as a UI, not a spinner) `[M]` — *UI.* `CONTENT_RENDER_PROGRESS` exists; this is a window the operator can glance at.
- [ ] 179. **Authenticity visual checklist** (variation / insight / substance) `[M]` — *viability / UI.* Policy gate as boxes, not a log line.
- [ ] 180. **Report-card poster** layout (letter + cost subtitle) `[M]` — *aesthetics.* A–F as a designed artifact for review, not ASCII.
- [ ] 181. Thumbnail **A/B click-picker** that logs the experiment arm `[M]` — *UI.* Distinct from #27 dual *generation*: pick between already-rendered thumbs.
- [ ] 182. **Caption overlay on a still** (proofread names before burn) `[M]` — *aesthetics.* Fighter/game names are the subject; catch "Salkilld" on a frame.
- [ ] 183. **Font-pairing picker** (title vs body captions) `[M]` — *aesthetics.* Writes a note / token; not the full #21 skin schema.
- [ ] 184. Named **motion-style presets** (punch-in, snap zoom) `[M]` — *aesthetics.* Distinct from #26 first-caption-beat Ken Burns: a library of named styles.
- [ ] 185. Caption-vs-background **contrast auditor** `[M]` — *aesthetics.* WCAG-ish ratio on sampled frames; burned captions fail on busy clips.
- [ ] 186. Player **safe-title grid overlay** `[M]` — *UI / aesthetics.* Distinct from #22 PIL checker: live overlay in the review player.
- [ ] 187. **End-card preview compositor** `[M]` — *aesthetics.* Distinct from #23 fail-open sting *asset*: see the last 1s before render.
- [ ] 188. **Intro-sting waveform** (see the 2.15s TapIn hit) `[M]` — *aesthetics / cost.* Stops relearning intro-offset sync against the SRT.
- [ ] 189. Brand-kit **screenshot linter** (banner vs in-video palette) `[M]` — *aesthetics.* MoneyWise handle/trailer already FAIL; this diffs colors, not file presence.
- [ ] 190. MoneyWise **on-screen disclaimer bug** layout `[M]` — *viability / aesthetics.* Distinct from #125 description copy: a burned or overlay bug.
- [ ] 191. **AI-disclosure lower-third template** `[M]` — *viability / aesthetics.* Policy UX, not the authenticity gate itself.
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
- [ ] 209. **Keyboard-first review** (J/K/L like an NLE) `[M]` — *UI.* Short-term success is also operator minutes; keyboard is faster than prompts.
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
- [ ] 225. Toast on **upload scheduled** / `publishAt` `[S]` — *UI.* Cadence is easy to miss after the worker claims the job.
- [x] 226. Toast when a **breaker trips** *(2026-08-21)* (Apify / LLM / ElevenLabs / signals) `[S]` — *cost / UI.* Notify only.
- [ ] 227. Toast when **overnight finishes drafts** `[S]` — *UI.* Drafts are cadence-safe; nobody knows they exist until morning CLI.
- [ ] 228. Balloon: **"N uploads left this reset"** `[S]` — *cost / UI.* Same number as reliability; push it to Action Center.
- [ ] 229. Click-toast **opens last mp4** in the default player `[S]` — *UI.* Fastest review path that is not a booth.
- [ ] 230. Taskbar **overlay badge** (queue depth) `[S]` — *UI.* Worker progress without a window.
- [x] 231. Start-menu shortcut via **pyw** *(2026-08-21)* — `ops shortcut` + `content_os.pyw` `[S]` — *new-app.*
- [ ] 232. Desktop `.lnk` to the **review-booth URL** `[S]` — *new-app.* Depends on #171; the shortcut is the PR.
- [ ] 233. Per-channel **notification sound** `[S]` — *aesthetics.* TapIn vs MoneyWise should not share one ding.
- [ ] 234. High-contrast CSS for HTML reports `[S]` — *aesthetics / UI.* Respect Windows contrast themes.
- [ ] 235. TapIn **swatch strip** in HTML headers `[S]` — *aesthetics.* Channel color without a full language pack.
- [ ] 236. MoneyWise **serif header** on HTML reports `[S]` — *aesthetics.* Editorial vs neon, typeset only.
- [ ] 237. Favicon for localhost booth (channel mark) `[S]` — *aesthetics.* Browser tab literacy.
- [ ] 238. Local **poster image** for the review page `[S]` — *aesthetics.* 9:16 frame as page chrome; no network OG.
- [ ] 239. **Print stylesheet** for weekly-report HTML `[S]` — *aesthetics.* Magazine #215 is days; print CSS is hours.
- [x] 240. `ops status --html` *(2026-08-21)* `[S]` — *UI.* Swap for skipped #147 FastAPI.
- [x] 241. `ops economics --html` *(2026-08-21)* `[S]` — *cost / UI.* Allocated vs marginal already in the command.
- [ ] 242. `ops grade --html --run-id` `[S]` — *UI.* Report card as a page.
- [ ] 243. Startup **PNG wordmark** option beside ASCII `[S]` — *aesthetics.* `ascii_art` stays; a mark is for windows and HTML.
- [ ] 244. Windows Terminal **profile snippet** (channel colors) `[S]` — *aesthetics.* Docs + JSON fragment; not a theme rewrite.
- [ ] 245. HTML **type pairing** (Segoe UI / JetBrains Mono) `[S]` — *aesthetics.* One CSS file; design-system #172 can adopt it later.
- [ ] 246. Blurred **9:16 poster** as booth background `[S]` — *aesthetics.* Last frame, CSS blur only — no new ffmpeg.
- [ ] 247. CSS **grain/vignette preview** toggle `[S]` — *aesthetics.* Preview-only; does not change the render command.
- [ ] 248. Caption **font specimen strip** (three faces) `[S]` — *aesthetics.* Pick writes a note, not `channels.json` yet (#21).
- [ ] 249. Title-card mock: **2-line vs 3-line wrap** `[S]` — *aesthetics.* YouTube chrome rehearsal without uploading.
- [ ] 250. Emoji-free / **ASCII-safe HTML** (cp1252 lesson) `[S]` — *UI.* Same class as render-gate `>=` — consoles and files that cannot swallow glyphs.
- [ ] 251. **Copy-as-markdown** on the report card `[S]` — *UI.* Paste into vault or chat.
- [ ] 252. **Copy last unlisted URL** button `[S]` — *UI.* Distinct from implementing #109; clipboard only.
- [x] 253. **Reveal mp4 in Explorer** *(2026-08-21)* — `ops reveal` (`explorer /select,`) `[S]` — *UI.*
- [x] 254. **Reveal thumbnail in Explorer** *(2026-08-21)* — `ops reveal --kind thumb` `[S]` — *UI.* Bundled with #253 (swap leftover for skipped #147).
- [ ] 255. **Open dossier** via Obsidian URI (if vault set) `[S]` — *UI.* Fail-open when path empty.
- [ ] 256. **Reveal trace JSON** `[S]` — *UI.* `data/traces/<id>.json` without hunting.
- [ ] 257. **Drag-drop facts `.txt`** onto the booth `[S]` — *UI / short-term.* Overnight still cannot take `key_facts=`; this is intake chrome only.
- [ ] 258. Paste-facts textarea + **4500-char meter** `[S]` — *UI.* Operator fact budget is already a number; show it.
- [ ] 259. HTML **channel switcher** (tapin / moneywise) `[S]` — *UI.* Same constraint as #211: never an `.env` editor.
- [ ] 260. Keyboard **`?` cheat-sheet** overlay `[S]` — *UI.* Booth/palette discoverability.
- [ ] 261. **Skip-link** a11y on the booth `[S]` — *UI.* Keyboard users skip chrome to the player.
- [ ] 262. HTML5 **captions from SRT** `[S]` — *aesthetics / UI.* Review names without burning a new mp4.
- [ ] 263. Playback-rate **1.25×** toggle `[S]` — *UI.* Operator minutes.
- [ ] 264. **Loop last 3s of hook** `[S]` — *aesthetics.* Retention cliff rehearsal; no new render.
- [ ] 265. **Frame-step** with `,` / `.` `[S]` — *UI.* Proofread burned captions on a frame.
- [ ] 266. **Save current frame** as a still `[S]` — *aesthetics.* Operator stills folder; not a thumbnail API.
- [ ] 267. **9:16 letterbox** in a landscape window `[S]` — *aesthetics / UI.* Stop stretching Shorts in the booth.
- [ ] 268. **Safe-area overlay toggle** (YouTube UI chrome) `[S]` — *aesthetics.* Player overlay; not the #22 PIL test.
- [ ] 269. **Burned vs sidecar** caption toggle `[S]` — *UI.* Compare retext vs proportional without re-encoding.
- [ ] 270. **Waveform under the player** (from existing mp3) `[S]` — *aesthetics.* No new TTS spend.
- [ ] 271. Spoken vs **estimated duration** readout `[S]` — *cost / UI.* Measured 3.32 wps vs Piper ~20% slower — show both.
- [ ] 272. **Cost subtitle under the player** (`tts $0.31 · 91%`) `[S]` — *cost.* The number that should never be off-screen.
- [ ] 273. **Escaped free-first LLM** red pill `[S]` — *cost / UI.* Flag already ships; put it on the booth.
- [ ] 274. **Thin-facts warning banner** `[S]` — *cost / UI.* Same gate as #200, one strip.
- [ ] 275. Ungrounded **numeric chips** `[S]` — *viability / UI.* Record/rank/purse hits as chips, not a paragraph.
- [ ] 276. Authenticity **semantic-arm bar** `[S]` — *viability / UI.* Cosine arm is live; a bar is the surface.
- [ ] 277. Report-card **component breakdown** `[S]` — *UI.* Hook / grounding / authenticity as three numbers.
- [ ] 278. **Standard-would-have-billed** line on Free runs `[S]` — *cost / UI.* Dry-run already exists; show it on the booth.
- [ ] 279. **Allocated vs marginal** one-liner `[S]` — *cost.* Booth footer, not a new economics engine.
- [ ] 280. TTS **cache-hit $0** pill `[S]` — *cost / UI.* Cache shipped opt-in; celebrate a $0 re-render.
- [ ] 281. **Pillow vs Flux** thumb badge `[S]` — *cost / aesthetics.* Grade gate already chooses; label what the operator is seeing.
- [ ] 282. Human-presence **last-seen relative time** `[S]` — *UI.* Companion to #205, one string.
- [ ] 283. Render-gate **blocked reason** in plain English `[S]` — *UI.* ASCII `>=` stays in logs; the booth gets a sentence.
- [ ] 284. RPM-cost-gate **deferred reason** `[S]` — *cost / UI.* Trailing-7d RPM < cost is a business event; say it.
- [ ] 285. Metrics-before-next **"yesterday unsynced"** copy `[S]` — *viability / UI.*
- [ ] 286. **Uploads-left in booth header** `[S]` — *cost / UI.* Same figure as the tray chip.
- [ ] 287. **ElevenLabs chars in booth header** `[S]` — *cost / UI.*
- [ ] 288. Remaining Apify actors as **pills** (`tiktok_trends`, `youtube_competitors`) `[S]` — *cost / UI.* Never imply reddit/twitter still bill.
- [ ] 289. Last-run **signal-health dots** `[S]` — *UI.* Discovery health without opening the spinner replay.
- [ ] 290. **Feed-stale strip** `[S]` — *UI.* Rot that used to hide for a month.
- [x] 291. Set Windows **AppUserModelID** *(2026-08-21)* — toasts group as "Content OS" (`ContentOS.Operator`) `[S]` — *new-app.*
- [ ] 292. **Mute toasts during quiet hours** `[S]` — *UI.* Read `channels.json` blackout if present; do not implement #116.
- [ ] 293. Prototype **`content-os://open-last`** protocol `[S]` — *new-app.* One verb; hours, not a plugin platform (#155).
- [ ] 294. Explorer **"Send to" facts.txt** `[S]` — *UI.* Windows send-to shortcut; overnight facts-file gap stays a pipeline issue.
- [ ] 295. **2×2 contact sheet PNG** of last thumbs `[S]` — *aesthetics.* Pillow collage; no image API.
- [ ] 296. **Print stylesheet** for the contact sheet `[S]` — *aesthetics.*
- [ ] 297. Caption fill **contrast ratio number** vs sampled frame `[S]` — *aesthetics.* Hours version of auditor #185.
- [ ] 298. YouTube-title **100-char meter** `[S]` — *UI.* Truncation rehearsal in the booth.
- [ ] 299. Description **first-line preview card** `[S]` — *UI / viability.* Search snippet chrome; not hashtag stuffing (#118 is the writer).
- [ ] 300. Local **tag chips** (edit in booth, apply writes the package) `[S]` — *UI.*
- [ ] 301. **Phone-bezel CSS** around the 9:16 player `[S]` — *aesthetics.* Review how a Short actually sits in a hand.
- [ ] 302. **YouTube chrome mock** (like/comment/subscribe) as an overlay `[S]` — *aesthetics.* Safe-area rehearsal distinct from #268's boxes.
- [ ] 303. Booth **theme toggle** (TapIn red vs MoneyWise green) `[S]` — *aesthetics.* Hours; packs #150 are weeks.
- [ ] 304. **Reduced-chroma** mode for OLED `[S]` — *aesthetics.* Accessibility + night reviewing.
- [ ] 305. **16px minimum type** on all HTML dumps `[S]` — *UI.* CLI font size is the current accessibility failure.
- [ ] 306. **Sticky cost bar** (TTS 91% always visible) `[S]` — *cost / UI.*
- [ ] 307. **Sticky quota bar** `[S]` — *cost / UI.*
- [ ] 308. Collapsible **raw trace JSON** `[S]` — *UI.* Debug without leaving the booth.
- [ ] 309. Collapsible **ffmpeg command** `[S]` — *UI.* Sync/intro bugs are command bugs.
- [ ] 310. **Copy ffmpeg command** `[S]` — *UI.*
- [ ] 311. Copy last **postmortem as markdown** `[S]` — *UI.*
- [ ] 312. Tray menu: **open last output folder** `[S]` — *new-app / UI.*
- [ ] 313. Tray action: **pause overnight** (flag file) `[S]` — *UI.* Does not change overnight code paths beyond an existing opt-in gate file.
- [ ] 314. Tray action: **run doctor → HTML** `[S]` — *UI.* Pairs with #198.
- [ ] 315. Tray: **last grade letter** `[S]` — *UI.*
- [ ] 316. Tray: **last domain** (UFC / GTA / NBA) `[S]` — *viability / UI.* RPM×cost by domain is useless if you cannot see what you just made.
- [ ] 317. Tray: **Free vs Standard** mode `[S]` — *cost / UI.* Run-70 class: lying readiness should be visible from the tray.
- [ ] 318. Remember **second-monitor bounds** `[S]` — *UI.* Booth on the 9:16 monitor.
- [x] 319. **"What's blocking publish"** *(2026-08-21)* — `ops blocking` one-sentence from existing gates `[S]` — *short-term / UI.*
- [ ] 320. Tray: **local git describe** when `ops` gains commands `[S]` — *UI.* Changelog awareness without opening GitHub.

---

## Completed

### Leave-the-terminal wave (2026-08-21)

- [x] **20 operator-visible pieces** — HTML dumps (`reliability` / `economics` / `doctor` / `status --html`), tray quota chip + AppUserModelID + breaker/ffmpeg toasts, lightbox, Explorer reveal (mp4 + thumb), MAX_PATH clip, FFmpeg file-lock retry, unlisted-before-public, blocking-publish sentence, script trim, trace redaction, pyw Start Menu shortcut, last-run booth, thin-facts abort screen, intelligence-report SKU. **#147 FastAPI skipped** (swapped for #240 + #254). No Phase M, no #141/#142.

### Phase 1 — Foundation

- [x] Discovery → content → optional render pipeline
- [x] OpenAI, TTS, FFmpeg vertical video, CLI

### Phase 2 — Database Layer

- [x] PostgreSQL + dual JSON repositories
- [x] `init_db`, `migrate_json`, `migrate_schema`

### Phase 3 — Efficiency & UI

- [x] Parallel signals/variants, cache, signal contract, health UI

### Phase 4 — Asset Management

- [x] Provider chain (local, Pexels, Pixabay), catalog, category detection
- [x] Postgres `assets` table + post-render recording
- [x] Pillow thumbnails per channel (`output/{channel}/thumbnails/`)

### Phases D–G (infrastructure)

- [x] **Upload:** OAuth, resumable `videos.insert`, idempotent `publish_log`, quota guard, job worker
- [x] **Signals:** `SignalRegistry` bootstrap, optional `USE_SIGNAL_SYNTHESIS`
- [x] **Scaling:** CI workflow, stuck-job reclaim, structured render logging
- [x] **Render:** Loop stock video to audio length, mute stock audio, 9:16 scale/crop

### Channel profiles

- [x] `channels.json`, weight overrides, asset order, OAuth token path, output subdirs
- [x] Interactive channel + upload prompts
- [x] TapIn profile with gaming weights + `output/tapin/`
- [x] Hybrid backgrounds (`background_mode`, `hybrid_local_ratio`, `assets/composite.py`)
- [x] Channel validation CLI + root-level asset/background fields

### Upload, scheduling, analytics (D–G continuation)

- [x] `py -m youtube.check_setup --channel tapin`
- [x] Optimal post scheduling, upload queue, YouTube `publishAt`
- [x] Publish idempotency hardening
- [x] Learn post slots from analytics (`learn_slots_from_analytics`)
- [x] Scheduled upload jobs: `scheduled_at` gate on worker claim
- [x] YouTube Analytics API + `py -m analytics.sync_metrics`
- [x] Learned weights (`apis/learned_weights.py`, `LEARNED_WEIGHT_BLEND`)

### Operator & research (pre–Phase H)

- [x] Operator batch CLI (`scripts/ops.py`)
- [x] Re-queue uploads (`scripts/requeue_upload.py`)
- [x] `ufc_context` + `tapology` signals; UFC `script_brief` + `content_engine` prompts
- [x] Docs: architecture, debugging, changelog

---

## Intelligence phase (H → K) — complete

*Principle: **generation before measurement**. Full spec: [intelligence_phase.md](intelligence_phase.md).*

### Prerequisites (before / with Phase H)

- [x] Alembic baseline + FKs (`content_run_id` on `publish_log`, `jobs`, `assets`, `thumbnail_scores`) — *shipped 2026-08-14, Alembic `0004`*
- [x] Provenance columns on `content_runs`: `brief_version`, `prompt_version`
- [~] Reddit OAuth + rate-limit-aware caching for agent workload — *signal retired 2026-08-14; the free OAuth backend (`apis/free_backends.fetch_reddit_free`) still exists and re-enabling only needs `REDDIT_CLIENT_ID`/`SECRET` + `enabled: true` in the catalog*
- [x] RSS feeds to reduce Tapology scrape dependency — *shipped 2026-08-14: Tapology
  retired (Cloudflare 403), all dead feeds replaced (37/37 live), `ops feeds` monitors*

### Phase H — Research Brief Engine (+ Reddit Agent + RSS) — **priority**

- [x] `core/research_brief.py` — typed `ResearchBrief`, built **once** after variant selection
- [x] `core/pipeline.py` hook; `content_engine` brief-first with signal-facts fallback
- [x] Reddit intelligence (`apis/reddit_intelligence.py`) — brief-only, cached
- [x] RSS headlines (`apis/rss_feeds.py`) — from `config/seo/{channel}.json`, brief-only
- [x] Brief/agent caching (topic + channel)
- [x] YouTube SEO: tags in content package + upload; `config/seo/`, `py -m analytics.seo_refresh`
- [x] Alembic baseline (`0001`–`0002`); provenance on `content_runs` via models + `migrate_schema`
- [x] Stats scrapers + `blog_rss` signal + `config/data_sources.json` — see [data-sources.md](data-sources.md)
- [x] Research brief v3 includes reference stat lines

### Phase I — Competitor Tracking

- [x] Config `config/competitors/{channel}.json` + `py -m analytics.competitor_sync`
- [x] Snapshot cache `data/competitors_{channel}.json` (quota-aware)
- [x] Daily sync: `py -m scripts.daily_sync` / `py -m scripts.ops daily-sync`
- [x] Auto-refresh on discovery if snapshot >24h (`COMPETITOR_SYNC_ON_DISCOVERY=auto`)
- [x] Feed discovery / brief / variants (`analytics/competitor_context.py`)

### Phase J — Minimal status view

- [x] `py -m scripts.ops status` / `py -m scripts.status`
- [x] Queue manager CLI + `py main.py` startup option 2 + upload option 5

### Queue operations

- [x] Re-queue after YouTube delete (`scripts.queue_manage`, `analytics.queue_manager`)
- [x] `publish_log` status `cancelled` + idempotency release for re-upload

### Phase K — Thumbnail generation (opportunistic)

- [x] Flux thumbnails in `assets/flux_thumbnail.py` + pipeline hook (`THUMBNAIL_MODE=auto|off`, `BFL_API_KEY`)
- [x] Live render progress (`core/render_progress.py`, `CONTENT_RENDER_PROGRESS=1`)
- [x] YouTube `thumbnails.set` after `videos.insert` (`youtube/thumbnails.py`, `YOUTUBE_THUMBNAIL_UPLOAD=auto|off`)
- [ ] Pillow remains fallback

### Phase L — Closed-loop recommenders (2026-06)

*All three share one pattern: `analytics` source when enough engagement history exists, sensible default otherwise, each with a rationale string.*

- [x] **Best Bet (topic)** — `core/best_bet.py`; `source="analytics"` path live once metrics sync working (engaged-rate by domain). **Confidence-weighted + diversified** (2026-06): empirical-Bayes domain shrinkage + adequately-sampled-domains-first ranking (`_adjusted_domain_rates`/`_domain_priority`), ≤1 pick per domain so thin 1-sample domains can't fill every slot, and measured-history domains count as on-brand (`_effective_allowed` — surfaces e.g. NBA on a gaming/UFC channel).
- [x] **Recommended post time** — `analytics/post_timing.py` (`get_recommended_time`); engagement bucketed by weekday/hour, domain-aware; surfaced in `main.py`, `auto_generate`, ops `recommend-time`
- [x] **Recommended length** — `core/length_recommender.py`; engaged-rate by length preset (uses `timings_json.length_preset`); `auto_generate --length auto`; ops `recommend-length`
- [x] YouTube Analytics sync hardened — validating probe query, clear "enable API"/scope guidance (`analytics/sync_metrics.py`)
- [ ] Backtest recommender accuracy vs. realised engagement once volume grows
- [x] Confidence thresholds / minimum-sample surfacing in the UI (`core/recommender_confidence.py`; low/moderate caveats on best-bet/post-time/length)

### Phase L2 — Apify data layer (2026-06)

*Catalog-driven external signals. Single source of truth: `config/apify_sources.json` (`apis/apify_catalog.py`).*

- [x] Apify client with key routing + local cache (`apis/apify_client.py`); `~`-form actor ids
- [x] `youtube_competitors` — top videos by **view velocity** (`apis/youtube_apify_signal.py`)
- [x] `twitter` — breaking news weighted by domain authority accounts (`apis/twitter_signal.py`)
- [x] `reddit`, `tiktok_trends` — community sentiment + viral angles
- [x] Per-domain targeting (`domain_targets`); fact formatting keeps competitor titles as context, not verified facts
- [x] Docs: [apify-data-sources.md](apify-data-sources.md)
- [x] `youtube_comments` — wired 2026-08-14 against the official Data API (not Apify)
- [ ] `instagram_figures` — still templated only; catalog `enabled: false`
- [x] Live-run tuning of actor inputs *(2026-08-14 — twitter retired; tiktok + youtube_competitors kept)*

### Phase L3 — Idea intake (2026-06)

- [x] `py main.py` menu **option 5** — generate from a user idea or a **YouTube link** (`watch`/`shorts`/`youtu.be`)
- [x] `apis/youtube_api.extract_youtube_video_id` + `fetch_video_metadata` (title/channel for the seed)
- [x] Shared `_run_new_video_flow(seed_topic=...)`; best-bet skipped when idea supplied
- [x] Tests: `tests/test_youtube_idea_intake.py`

### Engineering quality baseline (2026-06)

- [x] `pyproject.toml` — canonical deps + tool config; `[dev]` and `[sports]` extras
- [x] `ruff` lint + format across the tree (clean); `python-dotenv` replaces hand-rolled `.env` parser
- [x] CI: lint + format-check + type baseline + tests on Python 3.10/3.11/3.12
- [x] `.pre-commit-config.yaml`; `.gitignore` covers tool caches
- [x] `youtube.readonly` scope added for publisher dup-check / OAuth reads
- [ ] **git remote** — repo initialised locally; create **private** GitHub remote and push
- [x] **`CLAUDE.md`** — project guide for AI coding agents (pipeline overview, `ops`/`main.py` entry points, signal architecture, LLM router tiers, test/lint commands, hard rules). Companion: [docs/claude_code_usage.md](claude_code_usage.md) (Claude Code modes/features specific to this repo).
- [ ] Tighten the mypy baseline (~94 errors → fix the real ones, e.g. `timings` value type)
- [ ] Annotate/retire the remaining best-effort broad `except Exception` handlers
- [ ] Raise test coverage on render + publish paths

---

## Recently shipped (2026-06)

All on branch `youtube-readonly-scope-and-roadmap` (PR #1), CI green:

- **Recommenders + analytics loop live** — best-bet (now **3 rotating options**), recommended length, recommended post-time; analytics sync (most-recent-3 with titles).
- **Phase O — authenticity/compliance**: pre-upload self-check, AI disclosure, cadence guardrail, competitor-outlier surface, monetisation CTAs.
- **Phase P — hook intelligence**: 0–100 hook scorer + opt-in regeneration.
- **Phase Q — captions**: proportional, sentence-aware timing.
- **Idea intake (option 5)** with cross-genre creative-brief threading.
- **MoneyWise finance channel** (2nd channel) + `infer_domain` word-boundary fix.
- **Apify hardening**: `set_cache` credit-burn fix, 201 handling, circuit breaker + preflight on/off check, per-variant signal reuse (discovery minutes → seconds).
- **Script prompt refinement**: recap-first VOICE block, filler ban-list, anti-padding Extended format.
- **Engineering baseline**: pyproject/ruff/mypy/pre-commit, CI on 3.11, 220 tests.
- **Brand kit** for MoneyWise (`assets/branding/moneywise/`).
- **Assessment**: `docs/assessment.md` (strengths/weaknesses/fixes).

---

## Next — current focus

*Prioritised fix queue, top first. `[S]`/`[M]`/`[L]` = effort.*

**Immediate (from live runs):** *(mostly shipped — see recency cycle + script-accuracy PR)*
1. ~~Manual fact feeding~~ — key facts + vault + `paste` block + char budget (`core/operator_facts.py`)
2. ~~Domain-aware signal gating~~ — shipped
3. ~~Auto-disable on credit/quota~~ — shipped (+ persisted Apify, LLM router)
4. ~~Live discovery feedback~~ — shipped

**Current focus (2026-07):** *(wave shipped 2026-07-02 — see below)*
1. ~~Fact-first generation pipeline~~ — shipped (angles at discovery, title after facts + script)
2. ~~O10 reset-window auto-re-enable~~ — shipped (`core/reset_window.py`; [credit_efficiency.md](credit_efficiency.md) O10)
3. ~~Semantic trade validation~~ — shipped opt-in (`core/trade_validation.py`, `SEMANTIC_TRADE_VALIDATION`)
4. ~~Creator coach surface (Phase S)~~ — shipped (`core/creator_coach.py`, `ops coach`; weekly digest gained "Next actions")

**Up next:** the **internal-systems pillars** below — **Pillar 1 (Run Ledger)** first: per-run trace + quality persistence + `ops traces`/`dossier` viewers (absorbs Phase T observability + Phase V data-quality; carries Phase U unit economics). Pillar 2's calibration and Pillar 5's agents are data-gated behind publish volume. All pillar work is proposed — implementation held for operator review. *Note: CTR-based thumbnail attribution is externally blocked — YouTube's public Analytics API does not expose impressions/CTR (Studio-only); the thumbnail lever attributes engaged-rate until Google ships the metric.* *(Shipped 2026-07-06: **O11 complete** — Apify + LLM router persistence migrated behind `core/quota_governor.py` + unified `snapshot()` ([credit_efficiency.md](credit_efficiency.md) O1–O11 all ✅); earlier same day: signal-breaker persistence + key-hash invalidation (the O11 seed), batch generation `ops batch-drafts`, script-lever A/B `ops experiment`, thumbnail A/B via `thumbnail_style`, webhook events out.)*

➡ One-time: re-auth `youtube.readonly` (`py -m youtube.oauth_setup --channel tapin`) to activate the dup-upload check. MoneyWise needs its own `oauth_setup`.

---

## Market positioning (2026)

*From a scan of the short-form / creator-tooling market (OpusClip, AutoShorts, Revid, Higgsfield, vidIQ, TubeBuddy) and YouTube policy. Deeper tool-by-tool teardown (17 repos/guides, borrow/threat verdicts mapped to modules): [tooling_landscape.md](tooling_landscape.md).*

**The defining shift — authenticity enforcement.** YouTube's "inauthentic content" policy (Jul 2025) plus the **Jan 2026 mass-termination wave** demonetised templated, synthetic-voiceover, volume-over-substance faceless channels. *Faceless is still fine — synthetic-and-shallow is not.* What survives: **original insight, real variation between videos, human context, substance over volume.** That is an existential constraint for a generation-first pipeline and reorders our priorities (Phase O).

**Where rivals are strong (our gaps):**

| Capability | Who has it | Us today |
|---|---|---|
| Virality / hook score 0–100, hold-rate prediction | OpusClip, Higgsfield | composite topic score only — no hook/retention predictor |
| Hook-first generation (first 3 s / 60 frames) | most 2026 tools | generic hook rule in the prompt |
| Burned animated captions, speaker reframe | effectively all | not burning captions (table stakes) |
| A/B testing title/thumb/desc → CTR/watch-time | TubeBuddy | generate variants, but no post-publish A/B loop |
| "Daily ideas" coach | vidIQ | best-bet (close — expand into a coach) |
| Clip-from-long-form (VOD / podcast → shorts) | OpusClip core | generation-only; idea-intake already accepts YT links |

**Our moat (lean in):** no competitor runs the **full closed loop** — decide → *research with verified facts* → generate → publish → learn — self-hosted, on an anti-hallucination / intelligence-report spine. vidIQ decides, TubeBuddy optimises, OpusClip clips; we do all three plus a sourcing layer they lack. Double down on **verifiable substance + the analytics learning loop**.

---

## Candidate phases — 2026 roadmap expansion (proposed)

*Brainstorm, market-grounded. Ordering reflects risk/impact, not commitment.*

### Phase O — Authenticity & monetisation safety  *(highest priority — existential)*
Turn the research spine into a compliance moat.
- [x] **Pre-upload authenticity self-check** — `core/authenticity.py`: variation / original-insight / substance score + checklist; `AUTHENTICITY_GATE=block` to enforce.
- [x] **Per-video variation guard** — shipped as the authenticity "variation" check (difflib vs recent uploads' script_preview). Content-word cosine paraphrase arm added 2026-08-20 (`AUTHENTICITY_SEMANTIC`, default-on, warn-never-block).
- [x] **AI-content disclosure** — `core/description_extras.py`: in-description disclosure on every upload (YouTube's #1 compliance "do"); `AI_DISCLOSURE_ENABLED`, per-channel `ai_disclosure`.
- [x] **Cadence guardrail** — `core/cadence.py`: caps videos/rolling-week (recent + scheduled); `MAX_VIDEOS_PER_WEEK` (default 5); gates `auto_generate` (`--force` to override). Pairs with the variation check (variety + volume).
- [x] **Original-insight injection** — when a script reads as a neutral recap, inject one opinion/prediction/"why it matters" beat grounded only in verified facts (`content_engine._maybe_inject_insight`, `core/authenticity.has_insight`, `INSIGHT_INJECTION_ENABLED`). Runs before the grounding regen; default-on; no-op when a take already exists. Prompt also gained a detector-aligned STANCE bullet.
- [x] **Human-context layer** — per-channel persona (voice/tone/audience/recurring-segment/sign-off via `channels.json` "persona") + data-driven continuity callbacks to recent coverage, injected into the script prompt (`core/channel_persona.human_context_block`). Bounded so it can't override grounding; "" when unconfigured + thin history.
- [x] **Voice variety** — *shipped:* per-channel local voice + pool rotation
  (`core/tts.resolve_local_voice`, config-driven `config/voices.json`) + optional
  run-seeded delivery jitter (`TTS_VOICE_VARIETY`); real-voice **clone** slot via XTTS
  and the new **Qwen3-TTS** provider (`local.qwen[]`, GPU voice cloning, metered $0).

**From 2026 market research (shipped 2026-06):**
- [x] **Competitor "outlier" surface** — `core/outlier.py`: top view-velocity competitor video shown as a content prompt (every guide says "study over-performing competitors first").
- [x] **Alt-monetisation CTAs** — per-channel `monetization_cta` lines appended to descriptions (gaming/UFC is low-CPM; ad revenue alone underperforms).
- [ ] **Multi-language** — single script → translated script + localized TTS → per-language uploads. Real growth lever, **low priority** for the gaming/UFC niche; pairs with Phase Q captions. *(deferred — see Later horizons.)*

### Phase P — Hook & retention intelligence
- [x] **Hook-score 0–100** — `core/hook_score.py`: heuristic scorer (brevity, specificity, curiosity/contradiction, stakes; penalises weak openers) surfaced in the pipeline + auto_generate.
- [x] **Hook-first regeneration** — opt-in `HOOK_REGEN_ENABLED`: rewrites a weak opening line via the LLM, only swapping it in if it scores higher.
- [x] **Retention-curve modelling** — syncs the per-position audience-retention curve (`audienceWatchRatio` by `elapsedVideoTimeRatio`, stored on publish_log metrics) and aggregates it into a channel drop-off point (`core/retention.py`), confidence-gated (≥`RETENTION_MIN_VIDEOS`). Feeds the script prompt's pacing pivot (front-load before the measured cliff) + `ops retention` view. Activates as curves accrue.
- [x] **A/B variant loop** (single-channel attribution form) — a faceless channel can't double-publish without cannibalizing, so instead of head-to-head it attributes realized engagement to the published title's **structural pattern** (`core/title_features`), builds a per-channel pattern leaderboard (`core/title_experiments`, `scripts.ops title-patterns`), and surfaces "▲ proven pattern" on matching variants at selection time. Thumbnail A/B (true two-up) still open.
- [x] **Script-lever A/B experiments** — *shipped 2026-07-06:* controlled one-lever-at-a-time experiments (`core/experiments.py` lifecycle + `core/experiment_levers.py` arms: `hook_style`, `cta_style` + `core/experiment_stats.py` low-n-safe Bayesian winner detection). `py -m core.experiments start hook_style` → every batch draft gets the least-used arm's prompt directive, assignments persist in `data/experiments.json`, and `ops experiment` joins them to realized engaged-rates: "collecting" until ≥6 measured per arm, winner only at P(best) ≥ 95%. Fed by `ops batch-drafts` (volume-with-variation). Tests: `tests/test_experiments.py`.

### Phase Q — Captions & visual polish  *(table stakes)*
- [x] **Burned captions, properly timed** — `video/subtitles.py`: sentence-aware, tighter chunks (`CAPTION_WORDS_PER_LINE`, default 5), durations **proportional to word count** (was uniform 8-word lines). Already burned in the render command.
- [x] **Word-level animated captions** — real per-word timing from ElevenLabs `convert_with_timestamps` (no Whisper); `video/caption_timing.py` builds accurate SRT + karaoke-highlight ASS. `CAPTION_STYLE=word` (default, accurate SRT) / `karaoke` (animated, opt-in — verify with a render) / `plain`. Burned via the existing `subtitles` filter.
- [x] **Scene-matched b-roll** — `video/scene_plan.py` splits the script into timed beats (real word timings when available), one stock clip per beat concatenated (`assets/composite.build_multi_concat_command`). Opt-in `SCENE_MATCHED_BROLL`, fails safe to the normal background.
- [x] **Dynamic emphasis** — keyword pop (karaoke caption highlight) + beat-synced cuts (scene-matched b-roll) shipped; hook zoom-in remains an optional flourish.

### Phase R — Clip-from-source mode  *(market hedge)*
*The market's "real content" pivot; pairs with idea-intake, which already accepts YouTube links.*
- [ ] Ingest a long video / VOD / podcast (file or URL) → transcribe → find strong moments → cut vertical shorts with captions.
- [ ] Reuse the scoring / hook / caption stack from Phases P–Q.

### Phase S — Creator coach surface
- [x] Expand best-bet into a **"daily ideas + why"** coach view (vidIQ-style, but with our sourcing) — `core/creator_coach.py`, `py -m scripts.ops coach`: ranked ideas each with a *why*, plus recommended length/post-time, winning title patterns, retention pacing, and cadence headroom. Read-only + fail-open. *(2026-07-02)*
- [x] **Thumbnail A/B** — *shipped 2026-07-06 on the experiment harness:* `py -m core.experiments start thumbnail_style` → each Flux render appends the least-used arm's composition directive (`close_up` vs `wide_drama`, `core/experiment_levers.py` kind="thumbnail") to the prompt in `assets/flux_thumbnail.py`; the assignment is recorded only when Flux actually generated (Pillow fallbacks never pollute attribution), and `ops experiment` runs the same low-n-safe Bayesian report against realized engaged-rate. *CTR optimisation still open — needs impressions/CTR in the metrics sync before the report can attribute clicks rather than engagement.*
- [x] Weekly performance digest with concrete next actions — `analytics/weekly_report.build_next_actions`: the winners/losers per dimension become numbered operator instructions ("Lead with the 'fraud' angle again", "Retire the 'recap' angle"), noise-gated at ±3pp vs baseline. *(2026-07-02)*

### UI / experience — themeable skins  *(fun, on-brand)* — **shipped 2026-07-02**
*Builds on the existing braille ASCII art, `DiscoverySpinner`, and `print_domain_art`.*
- [x] **`CONTENT_UI_THEME=onepiece|zelda|pokemon|dbz|jjba|plain|default`** (`core/themes.py`) — each skin swaps the ANSI palette (16-color + auto-detected 256-color via `CONTENT_UI_COLOR_DEPTH`), spinner frames + themed loading copy, section glyphs, meter characters, startup tagline + inline mascot panel, publish celebration art, and a ≥90-score hype tag.
  - **Zelda** — ▲ spinner + glyphs, **heart-container meters** (❤❤♡♡♡ cadence/quota), "YOU GOT THE RENDERED VIDEO" item-get celebration, *SECRET FOUND* score tag.
  - **Pokémon** — Pokéball spinner (◓◑◒◐), "type advantage" loading copy, level-up celebration, *SUPER EFFECTIVE* score tag.
  - **DBZ** — ki-charge spinner, Scouter loading copy, **"IT'S OVER 9000!"** on composite ≥ 90, over-9000 celebration.
  - **JJBA** — ゴゴゴ menacing spinner + mascot, "ORA ORA scoring variants", **"TO BE CONTINUED ➡"** publish celebration, *MUDA MUDA* score tag.
- [x] Theme registry with per-channel skin via `"ui_theme"` in `channels.json` (env overrides); `plain` keeps logs/CI color- and art-free. Meters + milestones (`maybe_print_milestone`) + themed celebrations wired into main flow, cadence, `ops reliability`, and `ops coach`. Sections/banners now span the full terminal width (capped at 100 cols). Tests: `tests/test_themes.py`.

### Efficiency & integrations
> **Credit/quota/spend optimization backlog:** [credit_efficiency.md](credit_efficiency.md) — Apify preflight skip, cross-run breaker persistence, operator budgets, LLM provider failover, reliability dashboard, unified quota governor (O1–O11).
- [x] **Whisper** locally for caption timing — CPU `faster_whisper` + caption retext (2026-08-14/16). Clip-from-source transcription still sits with Phase R.
- [x] **Cost / quota dashboard** — shipped as `ops reliability` (O9) + O12.
- [x] **Multi-provider LLM router** (`core/llm_router.py`) — task-tier routing (cheap/extract/premium) across **DeepSeek, OpenRouter, Ollama (local), OpenAI, Anthropic** (Groq wired but not default — signup gated; Doubao wired but skipped — China-region-locked, ~$0 savings); OpenAI-compatible client shape + native Claude. Free-first defaults (**OpenRouter** free `:free` models anchor cheap, Ollama local fallback; **DeepSeek-V3** anchors extract+premium ≈ gpt-4o quality, ~10× cheaper), env-overridable per tier + per-provider `{PROVIDER}_MODEL_<TIER>`, graceful degradation, loads `.env` standalone. Consolidated the 3 ad-hoc Claude call sites + migrated content_engine / research_brief / fact_enrichment / topic_variants / background_query / local_provider. Real **per-provider token ledger** prices `cost_meter` (free `:free`/Ollama = $0). (`DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_MODEL`.)
- [x] **Local-LLM option (Ollama)** — folded into the router as the `ollama` provider (OpenAI-compatible, `OLLAMA_MODEL` + optional `OLLAMA_BASE_URL`); zero marginal cost in the ledger.
- [x] **Router follow-ups** — thumbnail vision scorer now uses `llm_router.complete` with image content-blocks (2026-08-20). `core/llm_client.py` deleted. Failover + per-provider spend already shipped as O5/O6 + O12. Pillar 2 rendered-video review is still later.
- [x] **Free in-process signal backends (Option 3)** — *spike done 2026-06-29; YouTube backend shipped 2026-07-01:* `apis/free_backends.py` (hybrid `yt-dlp` flat-rank → full-extract top-N) behind `SIGNAL_BACKEND=apify|free|auto` (default `apify` — unchanged behavior; `free` = keyless/zero-cost; `auto` = free-first with Apify fallback). Cost meter no longer bills a free-served `youtube_competitors` as an Apify run. *Reddit OAuth free backend shipped 2026-07-06* (`fetch_reddit_free`, official API via free script app — Reddit keyless *scraping* is 403-blocked; 429s feed the rate-limit cooldown). Twitter/TikTok stay Apify. Tests: `tests/test_free_backends.py`. Full write-up: [agent_reach_evaluation.md](agent_reach_evaluation.md).
- [x] **Per-platform rate-limit cooldown** — *shipped 2026-07-01:* free backends fail by 429 (rate-limit), not 402 (credit). Session breaker (`apis/register_signals.py`) now gives transient 429s a *disabled-until-T* cooldown (`SIGNAL_RATE_LIMIT_COOLDOWN_SECONDS`, default 15 min, 0 = off) instead of ignoring them; hard statuses still trip permanently, and `SIGNAL_BREAKER_INCLUDE_RATE_LIMIT=true` still promotes 429s to a full-session trip. "Next available" surfaces in `ops reliability` and the post-discovery signal-health panel (`youtube_competitors → 14:32`). Tests in `tests/test_circuit_breaker.py`.
- [x] **Script-accuracy follow-ups (2026-07-01)** — Apify 403 vs 402 messaging + shorter auth-failure TTL; `MAX_OPERATOR_KEY_FACTS` env cap; pipeline-end `finalize_run_observability()` for cache stats; `auto_generate` mirrors fact-grounding gate.
- [x] **Fact-first pipeline (2026-07-02)** — `core/operator_facts.py` (paste block, vault save-all, char budget); discovery → **angles** not titles; `core/title_generator.py` runs after facts + script; anti-slop title rules.
- [x] **O10 reset-window auto-re-enable (2026-07-02)** — `core/reset_window.py` encodes real reset cadences (YouTube daily 00:00 PT, Apify monthly `APIFY_RESET_DAY`, Odds monthly). Apify 402/monthly-limit exhaustion persists until the cycle reset (auth keeps 30m TTL, budget keeps flat TTL); quota-blocked YouTube uploads retry just after the real reset; reset times in `ops reliability`. `RESET_WINDOW_AUTO_ENABLE` master switch. Tests: `tests/test_reset_window.py`.
- [x] **Semantic trade validation (2026-07-02, opt-in)** — `core/trade_validation.py`: extracts `player → team` trade claims from the script and warns when the pair never co-occurs on a single fact line (catches fused trades token grounding passes, e.g. real Giannis→Heat + invented Butler→Celtics). `SEMANTIC_TRADE_VALIDATION`: unset ⇒ **default-on for NBA/NFL topics** (domain-gated, 2026-07-26; UFC excluded — `signed` would false-positive), set `true`/`false` to force globally; warns after the Fact-grounding section in `main.py`/`auto_generate`, never blocks. Tests: `tests/test_trade_validation.py`.
- [x] **Headless key facts for `auto_generate` (2026-07-02)** — `--facts-file` (same parser as interactive `paste` mode — trade blocks work) + repeatable `--fact` lines; deduped/tip-filtered, saved in full to the vault, injected as ground truth, and echoed in the grounding report. Tests: `tests/test_auto_generate_facts.py`.
- [x] **Webhook / n8n / Zapier out** — *shipped 2026-07-06:* `core/events.py` POSTs `{"event", "at", "payload"}` to `EVENT_WEBHOOK_URL` on `run_completed` (every pipeline finalize), `video_published` (YouTube upload/schedule success, includes video URL), and `batch_completed` (`ops batch-drafts` summary). Fire-and-forget on a daemon thread — a dead webhook can never stall a run; `EVENT_WEBHOOK_EVENTS` csv filters types. Pairs with a free self-hosted n8n for Discord pings, cross-posting, spreadsheets. Tests: `tests/test_events.py`.
- [x] **Batch generation** — *shipped 2026-07-06:* `py -m scripts.ops batch-drafts --channel tapin --count 3` (or `py -m core.batch_generation` with explicit topics / `--file ideas.txt`). N ideas → N draft scripts unattended: discovery → best variant → recommended length → script/title/description saved to `output/<ch>/drafts/<ts>-<slug>/` (`draft.md` + `meta.json` with hook score, authenticity verdict, grounding flags, cost). Render-free by design — no TTS spend, no cadence impact; feeds A/B + volume-with-variation. Tests: `tests/test_batch_generation.py`.
- [ ] **Observability** — structured run traces + timing dashboard (timings already captured). *(promoted into **Pillar 1 — Run Ledger** below.)*

---

## Internal-systems pillars — 2026-H2 (proposed 2026-07-06 — reorientation)

*Replaces the former "Candidate phases — 2026-H2 expansion" (Phases T–W). Three deep
code audits (fact/Obsidian layer, metadata/storage, grading/scoring) converged on one
finding: **the system writes down far more than it reads back, and no pre-publish
score is calibrated against outcomes** (decisions §15). The forward roadmap is now
organized around five internal systems instead of feature phases: Phases T + V fold
into Pillar 1, the open thumbnail-calibration + prompt-eval work into Pillar 2,
Phase W into Pillar 5; Phase U keeps its scope inside Pillar 1's ledger work.
Dependency order is explicit — **Pillar 1 first** (everything downstream keys off
it); Pillar 2's calibration stages and Pillar 5's agents are **data-gated** behind
publish volume. Still YouTube-native or platform-free — no Instagram/TikTok platform
linking (Phase M stays deferred), no Benable work (parked). **All items below are
proposed / not started — implementation held for operator review.***

### Pillar 1 — Run Ledger (metadata spine)  *(do first — absorbs Phases T + V; carries U)*
*Audit: most run metadata is write-only — the LLM call ledger is in-process and lost
after every run, `signals_json`/`variants_json` have no readers, experiment arms live
in a sidecar file, hook/authenticity scores aren't persisted at all (batch `meta.json`
only), and `finalize_run_observability()` today only flushes aggregate cache counters.*
*Shipped 2026-07-06 (same-day wave after the reorientation was approved):*
- [x] **Per-run trace** — `core/run_trace.py`: one JSON per run in `data/traces/<run_id>.json`,
  written fail-open from `_finalize_run`: phase timings, per-signal status, the priced
  LLM call ledger (`llm_router.get_usage()`), post-discovery cache counters
  (`cache_manager.session_cache_stats()`), experiment arm, quality dict. *(was Phase T)*
- [x] **Quality persistence** — `quality_json` on `content_runs` (models +
  `migrate_schema` + Alembic `0003`), built by `core/run_quality.py` in `_finalize_run`
  (hook score/verdict, authenticity score/verdict, ungrounded count, trade warnings)
  for **every** path — interactive, headless, batch; thumbnail overall merged
  post-render (`merge_quality`).
- [x] **Viewers** — `ops traces` (recent runs, slowest-phase hotspots, LLM cost,
  quality) + `ops dossier --run-id N` (run + features + quality + cost + publish
  metrics + experiment arm + trace) in `core/run_ledger.py`.
- [x] **Data-quality monitor** — `core/data_quality.py`: per-signal failure rates +
  consecutive not-ok streaks over recent traces, run↔quality/features/metrics join
  assertions; warnings surface in `ops reliability` + `py -m core.data_quality`.
  *(was Phase V)*
- [x] **Unit-economics ledger** — fail-open `estimatedRevenue` fetch in the metrics
  sync (own query — needs monetized channel + `yt-analytics-monetary` scope, never
  breaks the main sync) joined to `features_json.cost.total` in
  `core/unit_economics.py`; `ops economics` + margin lines in `weekly-report`;
  dossier shows per-video margin. *(Phase U)*
- Tests: `tests/test_run_ledger.py` (23) + pipeline tests isolate the ledger writes
  (see `tests/CLAUDE.md`).

### Pillar 2 — Video Grading System
*Audit: six scorers exist (composite topic, hook, authenticity, grounding, trade,
opt-in thumbnail) but nothing rolls them up; pre-publish scores are printed and
discarded in the interactive flow; `thumbnail_scores` has carried "CTR correlation
later" since Alembic `0002` with no reader; and the only backtest
(`core/analyst_accuracy.py`) uses views while the learning loop optimizes
engaged-rate.*
*Shipped 2026-07-06 (calibration/prediction stages are structurally live and
data-gated — they activate as measured volume accrues):*
- [x] **Pre-publish report card** — `core/video_grade.py`: weighted rollup of the
  Pillar-1-persisted scores (hook/authenticity/grounding/topic/thumbnail; missing
  components renormalize) → 0–100 + letter; shown before the render prompt in
  `main.py` + `ops grade --run-id N`.
- [x] **Predicted engaged-rate** *(data-gated)* — `core/engagement_predictor.py`:
  channel baseline + least-squares hook/authenticity adjustments over measured runs
  with quality; gated at `PREDICTOR_MIN_SAMPLES` (default 15); frozen into
  `quality_json.predicted_engaged_rate` at generation time so calibration can score
  it later; surfaces on the report card with an explainable note.
- [x] **Calibration loop** *(data-gated)* — `core/grade_calibration.py`: realized
  engaged-rate percentile per graded run, grade↔engagement Pearson r (the "is the
  report card meaningful?" number), prediction column, and the long-promised
  `thumbnail_scores` → engaged-rate join; `ops calibration` + one weekly-report
  line. `core/analyst_accuracy.py` realigned: backtests **engaged-rate** when ≥5
  runs carry it (views only as legacy fallback, labeled).
- [x] **Prompt-evolution eval set** — `core/prompt_evals.py` +
  `config/prompt_evals.json` (frozen golden topics + facts per channel, rubric v1:
  hook, ungrounded-vs-frozen-facts, length fit, filler count); `run` generates with
  live prompts and saves tagged with `prompt_version`, `compare` diffs the last two;
  `ops prompt-eval [--compare]`.
- [ ] **Multimodal rendered-video review** `[L]` *(later)* — sampled frames +
  transcript → LLM rubric (pacing, caption readability, visual interest); the
  router vision path shipped 2026-08-20 (supporting track).
- Tests: `tests/test_video_grade.py` (18).

### Pillar 3 — Fact Engine 2.0
*Audit: today's checker is a prompt-layer fact assembler + string-presence linter —
`find_ungrounded_entities()` passes any claim whose tokens appear anywhere in the
corpus, nothing is verified against a source, facts carry no provenance or TTL, and
operator paste / web snippets / YouTube descriptions share one undifferentiated
grounding corpus.*
*Shipped 2026-07-06 (decisions §16). All layers fail-open; verifier is the only new
LLM call (one extract-tier call per script).*
- [x] **Structured fact store** — `core/fact_store.py`: `FactRecord`
  `{claim, tier, source_url, verified_at, expires}` parsed from vault note
  frontmatter (no new DB — decisions §16a); `load_fact_records()` in
  `obsidian_facts.py` drops expired notes and ranks by topic overlap first, then
  provenance tier + freshness (rank bonus capped below one overlap token);
  `load_facts()` keeps its `list[str]` contract. Writers stamp frontmatter:
  operator capture → `tier: operator` + `verified_at`, source capture → `tier: link`.
- [x] **Tiered grounding corpus** — `core/grounding_tiers.py`:
  `build_tiered_corpus()` tags every corpus line
  `operator|link|web|signal|brief|context` (`full_text` stays byte-identical to the
  legacy corpus so `find_ungrounded_entities()` is unchanged); YouTube
  titles/descriptions are **context** (topic evidence, not facts) — entities that
  only ground there get a "treat as unverified" warning; high-stakes sentences
  (results/trades/records/champion) backed only by web/brief tiers warn.
- [x] **Claim-level LLM verifier** — `core/claim_verifier.py`:
  `verify_claims(script, facts)` on the extract tier → per-claim
  `{claim, supported, citation_line}`; default-on (`CLAIM_VERIFIER_ENABLED=false`
  to opt out), fail-open on LLM/parse errors; `GROUNDING_GATE=warn|block` mirrors
  the authenticity gate in both interactive (`main.py`, override prompt) and
  headless (`auto_generate`, `--force`) flows. Generalizes trade validation
  (decisions §13c) to all claim types.
- [x] **Contradiction detection pre-script** — `core/fact_conflicts.py`: rule-based
  trade-direction / reversed-result / champion conflicts between operator key facts
  and the signal+web corpus, detected **before** the LLM call; operator wins — the
  conflicting source lines are dropped from the corpus (`FACT_CONFLICT_FILTER=false`
  to keep them; conflicts always reported either way).
- [x] **Quick wins (partial)** — `capture_web_sources()` writes `web_search` result
  URLs to `_sources.md` (they re-rank as `link` tier on future related topics);
  all Fact Engine outputs persist into `quality_json` **v2**
  (`claim_support_rate`, `unsupported_claim_count`, `fact_conflict_count`,
  `tier_warning_count`) and penalize the report card's grounding component;
  dossier + batch summary surface them.
- [x] **Promote `SEMANTIC_TRADE_VALIDATION` default-on** `[S]` — domain-gated: auto-on for NBA/NFL topics, off elsewhere (UFC excluded); env override preserved
  once precision is confirmed in live runs (co-occurrence false-positive risk).
- Tests: `tests/test_fact_store.py` (23), `tests/test_grounding_tiers.py` (14),
  `tests/test_claim_verifier.py` (12), `tests/test_fact_conflicts.py` (18) +
  quality/grade/pipeline/source-capture coverage in the existing suites.

### Pillar 4 — Obsidian knowledge OS
*Audit: the vault is a one-way sidecar — read via token overlap with a full `rglob`
scan per call, written as exactly three file patterns (`_operator_facts/`,
`_sources.md`, `_machine-beliefs.md`); runs, scripts, and outcomes never land back in
it. Target: the vault as the human-readable mirror of machine state (vision.md §7's
"two faces").*
*Shipped 2026-07-07 (decisions §17b). Dossiers are records, not facts — they never
feed back into grounding.*
- [x] **Run dossiers into the vault** — `core/vault_dossiers.py`:
  `{channel}/_runs/{date}_{slug}-{id}.md` (topic, angle, grade, quality summary,
  cost, script + post-sync actuals/video URL) written fail-open from
  `_finalize_run` and re-upserted by `refresh_dossiers()` (wired into `daily_sync`
  + `ops vault-sync`). Weekly report lands in `{channel}/_reports/{date}_weekly.md`.
  Dossiers live under `_runs/`/`_reports/` and are excluded from `load_facts`
  (`_is_machine_record`) — records, not facts.
- [x] **Vault index** — `core/vault_index.py`: per-process, mtime-invalidated parse
  cache behind `obsidian_facts.load_fact_records()`; an unchanged note is `stat()`ed
  but never re-read (batch-drafts calls `load_facts` once per idea). Byte-identical
  parsing → ranking/filtering unchanged; no on-disk index (no `data/` growth).
- [x] **Playbook layer** — `obsidian_facts.load_playbook()` / `playbook_block()`:
  reads exactly the strategy/belief bullets `load_facts` drops and injects a bounded,
  clearly-non-factual "CHANNEL PLAYBOOK" block into the script prompt (beside the
  persona block; `""` when the vault is unset). Also fixed `_is_strategy_note` tag
  parsing (`[strategy]` bracket form was only excluded via its bullets before).
- [x] **Structured fact templates** — *(landed with Pillar 3)* writers stamp
  `tier`/`verified_at` frontmatter (`operator_facts.py`, `source_capture.py`) and
  `core/fact_store.note_metadata()` reads `tier`/`verified_at`/`expires`/`source`
  from any hand-written note — add those keys to a note and TTL/provenance apply.
- Tests: `tests/test_vault_pillar4.py` (12) + pipeline smoke isolates vault writes;
  `tests/test_obsidian_facts.py` unchanged (index is byte-identical parse).

### Pillar 5 — Agent layer  *(composes Pillars 1–4; absorbs Phase W)* — **shipped 2026-07-07**
*Only worth building once the pillars give agents trustworthy data to reason over —
autonomy is earned, not flipped on (vision.md §6). All three read-only + fail-open.*
- [x] **Channel Health Agent** — `core/channel_health.py`: composite per-channel
  Green/Yellow/Red over six rules-based sub-scores (engagement trend, cadence
  headroom, authenticity trend, reliability breakers, cost/margin, data-quality)
  each with a rationale string; folds worst-first, **thin data reads yellow, never
  green**. `ops health` + a line in `ops daily-brief`. *(was Phase W)*
- [x] **Verifier agent** — *(landed with Pillar 3)* the claim verifier runs inside
  `generate_content_package` for every path (interactive, headless, batch, prompt
  evals) with `GROUNDING_GATE` enforcement in both operator flows.
- [x] **Weekly analyst agent** — `core/analyst_agent.py`: bounds a context (weekly
  report + calibration + health + recent traces + economics) → **premium** LLM tier
  → prose briefing with 3–5 lever changes; writes `{channel}/_reports/{date}_analyst.md`
  (Pillar 4) + emits `analyst_briefing` webhook. Fail-open to the weekly report's
  rules-based next-actions on any LLM error. `ops analyst`.
- [x] **Overnight operator** — `core/overnight.py`: best-bet topics → `batch-drafts`
  (graded + verified, render-free ⇒ cadence-safe) → vault dossiers → health snapshot
  → `overnight_completed` webhook. `ops overnight --channel tapin --count 3`
  (`--file topics.txt`); schedulable like `daily_sync`. *(facts-file intake is a
  follow-up — needs `batch_generation.generate_draft` to accept key facts.)*
- Tests: `tests/test_pillar5_agents.py` (health folding + fail-open + cp1252,
  analyst LLM/rules-fallback, overnight chaining).

### Pillar 6 — Video Creation Provider Layer  *(2026-07-07 — overrides §8, decisions §17)*
*The operator reversed operating_plan §8's "keep generation boring" default:
generation quality is now a competitive lever. Full tool list + build order:
**[video_creation_stack.md](video_creation_stack.md)**. Each item ships as a
free/local-first, cost-metered, fail-open **provider slot** (the asset-chain /
`llm_router` pattern) — quality goes up without wrecking margin, and the moat
(grounding + loop) is untouched.*
*Shipped 2026-07-08 (baseline seams): shared provider contract (`core/providers.py`)
+ fail-open, env-gated seams for every included tool ([providers_runbook.md](providers_runbook.md));
**goose3 article extraction is live** in `core/link_facts.py`. Excluded this pass:
Higgsfield (paid) + the `[search github]` repos. Heavy backends →
`pip install -e ".[providers]"`; each seam stays OFF until its gate is set.*
*3-month north star (new tools + roadmap + adjacent projects + code-sharing):
[groundwork_2026Q3.md](groundwork_2026Q3.md).*

*Status honesty (2026-07-17 reconciliation): the seam→live-path wiring is done for
every slot below (U1–U9). The remaining `[ ]` items split into **live wiring shipped,
heavy backend parked** (each seam runs today and fails open to the current behavior; its
real backend — WhisperX / MusicGen / ComfyUI-Wan-LTX / YOLO / avatar / Real-ESRGAN·RIFE —
needs a **GPU box + `[providers]` install** and can't be verified on the Windows/CPU dev
box, so it stays OFF) and **not started** (clip-from-source, storyboard).*
- [x] **TTS provider chain + local (Kokoro/XTTS/Piper)** — *shipped 2026-07-09; voice
  variety 2026-07-17:* local providers synth → transcode to the render's mp3
  (`core/tts.py`), fail-open to ElevenLabs, metered **$0** in `cost_meter` (was ~96% of
  run cost). **Piper** is the CPU-only path (no torch/GPU); Kokoro/XTTS for a GPU box.
  **Voice variety (done):** per-channel local voice + pool rotation
  (`resolve_local_voice`, `channels.json` `tts.local_voice(s)` → `PIPER_VOICES` env) +
  optional run-seeded delivery jitter (`TTS_VOICE_VARIETY`, default off); fixed the
  Piper `synthesize_wav` API path. Real-voice clone slot (XTTS) still optional.
- [x] **Whisper local alignment** — *wired (U1):* `video/subtitles.py` →
  `core/caption_align.py` (`CAPTION_ALIGN_BACKEND=whisperx`); word timing for any TTS,
  fail-open to the proportional/ElevenLabs path. *Backend parked (GPU/torch extra).*
- [x] **Music/SFX bed** — *wired (U3):* `MUSIC_PROVIDER` bed ducked under the VO in the
  render command (`video/render_video.py`), retries VO-only on any mix failure.
  *MusicGen backend parked (GPU extra); ElevenLabs/Suno are paid opt-ins.*
- [x] **AI video-gen slot** — *registered (U4):* `assets/ai_video_provider.py` in the
  asset chain via `AI_VIDEO_PROVIDER`, routed through one `core/comfy_client.py` HTTP
  endpoint, fail-open to stock. *Real ComfyUI/Wan/LTX backend parked — needs a GPU box.*
- [x] **Thumbnail text-models + dual-format render** — *shipped (U5 + render profiles):*
  `THUMBNAIL_PROVIDER` chain (ideogram/recraft → flux → pillow); **dual-format render**
  emits 16:9 / 1:1 siblings from the same bg/VO/captions (`video/render_profiles.py`,
  `RENDER_FORMATS`, fail-open — the 9:16 primary is untouched).
- [ ] **Clip-from-source (Phase R)** + subject-tracked auto-reframe — *not started;
  auto-reframe seam is `core/reframe.py` (YOLO/AGPL, GPU). Deprioritized this pass.*
- [ ] **Avatar mode, upscaling (Real-ESRGAN/RIFE), storyboard shot-lists** — polish tiers.
  *Avatar/upscaling = seams parked (GPU + `[search github]` repos). Storyboard = build
  with the AI-video backend (its real consumer; prose hurts keyword stock search).*
- [x] **Distribution/ingestion borrows** — *shipped:* `goose3` scrape
  (`core/link_facts.py`); **multi-source vault importer** (`core/vault_ingest.py` —
  URL/PDF/YouTube → provenance-tagged vault note, `ops ingest`); n8n recipes ride the
  existing `core/events.py` webhooks (see [tooling_landscape.md](tooling_landscape.md)).

### Pillar 7 — Self-improving skills (Agent Skills + SkillOpt)  *(shipped 2026-07-24)*
*Names and closes loops the project already opened, adding almost no new dependency. The
open **Agent Skills** standard (`SKILL.md` folders that Copilot/Claude agents auto-load)
plus Microsoft's **SkillOpt** (a validation-gated optimizer that trains reusable
natural-language skills for a frozen LLM agent) map directly onto ingredients already
built here: the `scripts/ops.py` `@_register` command registry, the frozen
`core/prompt_evals.py` eval gate, `core/overnight.py`, and the Pillar 4 vault. Compounds
with a local frozen model (Bonsai/Ollama) into a self-improving $0 factory.*
- [x] **C1 — Ops-as-skills** — `core/ops_skills.py` renders `skills/content-ops/SKILL.md`
  (Agent Skills frontmatter + a command table) from the live `@_register` registry, so
  Pillar 5 agents / external Claude Code / Copilot agents can operate the pipeline as a
  first-class skill. `py -m scripts.ops gen-skills` regenerates it (never drifts from the CLI).
- [x] **C2 — SkillOpt-Sleep loop** — `core/skillopt.py`: scores the live prompts vs curated
  candidate **STYLE DIRECTIVEs** on the **frozen `core/prompt_evals` rubric** across the
  golden topics (via a new `extra_directive` seam in `content_engine`), keeps only a
  gate-beater (`SKILLOPT_MIN_MARGIN`), and writes a reviewable **proposal** record to the
  vault (Pillar 4) + a `skillopt_proposal` webhook. **Never auto-edits live prompts** — the
  operator promotes a proposal to a `[strategy]` playbook bullet. Runs nightly inside
  `overnight` when `SKILLOPT_ENABLED=true` (render-free, LLM-metered); `ops skillopt`.
  *Follow-up: LLM-proposed (not just curated) directives; optional auto-apply behind a flag.*

### Supporting track — API & efficiency (not a pillar)
*The credit/quota layer is in good shape post-O11; these stay incremental.*
- [ ] **Governor follow-ups (O12 candidates)** — YouTube units under a governor
  scope; per-provider LLM spend in the run cost line; reliability time series
  ([credit_efficiency.md](credit_efficiency.md) O11 follow-ups).
- [x] **Router vision path** *(2026-08-20)* — thumbnail scorer uses
  `llm_router.complete` with OpenAI-style image parts; Anthropic/DeepSeek/Ollama
  skipped rather than flattened; Free mode heuristic + warning. `core/llm_client.py`
  deleted. Unlocks Pillar 2's rendered-video review (still later).
- [ ] **Free-backend probes (optional)** — TikTok/Twitter equivalents of the
  yt-dlp / Reddit-OAuth backends, only if the Apify bill justifies it
  ([agent_reach_evaluation.md](agent_reach_evaluation.md)).

### Unphased levers (carried over, independently shippable)
- [x] **Whisper local** — CPU backend + retext shipped 2026-08-14/16; still OFF by default.
  Clip-from-source transcription remains with Phase R.
- [ ] **MoneyWise depth wave** ([domain-expansion.md](domain-expansion.md) ROI 9.5) —
  earnings-calendar signal (free API), ticker-watchlist tracking, finance-tuned research
  brief sections.
- [ ] **Third-vertical groundwork: AI Tools / Tech** (ROI 9.0) — new-channel playbook dry
  run: channel profile + SEO config + signal-coverage audit. *Groundwork only, not a
  launch commitment.*
- [ ] **Engineering hygiene** — CI coverage reporting (non-blocking), mypy-baseline
  tightening tracking, render/publish test depth (the acknowledged soft spot).

---

## Later horizons

*Valuable, but intentionally pushed out.*

### Phase M — Multi-platform distribution  *(pushed back — far later)*
*Repurpose one rendered vertical to several surfaces. Publisher contract already exists (`publishing/`). Deferred behind authenticity (O), hook/retention (P), and captions (Q) — distribution multiplies whatever quality we ship, so it waits until the content itself is policy-safe and sharper.*
- [ ] **TikTok publisher** — `TIKTOK_CLIENT_KEY`/`SECRET` present; `TikTokPublisher` still unimplemented (in `DEFERRED_PLATFORMS`)
- [ ] Instagram Reels / Meta — `META_APP_ID`/`SECRET`, `INSTAGRAM_*` (keys still empty)
- [ ] Per-platform caption/hashtag shaping from existing SEO + TikTok-trend signal
- [ ] Cross-platform performance back into the learning loop (unify with YouTube engaged-rate)

---

## Recently shipped — recency & robustness cycle (2026-06)

*Focus: get current facts into scripts (events past the LLM cutoff) and stop wasted/wrong signal calls.*

- [x] **Manual key facts** — operator pastes verified facts injected as top-priority `OPERATOR KEY FACTS` ground truth (`core/content_engine.py`, `main.py`)
- [x] **Domain-aware signal gating** — UFC/sports topics skip gaming signals (rawg/steam/igdb) & vice-versa (`apis/register_signals.py`, `DOMAIN_SIGNAL_GATING`)
- [x] **Generalized circuit breaker** — any signal returning quota/auth/no-key auto-skips for the session (`apis/register_signals.py`, `SIGNAL_CIRCUIT_BREAKER`)
- [x] **Live discovery feedback** — spinner shows real phases + per-variant `Scoring variants N/M` (`core/ui.py` `DiscoverySpinner.report`, `core/pipeline.py` `run_discovery(progress=…)`)
- [x] **Tapology enabled** — `TAPOLOGY_SCRAPE_ENABLED=true` for live UFC fight data
- [x] **Live web search signal** — universal, never-gated; Tavily preferred + Brave fallback; feeds VERIFIED FACTS (`apis/web_search_api.py`, `TAVILY_API_KEY`/`BRAVE_SEARCH_API_KEY`)
- [x] **Obsidian vault connector** — auto-pulls topic-relevant fact bullets to pre-fill the key-facts prompt; diversified, open-ended capture (`core/obsidian_facts.py`, `OBSIDIAN_VAULT_PATH`)
- [x] **Apify out-of-credits guard** — first 402 marks the key exhausted; later actor calls on it short-circuit (no repeated failing round-trips that dragged discovery to 200-300s+) (`apis/apify_client.py`)
- [x] **Tag-pollution fix** — stop force-injecting domain-mixed `trending_tags` (fighter names bled onto gaming videos); trending tags stay offered to the LLM relevance-gated (`config/seo.py`)
- [x] **Filler-phrase fix** — script prompt no longer coaches the "but here's the thing" crutch; stock transitions banned verbatim (`core/content_engine.py`)
- [x] **Recommender confidence surfacing** — best-bet/post-time/length annotate thin sample bases (low/moderate confidence + sample count); raised length `min_total` so 4 samples no longer reads as authoritative (`core/recommender_confidence.py`, `core/length_recommender.py`, `analytics/post_timing.py`, `core/best_bet.py`)
- [x] **Per-run cost surfaced** — run summary shows estimated fully-loaded cost (llm/tts/apify/web breakdown) + an Apify out-of-credits warning when a key was exhausted this session (`core/cost_meter.py` `format_cost_line`, `apis/apify_client.py` `apify_credit_exhausted`, `core/ui.py`)
- [x] **Fact-grounding post-check** — flags script specifics (heroes/products/patch-versions) not backed by VERIFIED FACTS/key facts before publish; conservative multi-word + version detector (`core/fact_grounding.py`, surfaced in `main.py`). **Now regenerate-then-warn** (`content_engine._maybe_reground_script`, `GROUNDING_REGEN_ENABLED`): regenerates once to strip the unsupported specifics, then warns on the remainder. Pasted-link facts are junk-filtered first (`core/link_facts._is_junk_line`).
- [x] **Sports-on-gaming domain override (2026-07-07)** — NBA standings/award-race topics + pasted sports key facts override TapIn's `gaming` default; NBA/NFL script matrices + `_video_game_drift` recenter stop Marvel Rivals/esports drift when facts are real sports (`apis/topic_scorer.py`, `core/script_brief.py`, `core/content_engine.py`).
- [x] **Link scrape hardening (2026-07-07)** — Bing search/captcha blocked, `ck/a` redirect unwrap, junk titles rejected, 12-line article cap (`core/link_facts.py`).
- [x] **RAWG relevance gate** — filters fuzzy RAWG matches ("Need for Speed Rivals" for *Marvel Rivals*) by topic token overlap + acronym (keeps GTA→Grand Theft Auto) so only the real game is injected as facts (`apis/rawg_api.py`)
- [x] **Domain-routed RSS** — feeds carry optional `domains` tags; gaming topics no longer pull MMA/soccer feeds (BBC Sport) and vice-versa; untagged feeds stay universal (`config/data_sources.py`, `config/seo.py`, `config/data_sources.json`, `config/seo/tapin.json`)
- [x] **Obsidian source capture** — links pasted in the key-facts prompt are appended to `<vault>/<channel>/_sources.md` (de-duped, channel-scoped, `[sources, research]`) and read back by `obsidian_facts.load_facts` on related topics — research brought in once is reusable, not discarded (`core/source_capture.py`, wired in `prompt_key_facts`). *Follow-up: also capture `web_search` result URLs.*
- [x] **Repo hygiene** — `.gitattributes` (LF/binary), ignore local background media, `.env.example` web-search keys surfaced, leaked-file-handle test fix; merged branches pruned (single-branch repo)

---

## Deferred (volume-gated)

*Do not build until publish volume supports meaningful correlations.*

- [ ] Thumbnail scoring → CTR
- [ ] Prompt performance analysis (after provenance shipped)
- [ ] Asset effectiveness ranking from `assets` history
- [ ] Full operator dashboard + Channel Command Center
- [ ] Tavily / broad web research
- [ ] Bluesky direction signal
- [x] Retire unused research stubs in `legacy/` (removed 2026-06)

### Asset intelligence (non-urgent)

- [ ] Reuse scoring from `assets` history for background selection

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

**`py main.py` menu:** 1) new video · 2) queue manager · 3) intelligence report · 4) sync analytics · 5) make a video from your own idea / a YouTube link

**Recommendation helpers:** `py -m scripts.ops recommend-time --channel tapin` · `recommend-length` · best-bet shown at startup

**Developer setup:** `pip install -e ".[dev]"` then `pre-commit install`; `ruff check .` · `ruff format .` · `mypy analytics apis core config storage`. Tooling config lives in `pyproject.toml`.

**Troubleshooting:** [debugging.md](debugging.md)

---

*Never commit `.env`, OAuth tokens, or `client_secrets.json`.*
