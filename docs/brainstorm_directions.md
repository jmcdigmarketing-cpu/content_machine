# Directions & Priorities — Brainstorm (2026-06-25)

**Planning only.** Two parts:
- **Part A** — a single *ranked* index of everything the cloud planning phase has
  produced (quality fixes, optimization audit, engineering standards), so there's one
  "do-this-first" view. Flags: **Type · Effort · Risk**.
- **Part B** — a wider brainstorm *beyond* audits: new capabilities and **tangential
  / spin-off projects** that reuse the engine the machine already has. Flags:
  **Type · Leverage (impact ÷ effort) · Risk · Horizon** (Now / Adjacent / Moonshot).

> Nothing here is committed work. Tangential ideas are deliberately speculative —
> ranked so the exciting-but-expensive ones don't crowd out the cheap wins.

---

## Part A — Ranked index of existing cloud-phase plans

Everything already specced/planned, ordered by **leverage at lowest risk** (do top
to bottom). Sources: [content_quality_plan.md](content_quality_plan.md),
[spec_quality_fixes_1_to_4.md](spec_quality_fixes_1_to_4.md),
[spec_background_query_entity_anchor.md](spec_background_query_entity_anchor.md),
[audit_2026-06-25.md](audit_2026-06-25.md),
[engineering_standards_backlog.md](engineering_standards_backlog.md).

| Rank | Item | Type | Effort | Risk | Source |
|---|---|---|---|---|---|
| 1 | Voice `voice_pool` config swap (tapin/moneywise) | Quality | `[S]` | None | QP §2 P1 |
| 2 | Entity-first background query (Ronaldo fix) | Quality | `[S–M]` | Low | Spec §5 / P1 |
| 3 | Superlative/recency prompt rule | Grounding | `[S]` | Low | Spec §1 P1 |
| 4 | Secret-scan pre-commit hook | Standards | `[S]` | None | ESB #8 |
| 5 | CI hardening (matrix/pip-audit/bandit/coverage) | Standards | `[S–M]` | None | ESB #7 |
| 6 | Config-flag helper + `print()`→logging | Standards | `[S–M]` | Low | ESB #1, #3 |
| 7 | B-roll cross-beat dedup (GTA VI) | Quality | `[S–M]` | Low | Spec §3 / §5 |
| 8 | Repo-metrics single source (`docs/metrics.md`) | Hygiene | `[S]` | None | Audit D1 |
| 9 | Recency-claim detector + reground wiring | Grounding | `[M]` | Low | Spec §1 P2–3 |
| 10 | `loudnorm` (audio consistency, no copyright) | Polish | `[S]` | Low | Spec §4-A |
| 11 | Coverage + conftest network-guard | Standards | `[S–M]` | Low | ESB #10 |
| 12 | Anti-repeat voice rotation state | Quality | `[S]` | Low | Spec §2 P2 |
| 13 | `core/ui.py` → `core/ui/` package split | Hygiene | `[M]` | Low | Audit B1 |
| 14 | Annotate the 31 silent excepts | Hygiene | `[S–M]` | Low | Audit B2 |
| 15 | Music bed + sidechain ducking | Polish | `[M]` | **Copyright** | Spec §4-A |
| 16 | Ken Burns + `xfade` transitions | Polish | `[S–M]` | Low ⚠render | Spec §4-B/C |
| 17 | Lockfile + Dockerfile/devcontainer | Standards | `[M]` | Low | ESB #5, #6 |
| 18 | Exception taxonomy → shared HTTP client | Standards | `[M]` | Low | ESB #2, #4 |
| 19 | Query variation + cross-video clip memory | Quality | `[M]` | Low | Spec §5 P4 |
| 20 | Hook-archetype rotation (data-driven) | Quality | `[M]` | Low | Spec §4-E |
| 21 | Module-graph de-cycling (`import-linter`) | Standards | `[M]` | Med | ESB #9 |

**The "first afternoon back" set:** ranks **1–6** are all `[S]`/low-risk and touch
six different parts of the machine — a high-visibility, near-zero-danger opening
batch.

---

## Part B — New brainstorm (beyond audits)

### B1. Reuse the engine for new *output surfaces* — same head, new tail
The expensive, defensible part is the **research → grounding → take** head
(`research_brief`, `fact_grounding`, `content_engine`). The video render is just one
tail. Cheap, high-leverage reuses:

- **Text repurpose** `Adjacent` `Lev:High` — same grounded package → blog post / X
  thread / LinkedIn / newsletter copy. No TTS/FFmpeg cost; multiplies channels.
  *(Distinct from roadmap Phase M/R, which are video reposting/clipping.)*
- **Email digest** `Now` `Lev:High` — the existing weekly/`daily_sync` reports
  delivered via Resend (see [external_tooling] thinking) instead of CLI markdown.
- **Newsletter-from-signals** `Adjacent` `Lev:Med` — the de-duped scored signal feed
  is already a "what's trending + why, with sources" object; format it as a recurring
  brief without ever rendering a video.

### B2. Tangential *products / spin-offs* (reputation or revenue)
- **`llm-router` as a standalone OSS package** `Adjacent` `Lev:High` `Risk:Low` —
  `core/llm_router.py` already does task-tier routing, free-first defaults, a real
  per-provider cost ledger, failover, and session breakers across DeepSeek /
  OpenRouter / Ollama / OpenAI / Anthropic. It's self-contained and genuinely useful
  to others. Extracting it builds reputation and pressure-tests the interface — the
  lowest-risk spin-off because it's already modular.
- **Grounded-content API** `Moonshot` `Lev:Med` — expose "fact-checked short script +
  sources for topic X" as an endpoint. The anti-hallucination spine is the
  differentiator competitors lack; this is the moat as a product.
- **"Automated analyst" report service** `Adjacent` `Lev:Med` — productize
  `intelligence_report.py` (already positioned as a freelance deliverable in
  `case_study.md`): scheduled per-topic/vertical reports, delivered as a page or
  email. The render pipeline is optional.
- **Faceless-channel starter template** `Moonshot` `Lev:Med` — the `channels.json`
  domain architecture already makes a new vertical mostly-config. Package a
  one-command "new niche" template (open-source lead-magnet or a paid kit).

### B3. Moat-deepening R&D (turn quality into a *measured* thing)
- **Grounding-eval harness** `Adjacent` `Lev:High` `Risk:Low` — a labeled set of
  `{topic, facts, script}` + a scorer that reports hallucination rate. Turns the
  anti-hallucination work (incl. the planned recency guard) into a metric you can
  *improve against* and regression-test in CI. Could become a small public benchmark.
- **LLM-judge quality gate** `Adjacent` `Lev:Med` — a pre-publish 0–100 score across
  hook/clarity/stance/grounding (hook_score already exists; generalize), logged with
  provenance so the learning loop can correlate prompt/version → engagement.
- **"Why did this win?" attribution view** `Adjacent` `Lev:Med` — join the title-
  pattern leaderboard + length + post-time + domain into a single per-upload
  explanation. Reuses data already captured; pure read-model.

### B4. Operator experience / internal tooling
- **Read-only TUI/web cockpit** `Adjacent` `Lev:Med` — a `textual` TUI or tiny
  FastAPI+htmx viewer over reports, queue, `reliability`, and recommenders. *Lighter
  than the roadmap's deferred "Channel Command Center" — a viewer, not a control
  plane.* Good first use of the clean `core/` separation the audit praised.
- **`--dry-run` / self-test command** `Now` `Lev:Med` `Risk:None` — one command that
  exercises discovery→script→(skip render) with fakes, to smoke-test a fresh
  checkout without API keys. Pairs with the container idea; great onboarding + CI.
- **Run "trace" artifact** `Adjacent` `Lev:Med` — dump a single JSON per run (signals
  used, facts, costs, flags, timings — mostly already captured) for offline
  inspection and as the substrate for B3's attribution view.

### B5. Quick delighters (cheap, on-brand)
- **Themeable UI skins** `Now` `Lev:Low` — *(already sketched in roadmap's UI
  section — noted here only so it isn't re-proposed).*
- **Cost-savings "receipt"** `Now` `Lev:Low` `Risk:None` — end-of-run line: "this run
  cost $X; free-first routing saved ~$Y vs all-premium." The ledger already has the
  numbers; it's a motivating, near-zero-effort surface.
- **Source-citation footer** `Now` `Lev:Low` — append the verified-fact source URLs
  to the description/report (builds the authenticity story the 2026 policy rewards).

---

## How to read the ranking

- **Leverage** = rough impact ÷ effort, not absolute value. A `Low` leverage item can
  still be worth doing if it's also near-zero effort/risk.
- **Horizon**: *Now* = days, reuses what exists; *Adjacent* = a contained new module
  or surface; *Moonshot* = a product bet, weeks+ and external dependencies.
- **Highest "excitement ÷ risk" picks** if you want momentum without a big commit:
  **B2 llm-router OSS extract**, **B3 grounding-eval harness**, **B4 `--dry-run`
  self-test** — each reuses something already built and de-risks or amplifies it.

---

## Honest note on phase
Brainstorm + docs has indeed been the cloud phase's output — appropriate while away
from the device, and the planning is now deep enough that several tracks are
shovel-ready. The natural next inflection is **converting the top of Part A into code
+ tests** when you're back at the machine; this doc exists so that conversion starts
from a ranked list, not a blank page. Everything above stays in `docs/` and merges
cleanly into `main`.
