# Roadmap archive — completed work and historical phases

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-09-25

> History. **Never edited again**, and it holds no open checkboxes — those live in
> [backlog.md](backlog.md). Current work is [roadmap.md](roadmap.md); the desktop
> programme is [desktop_app.md](desktop_app.md).

---

## Wave narratives (2026-08)

## Next up — all open items

*The single forward list — everything still open across this roadmap, grouped by area.
Detail lives in the phase/pillar sections further down. **Multi-platform distribution
(Phase M) is intentionally excluded here** — it stays parked under
[Later horizons](#later-horizons). Shipped this cycle: Pillars 1–6, the config-driven
voice catalog + honest Free-mode readiness, the **Qwen3-TTS** local voice-cloning provider,
the router/title/voice crash fixes, and the **scheduling upgrades** (clock-time upload
input + average-based learned post slots). Leave-the-terminal waves 2026-08-21
(1–3) and honesty wave 4 2026-08-22.

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

**Honesty + leave-the-terminal wave 2 (2026-08-21)** — **shipped.** Pickup was *not*
numerical next (21 caption skin / 22 safe-area / 146 tray daemon / 172 design
system). Ranked leftover `[S]` that unblocks the next publish, meters TTS 91%,
and keeps the operator out of PowerShell. **#147 FastAPI still skipped.**

1. **94** NVIDIA driver + NVENC *capability* probe in `ops doctor` `[S]` — *shipped.* `ffmpeg -encoders` lists `h264_nvenc`; does not encode (#38).
2. **95** RAM/VRAM preflight before whisper / local TTS `[S]` — *shipped.* `RAM_MIN_GB` / `VRAM_MIN_GB` opt-in; fail-open; Free mode refuses OOM.
3. **96** `ops secrets-doctor` `[S]` — *shipped.* Present/missing/placeholder; values never printed.
4. **100** OneDrive / nested `.git` hazard in `ops doctor` `[S]` — *shipped.* operating_plan §7.
5. **102** Auto-set YouTube category from `infer_domain` `[S]` — *shipped.* Sports 17 / Gaming 20 / finance 25.
6. **107** `madeForKids=false` self-declared audit `[S]` — *shipped.* Forced False on every `videos.insert`.
7. **108** Default language + audio language `[S]` — *shipped.* `YOUTUBE_DEFAULT_LANGUAGE` (default `en`).
8. **117** Title uniqueness vs own catalog `[S]` — *shipped.* `TITLE_UNIQUENESS=warn|block|off`.
9. **125** MoneyWise finance disclaimer in description `[S]` — *shipped.* Separate from AI disclosure.
10. **129** UFC/trademark title linter `[S]` — *shipped.* Warns `UFC` on a non-UFC topic.
11. **135** CSV export of `ops economics` `[S]` — *shipped.* `ops economics --csv` (not under `data/`).
12. **225** Toast on upload scheduled / `publishAt` `[S]` — *shipped.*
13. **227** Toast when overnight finishes drafts `[S]` — *shipped.*
14. **228** Balloon: N uploads left this reset `[S]` — *shipped.* Tray + `main.py` startup.
15. **242** `ops grade --html --run-id` `[S]` — *shipped.*
16. **250** Emoji-free / ASCII-safe HTML `[S]` — *shipped.* cp1252-safe dumps (`>=`, no smart dashes).
17. **256** Reveal trace JSON `[S]` — *shipped.* `ops reveal --kind trace`.
18. **272** Cost subtitle under the player `[S]` — *shipped.* `tts $0.31 · 91%` on the booth.
19. **312** Tray menu: open last output folder `[S]` — *shipped.* `--open-output` + `--stay` button.
20. **317** Tray: Free vs Standard mode `[S]` — *shipped.* Chip line `Mode: Free|Standard`.

**Swaps vs numerical next:** skipped 21–28 (need a real render), 31/33/34 (hygiene that is not the next publish), 38 NVENC *encode* (probe #94 instead), 39 draft preset, 44 `probe_sync`, 98 pip-audit CI, 101 caption *track*, 103 vault sources, 146 tray daemon `[L]`, 147 FastAPI `[L]`, 172 HTML design system `[M]`.

**Honesty + leave-the-terminal wave 3 (2026-08-21)** — **shipped.** Pickup was *not*
numerical next (21 caption skin / 31 artifact retention / 101 caption track /
146 tray daemon). Ranked leftover `[S]` that keep the next *public* honest
(PPV + quiet hours, SEO first line, UFC stock-query rewrite, odds “market”
voice, gambling-safe CTAs, FTC copy), surface TTS 91% / quota on the booth
(escaped-LLM pill, Standard-would-have-billed, allocated vs marginal, uploads
+ ElevenLabs header, Apify pills, thin-facts banner), and leave PowerShell
(click-toast opens the mp4, high-contrast CSS, skip-link, copy-as-markdown,
tray doctor HTML + last grade). **#147 FastAPI still skipped.**

1. **115** Don’t publish during a live UFC PPV window `[S]` — *shipped.* Sat 21:00–02:00 ET; UFC topics only; bumps `publishAt`. Unlisted review holds are not “publishing”.
2. **116** Blackout / quiet-hours calendar in `channels.json` `[S]` — *shipped.* TapIn + MoneyWise `quiet_hours` 1–8 ET; `QUIET_HOURS` master switch.
3. **118** Description first-line SEO `[S]` — *shipped.* Prepend title when the first line is hashtags / Subscribe / empty.
4. **121** Stock query rewriter: never Pexels-search “UFC” `[S]` — *shipped.* `sanitize_trademark_stock_query` → `mma`.
5. **126** Odds scripts say “market” / “favored”, never “will win” `[S]` — *shipped.* Odds-context only.
6. **127** Gambling/odds advertiser-safe mode `[S]` — *shipped.* Strips bet-now / parlay CTAs.
7. **128** FTC affiliate disclosure *line* `[S]` — *shipped.* Copy only, when `monetization_cta` is set. #79 is still the tracking spike.
8. **229** Click-toast opens last mp4 `[S]` — *shipped.* Toast `activationType=protocol` + `file:` URI.
9. **234** High-contrast CSS for HTML reports `[S]` — *shipped.* `prefers-contrast: more`.
10. **251** Copy-as-markdown on the report card `[S]` — *shipped.* Booth textarea + `ops grade --md`.
11. **261** Skip-link a11y on the booth `[S]` — *shipped.* Skip to `#player`; all dumps skip to `#main`.
12. **273** Escaped free-first LLM red pill `[S]` — *shipped.* Booth reads `llm_calls[].escaped_free_first`.
13. **274** Thin-facts warning banner `[S]` — *shipped.* Same gate as #200, one strip.
14. **278** Standard-would-have-billed on Free runs `[S]` — *shipped.* Existing dry-run line on the booth.
15. **279** Allocated vs marginal one-liner `[S]` — *shipped.* Booth footer; no new economics engine.
16. **286** Uploads-left in booth header `[S]` — *shipped.* Same figure as the tray chip.
17. **287** ElevenLabs chars in booth header `[S]` — *shipped.*
18. **288** Remaining Apify actors as pills `[S]` — *shipped.* Catalog-enabled only (`tiktok_trends`, `youtube_competitors`).
19. **314** Tray: run doctor → HTML `[S]` — *shipped.* `--doctor-html` + stay-window button.
20. **315** Tray: last grade letter `[S]` — *shipped.* Chip line `Grade: B`. Suite sets `CONTENT_TRAY_GRADE=false`.

**Swaps vs numerical next (wave 3):** skipped 21–28 (need a real render), 31/33/34, 38 NVENC encode, 39 draft preset, 44 `probe_sync`, 52 graveyard codes, 98 pip-audit, 101 caption track, 103 vault sources, 132 policy runbook (doc-only), 146 tray daemon `[L]`, 147 FastAPI `[L]`, 172 HTML design system `[M]`, 316 last-domain (companion to 315; next chip).

**Run-71 correctness wave (2026-08-22)** - **shipped.** Pickup was *not* the deferred
skip list (21-28 need a real render; 31/38/39/101/103/146/147/172 are not the next
publish) but the four defects **live-run 71 proved**, each verified in code before it
was planned. They share one shape: *a check passes because it measures the wrong
thing, then reports a clean number that hides the miss* (decisions.md SS18/SS24). The
run graded **A (91/100)** with grounding **100/100** and was not that good.

1. **321** Title claim check `[M]` - *shipped.* Run 71 shipped "GTA 6 Leak Forces
   **Rockstar** to Subpoena Microsoft and Discord Records"; the operator's own key fact
   said **Take-Two**, Rockstar's parent. `generate_title` runs after grounding and the
   claim verifier and is fail-open, so nothing read its output. Token grounding cannot
   close this - measured, it returns `[]` for *both* actors, because the error is
   relational. Reuses `verify_claims`; checked at generation so the warning reaches the
   report card **before** `Proceed?`. `TITLE_GROUNDING=warn|off`.
2. **322** Pre-rewrite claim verdict `[S]` - *shipped.* The verifier found **7 of 12
   unsupported**; the rewrite pass restated them as attributed speculation and the
   re-check printed **12/12**. Only the post-rewrite numbers persisted, so quality_json
   read 1.0, the card graded A, and **#52's `thin_facts` could never fire**. `to_dict()`
   now carries the pre-rewrite figures (only on a rewritten run - existing readers
   unchanged). Records and surfaces; does **not** gate or re-grade.
3. **323** Variant tie-break on the pre-clamp score `[M]` - *shipped.* All five angles
   read **100.0** because `composite_score` ends `min(final_score, 100)`, so the menu
   offered a tie dressed as a ranking. Split out `composite_score_raw`; the stored 0-100
   contract is untouched and `best_variant_index` is now the one ranking rule, shared by
   the menu and `run_pipeline`. A visible score difference can never be overridden.
4. **324** RAWG release-era gate `[S]` - *shipped.* Three 1990s Wolverine games reached a
   2026 GTA 6 story and counted toward the authenticity gate's "18 verified fact(s)".
   The overlap rule passed them correctly - it was incomplete, not broken. Release era
   is the discriminator (`RAWG_MAX_AGE_YEARS`, default 15); fail-open on a missing date,
   retro topics exempt, `GTA -> Grand Theft Auto` covered by a test.
5. **325** `Proceed?` re-prompts on a paste `[S]` - *shipped.* The run cost 30.6 min wall
   (**25.6 at prompts**, 5.0 machine) and produced no video because a pasted paragraph
   read as "stop". Structural, not carelessness: the key-facts loop directly above
   accepts pastes. Obvious prose gets one re-prompt; `n`/`N`/Enter still stop instantly.

**Deliberately out of this wave:** gating or re-grading hedged scripts (322 records
only - the operator's call); **vault-side** subject relevance
(`obsidian_facts.load_facts` attached four Marvel Rivals / SEGA bullets to the same run,
same root cause as 324) so one wave does not touch both fact paths; the **dependency
wave** (#98's 75 vulns / 19 packages, Pillow 9.5.0 = 26 of them; nothing caps it - needs a real
render); **MoneyWise persona**, the live gap #33's ratchet found (operator-authored).

**Honesty + leave-the-terminal wave 4 (2026-08-22)** — **shipped.** Pickup was
*not* numerical next (21 caption skin / 22 safe-area / 31 artifact retention /
101 caption track / 146 tray daemon). Ranked leftover `[S]` that keep the next
*public* honest (playbook lint so strategy cannot feed facts, vault `source_url`
in the description, ungrounded numeric chips, authenticity semantic bar, grade
breakdown, render/RPM/metrics gate copy), surface TTS 91% / quota on the booth
(TTS cache-hit $0, Pillow vs Flux badge, signal dots, feed-stale strip, sticky
cost + quota, 16px type), and leave PowerShell (copy unlisted URL + dossier URI
+ postmortem markdown, mute toasts in quiet hours, tray last domain). **#147
FastAPI still skipped.**

1. **37** Playbook lint `[S]` — *shipped.* `ops playbook-lint`; untagged strategy bullets that also look fact-anchored (rank / year / `$`) warn because `load_facts` will treat them as ground truth.
2. **103** Description **sources** block from vault `source_url`s `[S]` — *shipped.* `DESCRIPTION_SOURCES`; also http(s) from pasted key facts. Idempotent.
3. **252** Copy last unlisted URL `[S]` — *shipped.* Booth textarea + clipboard; prefers `privacy_status=unlisted`.
4. **255** Open dossier via Obsidian URI `[S]` — *shipped.* `obsidian://open?vault=&file=`; `''` when vault unset.
5. **275** Ungrounded **numeric chips** `[S]` — *shipped.* Record / rank / purse / date spans as chips.
6. **276** Authenticity **semantic-arm bar** `[S]` — *shipped.* Peak content-word cosine persisted as `authenticity_semantic`; warn at 45%.
7. **277** Report-card **component breakdown** `[S]` — *shipped.* Hook / grounding / authenticity (and present components) as numbers.
8. **280** TTS **cache-hit $0** pill `[S]` — *shipped.* Reads `tts_cached` from the post-render trace/features merge.
9. **281** **Pillow vs Flux** thumb badge `[S]` — *shipped.* Label from provider / thumbnail cost.
10. **283** Render-gate **blocked reason** in plain English `[S]` — *shipped.* `Overnight will not render: …`
11. **284** RPM-cost-gate **deferred reason** `[S]` — *shipped.* `Deferred: …` when the opt-in gate fires.
12. **285** Metrics-before-next **"yesterday unsynced"** copy `[S]` — *shipped.* Informational even when the gate is off.
13. **289** Last-run **signal-health dots** `[S]` — *shipped.* Trace `signals[].status` as ok / warn / fail / skip.
14. **290** **Feed-stale strip** `[S]` — *shipped.* Cached `ops feeds` snapshot only — no HTTP.
15. **292** **Mute toasts during quiet hours** `[S]` — *shipped, then fixed the same day.* As written it muted **nothing**: `_toasts_muted()` asked `quiet_hours_reason()` with no channel, which resolves to `default`, and only `tapin`/`moneywise` carry a `quiet_hours` block. Now resolved machine-level across every configured channel, with breaker toasts exempt (`urgent=True`) because the overnight batch runs inside the 1-8am window. `CONTENT_TOAST_DND`.
16. **305** **16px minimum type** on HTML dumps `[S]` — *shipped.* Buttons/inputs/textareas join the existing 16px body; header sticky.
17. **306** **Sticky cost bar** `[S]` — *shipped.* `#costbar` in the booth header (TTS 91% line).
18. **307** **Sticky quota bar** `[S]` — *shipped.* `#quotabar` (uploads-left + ElevenLabs chars).
19. **311** Copy last **postmortem as markdown** `[S]` — *shipped.* Booth field + `ops postmortem --md`.
20. **316** Tray: **last domain** (UFC / GTA / NBA) `[S]` — *shipped.* Chip line `Domain: UFC`. Suite sets `CONTENT_TRAY_DOMAIN=false`.

**Swaps vs numerical next (wave 4):** skipped 21–28 (need a real render), 31 artifact retention, 38 NVENC encode, 39 draft preset, 101 caption track, 122 `license.yaml`, 132 policy runbook (doc-only), 133 `.ics`, 146 tray daemon `[L]`, 147 FastAPI `[L]`, 172 HTML design system `[M]`, 232 booth `.lnk`, 237 favicon, 282 human-presence last-seen, 308–310 collapsible/copy ffmpeg, 313 tray pause-overnight (companion to 316).

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

**Deferred (volume-gated — do not build until publish volume supports correlations)**

*Excluded: **Phase M — multi-platform distribution** (TikTok/Instagram/Reels + cross-platform
learning) stays parked under [Later horizons](#later-horizons).*

**Candidate ideas (2026-08-20 session — Phase M excluded)**

*Brainstorm. Rationale: [planning_log.md](planning_log.md) 2026-08-20 and
[audit.md](audit_2026-08.md). None of these restates an open Next-up line
(clip-from-source, avatar, MoneyWise depth, Instagram figures). Items 1 and 4
plus the coverage-wave and router-vision Next-up lines shipped the same day.*

- [x] Capability-probe consolidation — one SoT for Ollama/TTS readiness; teach
  `ops free-doctor` "up but empty" vs "down" (the run-70 class) `[S]`
  *(2026-08-20: `ollama_probe` shared; free-doctor pull vs serve vs OpenRouter)*
- [x] Pre-run completion gate — readiness line ≡ applied env ≡ first LLM/TTS call
  before discovery starts `[S]`
  *(2026-08-20: `inspect_first_calls` / `guard_before_discovery`; Free fail-closed,
  Standard warns; stale Readiness cannot start discovery)*
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
- [x] CUDA torch as an ops enablement — RTX 4070 Ti is in the box; `2.8.0+cpu` is
  the actual gate `[M]`
  *(2026-08-28: code + fail-visible doctor, no wheel install. `ops doctor` had always
  PASSed `cuda`; it now reports `ok=False` only when `nvidia-smi` is present AND torch
  has no CUDA — a box with no dGPU is not a FAIL, and a usable CUDA torch passes.
  Confirmed non-blocking: nothing in pipeline/render/publish reads `ops_doctor`.
  **2026-08-28 night:** operator installed `2.8.0+cu128`; `ops doctor` cuda PASS.
  The wheel is not a repo pin — the environment is.)*
- [x] Audio LUFS normalize — ffmpeg `loudnorm` for Shorts level consistency `[S]`
  *(2026-08-20: `LUFS_NORMALIZE` opt-in; default command byte-identical; I=-14)*
- [x] Background clip anti-repeat — variation guard checks scripts, not pictures `[S]`
  *(2026-08-20: `assets/clip_memory.py` in-process deque; `CLIP_MEMORY` file persist
  opt-in; fail-open if every clip was used)*
- [x] Numeric/record grounding — gate catches names; invented ranks/dates/purses pass `[M]`
  *(2026-08-20: `find_ungrounded_numeric`; sports-context records/ranks/dates; purses
  always; warn/fail-open; round scores like 10-9 are not records; "If Netflix" intact)*


## Completed

### Honesty + leave-the-terminal wave 4 (2026-08-22)

- [x] **20 operator-visible pieces** — playbook lint + description sources, ungrounded numeric chips + authenticity semantic bar + grade breakdown, TTS cache-hit / Pillow-vs-Flux / signal dots / feed-stale / overnight-render + RPM-deferred + yesterday-unsynced copy, copy unlisted URL + Obsidian dossier URI + postmortem markdown, quiet-hours toast DND, sticky cost/quota + 16px type, tray last domain. **#147 FastAPI still skipped.** No Phase M, no #141/#142/#143.

### Honesty + leave-the-terminal wave 3 (2026-08-21)

- [x] **20 operator-visible pieces** — UFC PPV + quiet-hours publish windows, description SEO first line + FTC affiliate copy, UFC stock-query rewrite, odds market voice + gambling-safe CTAs, click-toast opens mp4, high-contrast CSS, booth skip-link / copy-markdown / escaped-LLM pill / thin-facts banner / Standard-would-have-billed / allocated-vs-marginal / uploads + ElevenLabs header / Apify pills, tray doctor HTML + last grade. **#147 FastAPI still skipped.** No Phase M, no #141/#142/#143.

### Leave-the-terminal wave 2 (2026-08-21)

- [x] **20 operator-visible pieces** — NVENC capability probe, RAM/VRAM preflight, secrets-doctor, OneDrive/.git hazard, YouTube category/language/madeForKids/title uniqueness/UFC lint, MoneyWise finance disclaimer, economics CSV, scheduled + overnight + uploads-left toasts, `ops grade --html`, ASCII-safe HTML, reveal trace, booth TTS 91% subtitle, tray open-folder + Free/Standard. **#147 FastAPI still skipped.** No Phase M, no #141/#142/#143.

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
- [x] Stats scrapers + `blog_rss` signal + `config/data_sources.json` — see [data_sources.md](data_sources.md)
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

### Phase L — Closed-loop recommenders (2026-06)

*All three share one pattern: `analytics` source when enough engagement history exists, sensible default otherwise, each with a rationale string.*

- [x] **Best Bet (topic)** — `core/best_bet.py`; `source="analytics"` path live once metrics sync working (engaged-rate by domain). **Confidence-weighted + diversified** (2026-06): empirical-Bayes domain shrinkage + adequately-sampled-domains-first ranking (`_adjusted_domain_rates`/`_domain_priority`), ≤1 pick per domain so thin 1-sample domains can't fill every slot, and measured-history domains count as on-brand (`_effective_allowed` — surfaces e.g. NBA on a gaming/UFC channel).
- [x] **Recommended post time** — `analytics/post_timing.py` (`get_recommended_time`); engagement bucketed by weekday/hour, domain-aware; surfaced in `main.py`, `auto_generate`, ops `recommend-time`
- [x] **Recommended length** — `core/length_recommender.py`; engaged-rate by length preset (uses `timings_json.length_preset`); `auto_generate --length auto`; ops `recommend-length`
- [x] YouTube Analytics sync hardened — validating probe query, clear "enable API"/scope guidance (`analytics/sync_metrics.py`)
- [x] Confidence thresholds / minimum-sample surfacing in the UI (`core/recommender_confidence.py`; low/moderate caveats on best-bet/post-time/length)

### Phase L2 — Apify data layer (2026-06)

*Catalog-driven external signals. Single source of truth: `config/apify_sources.json` (`apis/apify_catalog.py`).*

- [x] Apify client with key routing + local cache (`apis/apify_client.py`); `~`-form actor ids
- [x] `youtube_competitors` — top videos by **view velocity** (`apis/youtube_apify_signal.py`)
- [x] `twitter` — breaking news weighted by domain authority accounts (`apis/twitter_signal.py`)
- [x] `reddit`, `tiktok_trends` — community sentiment + viral angles
- [x] Per-domain targeting (`domain_targets`); fact formatting keeps competitor titles as context, not verified facts
- [x] Docs: [apify_data_sources.md](apify_data_sources.md)
- [x] `youtube_comments` — wired 2026-08-14 against the official Data API (not Apify)
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
- [x] **`CLAUDE.md`** — project guide for AI coding agents (pipeline overview, `ops`/`main.py` entry points, signal architecture, LLM router tiers, test/lint commands, hard rules). Companion: [docs/claude_code_usage.md](claude_code_usage.md) (Claude Code modes/features specific to this repo).

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

### Phase S — Creator coach surface
- [x] Expand best-bet into a **"daily ideas + why"** coach view (vidIQ-style, but with our sourcing) — `core/creator_coach.py`, `py -m scripts.ops coach`: ranked ideas each with a *why*, plus recommended length/post-time, winning title patterns, retention pacing, and cadence headroom. Read-only + fail-open. *(2026-07-02)*
- [x] **Thumbnail A/B** — *shipped 2026-07-06 on the experiment harness:* `py -m core.experiments start thumbnail_style` → each Flux render appends the least-used arm's composition directive (`close_up` / `wide_drama` plus 2026-08-26 named slots `subject_scale`, `text_negative_space`, `hard_light`; `core/experiment_levers.py` kind="thumbnail") to the prompt in `assets/flux_thumbnail.py`; the assignment is recorded only when Flux actually generated (Pillow fallbacks never pollute attribution), and `ops experiment` runs the same low-n-safe Bayesian report against realized engaged-rate. *CTR optimisation still open — needs impressions/CTR in the metrics sync before the report can attribute clicks rather than engagement.*
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
  (`--file topics.txt` for topics; `--facts-file` for operator key facts, same
  parser as `auto_generate`, passed through `run_batch(..., key_facts=)`).
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
[groundwork_q3_2026.md](groundwork_q3_2026.md).*

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
- [x] **Router vision path** *(2026-08-20)* — thumbnail scorer uses
  `llm_router.complete` with OpenAI-style image parts; Anthropic/DeepSeek/Ollama
  skipped rather than flattened; Free mode heuristic + warning. `core/llm_client.py`
  deleted. Unlocks Pillar 2's rendered-video review (still later).

### Unphased levers (carried over, independently shippable)
- [x] **Whisper local** — CPU backend + retext shipped 2026-08-14/16; still OFF by default.
  Clip-from-source transcription remains with Phase R.

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


## Later horizons

*Valuable, but intentionally pushed out.*

### Phase M — Multi-platform distribution  *(pushed back — far later)*
*Repurpose one rendered vertical to several surfaces. Publisher contract already exists (`publishing/`). Deferred behind authenticity (O), hook/retention (P), and captions (Q) — distribution multiplies whatever quality we ship, so it waits until the content itself is policy-safe and sharper.*

---


## Deferred (volume-gated)

*Do not build until publish volume supports meaningful correlations.*

- [x] Retire unused research stubs in `legacy/` (removed 2026-06)

### Asset intelligence (non-urgent)


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

## Moved from roadmap.md on 2026-09-15 (wave 17) - older closed waves

**Closed 2026-09-08 (review 4):** **#694** recency decay reached the recommendation · **#695** three write-only quality keys given a reader · **#696** retraction throttle before the fetch · **#697** HUD temp-dir leak + memo · **#698** pre-commit header.

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
