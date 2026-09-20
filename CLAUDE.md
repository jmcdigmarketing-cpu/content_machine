# CLAUDE.md

Guide for AI coding agents (Claude Code and others) working in this repo. This is
a **pointer + agent-specific guide**, not a duplicate of the docs below — read the
linked doc before touching the area it covers.

## What this is

Content Machine (Content OS): a Python CLI for short-form video —
discover signals → score topics → LLM script → TTS → FFmpeg render → optional
YouTube publish — with a closed analytics learning loop (best-bet topic,
recommended length + post-time) and a 2026-policy compliance layer (authenticity
check, AI disclosure, cadence guardrail).

Channels (`config/channels.json`): `tapin` (gaming/UFC shorts), `moneywise`
(finance). Full picture: [README.md](README.md) and
[docs/architecture.md](docs/architecture.md).

**Every doc is indexed in [docs/README.md](docs/README.md)** — start there rather than
globbing `docs/`. Each doc carries a card on line 3 giving its class and whether it is
still true; the conventions are [docs/docs_standard.md](docs/docs_standard.md) and they
are enforced by `tests/test_docs_standard.py`, so a new doc needs a card and an index
entry or CI fails.

The four you will want most: what happens next —
[docs/master_plan.md](docs/master_plan.md) (canonical) with the item-level ledger in
[docs/roadmap.md](docs/roadmap.md); where the system honestly stands —
[docs/audit_2026-09.md](docs/audit_2026-09.md); state as of the last working session —
[docs/HANDOFF_SYNOPSIS.md](docs/HANDOFF_SYNOPSIS.md); brainstorming and decisions from
planning sessions — [docs/planning_log.md](docs/planning_log.md), where you
**append a dated entry after any substantial planning session** so ideas aren't lost.

## Entry points

- `main.py` — interactive CLI (discovery → script → render → publish menu).
- `scripts/ops.py` — operator CLI, run in batch or one-by-one. `py -m scripts.ops
  list` prints all ~38 subcommands. Most-used: `all-checks`, `status`,
  `reliability` (credit/quota/cache dashboard), `weekly-report`, `test`.

## Signal architecture (read this before touching `apis/`)

Every discovery signal returns the same shape via
[`apis/signal_contract.py`](apis/signal_contract.py)'s `make_signal()` (status
constants, `normalize_signal()`, `classify_http()`). Orchestration, the
process-level circuit breaker, domain-aware gating, and cache TTLs all live in
[`apis/register_signals.py`](apis/register_signals.py) — signals run concurrently
in a `ThreadPoolExecutor`, so a new signal must be thread-safe and must never raise.

The remaining paid Apify signals (`tiktok_trends`, `youtube_competitors`) are the
project's main recurring actor cost — `reddit` and `twitter` are retired
(`enabled: false`). Free credits still exhaust in a handful of runs. See
[docs/agent_reach_evaluation.md](docs/agent_reach_evaluation.md)
(free/keyless backend evaluation) and [docs/credit_efficiency.md](docs/credit_efficiency.md).

## LLM router

All LLM calls route through [`core/llm_router.py`](core/llm_router.py) task tiers
(`cheap` / `extract` / `premium`), each with provider failover + a circuit
breaker. Free-first default chain: DeepSeek + OpenRouter (+ optional local
Ollama) — see the router block in [.env.example](.env.example) before adding a
new provider or changing tier routing.

## Commands (mirror `.github/workflows/ci.yml` — "done" means "CI passes")

```powershell
ruff check .                                   # lint — CI-blocking
ruff format --check .                          # format — CI-blocking
mypy analytics apis core config storage        # type check — non-blocking baseline
python -m unittest discover -s tests -t . -v        # tests — CI-blocking (or: pytest -q)
```

## Hard rules

- Never commit `.env` or `config/secrets/` (OAuth files).
- Don't touch Apify credentials, budget, or circuit-breaker logic
  ([`core/cost_meter.py`](core/cost_meter.py), [`apis/apify_client.py`](apis/apify_client.py))
  without reading how the breaker trips first — a wrong change can silently
  disable a paid signal for the whole session (or persist that disablement
  across runs via `data/quota_state.json`). Cross-run breaker persistence goes
  through [`core/quota_governor.py`](core/quota_governor.py) (the O11 façade) —
  don't write to `core/quota_state.py` directly from a subsystem, and keep the
  breakers' *check points* separate per `docs/decisions.md` §13.
- Any change to a signal must preserve `make_signal()`'s output shape — several
  tests key off it directly (e.g. `tests/test_circuit_breaker.py`,
  `tests/test_cadence_and_outlier.py`).
- Don't add a second cache inside a signal — `register_signals._fetch_one` +
  `_cache_ttl_for()` already cache every signal call.

## Windows

Dev environment is Windows/PowerShell — see
[docs/startup-powershell.md](docs/startup-powershell.md) for the command
cheat-sheet; don't repeat it here.

## Using Claude Code on this repo

See [docs/claude_code_usage.md](docs/claude_code_usage.md) for plan-mode,
subagent, and memory conventions specific to this project.
