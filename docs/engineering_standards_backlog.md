# Engineering Standards Backlog — 2026-06-25

> **Class:** plan · **Status:** living · **Reviewed:** 2026-09-26

Senior-level **standardization / hygiene** work that raises the codebase's
engineering baseline. **Planning only — no code in this pass.**

**Deconfliction (important).** This list **excludes** everything already tracked in
[master_plan.md](master_plan.md) M3 and [backlog.md](backlog.md) #831–#834 (the mypy
ratchet — landed 2026-09-26 as `scripts/mypy_ratchet.py` — and its scope, the ruff bump,
`core/` seams, `apis/scrapers` packaging; broad excepts are M3.4) and in
[audit_2026-06-25.md](audit_2026-06-25.md) (metrics single-source, `ui.py` split,
silent-except annotation, vault index, web-cache collapse, breaker TTL, test-dep
extras, moviepy fragility). Items here are *new* and grounded in counts measured
this pass.

| # | Standard gap | Evidence (measured) | Effort |
|---|---|---|---|
| 1 | Decentralized, untyped configuration | **165** `os.getenv` across **76** files | `[M]` |
| 2 | No domain exception hierarchy | **0** custom exception classes; 6 `raise Exception`; 177 broad catches | `[M]` |
| 3 | `print()` bypasses logging | **104** `print()` in **30** non-CLI modules | `[S–M]` |
| 4 | No shared HTTP/resilience layer | **53** ad-hoc `requests.get/post`, per-call timeouts | `[M]` |
| 5 | No reproducible env (container) | no `Dockerfile` / devcontainer → tests can't run in fresh envs | `[M]` |
| 6 | Hand-synced deps, no lockfile | `requirements.txt` "kept in sync" with pyproject by hand | `[S–M]` |
| 7 | CI under-hardened | single-entry matrix; no security scan; mypy on 5 of ~11 dirs | `[S–M]` |
| 8 | Secret hygiene not enforced | no secret-scan hook despite OAuth + ~12 API keys | `[S]` |
| 9 | Module-graph smell | **154** function-level imports (circular-import workarounds) | `[M]` |
| 10 | No coverage measurement / test infra | no `conftest.py`, no coverage gate, no network guard | `[S–M]` |
| 11 | No release engineering | no semver, tags, or release process (changelog admits it) | `[S]` |

---

## 1. Typed, centralized configuration

**Evidence.** `config/settings.py` has a `Settings` dataclass — but it only covers
credentials + core knobs. The **165** behavioral flags (`RECENCY_*`, `HOOK_*`,
`VOICE_*`, `GROUNDING_*`, `RENDER_*`, …) are read ad-hoc via `os.getenv` in **76
files**, each re-implementing truthy parsing (`.lower() in ("1","true","yes")` vs
`("0","false","no")` — inconsistent defaults and semantics).

**Standard.** One typed settings surface. Minimum: a shared
`config.flags.flag(name, default)` / `int_flag` / `float_flag` helper so parsing is
uniform and every flag is greppable in one module. Better: extend `Settings`
(or adopt `pydantic-settings`) so flags are typed, defaulted, and documented in
code — and `.env.example` is generated from it instead of hand-maintained.
**Why senior:** configuration becomes discoverable, validated at startup (fail-fast
on a malformed flag), and testable (inject settings, don't monkeypatch `os.environ`).

## 2. Domain exception hierarchy

**Evidence.** Zero custom exceptions; the code raises bare `Exception(...)` (e.g.
`core/tts.py:64` "ELEVEN_API_KEY not found", `assets/manager.py` "No background
video found") and catches `except Exception` 177 times. Callers can't distinguish a
*config* error from a *network* error from a *programming* bug.

**Standard.** A small `core/errors.py` taxonomy: `ContentMachineError` base, then
`ConfigError`, `ProviderError` (→ `QuotaError`, `AuthError`), `RenderError`,
`PublishError`. Raise the specific type; catch the specific type. This makes the
broad-except audit (roadmap) *mechanical* — `except ProviderError` documents intent,
and a stray `except Exception` becomes a real smell. **Why senior:** error handling
expresses intent and lets the circuit breakers / retries key off *types*, not status
strings.

## 3. Eliminate `print()` — single logging path

**Evidence.** **104** `print()` calls in **30** non-CLI modules
(`core/tts.py`, render, providers, …) alongside `core/logging.py`. Output bypasses
levels, handlers, and any future structured sink. `logging.py` uses plaintext
`basicConfig` with no run/correlation id.

**Standard.** Reserve `print()` for `main.py`/`scripts/` user-facing UI; everything
in library modules goes through `get_logger(__name__)`. Add an optional structured
(JSON) formatter and a **run-id** bound via `contextvars` so every line in a
generation run correlates. **Deconfliction:** this is the *logging discipline*
prerequisite to the roadmap's observability dashboard — not the dashboard itself.

## 4. Shared resilient HTTP client

**Evidence.** **53** direct `requests.get/post` calls across providers/signals, each
with its own (or missing) timeout, no retry/backoff, no shared User-Agent, no
connection pooling. The circuit breakers sit *above* this but every call still
hand-rolls its own resilience.

**Standard.** `core/http.py`: a configured `requests.Session` (pooling, default
timeout, a `urllib3` `Retry` with backoff on idempotent GETs, standard headers),
exposed as `http_get/http_post`. Providers call it instead of `requests.*`. Pairs
with #2 (raise `ProviderError`/`QuotaError` from one place). **Why senior:** network
resilience and observability live in one tested module, not 53 copies.

## 5. Reproducible environment (container / devcontainer)

**Evidence.** No `Dockerfile`, `docker-compose`, or `.devcontainer`. The suite is
**unrunnable in a fresh env** (this session: `moviepy` wheel fails to build →
39/90 test modules can't import). Local "works on my machine" is the only path.

**Standard.** A `Dockerfile` (Python 3.11 + ffmpeg + pinned deps) and a
`.devcontainer/` so contributors and CI share one image; `docker-compose` to bring
up Postgres for the storage tests. **Why senior:** reproducibility, onboarding in
one command, and CI parity with local. Directly fixes the "can't run tests here"
class of problem rather than working around it.

## 6. Dependency management — lockfile, single source

**Evidence.** `requirements.txt` is **hand-synced** with `pyproject.toml` (its own
header says so) — drift waiting to happen. No lockfile: transitive deps float, so
"works today" isn't reproducible next month.

**Standard.** Generate `requirements.txt` (or `requirements.lock`) from pyproject via
`pip-tools`/`uv` with hashes; make it a CI check that the lock is in sync. Remove the
manual-sync footgun. **Why senior:** builds become deterministic and supply-chain
auditable.

## 7. CI hardening

**Evidence.** `.github/workflows/ci.yml`: the test `matrix` has a **single** entry
(`["3.11"]` — vestigial; earlier docs claimed 3.10–3.12); **no** `pip-audit`/`bandit`
security scan; mypy runs on only `analytics apis core config storage` (not
`video/publishing/youtube/jobs/assets/scripts`); no coverage step; no
`concurrency:` to cancel superseded runs.

**Standard.** Either restore a real version matrix or drop the matrix scaffolding;
add `pip-audit` (deps) + `bandit` (code) jobs; extend mypy to the whole tree (even
if lenient); add a coverage step (#10); add `concurrency: cancel-in-progress`.
**Why senior:** CI should catch security regressions and type drift across the
*whole* codebase, and not waste runners on stale commits.

## 8. Secret-scanning hook

**Evidence.** The project handles **~12 API keys + OAuth client secrets/tokens**, yet
`.pre-commit-config.yaml` has no secret detection (it has whitespace/yaml/merge
hooks, ruff, but no `detect-secrets`/`gitleaks`) and CI has no secret scan. `.env`
and tokens are gitignored — but nothing *enforces* it at commit time.

**Standard.** Add `detect-secrets` (or `gitleaks`) to pre-commit + a CI job with a
baseline. **Why senior:** a single accidental `git add -f` of a token is a credential
leak; defense-in-depth belongs at the commit boundary, not just `.gitignore`.

## 9. Module-graph hygiene

**Evidence.** **154** function-level (`def`-scoped) imports in `core/apis/assets/
config`. A few are lazy-loading heavy deps (legitimate), but at this volume it's the
classic **circular-import workaround** — a sign the module dependency graph has
cycles (e.g. `manager` ↔ `composite` ↔ `background_query` ↔ `category`).

**Standard.** Map the import graph (`pydeps`/`import-linter`), break the cycles
(extract shared types/interfaces to leaf modules), and add an `import-linter`
contract to CI so new cycles fail fast. Then most function-level imports move back to
module top. **Why senior:** a clean acyclic module graph is what makes the
roadmap's planned web-layer adapter a thin add, not a refactor.

## 10. Coverage measurement + test infrastructure

**Evidence.** No `conftest.py`, no `coverage`/`pytest-cov` config, no coverage gate;
tests run via `unittest discover`. No shared fixtures, no guard against a unit test
making a real network call.

**Standard.** Add `pytest-cov` with a reported (then enforced) threshold, a
`tests/conftest.py` with shared fixtures (tmp data dir, fake settings, a
`no_network` autouse guard that fails on real sockets), and surface the % in CI.
**Deconfliction:** the roadmap says "*raise* coverage on render/publish"; this item
is the *measurement + guardrail tooling* that makes that target visible and keeps
unit tests hermetic — not the coverage-writing itself.

## 11. Release engineering

**Evidence.** `change_log.md` states the project "does not yet use semantic
versioning or tagged releases." `pyproject` has a version but nothing tags or
publishes it.

**Standard.** Adopt SemVer + annotated git tags; a lightweight release process
(tag → CI builds the image (#5) → changelog section finalized). Optionally
`release-please`/`towncrier` to derive the changelog from commits. **Why senior:**
versioned, reproducible artifacts make rollbacks and "what's deployed?" answerable.

---

## Suggested sequencing (low-risk → structural)

1. **#8 secret-scan hook** + **#7 CI hardening** `[S]` — pure config, immediate
   safety/quality, no code churn.
2. **#1 flag helper** + **#3 print→logging** `[S–M]` — mechanical, high
   discoverability payoff; do before the typed-settings push.
3. **#10 coverage + conftest network guard** `[S–M]` — makes every later change
   safer to verify.
4. **#6 lockfile** + **#5 Dockerfile/devcontainer** `[M]` — reproducibility;
   together they end the "can't run it here" problem.
5. **#2 exception taxonomy** → **#4 shared HTTP client** `[M]` — #2 first so #4 can
   raise typed errors; together they also make the broad-except cleanup mechanical.
6. **#9 module-graph** `[M]` — last, once the above reduce churn; lands the acyclic
   graph the future web layer wants.
7. **#11 release engineering** `[S]` — once an image (#5) exists to tag.

Each is an independent PR with a test/CI check, per [decisions.md](decisions.md) §11,
and **none changes runtime behavior** — they standardize how the machine is
configured, fails, logs, talks to the network, builds, and ships.

---

## Explicitly out of scope here (already tracked elsewhere)
Tighten mypy *errors*, annotate the broad/silent excepts, raise render/publish
coverage %, Alembic FKs, the observability *dashboard*, the feature store, `ui.py`
split, metrics single-source, vault/web caches, breaker TTL, test-dep extras — see
[master_plan.md](master_plan.md), [backlog.md](backlog.md) and
[audit_2026-06-25.md](audit_2026-06-25.md).
