# apis/ — signal layer rules

Supplement to the root [CLAUDE.md](../CLAUDE.md); read that first.

- **Every signal returns `make_signal()`'s shape** ([signal_contract.py](signal_contract.py)) —
  status constants, `normalize_signal()`, `classify_http()`. Tests key off the shape directly.
- Signals run concurrently in a `ThreadPoolExecutor` ([register_signals.py](register_signals.py)):
  a signal must be **thread-safe** and must **never raise** — return an error-status signal instead.
- **Never add a cache inside a signal** — `register_signals._fetch_one` + `_cache_ttl_for()`
  already cache every call. A second layer hides credit burn and breaks hit-rate stats.
- Breaker layers are intentionally separate (decisions.md §13): Apify global breaker
  ([apify_client.py](apify_client.py)) · per-signal session breaker + 429 cooldowns
  (register_signals) · cross-run persistence via `core/quota_governor.py` only.
- `reddit` + `youtube_competitors` have free backends ([free_backends.py](free_backends.py),
  `SIGNAL_BACKEND=apify|free|auto`); a backend change must keep both paths returning the
  same signal shape and must keep free-served runs out of the Apify cost meter.
- Domain gating (`_gated_signal_names`) decides which signals run per topic — a new signal
  should declare its domains or it runs for everything.
