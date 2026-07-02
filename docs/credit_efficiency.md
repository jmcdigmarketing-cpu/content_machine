# Credit, Quota & Spend Efficiency

How the system avoids burning paid credits/quota, what's shipped, and the
**prioritized backlog** of optimizations. Companion to the cost model in
[operating_plan.md §4](operating_plan.md) and the moat thesis in [vision.md](vision.md)
("quota & spend governor"). Decisions behind the current breakers: [decisions.md](decisions.md)
§5, §6, §7, §13.

> **Principle:** a failing/expensive call should be paid **at most once**, and
> ideally **zero** times when we can already know it will fail or isn't needed.
> Every optimization below moves a check earlier (cheaper) or remembers a result
> longer (fewer repeats).

---

## 1. What's shipped today (baseline)

| Layer | Mechanism | Where |
|---|---|---|
| **Apify** | Process circuit breaker (`_state`) + one-shot preflight (`/users/me` usage vs limit); trips on 401/402/403 + 2 repeated timeouts; 6h result cache | `apis/apify_client.py` |
| **Signals** | Session breaker `_SESSION_DISABLED` — trips on `QUOTA`/`AUTH`/`NO_KEY` (rate-limit only if `SIGNAL_BREAKER_INCLUDE_RATE_LIMIT`); per-signal cache TTLs | `apis/register_signals.py` |
| **Variant reuse** | Slow/paid social signals pinned from the base-topic fetch, not re-fetched per variant | `register_signals._VARIANT_REUSE` |
| **Domain gating** | Skip domain-mismatched signals (no RAWG on a UFC topic) — fewer paid calls | `register_signals._gated_signal_names` |
| **YouTube units** | Quota tracking in `data/youtube_quota.json` | `apis/youtube_quota.py` |
| **Cross-run state** | Persisted TTL'd exhaustion + usage cache (`data/quota_state.json`) | `core/quota_state.py` |
| **LLM** | Multi-provider router: free-first tiers, token ledger, **provider failover + session breaker** | `core/llm_router.py`, `core/cost_meter.py` |
| **Observability** | Cache hit/miss stats (`data/cache_stats.json`) + `ops reliability` dashboard | `apis/cache_manager.py`, `core/reliability.py` |
| **Per-run cost** | Fully-loaded estimate (now ledger-priced for LLM) | `core/cost_meter.py` |

**Waves 1–3 shipped (2026-06-23):** the Apify breaker **persists across runs**
(`core/quota_state.py` → `data/quota_state.json`), the preflight is **skipped when
no paid signal will run** and **reuses a cached usage reading**, the LLM router has
**provider failover + a session breaker**, there are **operator spend ceilings** for
both Apify (`APIFY_MONTHLY_BUDGET_USD`) and LLM (`LLM_DAILY_BUDGET_USD`) that degrade
*before* the hard walls, and a **reliability dashboard** (`ops reliability`) +
**cache-hit instrumentation** make it all visible. See O1–O9 below (marked ✅).
Remaining: signal-breaker persistence, reset-window awareness (O10), and the unified
governor (O11).

---

## 2. Optimization backlog (prioritized)

Effort: `[S]` days · `[M]` 1–2 wk · `[L]` 3+ wk. Each lists the saving.

### Tier 1 — cheap, high-leverage (do first)

**O1. Skip the Apify preflight when no paid signal will run** `[S]` — ✅ **SHIPPED**
`run_discovery` now calls `register_signals.will_use_apify(topic, channel_id)` and
only preflights when ≥1 paid Apify signal (`reddit`, `twitter`, `tiktok_trends`,
`youtube_competitors`) actually survives skip/gating/breaker. *Saving: the
`/users/me` call whenever those signals are skipped or already disabled.*

**O2. Persist the breaker across runs (file-backed, TTL'd)** `[S–M]` — ✅ **SHIPPED (Apify)**
`core/quota_state.py` stores hard Apify 402/limit/auth failures in
`data/quota_state.json` with a TTL (`QUOTA_STATE_TTL_SECONDS`, default 6h). A fresh
process seeds its breaker via `_sync_persistent` and **skips Apify instantly — no
preflight, no failing actor round-trip**. *Signal-breaker persistence is a later
wave (the auth/no-key "fixed my key but still skipped" trap needs key-hash
invalidation first).*

**O3. Cache the Apify usage reading with a short TTL** `[S]` — ✅ **SHIPPED**
`apify_preflight` caches `{usage, limit}` from `/users/me` in `quota_state`
(`APIFY_USAGE_CACHE_TTL_SECONDS`, default 20 min) and reuses it on back-to-back
runs instead of re-hitting the network. *Saving: the preflight round-trip on
repeated runs within the window.*

**O4. Operator spend ceiling — degrade before the hard wall** `[S–M]` — ✅ **SHIPPED**
`APIFY_MONTHLY_BUDGET_USD`: `apify_preflight` (via `_evaluate_apify_usage`) trips the
breaker — and persists it (O2) — when usage ≥ the **operator's budget**, before
Apify's hard limit. Enforced on both the fresh and cached usage paths. *Saving:
never hits the painful hard-limit 402 mid-run.*

### Tier 2 — bring the LLM router to parity with the signal breakers

**O5. LLM provider failover** `[M]` — ✅ **SHIPPED**
`llm_router.complete` resolves a tier to a *chain* (`_resolve_chain`) and, on a
retryable error (429/402/401/403/5xx/timeout), fails over to the next provider
instead of raising. Makes OpenRouter free-tier rate limits invisible (fall to
DeepSeek). Non-retryable errors (e.g. 400) propagate so prompt bugs aren't masked;
an explicit `provider=` pins one with no failover. *Saving: dropped LLM calls no
longer degrade to rule-based output, at no extra spend.*

**O6. LLM provider session breaker** `[S]` — ✅ **SHIPPED**
A hard auth/quota status disables that provider for the session
(`_disable_llm`/`reset_llm_breaker`), so later tier resolutions route around it.
Rate-limits/5xx are transient → failover only, no disable. *(Cross-run persistence
of LLM disables is deferred — free providers' limits reset fast.)*

**O7. LLM per-day spend ceiling** `[S–M]` — ✅ **SHIPPED**
`LLM_DAILY_BUDGET_USD`: `llm_router` tracks today's cross-run spend in
`quota_state` (only when a budget is set — no overhead otherwise), and once it's
exceeded a `premium`/`extract` call downgrades to the free-first `cheap` chain.
*Saving: bounds the one cost that scales with volume; only bites when a tier is
routed to a paid model.*

### Tier 3 — observability so the TTLs/budgets are tuned from data

**O8. Cache-hit instrumentation** `[S–M]` — ✅ **SHIPPED**
`cache_manager` counts hits/misses per key-prefix (signal/source name); counters
persist to `data/cache_stats.json` on `flush_cache_stats()` (after discovery and
again at pipeline end via `finalize_run_observability()`). `get_cache_stats()`
exposes the merged hit-rate. *Now you can see which signals are almost always cached (raise TTL) vs
frequently missed (lower it) — the `register_signals._cache_ttl_for` table becomes
data-driven.*

**O9. Reliability / quota dashboard** `[M]` — ✅ **SHIPPED**
`py -m scripts.ops reliability` (or `py -m core.reliability`) → `core/reliability.py`
gathers Apify breaker/budget + persisted exhaustion, LLM disabled providers + daily
spend vs budget, session-disabled signals, cache hit-rate by prefix, and YouTube
units used today — read-only and fail-open. *Makes the whole credit layer visible
in one view.* Remaining: per-run LLM cost line + a richer time series.

**O10. Reset-window auto-re-enable** `[S–M]`
Encode known reset cadences (YouTube Data API: daily 00:00 PT; Odds: monthly;
Apify: monthly cycle) so a disabled provider auto-re-enables after its reset rather
than staying off until restart. *Saving: recovers usable quota the session breaker
would otherwise waste for the rest of the day/month.*

### Tier 4 — unify

**O11. Single quota governor** `[L]`
Extract one `core/quota_governor.py` holding per-provider state (usage, ceiling,
breaker, reset window, ledger), consulted by Apify, the signal breaker, and the LLM
router. The three scattered breakers become one source of truth with one
persistence file (`data/quota_state.json`) and one dashboard. Endpoint of O2–O10.

> **Do not collapse the layered checks themselves.** Per [decisions.md](decisions.md)
> §13, the Apify global breaker and the per-signal session breaker are *intentionally
> separate layers*. The governor unifies **state + persistence + reporting**, not the
> distinct check points.

---

## 3. Suggested sequencing

1. ✅ **O1 + O3** — stop the needless preflight; cache the usage read. *(wave 1)*
2. ✅ **O2** (Apify) — persist the breaker; compounds O3 across runs. *(wave 1)*
3. ✅ **O5 + O6** — LLM failover + breaker (free OpenRouter tier now robust). *(wave 1)*
4. ✅ **O4 + O7** — operator budgets for Apify + LLM. *(wave 2)*
5. ✅ **O8 + O9** — instrument cache hits, surface the reliability dashboard. *(wave 3)*
6. **O10**, then **O11** (the governor) once the pieces exist to unify. *(next)*

Also still open from O2: **signal-breaker persistence** (needs key-hash
invalidation so a fixed key clears the record).

Each step is independently shippable with a test (per [decisions.md](decisions.md) §11).

---

## 4. Env vars (existing + proposed)

| Var | Status | Effect |
|---|---|---|
| `SIGNAL_CIRCUIT_BREAKER` | shipped | master switch for the signal session breaker |
| `SIGNAL_BREAKER_INCLUDE_RATE_LIMIT` | shipped | also trip on 429 (default off — transient) |
| `CONTENT_SKIP_SIGNALS` | shipped | omit named signals (speed + spend) |
| `DOMAIN_SIGNAL_GATING` | shipped | skip domain-mismatched signals |
| `VARIANT_REUSE_SIGNALS` | shipped | pin slow/paid signals across variants |
| `QUOTA_STATE_TTL_SECONDS` | **shipped (O2)** | how long a persisted Apify exhaustion lasts (default 6h) |
| `APIFY_USAGE_CACHE_TTL_SECONDS` | **shipped (O3)** | reuse window for the last Apify usage reading (default 20m) |
| `APIFY_MONTHLY_BUDGET_USD` | **shipped (O4)** | operator spend ceiling for Apify (trips before the hard limit) |
| `LLM_DAILY_BUDGET_USD` | **shipped (O7)** | daily LLM spend ceiling → premium/extract downgrade to cheap |
