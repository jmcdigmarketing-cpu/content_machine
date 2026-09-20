# Credit, Quota & Spend Efficiency

> **Class:** reference · **Status:** living · **Reviewed:** 2026-09-20

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
O10 (reset windows) and O11 (the unified governor) shipped 2026-07-02 / 2026-07-06 —
**the O1–O11 backlog is complete**; open follow-ups are listed under O11 as O12 candidates.

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
in one view.* Remaining: a richer time series. *(The per-run LLM cost line landed
2026-08-14 as O12 part 1 — see below.)*

**O12. Governor follow-ups (part 1)** `[S]` — ✅ **SHIPPED (2026-08-14)**
Two gaps the 2026-08-14 live runs made visible:
1. **Per-provider LLM spend in the run cost line** — `cost_meter.llm_cost_by_provider()`
   splits the token ledger by provider and `format_cost_line(..., llm_by_provider=)`
   renders `llm $0.0059 [deepseek $0.0059 · ollama $0 · openrouter $0]`. Free-by-
   construction calls (Ollama, `:free` slugs) are reported **at $0 rather than dropped**,
   so the operator can see *where* the free-first chain actually served a run.
2. **Cross-run dead-model persistence** — the router's dead-model set was session-only,
   so every new run re-paid the 404 for a retired slug (three consecutive live runs each
   logged the same two). `quota_governor.llm_mark_model_dead()` /
   `persisted_dead_models()` now persist it via the O11 store for
   `LLM_DEAD_MODEL_TTL_SECONDS` (default 24h) with key-hash invalidation — rotating the
   key or repointing `{PROVIDER}_MODEL_<TIER>` clears the record instead of pinning a
   live model off. Surfaced in `ops reliability` under `LLM → dead`. The *check point*
   stays in `llm_router` per §13; only persistence routes through the governor.
Tests: `tests/test_quota_governor.py` (dead-model roundtrip, fingerprint invalidation,
router-survives-a-new-process), `tests/test_cost_meter.py` (split reconciles with the
aggregate; cost line unchanged without the split).

**O10. Reset-window auto-re-enable** `[S–M]` — ✅ **SHIPPED (2026-07-02)**
`core/reset_window.py` encodes the known reset cadences (YouTube Data API: daily
00:00 Pacific; Apify: monthly cycle on `APIFY_RESET_DAY`; Odds: monthly on the
1st). Consumers: a hard Apify **402/monthly-limit** exhaustion now persists
*until the actual cycle reset* instead of re-checking every 6h (auth failures
keep the short 30m TTL; the operator-budget trip keeps the flat TTL so raising
the budget recovers fast), and a quota-blocked YouTube upload retries **5 min
after the real midnight-PT reset** instead of a +1-day heuristic. Reset times
surface in `ops reliability`. Master switch `RESET_WINDOW_AUTO_ENABLE` (default
on) falls back to the old flat-TTL behaviour. Tests: `tests/test_reset_window.py`.
*Saving: recovers usable quota the breaker would otherwise waste, and stops
pointless re-checks against a wall that won't move until the cycle turns.*

### Tier 4 — unify

**O11. Single quota governor** `[L]` — ✅ **SHIPPED (2026-07-06)**
`core/quota_governor.py` is now the **single module that talks to the cross-run
persistence store** (`core/quota_state.py` → `data/quota_state.json`) on behalf
of every credit subsystem — the endpoint of O2–O10:

- **Signals** (scope `"signal"`): persistent per-signal breaker records with
  **key-hash invalidation** (the O2 leftover): a hard trip (quota/auth/no_key)
  persists across runs (`SIGNAL_BREAKER_PERSIST`, default on), and a changed
  credential env var (`_SIGNAL_CREDENTIAL_ENVS` map) clears the record
  immediately instead of waiting out the TTL. 429 cooldowns stay session-only.
- **Apify** (scope `"apify"`): `apify_client._sync_persistent` /
  `_persist_exhausted` and the preflight usage cache (O3) route through
  `apify_is_exhausted` / `apify_mark_exhausted` / `apify_get_usage` /
  `apify_set_usage`. TTL/reset *policy* (auth 30m, 402 → cycle reset per O10)
  stays in `apify_client`.
- **LLM** (kv `llm_spend:<date>`): the router's daily-spend tracking (O7) goes
  through `llm_add_spend` / `llm_spend_today` / `llm_reset_spend`; the
  budget-configured guard stays in the router.
- **`snapshot()`** — one fail-open read of everything persisted (apify / llm /
  signals), consumed by `ops reliability` alongside the in-process breakers.

No env or file-format changes — same scopes/keys, `core/quota_state.py` remains
the dumb store underneath. Tests: `tests/test_quota_governor.py` (facade
roundtrips, key-hash invalidation, snapshot shape), `tests/test_circuit_breaker.py`.
*Follow-ups (O12 candidates):* YouTube units under a governor scope; per-provider
spend in the run cost line; reliability time series.

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
6. ✅ **O10** — reset-window auto-re-enable (`core/reset_window.py`). *(2026-07-02)*
7. ✅ **O11** — the governor: one persistence façade + unified snapshot. *(2026-07-06)*

~~Also still open from O2: **signal-breaker persistence** (needs key-hash
invalidation so a fixed key clears the record).~~ ✅ **SHIPPED (2026-07-06)** as
the O11 governor seed — see O11 above.

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
| `RESET_WINDOW_AUTO_ENABLE` | **shipped (O10)** | persist exhaustions until the provider's real reset (off = flat TTLs) |
| `APIFY_RESET_DAY` | **shipped (O10)** | day-of-month the Apify usage cycle resets (default 1) |
