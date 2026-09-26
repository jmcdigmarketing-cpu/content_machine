# Content Machine — Positioning & Product Split

> **Class:** charter · **Status:** living · **Reviewed:** 2026-09-26

This repo is intentionally split into two layers. The **intelligence layer** is the portfolio artifact, freelance deliverable, and future micro-SaaS surface. The **production tail** remains for TapIn-style YouTube automation.

## Architecture split

```
┌─────────────────────── INTELLIGENCE LAYER ───────────────────────┐
│  signal aggregation → topic scoring → research brief →            │
│  competitor pulse → Content Intelligence Report                   │
│  (niche-agnostic; analyst artifact + service + SaaS wedge)        │
└───────────────────────────────────────────────────────────────────┘
                                │
                                ▼  (optional, niche-specific)
┌─────────────────────── PRODUCTION TAIL ──────────────────────────┐
│  script → TTS → render → thumbnail → schedule → upload            │
│  (YouTube factory; keep for TapIn, not the resume headline)       │
└───────────────────────────────────────────────────────────────────┘
```

## Analyst levers (v2 report)

Temporal trajectory, corroboration confidence, opportunity-window status, and explainability blocks ship in `intelligence_report_v2`. See [analyst_intelligence.md](analyst_intelligence.md).

## Intelligence layer (what to show employers/clients)

| Capability | Module(s) |
|------------|-----------|
| Multi-source signals | `apis/register_signals.py`, `signal_contract.py`, `cache_manager.py` |
| Opportunity scoring | `apis/topic_scorer.py`, `core/opportunity.py` |
| Research brief | `core/research_brief.py` |
| Competitor pulse | `analytics/competitor_sync.py`, `competitor_context.py` |
| **Report output** | `core/intelligence_report.py` |
| Provenance | `brief_version`, `prompt_version` on `content_runs` |

## How to run intelligence-only

**CLI (batch):**

```powershell
py -m core.intelligence_report --topic "Marvel Rivals Cyclops" --channel tapin
```

**Interactive:**

```powershell
py main.py
# Start menu → 3) Intelligence report only (no script/render)
```

**Env (skip production tail globally — `main.py` prints `Mode: intelligence only`):**

```powershell
set CONTENT_MODE=intelligence
py main.py
```

Reports save to `output/{channel}/reports/` as `.md` and `.json`.

## Resume framing (analyst-track)

Lead with systems thinking and measurement discipline, not video automation:

> Designed and built a multi-source content-opportunity engine aggregating 12+ APIs into a normalized signal layer; implemented domain-weighted scoring with outcome-based learning, competitor tracking, and an LLM research-brief generator. Instrumented with analytics sync, provenance tracking, Postgres/Alembic, and CI.

Interview line: *"I deliberately didn't build the CTR model yet — at my data volume it would've learned from noise."*

See [case_study.md](case_study.md) for the linkable narrative.

## Freelance ladder (powered by the same report)

| Tier | Deliverable | Tooling |
|------|-------------|---------|
| Niche Opportunity Audit | One-time scored report + angles | `intelligence_report` |
| Content Intelligence Retainer | Recurring weekly report | `daily_sync` + report |
| Competitor Pulse add-on | Channel title/timing patterns | `competitor_sync` |
| Per-topic briefs | Structured brief only | `build_research_brief()` |

Start in combat-sports / gaming where niche modules (UFC context, stats scrapers) already work.

## Micro-SaaS wedges (pick one later)

1. **Opportunity scoring API** — `topic_scorer` + `register_signals` (strongest moat with outcome history)
2. **Brief generator** — `research_brief.py` (lowest extraction effort)
3. **Signal aggregation API** — `register_signals` + cache (infrastructure play)

Do not commercialize the full video factory or build all wedges at once.

## Priority order (solo founder)

1. **Report + case study** — days; highest certainty for analyst-track roles
2. **2–3 paid audits** — validates buyers before SaaS infra
3. **One API wedge** — only after real client signal
