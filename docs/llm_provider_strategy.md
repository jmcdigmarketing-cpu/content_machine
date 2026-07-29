# LLM provider strategy — the big 5 vs Content OS

*Analysis only (2026-07). What each frontier LLM could actually do for this project,
what **crosses over** with what's already built, what's **unnecessary**, and which is
**most necessary**. Supersedes the standalone Kimi K3 evaluation (now §3.5).*

> **Provenance:** model specs/pricing from a **July-2026 web scan — figures drift**.
> Sources: [BenchLM leaderboard](https://benchlm.ai/),
> [Kimi K3 vs Claude/GPT-5/Gemini](https://intuitionlabs.ai/articles/kimi-k3-vs-claude-gpt-5-gemini),
> [best-LLM comparison](https://alcconsulting.com.au/blog/best-llm/),
> [token pricing](https://tokencalculator.com/models),
> [OpenRouter](https://openrouter.ai/moonshotai/kimi-k3),
> [Moonshot docs](https://platform.kimi.ai/docs/guide/kimi-k3-quickstart).
> Repo claims are cited to real paths and were verified against the tree.

---

## 1. Doctrine first (why the answer is mostly "no")

Content OS is deliberately **free-first**: `core/llm_router.py` anchors `cheap` on
OpenRouter `:free` models (+ local Ollama) and `extract`/`premium` on **DeepSeek**,
so a normal run costs ≈ $0. Spend is bounded by `LLM_DAILY_BUDGET_USD` (O7 —
premium/extract downgrade to cheap at the ceiling), provider failover, and session
breakers ([credit_efficiency.md](credit_efficiency.md)).

**Therefore: none of the five below is required for the pipeline to work.** Each is
an *opt-in premium upgrade* for a specific job where a wrong or blind answer is
expensive. Nothing here should become a new default.

## 2. Current state — what's already wired

`core/llm_router._PROVIDERS` (verified):

| Provider | Wired? | Notes |
|---|---|---|
| **openai** (GPT) | ✅ | in all 3 tier chains; `_DEFAULT_MODELS` → `gpt-4o` / `gpt-4o-mini` |
| **anthropic** (Claude) | ✅ | native messages API; in `extract`/`premium` chains |
| **deepseek** | ✅ | the incumbent anchor for `extract` + `premium` |
| **openrouter** | ✅ | **meta-gateway — one key, many models, incl. `:free`** |
| groq / ollama / doubao | ✅ | free-fast / local / region-locked |
| **gemini** (Google) | ❌ | not native |
| **grok** (xAI) | ❌ | not native |
| **moonshot** (Kimi) | ❌ | not native |

> **The single biggest "unnecessary" finding:** Gemini, Grok and Kimi are **already
> reachable today with zero code** through the wired `openrouter` provider — e.g.
> `LLM_PREMIUM_MODEL=moonshotai/kimi-k3`. A *native* provider entry buys direct
> billing, lower latency, and provider-specific params — **not access**.

## 3. Per-model: what it could do here

### 3.1 Claude (Opus 5 / Sonnet 5) — the judge
Tops the July-2026 intelligence ranking. Best fit for **judgment** roles where
quality beats cost: Pillar 2 grading, the Pillar 3 claim-verifier,
authenticity/insight passes, and the prompt-eval harness.
- **Crossover: already wired** (`anthropic`, native messages API). Nothing to add.
- **Unnecessary if** you only need generation — DeepSeek already writes scripts fine.
- **Caveat:** `_DEFAULT_MODELS` still points at `claude-sonnet-4-…` / `claude-haiku-4-5-…`
  (see §5.2).

### 3.2 GPT-5.6 (OpenAI) — the incumbent generalist
Now ~1M context. Notably, it is **already the de-facto vision provider**:
`assets/thumbnail_scorer._vision_score` sends base64 `image_url` blocks to it today.
- **Crossover: already wired**, and already doing vision. Adding it is a no-op.
- **Unnecessary if** the free tiers already pass your quality bar — this is the
  costliest way to buy a marginal gain over DeepSeek.

### 3.3 Gemini 3.x Pro (Google) — the only native *video* reader
The one genuinely differentiated capability in this list: **native multimodal
ingestion of video and audio** (~2M context), versus everyone else's images-only.
That is the exact shape of the open roadmap item *"Router vision path → multimodal
rendered-video review (Pillar 2)"* — it could watch the **rendered video**, not just
extracted frames.
- **Crossover:** partial — a vision path exists (§3.2) but is images-only and
  stranded (§5.1).
- **Unnecessary if** frame-sampling is good enough for thumbnail/CTR review; stills
  are cheaper and every other model handles them.
- **Caveat:** video input may not proxy cleanly through OpenRouter — a native entry
  is more likely to be *actually* required here than for the others.

### 3.4 Grok 4.5 (xAI) — the recency play
Cheapest of the five (~$2/$6, 500K window) and the only one with **live X + web
access**. That maps onto two real project problems at once: **recency** (the #1
content weakness in [assessment.md](assessment.md)) and **cost** — `twitter` is one
of the four paid Apify signals (`_APIFY_PAID_SIGNALS` in
`apis/register_signals.py`), the project's main recurring spend.
- **Crossover / substitution candidate:** could partly displace the paid `twitter`
  signal — the only model here that touches the *data* layer, not just the brain.
- **⚠ Honest caveat (why this is not a slam dunk):** an LLM-summarized answer is
  **not a citable source**. The verified-facts spine (Pillar 3 tiered grounding)
  needs attributable lines, so this only works if the API returns real source URLs.
  **Unverified — treat as a candidate to test, not a plan.**
- **Unnecessary if** Tavily/Brave web search (already wired, ToS-clean) covers the
  recency gap — which is the current, deliberately least-invasive answer.

### 3.5 Kimi K3 (Moonshot) — long context + open weights
Released 2026-07-16 (open weights 07-26): 2.8T-param MoE (16 of 896 experts active),
**1M context** (up to 262K out), native vision, tool calling, always-on "thinking"
reasoning, structured JSON, prompt caching. ≈ **$3/$15 per M, $0.30 cache-hit**.
Reachable via OpenRouter (`moonshotai/kimi-k3`), the Moonshot API
(`https://api.moonshot.ai/v1`, OpenAI-compatible), or self-hosted weights.

Where the long context earns its keep: clip-from-source (Phase R) whole-transcript
scans; vault-wide synthesis (Pillar 4 / `core/vault_ingest.py`); SkillOpt whole-repo
and run-trace analysis (Pillar 7); prompt-eval over large corpora; research briefs
over big fact/competitor sets. Cheap cache hits suit large repeated system prompts.
- **How it relates to the 2026-07 GitHub adds** — those are *tools*; K3 is the
  *brain* that drives them: ComfyUI **generates** thumbnails/b-roll → K3 **grades**
  them; whisperx **transcribes** → K3 reasons over the whole transcript;
  anything-to-notebooklm **ingests** → K3 synthesizes the vault;
  ai-marketing-skills' Expert Panel and the system_prompts_leaks eval corpus get K3
  as grader/verifier. (See [groundwork_2026Q3.md](groundwork_2026Q3.md),
  [tooling_landscape.md](tooling_landscape.md).)
- **Crossover:** none blocking — reachable via OpenRouter today.
- **Unnecessary if** no workload actually exceeds DeepSeek's context; most current
  prompts are small.

### 3.6 Incumbent (not one of the five): DeepSeek
The reason none of the above is mandatory — near-frontier quality at ~10× lower cost,
anchoring `extract` + `premium`. Any change should be measured against *it*, not
against "no model."

## 4. What crosses over / is unnecessary — consolidated

| Idea | Verdict |
|---|---|
| "Add GPT / add Claude" | **Already wired.** No work exists to do. |
| "Add native Gemini / Grok / Kimi providers" | **Mostly unnecessary** — OpenRouter already reaches them. Justify natively only for direct billing, rate limits, or params OpenRouter can't proxy (Gemini video input; Grok live-search flags). |
| "Put a frontier model on `cheap`/`extract`" | **Anti-doctrine.** DeepSeek + free OpenRouter already cover script generation and extraction at ≈$0; this only burns budget. |
| "Add a 4th/5th premium provider for reliability" | **Unnecessary** — the router already has failover chains + session breakers (O5/O6). |
| "Frontier model to fix hallucinations" | **Misdiagnosis** — grounding is a *sourcing + verification* problem (Pillars 3/4), not a model-size problem. A better model still can't cite a fact it was never given. |

## 5. Verdict — which is most necessary

**Ranked by marginal value, most necessary first. The top two involve buying nothing.**

### 5.1 Fix the seam, not the model *(highest value, $0 API spend)*
`assets/thumbnail_scorer.py` calls vision through the **legacy**
`core/llm_client.get_openai_client()` — hardcoded to OpenAI, **bypassing the
router**: no cost ledger, no failover, no provider choice. Consequences:
- **no new vision model is usable** until this is routed, so §3.3's Gemini idea is
  blocked on plumbing, not on a purchase; and
- the vision spend that *already happens* is invisible to `core/cost_meter.py`.

Routing it through `core/llm_router` is the prerequisite for the open Pillar-2
*"router vision path"* item. **This is the answer to "which is most necessary."**

### 5.2 Refresh the stale default model IDs *(frontier quality, zero integration)*
`_DEFAULT_MODELS` pins OpenAI to `gpt-4o`/`gpt-4o-mini` and Anthropic to
`claude-sonnet-4-…`/`claude-haiku-4-5-…`, while the current field is GPT-5.6 and the
Claude 5 family. Both providers are **already wired** — so this is a config-level
upgrade. *Evaluate, don't blind-bump:* newer models change cost and prompt behavior,
and the prompts are tuned. (Nothing is broken today; this is an upgrade path.)

### 5.3 Gemini — the top *new* addition, conditional
Adopt **only if** the Pillar-2 rendered-video review is the priority. Native video
ingestion is the single capability none of the others have; everything else it does
is already covered.

### 5.4 Grok — highest upside, gated on verification
The only candidate that could *remove* a recurring cost (the paid `twitter` signal)
while attacking the recency weakness. **Gate:** confirm it returns attributable
source URLs; without that it can't feed the verified-facts spine.

### 5.5 Kimi K3 — nice-to-have
Long-context synthesis and grading. Real value, but no current workload is blocked on
it. Try it via OpenRouter before considering a native entry.

---

## Cross-references
- [roadmap.md](roadmap.md) — open Pillar-2 vision path, Phase R, Pillars 4/7.
- [credit_efficiency.md](credit_efficiency.md) — O7 budget ceiling, failover, breakers.
- [assessment.md](assessment.md) — recency as the #1 content weakness.
- [tooling_landscape.md](tooling_landscape.md), [groundwork_2026Q3.md](groundwork_2026Q3.md) — the 2026-07 tool adds.
- Code seams: `core/llm_router.py` (`_PROVIDERS`, `_DEFAULT_MODELS`, tier chains),
  `core/cost_meter.py` (`_LLM_PRICES`), `core/llm_client.py` (legacy),
  `assets/thumbnail_scorer.py` (`_vision_score`), `apis/register_signals.py`
  (`_APIFY_PAID_SIGNALS`).
