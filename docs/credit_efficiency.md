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
| **LLM** | Multi-provider router with free-first tiers + a real per-provider token ledger | `core/llm_router.py`, `core/cost_meter.py` |
| **Per-run cost** | Fully-loaded estimate (now ledger-priced for LLM) | `core/cost_meter.py` |

**Key limitation that motivates this doc:** all breakers are **process-scoped**.
Every fresh `py main.py` invocation re-pays the first failing call per exhausted
provider and re-runs the Apify preflight network round-trip. There is no memory of
"this provider is out of credits" across runs, no operator-set budget ceiling, and
no LLM-provider failover.

---

## 2. Optimization backlog (prioritized)

Effort: `[S]` days · `[M]` 1–2 wk · `[L]` 3+ wk. Each lists the saving.

### Tier 1 — cheap, high-leverage (do first)

**O1. Skip the Apify preflight when no paid signal will run** `[S]`
`run_discovery` calls `apify_preflight()` whenever `APIFY_CONTENT_MACHINE_KEY`
exists — even when domain gating / `CONTENT_SKIP_SIGNALS` / the session breaker have
already removed every paid social signal (`reddit`, `twitter`, `tiktok_trends`,
`youtube_competitors`) for this topic. Compute the active signal set **first**;
only preflight if ≥1 paid social signal survives. *Saving: one `/users/me` call on
every gaming/finance/UFC run that gates out social (the common case).*

**O2. Persist the breaker across runs (file-backed, TTL'd)** `[S–M]`
Write tripped providers/signals to `data/quota_state.json` with a per-reason
expiry: `auth`/`no_key` → long (until env changes / manual reset); `quota` → until
the known reset window (§O10); repeated-timeout → short (~30 min). Load on startup
so a fresh process **skips known-dead providers without re-paying the failing call
or re-running preflight**. *Saving: the first failing call per exhausted provider on
every subsequent run in the same window — the biggest cross-run win.*

**O3. Cache the Apify usage reading with a short TTL** `[S]`
Store `monthlyUsageUsd` + limit from `/users/me` in `data/quota_state.json` with a
15–30 min TTL; a fresh process within that window reuses it instead of a network
preflight. Refresh on expiry or after a 402. *Saving: the preflight round-trip on
back-to-back runs.*

**O4. Operator spend ceiling — degrade before the hard wall** `[S–M]`
`APIFY_MONTHLY_BUDGET_USD` (and per-provider equivalents): trip the breaker when
usage ≥ the **operator's budget**, not only Apify's hard limit. Graceful pre-limit
degradation; the seed of the vision.md "quota & spend governor." *Saving: prevents
ever hitting the painful hard-limit 402 mid-run.*

### Tier 2 — bring the LLM router to parity with the signal breakers

**O5. LLM provider failover** `[M]`
On a retryable status (429 rate-limit, 402, 401/403) from a tier's provider, fall
through to the **next provider in that tier's preference chain** instead of raising.
Mirrors the Apify breaker. Makes OpenRouter free-tier rate limits invisible (fall to
DeepSeek). *Saving: avoids dropped LLM calls degrading to rule-based output, with no
extra spend (next provider is also free).* Wiring point: `core/llm_router.complete`.

**O6. LLM provider session breaker** `[S]`
Once a provider returns a hard auth/quota status, disable it for the session (like
signals) so later tier resolutions skip it. Pairs with O5; reuses the same
`data/quota_state.json` once O2 lands.

**O7. LLM per-day / per-run spend ceiling** `[S–M]`
Use the token ledger (`llm_router.get_usage` → `cost_meter.llm_cost_from_usage`) +
a configurable cap to downgrade `premium`→`cheap` (or stop) when a daily LLM budget
is exceeded. *Saving: bounds the one cost that scales with volume.*

### Tier 3 — observability so the TTLs/budgets are tuned from data

**O8. Cache-hit instrumentation** `[S–M]`
Count hits/misses per signal in `cache_manager`; a signal that's almost always a
cache hit can take a longer TTL, a frequently-missed fast-moving one a shorter TTL.
*Saving: turns the hand-tuned TTLs in `register_signals._cache_ttl_for` into
data-driven ones.*

**O9. Reliability / quota dashboard** `[M]`
`scripts.ops reliability`: per-provider breaker state, Apify usage vs budget,
YouTube units used today, cache-hit rate, per-run LLM cost from the ledger. The
operating_plan §1 "Phase next." *Saving: makes every credit leak visible.*

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

1. **O1 + O3** (one PR) — stop the needless preflight; cache the usage read.
2. **O2** — persist the breaker; immediately compounds O3 across runs.
3. **O5 + O6** — LLM failover + breaker (makes the free OpenRouter tier robust).
4. **O4 + O7** — operator budgets for Apify + LLM.
5. **O8 + O9** — instrument, then surface a dashboard.
6. **O10**, then **O11** (the governor) once the pieces exist to unify.

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
| `APIFY_MONTHLY_BUDGET_USD` | **proposed (O4)** | operator spend ceiling for Apify |
| `LLM_MONTHLY_BUDGET_USD` / `LLM_DAILY_BUDGET_USD` | **proposed (O7)** | LLM spend ceiling → tier downgrade |
| `QUOTA_STATE_TTL_SECONDS` | **proposed (O2/O3)** | freshness of the persisted quota cache |
