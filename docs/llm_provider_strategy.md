# LLM provider strategy — Free mode vs Standard mode

*Analysis only (2026-07). Which LLMs can actually serve this project **while paid
chat + paid Apify are off**, what each would add if paid were re-enabled, the free
vs paid use case per job, and what crosses over or is unnecessary.*

> **Provenance:** model specs/pricing from a **July-2026 web scan — figures drift**.
> Sources inline per claim. Repo claims are cited to paths verified against the tree.

---

## 1. Two modes → two completely different questions

`core/run_mode.py` implements a real, **strict** cost mode — not a posture:

| | **Free ($0)** — *current state* | **Standard** |
|---|---|---|
| LLM | **local Ollama** (unlimited, offline); OpenRouter `:free` = rate-limited cloud fallback | any wired provider, paid allowed |
| Voice | local Piper / Kokoro / XTTS | ElevenLabs |
| Web search | keyless **DuckDuckGo** | Tavily / Brave |
| `reddit`, `youtube_competitors` | `SIGNAL_BACKEND=free` (Reddit OAuth + yt-dlp) | Apify |
| `twitter`, `tiktok_trends` | **skipped entirely** (`_PAID_NO_FREE_BACKEND`) | Apify |

**It blocks, it doesn't degrade.** Under `FREE_MODE_STRICT` the router filters the
tier chain to zero-cost candidates and **raises** rather than reaching for a paid
provider (`core/llm_router.py` `_free_mode_strict()` → chain filter → `RuntimeError`).

> ### ⇒ The headline reframe
> **With paid chat off, every frontier model below is blocked at the seam.** Claude,
> GPT, Gemini, Grok and Kimi are *unreachable* right now — not "expensive," but
> refused. The only live LLM decision today is **"which model do I `ollama pull`?"**
> Everything in Group A is a *Standard-mode contingency plan*.

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

## 3. All 12 models — grouped by which mode they can serve

| Model | Access | Free-mode usable? | Best job here |
|---|---|---|---|
| **Claude** Opus 5 / Sonnet 5 | paid API (**wired**) | ❌ | judgment: grading, claim-verify |
| **GPT-5.6** | paid API (**wired**) | ❌ | generalist; today's vision scorer |
| **Gemini 3.x Pro** | paid API | ❌ | **native video/audio** review |
| **Grok 4.5** | paid API | ❌ | live X/web recency |
| **Kimi K3** | paid API (open weights, 8×H100) | ❌ *(see §2)* | 1M-context synthesis |
| **Llama** 3.1/3.3 | **open — Ollama** | ✅ **default** | everything, locally |
| **Qwen** 2.5 / 3 | **open — Ollama** | ✅ **alternative** | everything; strong multilingual |
| **Mistral** | open + paid API | ✅ (local sizes) | fast local generation |
| **Gemma** | **open — Ollama** | ✅ | small-box fallback |
| **Phi** | **open — Ollama** | ✅ | smallest boxes; weakest |
| **GLM** | open + paid API | ⚠️ large locally | coding/structured output |
| **DeepSeek** V3/R1 | paid API (**wired**) + open distills | ⚠️ distills only | Standard anchor (§3.12) |

### Group A — paid frontier (**Standard mode only — all blocked today**)

**3.1 Claude (Opus 5 / Sonnet 5)** — tops the July-2026 intelligence ranking; the
*judge*: Pillar 2 grading, Pillar 3 claim-verifier, authenticity passes.
· **Crossover:** already wired (`anthropic`, native messages API) — nothing to build.
· **Unnecessary if** you only need generation; local Llama/Qwen write acceptable scripts.

**3.2 GPT-5.6 (OpenAI)** — ~1M context; already the *de-facto vision provider*
(`assets/thumbnail_scorer._vision_score`). · **Crossover:** already wired **and**
already doing vision — adding it is a no-op. · **Unnecessary if** free tiers pass your bar.

**3.3 Gemini 3.x Pro** — the one genuinely differentiated capability in this list:
**native video + audio ingestion** (~2M ctx) — it could watch the *rendered video*,
not just frames, which is the exact shape of the open Pillar-2 item.
· **Unnecessary if** frame-sampling suffices. · **Caveat:** video input may not proxy
through OpenRouter, so this is the one most likely to need a native entry.

**3.4 Grok 4.5** — cheapest frontier (~$2/$6) and the only one with **live X/web access**.
· **⚠ Reframed for paid-off:** previously pitched as "displaces the paid `twitter`
signal" — but Free mode **already skips `twitter`**, so Grok wouldn't *remove a cost*,
it would **restore a capability Free mode drops**. · **Gate:** an LLM summary is not a
citable source; the Pillar-3 grounding spine needs attributable URLs. **Unverified.**

**3.5 Kimi K3** — 2.8T MoE, 1M ctx, native vision, always-on reasoning, structured
JSON, $0.30 cache hits. Long-context synthesis: Phase R transcripts, vault-wide
reasoning (Pillar 4), SkillOpt repo/trace analysis (Pillar 7), prompt-eval corpora.
It's the *brain* for the 2026-07 tool adds (ComfyUI generates → K3 grades; whisperx
transcribes → K3 reasons; notebooklm ingests → K3 synthesizes).
· **Unnecessary if** no workload exceeds DeepSeek's context — and **unusable in Free
mode** (§2).

### Group B — open-weight / local (**what actually runs today**)

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

| Pipeline job | **$0 option (today)** | **Paid upgrade** | What staying free costs you |
|---|---|---|---|
| Discovery / extraction | Ollama local (`extract` tier) | DeepSeek V3 | Slower; more parse retries on messy pages |
| Script generation | Ollama local (`premium` tier) | DeepSeek → Claude/GPT | Flatter prose, weaker stance-holding; the biggest *quality* gap |
| Grading (Pillar 2) | local model self-grading | **Claude** (best judge) | A weak judge grading a weak writer — correlated blind spots |
| Claim verification (Pillar 3) | local + DuckDuckGo | Claude / Kimi | Lower recall on subtle fused claims |
| Thumbnail / vision | **none** (heuristic fallback only) | GPT-5.6 today; **Gemini** for video | No real vision review — heuristics only ⚠ see §5.1 |
| Long-context synthesis | limited by local ctx (~8–128K) | Kimi K3 / Gemini | Chunking instead of whole-vault reasoning |
| Recency | DuckDuckGo + RSS + free reddit/yt | Grok live X; Apify twitter/tiktok | **`twitter` + `tiktok_trends` simply absent** |
| Voice | Piper / Kokoro / XTTS | ElevenLabs | Less natural delivery |

Per [free_mode.md](free_mode.md), local inference is **slower and lower-quality** than
paid models and wants ~8GB+ RAM (GPU ideal) — that is the honest headline tradeoff,
and it is stated by the project itself, not inferred here.

## 5. Reevaluated verdict (paid off)

### 5.1 Close the Free-mode never-pay gap — *correctness, $0 spend* ⚠
`assets/thumbnail_scorer.py` calls paid OpenAI **directly** via the legacy
`core/llm_client.get_openai_client()` — bypassing the router **and therefore
`FREE_MODE_STRICT`**. `core/run_mode.py` contains **zero** thumbnail/vision references
and the scorer has no free-mode awareness. Free mode promises it "never falls back to
a paid provider"; this path is outside the guard.

**Precision — this is latent, not a live bug:** the scorer is opt-in and default-off
(`THUMBNAIL_SCORER_ENABLED`), so it only fires if the operator enabled it *and* an
`OPENAI_API_KEY` is present. But that's exactly the configuration a Standard-mode user
who later switches to Free would be in. Routing it through `core/llm_router` (or making
it free-mode aware) both closes the gap and unblocks the Pillar-2 vision path — the same
fix serves both modes. **Highest-value LLM-adjacent work while paid is off.**

### 5.2 Pick the right local model — *the only live model decision*
`llama3.1:8b` (documented default) vs `qwen2.5:7b` (documented alternative) is the one
choice that changes output **today**. Worth a real A/B on hook quality and stance-holding
— the two things §4 flags as the biggest free-mode quality gap — before assuming a bigger
pull or a paid tier is needed.

### 5.3 When/if paid returns (Standard mode), in order
1. **Refresh the stale `_DEFAULT_MODELS` IDs** — still pinned to `gpt-4o` and
   `claude-sonnet-4-…` on two **already-wired** providers. Frontier quality for zero
   integration. *Evaluate, don't blind-bump* — cost and prompt behavior shift.
2. **Gemini** — only if the Pillar-2 rendered-video review is the priority (native
   video is the one capability nothing else has).
3. **Grok** — gated on verifying citable source URLs (§3.4).
4. **Kimi K3** — last; paid-only despite open weights (§2), and nothing is blocked on it.

## 6. Crossover / unnecessary — consolidated

| Idea | Verdict |
|---|---|
| "Adopt Claude / GPT / Gemini / Grok / Kimi **now**" | **Moot while paid is off** — `FREE_MODE_STRICT` blocks them at the seam. |
| "Add GPT / add Claude" (Standard) | **Already wired.** No work exists to do. |
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
