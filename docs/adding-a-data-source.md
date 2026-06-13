# Adding a data source

Content Machine extends through a fixed recipe — the `signal_contract` abstraction is the whole point.

## 1. Implement the provider

Create `apis/{source}_api.py` or `apis/scrapers/{source}.py` (extend `scrapers/base.py` for HTML scrapes).

Return a dict via `make_signal()`:

```python
from apis.signal_contract import make_signal, STATUS_OK

def get_my_signal(topic: str) -> dict:
    return make_signal(
        connected=True,
        active=True,
        score=42,           # 0–100 normalized
        confidence=0.7,     # source-specific certainty
        status=STATUS_OK,
        status_detail="optional hint",
        data={"raw": "payload"},
    )
```

## 2. Register

In `apis/signals_bootstrap.py`:

```python
reg.register("my_source", get_my_signal)
```

`register_signals.build_registry(topic)` picks it up automatically. Respect `CONTENT_SKIP_SIGNALS=my_source`.

## 3. Cache

Use `apis/cache_manager.py` — TTL matched to volatility:

| Volatility | TTL example |
|------------|-------------|
| Live scores | minutes–1h |
| Trends / news | 3–6h |
| Blog RSS / Wikipedia | 6–12h |
| Stats scrapers | 6h |

Add a branch in `register_signals._cache_ttl_for(name)` if not using the default 3h.

## 4. Weight in scoring

Add the signal to domain profiles in `apis/topic_scorer.py` (`_LEARNED_PROFILES` for `gaming`, `ufc`, `nba`, etc.). Without weights, the signal appears in health but not composite score.

Optional: `config/channels.json` → `weight_overrides` per channel.

## 5. Enrich the analyst (not just the score)

Feed into `core/research_brief.py` or `core/analyst_explain.py` so the source improves **narrative**, not noise.

Config-only sources: `config/data_sources.json`, `config/seo/{channel}.json`.

## 6. Test

Add `tests/test_{source}.py`:

- Mock HTTP / scrape
- Assert `connected`, `active`, `score` shape
- Contract: `normalize_signal()` leaves valid `status`

## 7. Document

Add a row to [data-sources.md](data-sources.md) and env vars to `.env.example`.

## Reference implementation

`apis/wikipedia_pageviews_api.py` — free API, cache, spike scoring, registered as `wikipedia`.
