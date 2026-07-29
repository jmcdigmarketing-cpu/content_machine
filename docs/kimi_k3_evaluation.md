# Kimi K3 — fit evaluation for Content OS

*Analysis only (2026-07). No integration shipped. How Moonshot AI's Kimi K3 could
serve this project, positioned **alongside** the 2026-07 GitHub adds in
[groundwork_2026Q3.md](groundwork_2026Q3.md) and [tooling_landscape.md](tooling_landscape.md).*

> **Provenance:** specs/pricing from a July-2026 web scan — treat as
> order-of-magnitude, they drift. Sources:
> [OpenRouter](https://openrouter.ai/moonshotai/kimi-k3),
> [Moonshot platform docs](https://platform.kimi.ai/docs/guide/kimi-k3-quickstart),
> [benchmark/pricing roundup](https://benchlm.ai/moonshot/api-pricing).

## 1. What Kimi K3 is

Moonshot AI's frontier model (released 2026-07-16; open weights 2026-07-26). A
2.8T-parameter MoE (16 of 896 experts active) with:

- **1M-token context** (1,048,576 in / up to 262,144 out),
- **native vision / multimodal** input,
- **tool calling** + **always-on reasoning** ("thinking mode" by default — no
  separate reasoning variant),
- **structured JSON** (schema) output and **prompt caching**.

Pricing ≈ **$3 / M input, $15 / M output, $0.30 cache-hit** — roughly the Claude
Sonnet tier, a step up from Kimi K2. Reachable three ways: **OpenRouter**
(`moonshotai/kimi-k3`), the **Moonshot API** (`https://api.moonshot.ai/v1`,
OpenAI-compatible), or **self-hosted open weights**.

## 2. The framing — brain, not tool (why it *complements* the recent adds)

The 2026-07 GitHub adds are **backends/tools**. Kimi K3 is the **LLM brain** that
drives and grades them — orthogonal, not overlapping. It slots into the existing
free-first router (`core/llm_router.py`) as an **opt-in premium** provider; the
free cheap/extract defaults stay exactly as they are.

| Recent add (what it does) | How Kimi K3 amplifies it |
|---|---|
| **ComfyUI** — *generates* thumbnails / b-roll / upscales | K3's **vision** *grades/reviews* the generated frame (which thumbnail reads best; does the b-roll match the beat) |
| **whisperx** + clip-from-source (Phase R) — transcribes long video | K3's **1M context** reasons over an entire multi-hour transcript in one pass to find clip moments |
| **anything-to-notebooklm** / `core/vault_ingest.py` (Pillar 4) — ingests sources into the vault | K3 synthesizes across the **whole vault** at once instead of chunked retrieval |
| **ai-marketing-skills** "Expert Panel" (Pillar 2 grading) | K3 as the **grader** model — tool-calling + always-on reasoning suit a judge role |
| **system_prompts_leaks** eval corpus (Pillar 2) | K3 as the **verifier** model run against the corpus |

**None of these needs K3 to work** — they degrade to today's free models. K3 is the
*quality ceiling* you reach for when a task is worth paying for.

## 3. Where it maps to **open** roadmap items

Cross-referenced to [roadmap.md](roadmap.md) "Next up — all open items":

1. **Router vision path → multimodal rendered-video review (Pillar 2)** *(open)* —
   the router's `complete()` is text-only today. K3's **native vision + OpenAI-
   compatible message shape** means *one* provider covers text **and** image:
   thumbnail scoring and rendered-frame review through a single seam. Strongest fit.
2. **Premium tier option** — K3 joins the router's `premium` chain beside
   OpenAI/Anthropic, uniquely adding **1M context + always-on reasoning + structured
   JSON**. Opt-in; never displaces the free cheap/extract defaults.
3. **1M-context work** — clip-from-source (Phase R) full-transcript scans;
   vault-wide synthesis (Pillar 4); **SkillOpt** whole-repo / run-trace analysis
   (Pillar 7); prompt-eval over large corpora (Pillar 2); research brief over big
   fact/competitor sets.
4. **Agentic / tool-calling** — the claim-verifier (Pillar 3) and grading loops,
   where reasoning quality matters more than cost.
5. **Structured JSON** — hardens `core/content_engine`'s JSON returns (K3's
   schema-constrained output → fewer parse-guard failures).

## 4. Integration seam (noted, **not built** in this task)

Deliberately just documented — it's trivial and opt-in:

- **Text:** one entry in `core/llm_router._PROVIDERS`
  (`kind:"openai"`, `key_env:"MOONSHOT_API_KEY"`, `base_url:"https://api.moonshot.ai/v1"`),
  add to `_DEFAULT_MODELS` + the `premium` chain; or **zero-code** via the existing
  `openrouter` provider with `LLM_PREMIUM_MODEL=moonshotai/kimi-k3`.
- **Cost:** one row in `core/cost_meter._LLM_PRICES` (`kimi-k3: (3.00, 15.00)`).
- **Vision:** a *new* piece — `complete()` would need image content-blocks
  (OpenAI-compatible `content:[{type:"image_url",…}]`). This is the Pillar-2 work
  in §3.1, not a drop-in.
- **Already-safe cost governance:** `LLM_DAILY_BUDGET_USD` (O7) downgrades
  premium→cheap at the ceiling, plus provider failover + session breakers
  ([credit_efficiency.md](credit_efficiency.md)). A paid model is bounded by design.

## 5. Cost / risk & verdict

Kimi K3 is **paid** (~Sonnet tier) and this project is deliberately **free-first**
(DeepSeek + OpenRouter `:free` anchor the tiers). So:

- **Do** reserve it for high-value work: vision review, grading/verification,
  long-context synthesis — tasks where a wrong/blind answer is expensive.
- **Don't** put it on the cheap/extract throwaway tiers; that would burn the budget
  the free models already cover well. Prompt caching ($0.30 hit) offsets the large,
  repeated system prompts if it *is* used on a hot path.

**Verdict: Complement (premium provider).** Highest leverage as the model behind the
**vision path** and **long-context/grading** tasks — the two things the current
free tiers genuinely can't do — while the free-first defaults stay untouched. It is
an *opt-in upgrade*, never a new default, and the vision use is an **unbuilt open
roadmap item**, not a shipped capability.

## Cross-references
- [roadmap.md](roadmap.md) "Next up" (vision path, Pillars 2/4/7, Phase R),
  [tooling_landscape.md](tooling_landscape.md), [groundwork_2026Q3.md](groundwork_2026Q3.md),
  [credit_efficiency.md](credit_efficiency.md) (O7 budget).
- Code seams: `core/llm_router.py` (`_PROVIDERS`, `_DEFAULT_MODELS`, tier chains),
  `core/cost_meter.py` (`_LLM_PRICES`).
