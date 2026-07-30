# Handoff synopsis — 2026-07-29: Pillars 1–7 shipped · **5 PRs open** (docs + one code)

Use in a fresh session to continue `content_machine` without re-reading the full thread.

## Branch / PR

- **Branch:** `main` — **Pillars 1–7 merged.** The working tree is clean, but **five
  branches are unmerged with open PRs** (below).
- **Suite:** ~1,125 tests green on a fully-installed machine (see *How to count metrics*).
  **Pre-commit:** `ruff check .` · `ruff format .` · `python -m unittest discover -s tests`
- History carries: morning (free backends, batch/A/B, webhooks, O11), Pillars 1–3,
  **Pillar 4** (Obsidian knowledge OS), **Pillar 5** (agent layer: `ops health` /
  `analyst` / `overnight`), **live-run hardening**, **Pillar 6** (provider seams + goose3,
  seam→live-path wiring U1–U9, local TTS + voice variety), and **Pillar 7**
  (self-improving skills, 2026-07-24).

### Open PRs (2026-07-29) — read before starting anything

| PR | Branch | Contents | Type |
|---|---|---|---|
| **#26** | `claude/kimi-k3-evaluation` | `llm_provider_strategy.md` — 12-model comparison, free vs paid use cases per job | docs |
| **#27** | `claude/trade-validation-default-on` | `SEMANTIC_TRADE_VALIDATION` **default-on for NBA/NFL** (domain-gated); 18/18 tests green | **code** |
| **#28** | `claude/code-audit-2026-07` | `code_audit_2026-07.md` — whole-repo health pass | docs |
| **#29** | `claude/strategy-2026h2` | `strategy_2026H2.md` + roadmap refresh (volume paradox, Phase M eligibility, do-not-build list) | docs |
| **#30** | `claude/efficiency-audit` | `efficiency_audit_2026-07.md` — dead code, hardcoding, waste | docs |

**Merge order:** #26 and #28 first — **#29 links to both** of their docs, so landing #29
alone leaves two temporarily dangling links. #27 (code) and #30 are independent.

**Branch hygiene — do NOT merge `claude/docs-optimization-review-a4l104`.** It carries 9
docs commits written against an *older lineage* (its `audit_2026-06-25.md` claims 521
tests / 35,688 LOC vs today's ~1,125 / 56,222) and it diverges on ~15 docs that `main`
has since moved forward — `HANDOFF_SYNOPSIS.md`, `architecture.md`, `assessment.md`,
`change_log.md`, `decisions.md`… **Merging it would revert newer content.** No PR was
opened for it; recommend abandoning/deleting the branch. Anything valuable in it is
superseded by #26–#30.

### Shipped since 2026-07-17 (not in the sections below)

- **Pillar 7 — self-improving skills** (2026-07-24): `core/ops_skills.py` renders
  `skills/content-ops/SKILL.md` from the live `@_register` registry (`ops gen-skills`);
  `core/skillopt.py` is a gated **proposal-only** loop in `overnight`
  (`SKILLOPT_ENABLED`) — it **never auto-edits live prompts** by design.
- **Scheduling upgrades**: clock-time upload input (`parse_local_time_input`) + learned
  post slots now rank by **average** engaged-rate (killed the weekend feedback loop).
- **Voices as config**: `config/voices.json` catalog + `ops voices`; **Qwen3-TTS** local
  voice-cloning provider; honest Free-mode readiness reporting.
- **Crash fixes**: retired free-model slug no longer kills a completed run; title/voice fixes.

### Known-inert capability ⚠ (operator has NOT installed the external additions)

All four cloned reference repos are **absent** (ComfyUI, ai-marketing-skills,
anything-to-notebooklm, system_prompts_leaks) and no `[providers]`/`[free]` backends are
installed. ~757 LOC of seam code is therefore **dormant — env-gated and fail-open**, so
nothing breaks, but three capabilities are silently unavailable (detail in #30):

1. **Free mode is not actually $0-ready** — it needs `piper` (local voice) and `ddgs`.
   Without `piper` it **blocks at render by design**. Fix: `pip install -e ".[free]"`.
2. **Expert-Panel grading (Pillar 2) has no personas** — `EXPERT_PANEL_ENABLED` is inert.
3. **The prompt-eval corpus harness has no corpus** to replay, so guardrail regressions
   aren't caught by it.

### Live findings a fresh session should know (from #28 / #30)

1. **`core/run_mode.free_mode_strict()` has ZERO importers** — all three paid seams
   (`llm_router:272`, `tts:253`, `apify_client:240`) reimplemented it privately. The
   canonical guard already exists and is being ignored; **~4-line fix**, and it's a
   correctness item (a new paid seam currently opts out of Free mode by default).
2. **The vision path is stranded and silently inactive** —
   `assets/thumbnail_scorer._vision_score` goes through the legacy `core/llm_client`
   (raw OpenAI SDK), bypassing the router *and* `cost_meter`. It guards on
   `OPENAI_API_KEY`; with paid chat off it returns `None` and falls back to heuristics
   **with no error**. Claude (paid, available) does vision, but the router can't carry an
   image (`_normalize_messages` is `list[dict[str, str]]`).
3. **`core/engagement.safe_infer_domain` returns `"neutral"` on any exception** — an
   import/DB hiccup silently re-opens **tag pollution** (UFC tags on gaming topics) with
   no warning. This is why two tests fail in a bare container.

### How to count metrics (three numbers, all correct)

Future audits should reconcile these rather than "correct" them:

| Number | What it is | Command |
|---|---|---|
| **1,139** | `def test_` definitions (static grep; includes helpers) | `grep -rh "def test_" tests/ \| wc -l` |
| **~1,125** | the green suite on a fully-installed machine | `python -m unittest discover -s tests` |
| **863** | what runs in a **bare** container — 148 modules can't import without heavy deps (90 × `sqlalchemy`) | same command, no deps installed |

Also: **56,222 LOC / 388 files** (`find . -name '*.py' … \| xargs wc -l`), ruff
**0.8.4** (CI-pinned — newer ruff reports false drift), mypy **106 errors / 68 files**.

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

Setup path (fresh machine): `py -m scripts.ops all-setup --channel tapin`.

---

## Open (roadmap next)

> **Do these first (cheap, and two change behavior):** ① use the existing
> `run_mode.free_mode_strict()` in all three paid seams (~4 lines, correctness);
> ② `pip install -e ".[free]"` so Free mode actually works; ③ narrow
> `safe_infer_domain`'s catch; ④ refresh the **Anthropic** default model IDs
> (`_DEFAULT_MODELS` still pins `claude-sonnet-4-…` on the live paid provider);
> ⑤ merge the five open PRs. Full ranking: #30 §5 and
> [strategy_2026H2.md](strategy_2026H2.md) §4 *(arrives with #29)*.

***Pillars 1–7 all shipped** (decisions §15–17) — the internal-systems reorientation
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
3. Supporting/unphased: O12 governor follow-ups, router vision path, Whisper local,
   MoneyWise depth, AI Tools/Tech groundwork.
4. Agent follow-ups: overnight facts-file intake (needs `generate_draft(key_facts=)`).
   *(`SEMANTIC_TRADE_VALIDATION` default-on is **done** — domain-gated to NBA/NFL in PR #27.)*
5. Vault housekeeping: cross-day dossier refresh leaves prior-day `_runs/` notes (same
   `run_id`, different date prefix) — safe but clutter; stable-path upsert is a follow-up.
6. One-time ops: re-auth `youtube.readonly` for tapin; `oauth_setup` for MoneyWise.

**Parked / excluded:** **Phase M — multi-platform stays parked** (operator decision,
2026-07). Eligibility was researched so it needn't be again: TikTok *Upload to Inbox /
Creator's Draft* needs **no audit** (human publishes from drafts), while **Direct Post**
needs a 2–4 week audit and **unaudited Direct Post is private-only**; Instagram needs a
Business/Creator account + linked FB Page + app review. Both audits are shaped for
*interactive multi-tenant apps*, which a solo headless pipeline is not — see
`roadmap.md` → Later horizons → Phase M. · Benable bot.

---

## Docs to read first

- `docs/roadmap.md` — **"Next up — all open items"** is the single forward list; Pillars 1–7 ✅
- `docs/decisions.md` §15 (pillar reorientation), §16 (Fact Engine), **§17 (vault OS)**
- `docs/credit_efficiency.md` — O1–O11 (all ✅)
- `docs/free_mode.md` — the $0 stack + `ops free-doctor` (**needs `.[free]` installed**)
- `docs/providers_runbook.md` — Pillar 6 tool → module → env → proof index
- `docs/debugging.md` — playbook vs facts, hallucination triage
- *Arriving with the open PRs:* `code_audit_2026-07.md` (#28) · `efficiency_audit_2026-07.md`
  (#30) · `strategy_2026H2.md` (#29) · `llm_provider_strategy.md` (#26)

---

## Key files

```
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
