# Handoff synopsis — 2026-08-14: fact-layer repair wave (after Pillars 1–7)

Use in a fresh session to continue `content_machine` without re-reading the full thread.

## Branch / PR

- **Branch:** `feat/research-intake-repair`, stacked on `feat/trade-validation-default-on`
  (pushed, **not merged** — no PR opened yet). Both branch from `main` at `95a6646`.
- **Suite:** 1347 tests green · **Pre-commit:** `ruff check .` · `ruff format .` · `python -m unittest discover -s tests`
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

**Neither branch is merged and no PR exists.** Also:
`origin/claude/trade-validation-default-on` is **superseded and should be deleted** — it
carries a pre-#33 CI time-bomb test that would revert the fix. PRs #29–#32 have been
open since late July and need triage.

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

**Next step (small, well-defined):** keep whisper's timings, take the *text* from the
known script by sequence alignment — `generate_subtitle_file` already receives `script`,
and `scripts/bench_caption_align.align_sequences` is most of the matcher. That unblocks
the **$0 TTS switch**, worth **$0.25/video (~88% of run cost)**.

Also noted: Piper renders the same script **66.3s vs ElevenLabs 55.2s** (~20% slower),
which shifts video length and feeds the learned-length loop. A voice sample exists at
`output/samples/piper_lessac_run65.mp3` for the operator to judge; **ElevenLabs remains
the default and nothing was switched.** Voice: `models/piper/` (gitignored).

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
| LLM packing | Char budget default 4500 (`OPERATOR_KEY_FACT_CHAR_BUDGET`), soft 24 lines |
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

> **Start here next session:** finish the caption-text fix described above (whisper
> timings + script text via sequence alignment). It is small, well-scoped, and it
> unblocks the **$0 TTS switch — $0.25/video, ~88% of run cost**, the largest remaining
> cost lever in the project. Everything needed is installed and measured.

***Pillars 1–5 all shipped** (decisions §15–17) — the internal-systems reorientation
is complete. `ops health` / `analyst` / `overnight` are live. Remaining:*

1. **Pillar 6 — Video Creation Provider Layer** (decisions §17, overrides §8): the
   seam→live-path wiring is **done** for every slot (U1–U9; local TTS + voice variety
   shipped) — see the reconciled roadmap + [providers_runbook.md](providers_runbook.md).
   What's left is **backend + feature work that needs a GPU box** (can't be verified on the
   Windows/CPU dev machine, so each stays OFF and fails open): real WhisperX / MusicGen /
   ComfyUI-Wan-LTX AI-video / YOLO auto-reframe / avatar / Real-ESRGAN·RIFE upscaling — plus
   two **not-started** items: **clip-from-source (Phase R)** and **storyboard shot-lists**
   (build storyboard *with* the AI-video backend — its real consumer; cinematic prose hurts
   keyword stock search). Full tool list + build order:
   [video_creation_stack.md](video_creation_stack.md). Excluded: Higgsfield + `[search github]` repos.
2. **Pillar 2 remainder**: multimodal rendered-video review *(needs router vision path)*;
   calibration/predictor activate as measured volume accrues.
3. Supporting/unphased: router vision path, MoneyWise depth, AI Tools/Tech groundwork.
   *(O12 complete 2026-08-14. Whisper local: CPU backend landed — see above; the
   caption-text fix is the open half.)* Still volume-gated: the **recommender backtest**
   (10 measured run-linked videos vs the predictor's threshold of 15).
4. Agent follow-ups: overnight facts-file intake (needs `generate_draft(key_facts=)`).
   *(`SEMANTIC_TRADE_VALIDATION` default-on shipped 2026-08-14 — domain-gated NBA/NFL.)*
5. Vault housekeeping: cross-day dossier refresh leaves prior-day `_runs/` notes (same
   `run_id`, different date prefix) — safe but clutter; stable-path upsert is a follow-up.
   17 test-fixture `<date>_topic.md` notes remain in the vault (harmless; they no longer
   regenerate now that the suite is isolated).
6. One-time ops: re-auth `youtube.readonly` for tapin; `oauth_setup` for MoneyWise.
7. **Open PRs to triage** — the two 2026-08-14 branches are unmerged, and PRs #29–#32
   have been open since late July. `origin/claude/trade-validation-default-on` is
   **superseded and should be deleted** — it carries a pre-#33 CI time-bomb test that
   would revert the fix.
8. Two retired LLM slugs still need repointing (`OPENROUTER_MODEL_CHEAP`,
   `OLLAMA_MODEL_CHEAP`) — each currently costs one failed probe per 24h.

**Parked / excluded:** Instagram + TikTok platform linking (Phase M, far later) · Benable bot.

---

## Docs to read first

- `docs/decisions.md` §15 (pillar reorientation), §16 (Fact Engine), **§17 (vault OS)**
- `docs/credit_efficiency.md` — O1–O11 (all ✅)
- `docs/roadmap.md` — Pillars 1–5 ✅, Pillar 6 baseline seams landed
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
