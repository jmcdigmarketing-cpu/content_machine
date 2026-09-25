# Tooling Landscape — 17 tools vs Content OS (2026-07)

> **Class:** snapshot · **Status:** frozen · **Reviewed:** 2026-09-20

A competitive/tooling scan of 17 external projects and market guides, each mapped
against Content OS's moat. Companion to [positioning.md](positioning.md),
[operating_plan.md](operating_plan.md) §8, and [roadmap.md](roadmap.md) "Market
positioning (2026)" — this extends, not replaces, those. Purpose is
decision-useful: for each tool, **borrow / overlap-threat / complement / reference
/ irrelevant**, and a concrete takeaway tied to a real module.

> **Maturity figures are approximate** (star/fork counts from a July-2026 web
> scan; they drift). Read them as an order-of-magnitude "is this alive and
> adopted" signal, not a spec. Where a repo looked abandoned or empty it is
> flagged plainly.

---

## The lens (why these verdicts)

Content OS's moat is **not the generator** — faceless script→TTS→render→upload is
a commodity (see the six generators below, all of which do it). The moat is the
**full closed loop, self-hosted, on a verifiable-substance spine**:

decide → **research with verified facts** (tiered grounding + claim verifier,
Pillar 3) → generate → grade before publish (Pillar 2) → publish → **learn from
real engagement** (analytics loop) → write it all back to a knowledge OS
(Pillar 4) and a run ledger (Pillar 1).

Per [operating_plan.md](operating_plan.md) §8, *"the real threat is not other
builders — it's the platforms,"* and the defense is **proprietary,
causally-validated performance data**. So every judgment here asks one question:
*does this tool touch the loop/grounding/data moat, or is it just another way to
render a video?* Borrow what hardens the moat; ignore what only adds generation
volume.

**The decisive finding:** across all 17, **not one** combines fact-grounding
*and* a closed analytics learning loop. The two closest (AI-Content-Studio has
grounding; youtube-automation-agent has an analytics loop) each hold only half.
That gap *is* the moat.

---

## Verdict table

| # | Tool | Category | Maturity | Verdict | One-line takeaway |
|---|------|----------|----------|---------|-------------------|
| 1 | [ShortGPT](https://github.com/RayVentura/ShortGPT) | Faceless generator | ~7.4k★, slowing (last release Feb 2025) | Overlap (no moat) | Commodity idea→render; borrow its resumable state pattern only |
| 2 | [MoneyPrinterV2](https://github.com/FujiwaraChoki/MoneyPrinterV2) | Faceless generator | ~30k★, active, AGPL-3.0 | Overlap-threat | Highest-star rival; cost/velocity play, zero substance — borrow cost tactics |
| 3 | [AI-Content-Studio](https://github.com/naqashafzal/AI-Content-Studio) | Faceless generator | ~0.5k★, active | **Closest threat** | Only rival with fact-checking; missing the analytics loop |
| 4 | [Higgsfield](https://higgsfield.ai/) | AI media-gen suite | Closed SaaS, well-funded | Complement (provider) | A media *provider*, not a pipeline; potential b-roll/thumbnail source |
| 5 | [youtube-automation-agent](https://github.com/darkzOGx/youtube-automation-agent) | Faceless generator | ~1.5k★, active, Node | **Half-moat threat** | Has the analytics-feedback loop but no grounding; validates Pillar 5 |
| 6 | [AutoSocial](https://github.com/Katzca/AutoSocial) | Multi-platform poster | ~0.2k★, single dev, early | Complement | Local browser posting — a Phase M distribution idea, not a rival |
| 7 | [Marvomatic/n8n-templates](https://github.com/Marvomatic/n8n-templates) | n8n recipe pack | ~1.5k★, active | Complement | SEO/analyst n8n recipes downstream of our webhooks |
| 8 | [lucaswalter/n8n-ai-automations](https://github.com/lucaswalter/n8n-ai-automations) | n8n recipe pack | ~1.5k★, active | Complement | The distribution/repurposing layer for our `run_completed` events |
| 9 | [ericosiu/ai-marketing-skills](https://github.com/ericosiu/ai-marketing-skills) | Claude-Code skills | ~2.8k★, MIT, active | Reference | "Expert Panel" persona scoring → richer pre-publish grading |
| 10 | [gemini-youtube-automation](https://github.com/ChaitanyaEswarRajeshJakki/gemini-youtube-automation) | Faceless generator | ~0.3k★, MIT | Overlap (borrow one) | Dual-format render (16:9 + 9:16 from one script) is a clean win |
| 11 | [anything-to-notebooklm](https://github.com/joeseesun/qiaomu-anything-to-notebooklm) | Ingestion | ~5.5k★, MIT, active | Borrow | Multi-source → knowledge ingestion for the Obsidian OS |
| 12 | [python-goose](https://github.com/grangier/python-goose) | Scraping lib | ~4k★, **stale (Py2-era)** | Reference (use goose3) | Article-extraction ideas for `link_facts.py`; adopt the maintained fork |
| 13 | [system_prompts_leaks](https://github.com/asgeirtj/system_prompts_leaks) | Prompt archive | ~52k★, CC0, active | Reference | Prompt-engineering corpus for the verifier + prompt-eval set |
| 14 | [ComplianceAsCode/content](https://github.com/ComplianceAsCode/content) | Security compliance | ~2.8k★, active | **Irrelevant** (naming analogy only) | "Compliance-as-code" identifier scheme — thin analogy for provenance tags |
| 15 | [youtubeniches guide](https://youtubeniches.com/blog/ai-youtube-automation-complete-guide-2026) | Market guide | — | Positioning intel | Validates 2026 disclosure penalties + faceless viability |
| 16 | [directai roundup](https://www.directai.app/blog/best-ai-tools-for-youtube-automation) | Market guide | — | Positioning intel | Confirms no market tool ships grounding+loop; "automation ≠ quality" |
| 17 | [qiaomu (dup)](https://github.com/joeseesun/qiaomu-anything-to-notebooklm) | Ingestion | see #11 | — | Listed twice in the brief; same repo as #11 |

---

## A. Faceless short-form generators

*These are the direct-category tools. All render idea→script→TTS→video→upload.
None has both grounding and a learning loop — the recurring theme.*

### 1. ShortGPT — `Overlap (no moat)`
Automates Shorts/TikTok: script → multi-language TTS → web-sourced visuals →
captions → MoviePy render. Stack: OpenAI/Gemini scripts, ElevenLabs/EdgeTTS,
Pexels/Bing images, TinyDB state. ~7.4k★ but momentum slowing (last release
Feb 2025, experimental). **No grounding, no analytics.** Mirrors Content OS's
production tail feature-for-feature — and stops there.
- **Borrow:** its TinyDB resumable-workflow state is a lighter analog of our run
  ledger; nothing we need (Pillar 1 already exceeds it).
- **Threat read:** only becomes a threat if someone bolts a fact corpus + analytics
  loop onto it — i.e. rebuilds our moat. Low probability; that's the hard part.

### 2. MoneyPrinterV2 — `Overlap-threat`
The category's popularity leader (~30k★, AGPL-3.0, active). Multi-channel
(Twitter bot + YouTube Shorts + affiliate + cold outreach), CRON-scheduled.
Stack is aggressively **free/cheap**: gpt4free, KittenTTS, optional local Ollama,
MoviePy, Selenium. **No research, no grounding, no learning loop** — pure
monetization velocity.
- **Borrow (real):** its cost posture. Content OS already routes free-first
  ([llm_router.py](../core/llm_router.py)); MoneyPrinterV2's KittenTTS/local-first
  stance is a reminder that **TTS is now the dominant per-video cost** — worth a
  local-TTS provider slot behind the existing cost meter.
- **Threat read:** competes on speed+cost, not substance. AGPL-3.0 also makes it
  unattractive to lift code from. Our answer is the authenticity/compliance layer
  the 2026 policy now rewards (see §D) — velocity-over-substance is exactly what
  YouTube demonetized.

### 3. AI-Content-Studio — `Closest threat`
The only rival here with **visible fact-grounding**: a "Deep Research" step
(Google Search + NewsAPI) with a fact-check pass before TTS, plus multi-voice
narration and full SEO automation. Stack: Gemini 2.5 Flash + Vertex Imagen,
FFmpeg, CustomTkinter GUI. ~0.5k★, active, community-scale.
- **Why it matters:** it independently arrived at half of our thesis (grounding).
  It has **no closed analytics loop** — no post-publish engagement feeding topic/
  length/timing — so it can research but can't *learn*.
- **Borrow:** its tiered research→verify→generate ordering validates our Pillar 3
  design; nothing to adopt, but the closest external proof the approach is right.
- **Threat read:** the mid-market tool to watch. If it adds an analytics loop it
  converges on us — our lead is Pillars 1–4 + the grading calibration already
  shipped. Keep the loop + data moat widening.

### 4. Higgsfield — `Complement (media provider)`
Not a pipeline — a closed-source **AI media-generation suite** (text→video/image,
upscaling, 40+ creative tools, Premiere/DaVinci plugins; multi-model incl. Gemini
Omni, Claude via MCP, Kling/Seedance). Well-funded, ~4.5M videos/day claimed.
Different user (designer/animator), no scripting/publish/analytics.
- **Borrow / complement:** treat as a candidate **b-roll/thumbnail provider**
  behind the existing asset chain ([assets/composite.py](../assets/composite.py),
  Flux thumbnails) if its API is reachable — a quality lever, not a competitor.
- **Threat read:** low. It sells generation horsepower; we sell the loop. It would
  have to add scripting+publishing+learning to compete (against its own focus).

### 5. youtube-automation-agent — `Half-moat threat`
Seven-agent orchestration (strategy → script → thumbnail → SEO → production →
publish → **analytics**) with a real scheduled feedback loop (daily runs, weekly
strategy reviews). Node/Express/SQLite, OpenRouter (300+ models), FFmpeg,
Playwright. ~1.5k★, active. **Has the analytics-loop half, lacks grounding.**
- **Validates Pillar 5:** its agent-orchestration + scheduled-review shape is
  exactly the [roadmap.md](roadmap.md) Pillar 5 "Channel Health Agent + weekly
  analyst + overnight operator" — external confirmation that direction is live in
  the market. Our version composes it *on top of* graded, verified, ledgered data.
- **Borrow:** the "weekly strategy review" cadence maps onto our `ops daily-brief`
  + planned `ops analyst`; the OpenRouter-abstraction is already our `llm_router`.
- **Threat read:** the other half-moat rival. Dangerous only if it adds grounding.

### 6. AutoSocial — `Complement`
No AI at all: a **local, browser-driven multi-platform poster** (TikTok/Instagram/
YouTube via Playwright), with FFmpeg "uniquification" and yt-dlp. ~0.2k★, single
dev, early. Solves distribution, not creation.
- **Borrow / complement:** relevant to the **deferred Phase M** (multi-platform
  distribution, currently parked). Local browser posting sidesteps API quotas/
  deprecation — an alternative to building N platform API clients when Phase M
  eventually unparks. Note: browser automation risks ToS/detection issues; weigh
  against the API path.

---

## B. Workflow / agent recipe packs

*Not competitors — these are the ecosystem Content OS's webhook events
(`core/events.py`: `run_completed` / `video_published` / `batch_completed`) are
meant to feed, plus one agent-skill reference.*

### 7. Marvomatic/n8n-templates — `Complement`
~15 n8n templates for SEO/content: keyword-rank tracking, SERP/gap analysis, an
"SEO Data Analyst Agent" (natural-language queries over BigQuery), an "AI Overview
Optimizer." Google/BigQuery nodes, largely rule-based. ~1.5k★, active. No video.
- **Borrow:** the **NL-over-warehouse analyst** pattern is the n8n mirror of our
  `weekly-report` / `ops analyst` — a downstream recipe an operator could wire to
  our data, not something to build in-repo.

### 8. lucaswalter/n8n-ai-automations — `Complement`
40+ n8n **AI** agent workflows: a "Content Repurposing Factory" and "Viral YouTube
Clipper" (video → shorts/social), UGC ad generators. Rich provider set (OpenAI/
Gemini/Claude/ElevenLabs/HeyGen/Firecrawl/Apify). ~1.5k★, active.
- **Borrow / complement (highest-value in this group):** this is the concrete
  **distribution layer** for our pipeline. Content OS publishes → fires
  `video_published` webhook → an n8n workflow like these repurposes/cross-posts.
  A small **companion n8n recipe pack** keyed to our webhook payloads is the
  cleanest way to get Phase-M-style reach *without* building publishers in-repo.

### 9. ericosiu/ai-marketing-skills — `Reference`
A Claude-Code **skills** library (~2.8k★, MIT, Python): statistical A/B testing,
an ICP win/loss learner, and an **"Expert Panel"** that invokes domain personas to
recursively score content until it clears a threshold. Most mature in this group.
- **Borrow:** the **Expert Panel persona-scoring** pattern is directly adoptable
  into Pillar 2 grading ([core/video_grade.py](../core/video_grade.py)): today the
  report card is heuristic rollup; a persona panel (shorts-editor, skeptic,
  SEO) could add a qualitative pre-publish read. Its statistical-testing rigor also
  echoes our low-n Bayesian experiment harness. Reference architecture, not a dep.

### 10. gemini-youtube-automation — `Overlap (borrow one)`
A simple autonomous Python pipeline (Gemini 2.5 Flash script/metadata, Pexels,
gTTS, MoviePy, GitHub-Actions cron, `content_plan.json` state). ~0.3k★, MIT,
education niche. Much narrower than Content OS, no grounding/loop.
- **Borrow (clean win):** **dual-format rendering** — one script → both a 16:9 and
  a 9:16 cut. A "format profile" abstraction over the FFmpeg render step would let
  Content OS emit multiple aspect ratios without re-scripting/re-TTS — cheap reach
  and directly useful when Phase M unparks.

---

## C. Ingestion / knowledge / prompts / scraping

### 11. anything-to-notebooklm (qiaomu) — `Borrow`
~5.5k★, MIT, active. Ingests 15+ source types (articles, podcasts, YouTube, PDFs,
social) → NotebookLM formats; paywall bypass for 300+ sites; recursive "12-question"
deep-analysis tiers; markitdown + Playwright.
- **Borrow (maps to Pillar 4):** its **multi-source ingestion** is the natural
  feeder for the Obsidian knowledge OS ([core/obsidian_facts.py](../core/obsidian_facts.py)):
  a "URL/podcast/PDF → vault note with provenance frontmatter" importer would let
  the operator grow the verified-facts vault from more than pasted text. Its
  recursive-tiering also rhymes with our tiered grounding corpus.
- **Not a threat:** different philosophy (pipeline-agnostic converter vs our
  vault-centric, provenance-tiered fact store).

### 12. python-goose — `Reference (adopt the maintained fork)`
Article-extraction library: main text, metadata, images, embedded video,
multi-language. ~4k★, Apache-2.0 — but the original `grangier/python-goose` is
**Python-2-era and effectively stale**; the maintained successor is
**`goose3`**.
- **Borrow:** extraction robustness for [core/link_facts.py](../core/link_facts.py)
  (our pasted-link fact scraper, which already junk-filters ESPN/WAF noise). If
  scrape quality becomes a live-run pain point, a `goose3` spike is the reference
  implementation for clean main-text + metadata extraction. Adopt `goose3`, not
  this repo.

### 13. system_prompts_leaks — `Reference`
~52k★, CC0, actively updated (Claude/GPT/Gemini incl. Claude Code system prompts,
refreshed mid-2026). Not a tool — a **prompt-engineering corpus**.
- **Borrow:** a reference when tuning the claim-verifier prompt
  ([core/claim_verifier.py](../core/claim_verifier.py)) and the prompt-eval rubric
  ([core/prompt_evals.py](../core/prompt_evals.py)) — see how frontier assistants
  structure guardrails/refusals/citation instructions. Reference only; nothing to
  import.

### 14. ComplianceAsCode/content — `Irrelevant (naming analogy only)`
Security-compliance IaC (SCAP/Ansible/NIST/STIG/CIS for Linux). ~2.8k★, active,
but **architecturally unrelated** to a video pipeline — included only because the
brief listed it.
- **Thin analogy:** its standardized identifier scheme (CCE/NIST IDs mapping one
  control across frameworks) is a distant echo of our **provenance tiers**
  ([core/fact_store.py](../core/fact_store.py) `tier`/`verified_at`) and the
  "compliance-as-code" naming rhymes with our authenticity-compliance layer. No
  code, no pattern to adopt. **Do not pursue.**

---

## D. Market guides (positioning intel)

### 15. youtubeniches — "AI YouTube Automation Complete Guide 2026"
- **Recommended 2026 stack:** Perplexity/Claude/GPT-4o (research/script),
  **ElevenLabs ("gold standard" voiceover)**, Runway/Storyblocks/CapCut/Opus Clip;
  ~$166/mo. (Content OS already uses ElevenLabs — on-consensus.)
- **Policy (validates our compliance layer):** 2026 disclosure of AI voice/likeness
  is **mandatory**; the guide cites ~15–30% ad-revenue suppression for 90 days on
  non-disclosure. This is exactly what Content OS's AI-disclosure + authenticity
  gate ([core/authenticity.py](../core/authenticity.py), `core/description_extras.py`)
  are built for — the compliance layer is a **revenue-protecting feature**, not
  overhead.
- **Faceless:** confirmed viable at scale (Magnates Media ~1.2M subs). Faceless is
  fine; *synthetic-and-shallow* is what gets demonetized — aligns with our thesis.

### 16. directai — "Best AI Tools for YouTube Automation"
- **Named field:** TubeBuddy, vidIQ, ChatGPT/Claude, Jasper, ElevenLabs, Murf,
  Pictory, InVideo AI, **DirectAI** (their own "end-to-end" tool). Extends the
  [operating_plan.md](operating_plan.md) §8 competitor table (Pictory/InVideo/Murf
  are new names worth tracking; DirectAI is the closest "EOTP pipeline").
- **Key admission (our whole thesis, in their words):** *"No tool… removes the
  judgment required to pick topics your audience cares about"* — automation ≠
  quality. **None of the 10 named tools ships claim-verification or a compliance/
  grading layer.** The market gap Content OS occupies is real and unfilled.
- **Faceless:** "not against YouTube's ToS" (matches the disclosure-not-ban stance).

---

## Synthesis

### Borrow shortlist (each maps to a real module)
1. **n8n companion recipe pack** for the webhook events (`core/events.py`) — lift
   the *shape* of lucaswalter's repurposing/clipper workflows as downstream n8n
   recipes keyed to our `video_published` payload. Reach without in-repo publishers.
   *(pairs with the parked Phase M.)*
2. **Multi-source vault ingestion** (Pillar 4 extension) — an anything-to-notebooklm-
   style "URL/PDF/podcast → provenance-tagged vault note" importer feeding
   `core/obsidian_facts.py`. Grows the verified-fact base beyond pasted text.
3. **Dual-format render profiles** — gemini-youtube-automation's one-script→16:9+9:16
   pattern over the FFmpeg render step. Cheap reach, Phase-M-ready.
4. **Expert-Panel persona grading** (Pillar 2) — ericosiu's recursive persona
   scorer as an optional qualitative pass in `core/video_grade.py`.
5. **`goose3` scrape hardening** — reference implementation for `core/link_facts.py`
   if pasted-link extraction quality regresses in live runs. (Spike, not a rewrite.)
6. **Local-TTS provider slot** — MoneyPrinterV2's free/local-first stance is a
   reminder TTS now dominates per-video cost; a local-TTS option behind the cost
   meter is the highest-leverage cost lever left.
7. **Prompt references** — system_prompts_leaks as a corpus when tuning
   `core/claim_verifier.py` + `core/prompt_evals.py`.

### Where Content OS is already ahead
- **Grounding + closed loop together** — the one combination no tool in this scan
  ships. AI-Content-Studio has grounding; youtube-automation-agent has the loop;
  Content OS has both, plus grading calibration (Pillar 2) and a run ledger/
  knowledge OS (Pillars 1 & 4) none of them approach.
- **Compliance as a revenue feature** — the 2026 disclosure regime (guides §D)
  *rewards* exactly what the generators skip.
- **Self-hosted, data-owning** — the moat is the proprietary performance history;
  SaaS rivals (Higgsfield, DirectAI) can't hand that to a competitor and can't
  reconstruct yours.

### Genuine threats (and the defensive read)
- **The half-moat convergers** (AI-Content-Studio adding a loop; youtube-automation-
  agent adding grounding). Defense: keep widening the *data* moat — calibrated
  grading + causal experiment history is the part they can't clone by adding a
  feature. (This is [operating_plan.md](operating_plan.md) §8's thesis verbatim.)
- **Platform-native pipelines** (the real threat per §8) — if YouTube/Google ship
  one-click research→video→upload, the generators die; Content OS survives on the
  one thing platforms won't hand over: *your* channel's causal performance data.
- **Well-funded media-gen** (Higgsfield-class) — not a pipeline threat; convert to
  a provider if useful.

### Do NOT adopt
- **ComplianceAsCode** — category mismatch; naming analogy only.
- **Original `python-goose`** — stale; use `goose3` if anything.
- **Copying AGPL source** (MoneyPrinterV2) — pattern-borrow only; don't lift code.

> **Update (2026-07-07, decisions §17):** the earlier "don't invest in
> generation / don't chase quality" stance is **overridden**. Generation quality
> is now a lever — the full add-list is [video_creation_stack.md](video_creation_stack.md)
> (AI video-gen, local TTS, music/SFX, thumbnail text-models, clip-from-source,
> etc., all as cost-metered provider slots). Grounding + the loop still stand.

---

## Actionable next steps (ranked, moat-first)

1. **[borrow] n8n webhook companion pack** — document 2–3 n8n recipes triggered by
   `core/events.py` payloads (cross-post, Discord digest, sheet log). Low effort,
   unlocks reach downstream of the parked Phase M. *(pairs with existing webhooks.)*
2. **[borrow] Multi-source vault importer** — smallest useful slice: `URL → goose3
   extract → provenance-tagged `_sources`/`_facts` note`. Compounds Pillar 4 and the
   fact engine. Folds in the `goose3` spike (#5 above).
3. **[borrow] Dual-format render profiles** — format-profile abstraction over the
   render step; ships reach cheaply and de-risks Phase M.
4. **[evaluate] Local-TTS provider slot** — behind the cost meter; the last big
   per-video cost lever (MoneyPrinterV2's lesson).
5. **[evaluate] Expert-Panel grading pass** — optional persona scorer in Pillar 2,
   gated so it never blocks (mirrors the authenticity gate's opt-in posture).
6. **[ignore, logged] ComplianceAsCode, original python-goose, any "add more
   generation" idea** — recorded here so the loop is closed.

*Updated stance (decisions §17): alongside the loop/grounding/data moat, we now
**also** invest in generation quality — see [video_creation_stack.md](video_creation_stack.md)
for the video-creation provider slots to build.*

---

## Ranking — the 17 by value to Content OS

*Ranked by how much adopting/borrowing helps the project **now** (real module
mapping × maturity × fills-a-gap × low friction). The brief listed
qiaomu/anything-to-notebooklm twice, so there are 16 unique resources.*

| Rank | Resource | Verdict | Why it ranks here |
|---|---|---|---|
| 1 | goose3 (← python-goose) | Borrow | Hardens fact intake (`core/link_facts.py`) — grounding is the moat; free, near-drop-in |
| 2 | anything-to-notebooklm | Borrow | Multi-source → provenance-tagged vault notes (Pillar 4); grows the verified-fact base |
| 3 | ericosiu/ai-marketing-skills | Reference→Borrow | Mature MIT "Expert Panel" persona-scoring → richer Pillar 2 grading |
| 4 | lucaswalter/n8n-ai-automations | Complement | Distribution/repurposing layer downstream of `core/events.py` webhooks — reach |
| 5 | system_prompts_leaks | Reference | Free prompt-engineering corpus for the verifier + prompt-evals; ongoing value |
| 6 | AI-Content-Studio | Reference (watch) | Closest thesis-aligned rival (has grounding, no loop) — proves the approach |
| 7 | youtube-automation-agent | Reference | Validates Pillar 5 (agent orchestration + weekly review cadence) |
| 8 | gemini-youtube-automation | Borrow (one) | Clean dual-format render tactic (one script → 9:16 + 16:9) |
| 9 | Marvomatic/n8n-templates | Complement | SEO "analyst agent" n8n recipes downstream of our data |
| 10 | youtubeniches 2026 guide | Intel | Validates the authenticity/disclosure strategy + faceless viability |
| 11 | directai roundup | Intel | Competitor watch (DirectAI/Pictory/InVideo) + confirms the grounding+loop market gap |
| 12 | Higgsfield | Complement (paid) | Optional media-provider quality lever — not free |
| 13 | AutoSocial | Complement (parked) | Local browser posting — a Phase-M hedge, low near-term value |
| 14 | ShortGPT | Overlap | Commodity generator; its resumable-state pattern is already exceeded by Pillar 1 |
| 15 | MoneyPrinterV2 | Overlap-threat | AGPL-3.0 blocks code reuse; only a cost-posture idea (local TTS) survives |
| 16 | ComplianceAsCode/content | Irrelevant | Category mismatch; naming analogy only — do not pursue |

## Top 10 free (OSS) tools to actually adopt

*Genuinely free / self-hostable, highest leverage, each mapped to a slot/module.
Spans the moat (grounding) **and** the new video-quality investment (decisions §17).*

| # | Tool | Slot / module | Payoff |
|---|---|---|---|
| 1 | **faster-whisper / WhisperX** | captions/alignment (stack §3) | Local word-timing for *any* TTS + unlocks clip-from-source (Phase R) |
| 2 | **Kokoro-82M** (TTS) | `core/tts.py` (stack §2) | Free local voice — kills the dominant per-video cost |
| 3 | **goose3** | `core/link_facts.py` (#1 above) | Cleaner fact extraction → stronger grounding (the moat) |
| 4 | **LTX-Video** (or Wan 2.x) | AI video-gen (stack §1) | Headline quality upgrade at ~$0 marginal (local GPU) |
| 5 | **MusicGen** (Meta AudioCraft) | music/SFX (stack §4) | Free background beds — big perceived-quality jump, low effort |
| 6 | **anything-to-notebooklm** | Obsidian ingestion (#2 above) | Grows the verified-fact vault from many source types |
| 7 | **ComfyUI** | infra backend (stack §12) | One endpoint to run/swap image+video+upscale models |
| 8 | **ericosiu/ai-marketing-skills** | Pillar 2 grading (#3 above) | Expert-Panel persona scoring pattern for the report card |
| 9 | **Real-ESRGAN + RIFE** | upscale/interp (stack §8) | Polish AI b-roll (sharper, smoother) for free |
| 10 | **lucaswalter/n8n-ai-automations** | distribution (#4 above) | Free templates for cross-post/repurpose off the webhook events |

*Honorable mentions (free, next-in): XTTS-v2 (voice cloning → multilingual dub),
LatentSync (lip-sync avatar), Ultralytics YOLO (auto-reframe — note AGPL),
system_prompts_leaks (prompt reference).*

---

## Addendum — 14 operator-submitted tools (2026-08-25)

Same lens and vocabulary as above; ranked 0–10 **for this project**, not for general
quality. Maturity figures are from an August-2026 web scan and carry the same
order-of-magnitude caveat as the header — several fetched star counts looked inflated
(a four-principles CLAUDE.md repo reporting ~200k stars, an AI gateway reporting ~55k)
and are treated as "alive and adopted", not as fact.

> **Correction to row 2 above.** The table's MoneyPrinter entry covers
> **MoneyPrinterV2** (`FujiwaraChoki`, AGPL-3.0 — pattern-borrow only). The repo
> assessed here is **MoneyPrinterTurbo** (`harry0703`) — a *different project* under
> **MIT**. The copyleft warning does not carry over: Turbo's code is reusable, which is
> most of why it tops this list.

| 0-10 | Tool | Verdict | How it can be used here |
|---|------|---------|-------------------------|
| **7** | [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | **Borrow (narrowed 2026-08-26)** | MIT faceless assembler. Clip path is LLM → ~5 keyword searches → 5s stock clips, random concat, optional fades — **worse** for TapIn's "gameplay then random reality" problem ([moneyprinter_vs_content_os.md](moneyprinter_vs_content_os.md), decisions §26). Source of Coverr's API shape and of Edge TTS (`TTS_PROVIDER=edge`, 2026-08-28). Do not adopt its stock concatenator. |
| **6** | [public-apis](https://github.com/public-apis/public-apis) | **Intel** | The standard directory of free APIs (~470k★). Aims straight at the recurring Apify cost problem and [agent_reach_evaluation.md](agent_reach_evaluation.md)'s free-backend hunt — a shortlist source for keyless signal backends. Research input, never a dependency. |
| **6** | [awesome-gpt-image-2](https://github.com/freestylefly/awesome-gpt-image-2) | **Borrow (patterns)** | 530+ structured image prompts ("prompt as code"). Thumbnail CTR is an untested lever and [core/experiment_levers.py](../core/experiment_levers.py) already has a `thumbnail` kind feeding [assets/flux_thumbnail.py](../assets/flux_thumbnail.py) — ready home, measurable. Targets GPT-Image-2; the *structures* port to Flux, the exact prompts may not. |
| **6** | [mattpocock/skills](https://github.com/mattpocock/skills) | **Reference** | Composable agent skills. `/tdd` enforces watch-it-fail-first — the discipline that would have caught all four defects in the 21–28 audit (see [.cursor/rules/content-machine.mdc](../.cursor/rules/content-machine.mdc)). JS/TS-flavoured; the philosophy ports, `/handoff` duplicates HANDOFF_SYNOPSIS. |
| **5** | [senior-prompt-engineer skill](https://github.com/alirezarezvani/claude-skills/blob/main/engineering-team/skills/senior-prompt-engineer/SKILL.md) | **Reference** | One rule is a real gap: *"never change a prompt without a baseline"* — `PROMPT_VERSION` in [core/content_engine.py](../core/content_engine.py) is bumped by hand with no A/B behind it. Its three CLI tools duplicate `ops grade`/the report card. Take the discipline, skip the tooling. |
| **5** | [hister](https://github.com/asciimoo/hister) | **Complement (evaluate)** | Go/AGPL personal search: a browser extension indexes pages you visit, MCP-searchable. Interesting because it addresses a *live* failure — run 71's MSN link came back headline-only because [core/link_facts.py](../core/link_facts.py) can't render JS pages, while a browser that already rendered it can. AGPL + separate service: evaluate standalone, never couple. |
| **5** | [OmniRoute](https://github.com/diegosouzapw/OmniRoute) | **Overlap** | An LLM gateway — a direct competitor to [core/llm_router.py](../core/llm_router.py), which already has tier routing, failover, a session breaker and the cost-meter wiring. Do not adopt; a gateway between us and providers would blind the breaker. Mine its free-tier provider list for slugs to add to *our* router. Its token-compression claims (~89% avg) warrant scepticism. |
| **4** | [claude-plugins-community](https://github.com/anthropics/claude-plugins-community) | **Reference** | Anthropic-managed mirror of security-reviewed community plugins (`claude plugin marketplace add anthropics/claude-plugins-community`). Worth knowing it exists as the vetted channel; nothing in it today is specific to this pipeline. |
| **4** | [andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) | **Reference** | Four generic principles in a CLAUDE.md (think first, simplicity, surgical changes, goal-driven). Duplicates the repo-specific, evidence-based rules already in `.cursor/rules`. "Surgical changes" is the one worth absorbing — the last Cursor drop was 1384 lines in one body. |
| **3** | [ai-memory](https://github.com/akitaonrails/ai-memory) | **Overlap** | Rust MCP memory server (git-versioned markdown + SQLite FTS). Well built — but a second markdown memory store would compete with the Obsidian vault, which is a *product* surface (Pillar 4, provenance tiers in [core/fact_store.py](../core/fact_store.py)), not agent scratch. Cross-vendor handoff is real; HANDOFF_SYNOPSIS covers it. |
| **2** | [cs-senior-engineer agent](https://alirezarezvani.github.io/claude-skills/agents/cs-senior-engineer/) | **Reference (thin)** | A generic senior-engineer persona (architecture/review/CI/security workflows). This repo's problem was never a missing persona — it was specific failure patterns, now encoded with evidence in `.cursor/rules`. Little marginal value. |
| **2** | [PostHog](https://github.com/PostHog/posthog) | **Irrelevant (for now)** | Product analytics for *apps* (events, replays, flags; MIT core, generous free tier). Our loop measures **YouTube content** performance, which PostHog does not. Revisit only if the operator surface ever becomes a hosted app — #147 FastAPI is explicitly skipped. |
| **1** | [openhuman](https://github.com/tinyhumansai/openhuman) | **Avoid** | Early-beta Rust/Node personal-agent framework, **GPL-3.0**, "expect rough edges". Overlaps memory + orchestration that already exist here and fit the pipeline better; copyleft beside this codebase is a hazard with no offsetting gain. Not avatar/video software despite the name. |
| **0** | [reverse-skill](https://github.com/zhaoxuya520/reverse-skill) | **Irrelevant** | Security/reverse-engineering task routing — APKs, Ghidra, Frida, CTF sandboxes. No intersection with a video pipeline. The honest zero. |

> **Integration plan:** [tool_integration_plan.md](tool_integration_plan.md) works the
> top 7 through to what actually ships. Read it alongside this table — Edge TTS shipped
> 2026-08-28 as an unmodified `[free]` extra (LGPL-3.0 linking, decisions §28), and
> three of the seven turned out to be **already built here** (`core/prompt_evals.py`,
> `LINK_READER_PROXY`, `core/llm_router.py`), including a correction to the
> senior-prompt-engineer row below.

### Edge TTS — shipped behind a flag (2026-08-28)

The roadmap's pronunciation-lexicon item (#412) is superseded: a dictionary is a
workaround for a voice that cannot be told how to say a word. MoneyPrinterTurbo's
lead voice is **Edge TTS** — free, keyless, neural — wired as `TTS_PROVIDER=edge`
(never the default; Piper stays the true-offline floor).

**The risk, stated plainly:** Edge TTS drives an undocumented Microsoft endpoint.
That is a terms grey area and can break without notice. It enters as one more
`TTS_PROVIDER` slot that **fails open to the existing chain**, never as the only $0
path. CI does not hit Microsoft. Decision taken 2026-08-25 (operator): worth trying
behind a flag; 2026-08-28: shipped under decisions §28.
