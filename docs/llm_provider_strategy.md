# LLM provider strategy — what's reachable today, and what each model adds

> **Harvested 2026-08-17 from PR #26 (`claude/kimi-k3-evaluation`), which was closed
> unmerged.** Kept for the model comparison and the sourced Kimi K3 open-weights analysis,
> which nothing else in the repo records. **Read the routing advice as of 2026-07, not as
> current:** it anchors the cheap tier on `meta-llama/llama-3.3-70b-instruct:free`, which
> live run 66 found **retired and 404ing daily** — it was hardcoded, so `.env` could not
> override it (see [decisions.md](decisions.md) §21 and [roadmap.md](roadmap.md)). Current
> chain and defaults: [providers_runbook.md](providers_runbook.md), `core/llm_router.py`.

*Analysis only (2026-07). Which LLMs can actually serve this project **given that
paid `chat` (OpenAI) and paid Apify are currently off while Claude is available**,
the free vs paid use case per job, and what crosses over or is unnecessary.*

> **Provenance:** model specs/pricing from a **July-2026 web scan — figures drift**.
> Sources inline per claim. Repo claims are cited to paths verified against the tree.

---

## 1. Three states, not two

A previous revision of this doc treated "paid chat + Apify off" as though the project
were running **Free mode**. That was wrong, and it skewed the verdict. There are
three distinct states:

| | **(a) Today** — Standard *with gaps* | **(b) Free mode** — a per-run tool | **(c) Full Standard** |
|---|---|---|---|
| LLM | **Claude available (paid)**; DeepSeek/OpenRouter as configured; **OpenAI unavailable** | local Ollama; OpenRouter `:free` fallback | any wired provider |
| Voice | ElevenLabs or local | local Piper / Kokoro / XTTS | ElevenLabs |
| Web search | Tavily / Brave / DuckDuckGo | keyless **DuckDuckGo** | Tavily / Brave |
| `reddit`, `youtube_competitors` | free backends (Apify off) | `SIGNAL_BACKEND=free` | Apify |
| `twitter`, `tiktok_trends` | **unavailable** (Apify off) | **skipped** (`_PAID_NO_FREE_BACKEND`) | Apify |

**(a) is the live state.** Paid is *not* being switched off permanently — quality is
the priority, and Claude is the paid provider in hand. **(b) Free mode** is a real,
strict subsystem in `core/run_mode.py` that can be selected per run
(`RUN_COST_MODE=free`), where the router filters the tier chain to zero-cost
candidates and **raises** rather than reaching for a paid provider
(`_free_mode_strict()` → chain filter → `RuntimeError`). It is a tool, not the posture.

> ### ⇒ What this actually means
> Frontier models are **not** globally blocked — that is only true *inside* Free mode.
> Today the live facts are: **Claude is reachable and paid** (so the judge/grading
> roles are available now), **OpenAI is not** (which silently kills the one vision
> path — see §5.2), and **Apify is not** (so `twitter`/`tiktok_trends` are absent).

## 2. ⚠ Verified: "Is Kimi open weight and free?"

Asked directly, so answered directly: **open weight ✅ — free ❌.**

| Claim | Verdict | Evidence |
|---|---|---|
| Open weights | ✅ **Yes** — released 2026-07-27, **Modified MIT**; free to use/modify/deploy commercially with attribution. Conditions bite only at scale (>$20M/yr model-as-a-service, or >100M MAU) — **not this project** | [Yotta Labs](https://www.yottalabs.ai/post/kimi-k3-specs-benchmarks-how-to-access-2026) |
| Free to *run* | ❌ **No** — weights are **1.56 TB**; vLLM needs **~1.68 TB VRAM**; realistic self-host is a multi-node cluster, **8×H100 minimum**. "Not a single-consumer-GPU model even quantized" | [Northflank](https://northflank.com/blog/what-is-kimi-k3-self-hosting), [explainx](https://explainx.ai/blog/kimi-k3-run-locally-open-weights-desktop-july-2026) |
| Free API tier | ❌ **No** — $3/$15 per M on both the direct API and OpenRouter (which lacks even the $0.30 cache rate); **no `:free` variant**. Free chat exists only on kimi.com, not the API | [freellm](https://freellm.net/blog/is-kimi-k3-free-api-pricing-openrouter-alternatives), [OpenRouter](https://openrouter.ai/moonshotai/kimi-k3) |

**Conclusion: open weight ≠ free here.** The permissive license is real, but the
hardware floor puts self-hosting out of reach and there's no free API. **Kimi cannot
serve Free mode.** (An earlier draft of this doc implied open weights were an
advantage — they are, but only to someone with a datacenter.)

## 3. All 12 models — grouped by availability

| Model | Access | Available **today**? | Free-mode usable? | Best job here |
|---|---|---|---|---|
| **Claude** Opus 5 / Sonnet 5 | paid API (**wired**) | ✅ **yes — paid, in hand** | ❌ | judgment: grading, claim-verify |
| **GPT-5.6** | paid API (**wired**) | ❌ *chat paid off* | ❌ | generalist; the (now dead) vision scorer |
| **Gemini 3.x Pro** | paid API | ➖ needs a key | ❌ | **native video/audio** review |
| **Grok 4.5** | paid API | ➖ needs a key | ❌ | live X/web recency |
| **Kimi K3** | paid API (open weights, 8×H100) | ➖ needs a key | ❌ *(see §2)* | 1M-context synthesis |
| **Llama** 3.1/3.3 | **open — local Ollama** | ✅ local | ✅ **default** | everything, locally |
| **Qwen** 2.5 / 3 | **open — local Ollama** | ✅ local | ✅ **alternative** | everything; strong multilingual |
| **Mistral** | open + paid API | ✅ local sizes | ✅ | fast local generation |
| **Gemma** | **open — local Ollama** | ✅ local | ✅ | small-box fallback |
| **Phi** | **open — local Ollama** | ✅ local | ✅ | smallest boxes; weakest |
| **GLM** | open + paid API | ➖ needs a key | ⚠️ large locally | coding/structured output |
| **DeepSeek** V3/R1 | paid API (**wired**) + open distills | ✅ if key set | ⚠️ distills only | Standard anchor (§3.12) |

### Group A — paid frontier

**3.1 Claude (Opus 5 / Sonnet 5) — ✅ available today, and the one to use**
Tops the July-2026 intelligence ranking; the *judge*: Pillar 2 grading, Pillar 3
claim-verifier, authenticity passes. **It is the paid provider actually in hand**, so
these are live options right now — not contingencies.
· **Crossover:** already wired (`anthropic`, native messages API) — nothing to build.
· **Gap:** `_DEFAULT_MODELS` still pins `claude-sonnet-4-…` / `claude-haiku-4-5-…`
(see §5.1), and the router can't send it images (§5.2) even though the model supports
vision.
· **Unnecessary if** you only need generation; local Llama/Qwen write acceptable scripts.

**3.2 GPT-5.6 (OpenAI) — ❌ unavailable today (paid chat off)**
~1M context, and the *only* provider the vision scorer knows how to call
(`assets/thumbnail_scorer._vision_score`). With the key absent that function returns
`None` and thumbnail scoring **silently degrades to heuristics** (§5.2).
· **Crossover:** wired, so it returns the moment a key does. · **Unnecessary if**
Claude covers the same jobs — which, for everything except the hardcoded vision path,
it does.

**3.3 Gemini 3.x Pro** — the one genuinely differentiated capability in this list:
**native video + audio ingestion** (~2M ctx) — it could watch the *rendered video*,
not just frames, which is the exact shape of the open Pillar-2 item.
· **Unnecessary if** frame-sampling suffices. · **Caveat:** video input may not proxy
through OpenRouter, so this is the one most likely to need a native entry.

**3.4 Grok 4.5** — cheapest frontier (~$2/$6) and the only one with **live X/web access**.
· **⚠ Reframed:** previously pitched as "displaces the paid `twitter` Apify signal" —
but with **Apify paid off, `twitter`/`tiktok_trends` are already gone**, so Grok
wouldn't *remove a cost*, it would **restore a capability that is currently absent**.
· **Gate:** an LLM summary is not a
citable source; the Pillar-3 grounding spine needs attributable URLs. **Unverified.**

**3.5 Kimi K3** — 2.8T MoE, 1M ctx, native vision, always-on reasoning, structured
JSON, $0.30 cache hits. Long-context synthesis: Phase R transcripts, vault-wide
reasoning (Pillar 4), SkillOpt repo/trace analysis (Pillar 7), prompt-eval corpora.
It's the *brain* for the 2026-07 tool adds (ComfyUI generates → K3 grades; whisperx
transcribes → K3 reasons; notebooklm ingests → K3 synthesizes).
· **Unnecessary if** no workload exceeds DeepSeek's context — and **unusable in Free
mode** (§2).

### Group B — open-weight / local (**the $0 path**)

> **⚠ Ollama is no longer unqualifiedly "free."** The **local runtime remains free and
> open-source (MIT)** — that is the `localhost:11434` path
> [free_mode.md](free_mode.md) uses, and it is still $0 and unlimited. But **Ollama
> Cloud** is now a paid managed-inference service (roughly $0 free / ~$20 Pro /
> ~$100–200 Pro Max — *aggregator sources disagree on the top tier*). Local = free;
> hosted = paid. Sources:
> [cloud pricing](https://pooyagolchian.com/blog/ollama-cloud-pricing-hardware-requirements-2026/),
> [overview](https://aisotools.com/pricing/ollama).

**3.6 Llama (`llama3.1:8b`)** — **the project's own documented default**
([free_mode.md](free_mode.md) §1) and the OpenRouter `:free` anchor
(`meta-llama/llama-3.3-70b-instruct:free`). · **Crossover: already the incumbent** —
no work to adopt. · Best all-round balance of quality and size on a modest box.

**3.7 Qwen (`qwen2.5:7b`)** — named in `free_mode.md` as "a solid alternative";
often stronger on structured/multilingual output at the same size. Also the family
behind the shipped **Qwen3-TTS** voice provider, so it's already in the stack's
vocabulary. · **The main live A/B worth running** (see §5.2).

**3.8 Mistral** — efficient local sizes with a paid API above them; a reasonable
third try if Llama and Qwen both disappoint on script prose.

**3.9 Gemma (Google)** — small, well-behaved, instruction-tuned; the fallback when
7–8B is too heavy. Interesting as Gemini's open sibling, but **no video/vision parity** —
it does not give you §3.3's capability for free.

**3.10 Phi (Microsoft)** — smallest viable; reach for it only on RAM-limited boxes.
Expect noticeably weaker long-form scripts.

**3.11 GLM (Zhipu)** — strong structured-output/coding reputation, aggressive API
pricing; the useful local sizes are large, so on a typical box it's effectively a
paid-API option → Standard mode.

**3.12 DeepSeek (promoted from footnote)** — the **Standard-mode anchor**: near-frontier
quality at ~10× frontier cost, currently anchoring `extract` + `premium` in the router.
It is *the reason no frontier model is mandatory*. · **In Free mode it is paid → blocked**;
only the open **R1 distills** (e.g. 7–8B) qualify locally, and those are meaningfully
weaker than the hosted V3/R1. Measure any change against DeepSeek, not against "no model."

## 4. Use cases — free vs paid, per job

| Pipeline job | **$0 / Free mode** | **Paid, available today (Claude)** | **Paid, needs a key** |
|---|---|---|---|
| Discovery / extraction | Ollama local (`extract`) | Claude Haiku-class | DeepSeek V3 (cheapest) |
| Script generation | Ollama local (`premium`) | **Claude Sonnet 5** — biggest quality jump | GPT-5.6 |
| Grading (Pillar 2) | local self-grading *(weak judge grading a weak writer — correlated blind spots)* | **Claude — best judge available** | — |
| Claim verification (Pillar 3) | local + DuckDuckGo | **Claude** | Kimi (long ctx) |
| Thumbnail / vision | none (heuristics) | **Claude supports vision — but the router can't send images** ⚠ §5.2 | GPT-5.6 (wired but key off); **Gemini** for video |
| Long-context synthesis | limited by local ctx | Claude (200K-class) | Kimi K3 (1M) / Gemini (2M) |
| Recency | DuckDuckGo + RSS + free reddit/yt | *(same — LLM doesn't fix sourcing)* | Grok live X; Apify twitter/tiktok |
| Voice | Piper / Kokoro / XTTS | ElevenLabs | — |

**Reading this table today:** the middle column is what you can actually use right
now. The one row where paid-in-hand does *not* help is **vision** — Claude can do it,
but nothing in the codebase can hand it an image (§5.2).

Per [free_mode.md](free_mode.md), local inference is **slower and lower-quality** than
paid models and wants ~8GB+ RAM (GPU ideal) — the project's own words, not inferred
here. That is the honest cost of the left column.

## 5. Verdict — ordered for the actual state

### 5.1 Refresh the Anthropic default model IDs — *highest value, zero integration*
Claude is **the live paid provider**, yet `core/llm_router._DEFAULT_MODELS` still pins
it to `claude-sonnet-4-…` / `claude-haiku-4-5-…` while the Claude 5 family exists. The
provider is already wired, so this is a **config-level** upgrade to the model doing
your most quality-sensitive work (script generation, grading, claim-verify).
*Evaluate, don't blind-bump* — newer models shift cost and prompt behavior, and the
prompts are tuned. (The OpenAI pins are stale too, but moot until that key returns.)

### 5.2 Give the router an image path — *restores a dead capability* ⚠
**The only vision capability in the project is hard-pinned to the one provider that is
currently off.** `assets/thumbnail_scorer._vision_score` builds base64 `image_url`
blocks and sends them through the legacy `core/llm_client.get_openai_client()` —
bypassing the router entirely. It guards on `OPENAI_API_KEY`, so with chat paid off it
returns `None` and `score_thumbnail` falls back to `_heuristic_score`: **thumbnail
vision scoring is silently dead right now**, with no error.

Meanwhile **Claude — which you are paying for — supports vision**, but the router
cannot carry an image: `_normalize_messages` is typed `list[dict[str, str]]`, text-only.

So one fix does three things: restores thumbnail vision on an already-paid provider,
puts that spend under `cost_meter`/failover, and unblocks the open Pillar-2
"router vision path" roadmap item.

> **Correction to an earlier revision of this doc:** this was previously framed as a
> Free-mode "never-pay leak." That framing rested on a wrong premise. The real,
> current impact is a **dead capability**, not an unguarded charge. (A narrow latent
> case does still exist — an `OPENAI_API_KEY` present *while* `FREE_MODE_STRICT` is
> set would bypass the guard — but it is not today's situation.)

### 5.3 Pick the local model — *only when running Free mode*
`llama3.1:8b` (documented default) vs `qwen2.5:7b` (documented alternative). Worth a
real A/B on hook quality and stance-holding before assuming a bigger pull is needed —
but this only affects runs you deliberately start in Free mode, not the default path.

### 5.4 Optional additions, in order
1. **Gemini** — only if the Pillar-2 **rendered-video** review is the priority; native
   video is the one capability nothing else has. (§5.2 is its prerequisite either way.)
2. **Grok** — would *restore* the `twitter`/`tiktok_trends` capability that Apify-off
   removed; gated on verifying it returns citable source URLs (§3.4).
3. **Kimi K3** — last; paid-only despite open weights (§2), and nothing is blocked on it.

## 6. Crossover / unnecessary — consolidated

| Idea | Verdict |
|---|---|
| "Adopt Claude" | **Already available and already wired** — use it; just refresh the model IDs (§5.1). |
| "Adopt GPT now" | **Blocked by the missing key**, not by code — it returns the moment paid chat is back. |
| "Everything is blocked because paid is off" | **False** — that's only true *inside* Free mode (§1). Claude is reachable today. |
| "Add GPT / add Claude" (as providers) | **Already wired.** No work exists to do. |
| "Add native Gemini / Grok / Kimi providers" | **Mostly unnecessary** — OpenRouter already reaches them (Standard only). Justify natively only for params OpenRouter can't proxy (Gemini video, Grok live-search). |
| "Kimi is open weight, so it's our free model" | **False** — §2: 1.56 TB weights, 8×H100, no free API tier. |
| "Put a frontier model on `cheap`/`extract`" | **Anti-doctrine** — and impossible in Free mode. |
| "Add a 4th/5th premium provider for reliability" | **Unnecessary** — router already has failover chains + session breakers (O5/O6). |
| "A frontier model will fix hallucinations" | **Misdiagnosis** — grounding is a *sourcing + verification* problem (Pillars 3/4). A better model still can't cite a fact it was never given. |

---

## Cross-references
- [free_mode.md](free_mode.md) — the $0 stack, setup, `ops free-doctor`.
- [roadmap.md](roadmap.md) — open Pillar-2 vision path, Phase R, Pillars 4/7.
- [credit_efficiency.md](credit_efficiency.md) — budget ceiling, failover, breakers.
- [assessment.md](assessment.md) — recency as the #1 content weakness.
- [tooling_landscape.md](tooling_landscape.md), [groundwork_2026Q3.md](groundwork_2026Q3.md).
- Code seams: `core/run_mode.py` (`_PAID_NO_FREE_BACKEND`, cost modes),
  `core/llm_router.py` (`_free_mode_strict`, `_PROVIDERS`, `_DEFAULT_MODELS`),
  `core/cost_meter.py`, `core/llm_client.py` (legacy),
  `assets/thumbnail_scorer.py` (`_vision_score`).
