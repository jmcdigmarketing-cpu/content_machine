# tests/ — isolation rules

Supplement to the root [CLAUDE.md](../CLAUDE.md). Runner is **unittest** (CI:
`python -m unittest discover -s tests`) — write `unittest.TestCase` classes, not
pytest fixtures (pytest runs them fine, the reverse isn't true).

- **Any test that can touch persisted quota state must isolate the store**: patch
  `quota_state.QUOTA_STATE_FILE` to a temp dir. Poisoning the real
  `data/quota_state.json` silently disables paid signals for the operator's real
  runs (an exhaustion record persists up to a full billing cycle).
  Reuse the existing bases instead of hand-rolling: `GovernorCase`
  ([test_quota_governor.py](test_quota_governor.py)) or `_IsolatedStateCase`
  ([test_circuit_breaker.py](test_circuit_breaker.py)).
- Same idea for other stores: `data/youtube_quota.json`, `data/cache_stats.json`,
  `data/experiments.json`, `data/traces/` — never let a test write to the real
  `data/` files.
- A test that drives `run_pipeline` into `_finalize_run` must also patch the
  Pillar-1 ledger writes — `core.pipeline.build_quality` (returns `{}`),
  `core.pipeline.persist_quality`, `core.pipeline.write_run_trace` — or it will
  write real `data/traces/<id>.json` files and hit the live DB
  (see [test_pipeline_smoke.py](test_pipeline_smoke.py) for the pattern).
- No network in tests — mock `requests`/clients; signals must be tested through
  `make_signal()`-shaped fakes.
- Credential env vars leak between tests: wrap in `patch.dict("os.environ", ...)`
  (key-hash invalidation makes the governor sensitive to env changes).
