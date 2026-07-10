# Content OS — New-Tools Documentation & 2026-Q3 Groundwork (3-month north star)

> A standing map for future work: (1) documents the new tools/repositories added in the 2026-07
> wave, (2) records the tested state of goose3 and why it matters, and (3) lays a detailed
> 3-month development roadmap. Written 2026-07-09. Companion to [roadmap.md](roadmap.md) (tactical
> phases), [providers_runbook.md](providers_runbook.md) (per-tool mechanics),
> [video_creation_stack.md](video_creation_stack.md) (slot design), and
> [tooling_landscape.md](tooling_landscape.md) (borrow/threat verdicts).
>
> Status snapshot: the 2026-07-06→08 wave (Pillars 1–6 baseline + goose3 + live-run quality fixes)
> is **working-tree only, not yet committed**, on `feat/reddit-free-backend-and-signal-persistence`.

---

# PART 1 — New tools & repositories added

Four external repos were cloned into the working tree (local-only, **gitignored** — each has its
own `.git`), plus new Python backends and a provider-seam framework. This section documents the
new additions and their integration status.

## 1.1 Cloned repositories (local reference/runtime, not embedded)

| Repo | What it is | Role in Content OS | Status |
|---|---|---|---|
| **ComfyUI/** (+ `ComfyUI-LTXVideo`) | Self-hosted node-graph server for image/video/upscale models | Single backend endpoint for AI b-roll (LTX-Video), thumbnails, upscaling — one HTTP client (`core/comfy_client.py`), many swappable models | **seam** — client + `workflows/` exist; needs a running GPU server + a saved workflow JSON |
| **ai-marketing-skills/** | Claude-Code skills lib (MIT); "Expert Panel" persona scorer, A/B stats, ICP learner | Optional qualitative pre-publish grading pass in Pillar 2 (`core/grade.py` + `prompts/expert_panel/`) | **seam** — loader + LLM loop exist; one example persona shipped; `EXPERT_PANEL_ENABLED` |
| **qiaomu-anything-to-notebooklm/** | Multi-source ingester (URL/PDF/podcast/YouTube → notes), MIT | *Pattern* (not the package) for the multi-source vault importer that grows the verified-fact base (`core/vault_ingest.py`) | **seam** — `ingest_url` is real (reuses goose3); PDF/YouTube-transcript are thin records |
| **system_prompts_leaks/** | Prompt-engineering corpus (CC0) — frontier-assistant system prompts | Reference corpus for the claim-verifier + a regression harness (`core/run_eval_corpus.py` over `prompts/eval_corpus/`) | **seam/reference** — runner skeleton exists; corpus files stay local (gitignored) |

## 1.2 Python backends / packages added

- **goose3** — added to **core deps** ([pyproject.toml](../pyproject.toml)); **IMPLEMENTED & live** (see §1.4).
- **`[providers]` optional extra** (install-on-demand, lazy-imported, fail-open): `kokoro`,
  `soundfile`, `whisperx`, `audiocraft`, `TTS` (XTTS-v2), `ultralytics` (AGPL — internal only).
  Planned add: `piper-tts` (CPU-only local TTS). None install in CI; each seam degrades to
  current behavior when its backend is absent.

## 1.3 Provider-seam framework (the "support layer" that hosts the above)

`core/providers.py` — a shared contract (`ProviderResult`, `resolve_order`, `selected_provider`,
`flag_enabled`, `run_chain`) generalizing the two patterns already in the repo
(`apis/signal_contract.make_signal` + the `assets/` fail-open chain). Rule for every seam:
**env-gated OFF by default · lazy-imports its heavy backend · fails open to current behavior.**

Tool → module → env → status (source of truth: [providers_runbook.md](providers_runbook.md)):

| Slot | Module | Env gate | Status |
|---|---|---|---|
| Article extraction | `core/link_facts.py` (`_goose3_body_lines`) | always-on, BS4 fallback | **implemented** |
| Local TTS | `core/tts.py` (`_try_alt_tts_provider`) | `TTS_PROVIDER=kokoro\|xtts\|piper` | seam (next phase) |
| Caption alignment | `core/caption_align.py` | `CAPTION_ALIGN_BACKEND=whisperx` | seam |
| Music/SFX bed | `core/music.py` | `MUSIC_PROVIDER=musicgen` | seam |
| AI video / ComfyUI | `core/comfy_client.py`, `assets/ai_video_provider.py` | `AI_VIDEO_PROVIDER`, `COMFYUI_URL` | seam |
| Expert-Panel grading | `core/grade.py` | `EXPERT_PANEL_ENABLED` | seam |
| Multi-source ingest | `core/vault_ingest.py` | `INGEST_ENABLED` | seam (`ingest_url` real) |
| Prompt-eval corpus | `core/run_eval_corpus.py` | `EVAL_CORPUS_LLM` | seam |
| Avatar / auto-reframe | `core/avatar.py`, `core/reframe.py` | `AVATAR_PROVIDER`, `REFRAME_ENABLED` | seam (stubs) |
| Distribution (n8n) | `core/events.py` (shipped) | `EVENT_WEBHOOK_URL` | wired |

**Excluded on purpose:** Higgsfield (paid); the `[search github]` repos (Real-ESRGAN/RIFE nodes,
youtube-automation-agent, gemini-youtube-automation, AutoSocial); ShortGPT; **MoneyPrinterV2**
(AGPL — never clone near the repo); ComplianceAsCode (category mismatch).

## 1.4 goose3 — tested verdict: **it works (on its target: news/blog articles)**

Measured 2026-07-09 (`_goose3_body_lines` on raw HTML), goose3-first with a BeautifulSoup fallback:

| Page type | Example | goose3 lines | Combined `_article_facts` |
|---|---|---|---|
| **Real news article** (its sweet spot) | PC Gamer article | **27 clean body lines** | 12 (capped) |
| Homepage / index | bbc.com/news | 2 | 12 (fallback carries) |
| Encyclopedic | Wikipedia GTA VI | 0 | 12 (fallback carries) |
| JS-heavy | MSN | 0 (headline-only) | title-only → `LINK_READER_PROXY` |

**Verdict:** goose3 is a genuine upgrade **exactly where it matters** — the news/blog article pages
an operator pastes as fact sources — pulling the full, clean article body (27 lines of coherent
prose vs the old blanket `<p>` scrape that let sidebar/nav chrome through). On non-article pages
(indexes, Wikipedia, JS-heavy) it correctly returns little and the **BeautifulSoup fallback + title
+ meta description carry the result with zero regression**. That is precisely why the design is
goose3-first *with* a fallback rather than goose3-only.

**Why it matters (this is the moat, not a nice-to-have):** Content OS's defensibility is *verifiable
substance* — grounding + the closed analytics loop. Cleaner article extraction means better source
lines for the claim verifier and fewer junk lines poisoning the corpus (junk is what pushed the
model to "fill gaps by inventing"). Highest-leverage grounding upgrade for near-zero cost/risk.

**Design note:** parses already-fetched HTML (`raw_html=`) → no second network call, existing
`requests.get` mocks stay authoritative; trade-tracker pages keep the specialised `<li>` extractor.
Tests: `tests/test_link_facts_goose3.py` (goose3-first, empty/error fallback, trade bypass).

**Next steps:** feed goose3 into the multi-source vault importer (Month 1) so every ingested URL
becomes a provenance-tagged note; use goose3 metadata (authors, publish_date, top_image) for
freshness/recency scoring; the MSN-class JS gap is already covered by the opt-in reader proxy.

---

# PART 2 — Current state, pace & guiding thesis

**Shipped (2026-07-06 → 07-08, working tree):** Pillars 1–5 (run ledger, video grading, fact
engine 2.0, Obsidian knowledge OS, agent layer), Pillar 6 **baseline provider seams + goose3**, and
a live-run quality wave (script framing, best-bet freshness/anchor-diversity, MSN scrape warning,
Apify-403→free fallback). CI green (905 tests); nothing committed yet.

**Pace:** with agent-assisted development the project ships multiple subsystems per day (5–6
"pillars" in ~3 days). Implication: the 3-month plan is **not calendar-bound by effort** — it's
bound by (a) external infra (GPU for the visual-gen tier) and (b) *data gating* (calibration /
predictor need publish volume). Sequence by moat-priority + dependency, not by hours.

**Thesis that orders everything (do not drift):** the moat is **grounding + the closed loop + 2026
compliance**, self-hosted, on proprietary performance data — NOT the generator. Generation quality
(Pillar 6) is an *additive* lever that must never wreck margin or the authenticity/disclosure gate.
Priority ladder: **(1) cost + grounding + captions → (2) generation quality that differentiates →
(3) reach/distribution → (4) new verticals.**

---

# PART 3 — 3-month groundwork (2026-07 → 2026-10)

Each item: **goal · files/seam · deps · risk · done-when.** ✅ = already shipped this wave (listed
so future runs see the full arc).

## Month 1 — Cost, grounding, captions (no GPU required; highest ROI)

1. **Local TTS provider chain (Kokoro / Piper / XTTS)** — *the cost lever.*
   - Goal: rendered TTS from ~$0.30/video (96% of run cost) → ~$0.
   - Files: `core/tts.py` (transcode local synth → the expected `.mp3`; today the seam returns a
     `.wav` that `core/pipeline.py:490` ignores → render would break), `core/cost_meter.py` ($0 for
     local), `pyproject.toml` (`piper-tts`).
   - Deps: Kokoro/XTTS need torch (GPU-preferred); **Piper is CPU/ONNX — the Windows-box path.**
   - Risk: low (fail-open to ElevenLabs). Done-when: `TTS_PROVIDER=piper` renders a real mp3 and the
     run summary shows `tts $0.0000`; ElevenLabs unchanged when unset.
2. **Whisper local alignment** — word-timing for *any* TTS.
   - Goal: karaoke/word captions for local TTS (emits no timestamps) + unlock clip-from-source.
   - Files: `core/caption_align.py` (seam) → wire into `video/caption_timing.py` when ElevenLabs
     timestamps are absent. Deps: `whisperx`/`faster-whisper` (torch). Risk: low.
3. **Multi-source vault importer** — grow the verified-fact base (moat).
   - Goal: `URL/PDF/YouTube → provenance-tagged vault note` feeding `core/obsidian_facts`.
   - Files: `core/vault_ingest.py` (flesh out `ingest_pdf` via markitdown/pypdf, YouTube transcript),
     add an `ops ingest` subcommand (`scripts/ops.py` `@_register` pattern). Reuses goose3. No GPU.
   - Risk: low. Done-when: `ops ingest <url>` writes a tiered note that `load_fact_records` reads.
4. ✅ **goose3 grounding** · ✅ **best-bet freshness + anchor diversity** · ✅ **MSN scrape warning +
   reader proxy** · ✅ **Apify-403 → free fallback**.
5. **Free-backend probes (optional)** — TikTok/Twitter equivalents of the yt-dlp/Reddit-OAuth
   backends, *only if the Apify bill justifies it* (`apis/free_backends.py`).

## Month 2 — Generation quality & visual tier (GPU-gated; the headline upgrade)

6. **Music/SFX bed (MusicGen)** — big perceived-quality jump, low effort.
   - Files: `core/music.py` (seam) → duck under VO in the FFmpeg mix (`video/render_video.py`); mood
     from the research brief. Deps: `audiocraft` (torch). Risk: medium (render-mix wiring).
7. **AI video-gen slot via ComfyUI + LTX-Video** — prompt-matched footage per scene beat.
   - Files: `core/comfy_client.py` + `assets/ai_video_provider.py` (register into
     `assets/manager._PROVIDERS` behind `AI_VIDEO_PROVIDER`); a saved `workflows/ltx_broll.json`.
   - Deps: a **GPU box** (RunPod/Modal) running ComfyUI + LTX-Video. Risk: medium-high (quality,
     latency, cost/clip-second — must be cost-metered). Start behind a flag on tapin only.
8. **Thumbnail text-models (Ideogram/Recraft)** — better text-in-thumbnail; A/B via the existing
   `thumbnail_style` harness. Files: extend `assets/flux_thumbnail.py`.
9. **Expert-Panel grading pass** — flesh out `core/grade.py` into an optional Pillar 2 qualitative
   read beside the deterministic report card. No new dep (uses `core/llm_router`).
10. **Upscale/interpolation (Real-ESRGAN / RIFE)** — polish AI b-roll. *(Was excluded as a
    `[search github]` item — revisit once ComfyUI is running; they're ComfyUI nodes.)*

## Month 3 — Reach, verticals, calibration (compounding + data-gated)

11. **Dual-format render (9:16 / 16:9 / 1:1)** — cheap reach; a "format profile" abstraction over
    the FFmpeg render step. No new dep. *(Borrow the shape from the excluded gemini repo, not code.)*
12. **n8n companion recipe pack** — cross-post/repurpose/Discord-digest keyed to `core/events.py`
    webhooks. Reach without in-repo publishers; the deferred Phase-M hedge.
13. **Clip-from-source (Phase R)** — long video/VOD/podcast → transcribe (Whisper, Month 1) → LLM
    moment scoring (reuse `core/hook_score`) → subject-tracked 9:16 cut (`core/reframe.py`). Pairs
    with idea-intake (already accepts YouTube links). Note: YOLO reframe is AGPL → internal only.
14. **MoneyWise depth wave + third vertical groundwork** — finance earnings-calendar signal + ticker
    watchlist ([domain-expansion.md](domain-expansion.md)); dry-run the new-channel playbook for AI-Tools/Tech.
15. **Pillar 2 calibration/predictor + multimodal review** — activate as publish volume accrues; the
    rendered-video review needs the **router vision path** (migrate the thumbnail scorer off
    `core/llm_client.py`) — a prerequisite to schedule early.
16. **Engineering hygiene (continuous):** tighten the mypy baseline (~111 errors), raise
    render/publish test coverage (the acknowledged soft spot), CI coverage reporting; **commit the
    2026-07-08 wave** and push the private GitHub remote.

---

# PART 4 — Adjacent projects (only if they serve the core purpose)

Filter: does it harden the moat (grounding/loop/compliance) or reduce cost/effort for the
*existing* channels? If it's "more generation volume," skip it (operating_plan §8 thesis).

- **GPU render worker (RunPod/Modal)** — *warranted.* The "on-device fast path" (Kokoro/Piper TTS +
  LTX-Video + local Whisper + MusicGen) needs a per-second GPU box. Enabling infra for the entire
  Month-2 visual tier and the ~$0-marginal render. Build as a thin job-worker that pulls render jobs
  and returns artifacts. Highest-value adjacency.
- **n8n companion repo** — *warranted, low effort.* A recipe pack (not in-repo publishers) downstream
  of the webhook events. Distribution reach that respects the "no platform clients in core" stance.
- **Shared prompt/eval harness** — *warranted.* `core/prompt_evals` + `core/run_eval_corpus` + the
  system_prompts_leaks corpus, factored so prompt regressions are caught across channels.
- **NOT warranted:** standalone faceless-generator clones (ShortGPT-class), anything AGPL you'd ship
  (YOLO/MoneyPrinterV2 code), platform-native auto-posters with ToS/detection risk (AutoSocial), or a
  second pipeline. Borrow patterns, never a parallel stack.

# PART 5 — Code-sharing & reuse opportunities

- **Extract a "Content OS core" library** — the channel-agnostic spine: `core/providers.py`, Pillar 1
  run ledger, Pillar 3 fact engine, `core/llm_router`, and the `channels.json` profile abstraction. A
  new vertical/channel should spin up from config, not code. Single biggest reuse lever; de-risks the
  "operate media businesses" vision.
- **The grounding/fact-engine as the crown jewel** — the most valuable shareable asset internally;
  keep its interfaces clean (`load_fact_records`, `verify_claims`, tiered corpus) so every surface
  (interactive, headless, batch, future verticals) consumes one grounding layer.
- **Provider-slot framework as the integration standard** — every future tool lands as a fail-open,
  env-gated seam behind `ProviderResult`; documented once in `providers_runbook.md`.
- **New-channel playbook generator** — turn `domain-expansion.md` + the profile schema into a
  scaffolder that emits a channel profile + SEO config + signal-coverage audit for a new vertical.

# PART 6 — Risks, constraints & licensing (carry forward)

- **Apify credit fragility** (a 403 killed reddit/twitter/tiktok in a live run) — free backends are
  the hedge; the auto-degrade-on-disable fallback (shipped) reduces blast radius.
- **YouTube Analytics has no CTR/impressions** (Studio-only) — thumbnail→CTR attribution is
  externally blocked; keep attributing engaged-rate until Google ships the metric.
- **2026 authenticity enforcement** — every generation upgrade MUST keep the AI-disclosure +
  authenticity gate (`core/authenticity.py`, `core/description_extras.py`); richer/realistic AI video
  *increases* the need for disclosure. Compliance is a revenue-protecting feature, not overhead.
- **Licensing:** Apache/MIT/OpenRAIL are commercial-safe (Wan, LTX-Video, Mochi, MusicGen, **Kokoro**,
  **Piper**, faster-whisper); **AGPL** (Ultralytics YOLO, MoneyPrinterV2) is internal-use/pattern-only
  — flag before shipping. Some hot video weights are research/non-commercial (check per model).
- **Data gating** — Pillar 2 calibration/predictor and best-bet analytics only sharpen with publish
  volume; don't over-tune on thin samples (the confidence-note discipline already exists).

# PART 7 — Backlog / parked (do not build until pulled forward)

Phase M multi-platform publishers (TikTok/Instagram — behind quality first); Benable bot; Bluesky
signal; full operator dashboard/Command Center; asset-effectiveness ranking; broad Tavily research.
Deferred, volume-gated, or superseded — kept here so future runs don't rediscover them.

---

## Immediate next action
Commit the 2026-07-08 wave (seams + goose3 + quality fixes), then start **Month-1 #1: local TTS**
(the cost lever) — the highest-ROI, no-moat-risk next step.
