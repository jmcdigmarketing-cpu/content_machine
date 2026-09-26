# CLAUDE.md

Guide for AI coding agents (Claude Code and others) working in this repo. This is
a **pointer + agent-specific guide**, not a duplicate of the docs below — read the
linked doc before touching the area it covers.

> **Read [docs/handoff.md](docs/handoff.md) first, every session.** It is the mailbox:
> what the other agent just did, what it left uncommitted, what it found broken. More
> than one agent works here and nothing signals a switch. Verify it against
> `git log <sha>..HEAD --oneline` and `git status --short` before trusting it, and
> **write your own slot as your last edit** — not from memory next session.

## What this is

Content Machine — the engine; *Content OS* is the operator application built on it
(decisions §33) — a Python CLI for short-form video —
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

Current priorities: [docs/roadmap.md](docs/roadmap.md) — short by design; the
full inventory is [docs/backlog.md](docs/backlog.md), the Windows application programme is
[docs/desktop_app.md](docs/desktop_app.md), and history is
[docs/roadmap_archive.md](docs/roadmap_archive.md). Counts come from
`py -m scripts.ops roadmap-index`, never by hand. The forward horizons those items roll
up into: [docs/master_plan.md](docs/master_plan.md). Where the system honestly stands:
[docs/audit_2026-09.md](docs/audit_2026-09.md) and
[docs/assessment.md](docs/assessment.md). Why the generated ideas/scripts come out the
way they do — the six framing layers and the selection tie:
[docs/idea_quality_diagnosis.md](docs/idea_quality_diagnosis.md); where the project can
realistically go next: [docs/strategy_next_level.md](docs/strategy_next_level.md); what to build
next in the engine itself, measured against the 38 recorded runs:
[docs/engine_upgrades.md](docs/engine_upgrades.md). State as of the last working session
(branch, shipped wave, open items): [docs/handoff_synopsis.md](docs/handoff_synopsis.md).
Brainstorming/decisions from planning sessions: [docs/planning_log.md](docs/planning_log.md)
— **append a dated entry after any substantial planning session** so ideas aren't lost.

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
python -m unittest discover -s tests -t . -v        # tests — CI-blocking; the `-t .` is load-bearing
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
[docs/startup_powershell.md](docs/startup_powershell.md) for the command
cheat-sheet; don't repeat it here.

## Using Claude Code on this repo

See [docs/claude_code_usage.md](docs/claude_code_usage.md) for plan-mode,
subagent, and memory conventions specific to this project.
