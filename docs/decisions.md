# Decisions (ADR-lite)

Why the load-bearing choices are the way they are. Code says *what*; this says
*why* — so a future change (or a future Claude session) doesn't "fix" something
that was deliberate. Newest near the bottom. Keep entries short.

---

### 1. Every signal returns the same contract
**Decision:** All signal providers return `make_signal(connected, active, score, data, status, …)` (`apis/signal_contract.py`).
**Why:** Discovery fans out across ~30 heterogeneous sources; a uniform shape lets scoring, the health UI, and circuit breaking treat them identically and degrade gracefully when one fails.
**Consequence:** Adding a signal = implement the contract + register it; no pipeline changes.

### 2. Recommenders share one pattern: analytics-or-default + a rationale
**Decision:** Best-bet (topic), length, and post-time (`core/best_bet.py`, `core/length_recommender.py`, `analytics/post_timing.py`) each return an `analytics` result when enough engagement history exists, else a sensible default — always with a human-readable reason string. Best-bet ranks **confidence-first**: per-domain rates are empirical-Bayes-shrunk (`_adjusted_domain_rates`) and adequately-sampled domains outrank thin ones (`_domain_priority`), so a 1-video 39% domain can't beat a 6-video 11% one; picks are also **diversified** across domains (≤1 per domain in the first pass), and a domain the channel has actually published with measured engagement counts as on-brand (`_effective_allowed`).
**Why:** Explainability and graceful cold-start. The operator sees *why* a pick was made and isn't blocked before data exists. A live run exposed the failure of raw-rate ranking + a too-narrow on-brand set: an NBA session got 3 stale 1-sample UFC picks.
**Consequence:** Early picks are tentative (small n) and labelled with `confidence_note`; the diversity pass means the top-N spans the channel's real topic mix instead of stacking one hot-but-thin domain.

### 3. The LLM may only state specifics that are in VERIFIED FACTS
**Decision:** Facts are split into verified vs context-only; "thin facts mode" + anti-hallucination rules forbid inventing patches/heroes/seasons and (for sports) champions/records/results from training memory. The post-gen grounding check (`core/fact_grounding.py`) flags specifics not in the facts — multi-word proper nouns, **sports mononyms** (e.g. LeBron), and version tokens — using **whole-token** matching in the corpus. CLI surfaces this in a dedicated **Fact grounding** section before the Phase O authenticity gate (`display_grounding_report` in `main.py`). When it fires, `content_engine._maybe_reground_script` **regenerates once** to strip them and then **warns on whatever remains** (`GROUNDING_REGEN_ENABLED`, default on). Link-pasted facts are cleaned of promo/teaser junk first (`core/link_facts._is_junk_line`); ESPN and similar hosts may block automated fetch (WAF) — paste text manually.
**Why:** Faceless generation on a stale LLM will confidently invent specifics (we hit "Topuria, the featherweight champion"; and a script once fused a real Giannis→Heat trade with an invented Butler→Celtics one recalled as a stale prediction). Grounding to signals is the moat *and* the 2026-policy survival requirement. The model has no outcome-awareness of its past predictions — grounding is the only defense.
**Consequence:** When signals are thin the script must go opinion/community-level rather than assert specifics. Regen is **"regenerate then warn," not block** — the operator stays in control and still sees the residual warning; the rewrite is only accepted if it reduces unsupported specifics without gutting the script (≥60% word count).

### 4. Operator key facts are ground truth that overrides everything
**Decision:** Pasted "key facts" inject as highest-priority VERIFIED FACTS and override training memory and signals (`prompt_key_facts` → `content_engine`). **All** collected facts persist to `vault/<channel>/_operator_facts/`; the LLM receives a **char budget** (`OPERATOR_KEY_FACT_CHAR_BUDGET`, default 4500) with soft line cap (`MAX_OPERATOR_KEY_FACTS`, default 24). Manual + link facts rank before vault suggestions. Multi-line `paste` mode parses trade trackers. Writing-tip / playbook bullets filtered via `is_writing_tip()`.
**Why:** Recent events live past the LLM cutoff; trade-heavy runs need more than 5 lines. Vault storage ≠ prompt cap — everything is kept for reuse.
**Consequence:** Accuracy on fresh events depends on operator supplying facts (or web-search filling them). ESPN/WAF hosts need manual paste.

### 4b. YouTube title is generated after facts + script, not at discovery
**Decision:** Discovery (`apis/topic_variants.py`) returns editorial **angles** (≤12 words), not publishable titles. The YouTube title is generated in `core/title_generator.py` after operator key facts, script, and grounding — using the script hook + fact corpus. Anti-slop banned phrases enforced in both stages.
**Why:** Pre-fact title variants were engagement slop ("Just Broke the League") and misled variant selection before the operator pasted trades.
**Consequence:** UI labels discovery picks as "angles"; final title appears after script generation in `main.py`.

### 5. Apify is trend discovery, NOT fact freshness
**Decision:** Apify (reddit/twitter/tiktok/youtube_competitors) feeds *what's trending / community sentiment / competitor angles* — never treated as verified facts. Fact freshness comes from free APIs + Tapology + web search (Tavily/Brave) + manual key facts.
**Why:** Apify is ~$40–200/mo and returns social chatter, not ground truth; conflating the two both costs money and pollutes facts.
**Consequence:** Apify can be fully disabled (circuit breaker) with no loss of factual grounding.

### 6. Paid/quota APIs self-disable for the session — and Apify remembers across runs
**Decision:** A circuit breaker + preflight (`apis/apify_client.py`; generalized signal breaker in `register_signals.py`) skips an API for the rest of the run after a 401/402/403/quota/repeated-timeout. **Apify hard failures additionally persist** to `data/quota_state.json` (`core/quota_state.py`) with a TTL (`QUOTA_STATE_TTL_SECONDS`, default 6h), so a *fresh* process skips Apify instantly instead of re-paying the failing call; the `/users/me` usage reading is likewise cached (`APIFY_USAGE_CACHE_TTL_SECONDS`). The LLM router has the same shape: failover across a provider chain + a session breaker (`core/llm_router.py`).
**Why:** A live run once re-ran failing actors per variant and burned credits + took 300s. Failing once should stop retrying — and the *next* run shouldn't re-pay it either. See [credit_efficiency.md](credit_efficiency.md).
**Consequence:** A transient blip can disable a signal for the session; persisted Apify exhaustion auto-expires after the TTL (or clear `data/quota_state.json`). Signal-breaker persistence is intentionally deferred — auth/no-key disables must not survive the operator fixing the key (needs key-hash invalidation first). `quota_state` is fail-open: a corrupt/unwritable file never blocks a run.

### 7. Social signals are reused across variants, not re-fetched
**Decision:** During per-variant scoring, the slow/paid Apify signals are pinned from the base-topic fetch (`VARIANT_REUSE_SIGNALS`).
**Why:** Social signals barely differ across title variants of the same topic; re-running them 5× was the dominant cost + the discovery hang.
**Consequence:** Variants are differentiated by the title-sensitive signals (youtube) + scoring, not by fresh social calls.

### 8. Channels are config + domain, not code
**Decision:** A channel = a profile in `config/channels.json` + `config/seo/{id}.json`; `infer_domain` (whole-word matching) routes topics to per-domain signal weights/slots. One pipeline serves all channels (tapin gaming/UFC, moneywise finance).
**Why:** Adding a vertical should be configuration, not a fork.
**Consequence:** Domain keyword lists need maintenance; relevance gating (don't run gaming signals on UFC topics) is a known TODO.

### 9. Authenticity/compliance is a first-class gate, not an afterthought
**Decision:** Pre-upload authenticity check, AI disclosure, cadence guardrail (Phase O). Generation actively *earns* the score, not just measures it: if a script reads as a neutral recap, `content_engine._maybe_inject_insight` adds one opinion/prediction beat (grounded only in verified facts) using the gate's own detector (`authenticity.has_insight`), before the grounding regen.
**Why:** YouTube's Jul-2025 "inauthentic content" policy + Jan-2026 termination wave make synthetic-and-shallow faceless content an existential risk. Compliance is the differentiator vs most rivals. A gate that only *flags* a recap still ships the recap — closing the loop (inject the missing beat) is what actually moves the score.
**Consequence:** Some runs are flagged/blocked by design; the operator can override. Injection is grounded + bounded (no invented specifics, ≥90% word count, no-op when a take already exists) and ordered before grounding so it can't smuggle in unsupported claims.

### 10. Repositories are dual JSON/Postgres; the suite runs keyless
**Decision:** Storage uses a repository pattern with a JSON fallback when Postgres/keys are absent; tests must pass with `.env` + OAuth token moved aside.
**Why:** The app must run on a fresh machine without a DB, and CI runs without secrets.
**Consequence:** Before pushing, simulate keyless (move `.env` + token aside, run the suite) to catch CI failures locally.

### 11. Tests + CI are the guardrail against AI churn
**Decision:** Ship features with tests; CI gates lint + format + the suite on 3.11. Targeted edits over rewrites.
**Why:** The "vibe-coding three-month wall" — AI fixes one thing and breaks ten — is held back by acceptance tests on every change.
**Consequence:** A feature without a test is incomplete.

### 12. One line of history; merge before starting the next thing
**Decision:** Avoid long-lived parallel feature branches; land a PR before opening overlapping work.
**Why:** Parallel branches (`youtube-readonly-scope-and-roadmap` vs `recency-intelligence-cycle`) re-implemented overlapping code and diverged into a conflict + a wrongly-diagnosed "revert." That churn is the cost of not consolidating.
**Consequence:** Slightly less parallelism, far less merge pain and lost work.

### 13. The two PRs were consolidated by keeping BOTH sides (2026-06-23)
**Decision:** PR #2 (recency layer) was fast-forwarded into `main`, then `main` was merged into PR #1 (Phase O/P/Q + idea-intake + recommenders) and PR #1 merged — landing everything on `main` (`e6d5c9c`). The 10-file conflict was resolved to **preserve both feature sets**, not pick a winner.
**Why:** The PRs were largely disjoint; dropping either would lose shipped work.
**Consequence — deliberate redundancy a future cleanup must NOT "simplify away":**
- `apis/apify_client.py` keeps PR #1's **global** circuit breaker (`apify_disabled`/`disable_apify`/`apify_preflight`, tripped by 401/402/403 + repeated timeouts) AND exposes `apify_credit_exhausted()` as a thin alias that `core/ui.py`'s run summary imports. Both are intentional; the alias is not dead code.
- `apis/register_signals.py` keeps the per-signal **session circuit breaker** (`_record_signal_health` etc.) AND the broader variant-reuse pinning — different layers, both load-bearing.
- `core/pipeline.py` keeps both `apify_preflight()` (Apify on/off precheck) and the `progress=`/`_report` discovery feedback.
- `main.py` runs both the fact-grounding warning (`core/fact_grounding.py`) and the Phase O authenticity gate (`core/authenticity.py`) before the render prompt — distinct checks.
- `apis/tapology_api.py` exposes one real `scrape_enabled()` with `_scrape_enabled` as a back-compat alias.

### 13b. Exhaustions persist until the provider's REAL reset, not a guessed TTL (2026-07-02)
**Decision:** `core/reset_window.py` encodes known reset cadences (YouTube: daily midnight Pacific; Apify: monthly on `APIFY_RESET_DAY`; Odds: monthly). Apify **402/monthly-limit** exhaustion TTLs are computed to the cycle reset; blocked YouTube uploads retry just after the daily reset. Auth (401/403) failures keep the short 30m TTL and the operator-budget trip keeps the flat 6h TTL — those clear when the *operator* acts, not when the calendar turns. `RESET_WINDOW_AUTO_ENABLE=false` restores flat TTLs.
**Why:** A monthly credit wall re-checked every 6h wastes failing round-trips for weeks; a fixed key or raised budget shouldn't stay blocked until month-end. Matching the TTL to *what actually clears the condition* is the O10 half of the eventual quota governor (O11).
**Consequence:** A 402 near month-end recovers within days automatically; a mid-cycle 402 stays quiet for weeks (correct — the credits won't return sooner). Manual recovery remains: delete `data/quota_state.json`.

### 13c. Trade-direction validation is opt-in and warns, never blocks (2026-07-02)
**Decision:** `core/trade_validation.py` checks that each `player → team` claim in the script co-occurs on a **single fact line**; enabled only via `SEMANTIC_TRADE_VALIDATION` (default off), surfaced after the Fact-grounding section.
**Why:** Token grounding passes a fused trade when both names appear anywhere in the corpus (the Giannis→Heat + invented Butler→Celtics incident). Line-level co-occurrence catches that but false-positives on facts split across pasted lines — so it's an operator-judgment warning, not a gate, and off by default.
**Consequence:** NBA-trade nights can turn it on for an extra check; everyone else pays nothing. If it proves precise in practice, promoting it to default-on is a one-env change.

### 14. All runtime LLM calls go through one router with task tiers (2026-06-23)
**Decision:** `core/llm_router.py` is the single entry point (`complete`/`complete_json`) for every runtime LLM call. Calls pick a **task tier** — `cheap` (tagging, variant titles, background-query, hook regen), `extract` (grounded fact extraction), `premium` (final script, research brief) — and a free-first preference chain resolves each tier to a provider: OpenRouter `:free` anchors cheap (Ollama local fallback), DeepSeek-V3 anchors extract+premium; OpenAI/Claude are opt-in paid upgrades. Direct `OpenAI()` clients and raw Anthropic `requests.post` calls are not added elsewhere.
**Why:** the old code hardcoded gpt-4o and bolted Claude on as duplicated raw HTTP in three places — no way to route cheap work to cheap models, add a provider without touching every call site, or measure per-provider spend. Routing the cheap/extract tiers to free providers (DeepSeek/OpenRouter) takes per-run LLM cost to ~$0 (TTS then dominates); DeepSeek-V3 is near-gpt-4o quality so even premium can stay free. This is operating_plan §4's #1 cost lever.
**Consequence:** a per-provider token ledger prices `cost_meter` for real. Provider **failover** on rate-limit/quota is a deliberate follow-up (see [credit_efficiency.md](credit_efficiency.md) O5–O6), not in the first cut — today a hard provider error degrades the caller (most catch and fall back to rule-based). Groq is wired but not a default (console signup is gated for the operator); Doubao is wired but skipped (China-region-locked, ~$0 savings over DeepSeek/OpenRouter). The multimodal thumbnail scorer stays on `core/llm_client.py` until the router gains a vision path.
