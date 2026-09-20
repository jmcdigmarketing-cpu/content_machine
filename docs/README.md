# Documentation index

> **Class:** index · **Status:** living · **Reviewed:** 2026-09-20

Every doc in this repo, by what it is for. Conventions:
[docs_standard.md](docs_standard.md). Current verdict on the system:
[audit_2026-09.md](audit_2026-09.md). What happens next:
[master_plan.md](master_plan.md).

**Status keys.** `living` = kept true at HEAD · `frozen` = true on its date, never
edited after · `archived` = superseded, kept for the reasoning.

## Start here

| Doc | For |
|---|---|
| [../README.md](../README.md) | What the product is and how to run it |
| [../CLAUDE.md](../CLAUDE.md) · [../AGENTS.md](../AGENTS.md) | Agent entry points — read before editing code |
| [master_plan.md](master_plan.md) | The canonical forward plan (M0–M5) |
| [audit_2026-09.md](audit_2026-09.md) | Where the system actually stands, with evidence |
| [HANDOFF_SYNOPSIS.md](HANDOFF_SYNOPSIS.md) | State as of the last working session |

## Charter — why this exists

| Doc | |
|---|---|
| [vision.md](vision.md) | 12-month architecture and the thesis |
| [positioning.md](positioning.md) | Positioning and product split |
| [project_brief.md](project_brief.md) | The brief in one page |

## Reference — how it works now

| Doc | |
|---|---|
| [architecture.md](architecture.md) | Pipeline, modules, data flow |
| [decisions.md](decisions.md) | ADR-lite. §18, §24, §25, §26 are required reading |
| [credit_efficiency.md](credit_efficiency.md) | Credit, quota and spend efficiency (O1–O12) |
| [llm_provider_strategy.md](llm_provider_strategy.md) | Router tiers, providers, what each adds |
| [data-sources.md](data-sources.md) | Stats, blogs and APIs behind the signals |
| [signals-and-sources.md](signals-and-sources.md) | Signals, zeros, expanding sources |
| [apify-data-sources.md](apify-data-sources.md) | The paid Apify layer |
| [analyst-intelligence.md](analyst-intelligence.md) | The analyst layer |
| [post_scheduling.md](post_scheduling.md) | Scheduling and the upload queue |
| [agent_collaboration.md](agent_collaboration.md) | How Cursor and Claude Code split work here |
| [moneyprinter_vs_content_os.md](moneyprinter_vs_content_os.md) | Clip pipeline, compared |
| [docs_standard.md](docs_standard.md) | The rules this index obeys |

## Runbooks — how do I do X

| Doc | |
|---|---|
| [debugging.md](debugging.md) | Operator troubleshooting, hallucination triage |
| [startup-powershell.md](startup-powershell.md) | Windows/PowerShell command cheat-sheet |
| [free_mode.md](free_mode.md) | Running at $0 |
| [providers_runbook.md](providers_runbook.md) | Pillar 6 seams: tool → module → env → proof |
| [adding-a-data-source.md](adding-a-data-source.md) | Adding a signal end to end |
| [domain-expansion.md](domain-expansion.md) | Standing up a new domain/channel |
| [platform_publish_setup.md](platform_publish_setup.md) | Platform publishing setup |
| [youtube_quota_increase.md](youtube_quota_increase.md) | Quota-increase checklist |
| [policy_incident_runbook.md](policy_incident_runbook.md) | When a policy strike lands |
| [n8n_recipes.md](n8n_recipes.md) | n8n companion recipes |
| [claude_code_usage.md](claude_code_usage.md) | Plan mode, subagents, memory on this repo |
| [cursor_audit_prompt.md](cursor_audit_prompt.md) | The audit prompt handed to Cursor |

## Plans — what happens next

| Doc | |
|---|---|
| [master_plan.md](master_plan.md) | **Canonical.** Horizons M0–M5 |
| [roadmap.md](roadmap.md) | Item-level open/shipped ledger |
| [operating_plan.md](operating_plan.md) | Pace, cost, channels, ops |
| [content_intelligence_roadmap.md](content_intelligence_roadmap.md) | *archived* → master_plan.md |
| [groundwork_2026Q3.md](groundwork_2026Q3.md) | *archived* → master_plan.md |
| [intelligence_phase.md](intelligence_phase.md) | *archived* → roadmap.md |
| [scope_feature_store_and_research_v2.md](scope_feature_store_and_research_v2.md) | *archived* → master_plan.md |

## Snapshots — true on their date, never edited after

| Doc | Date |
|---|---|
| [audit_2026-09.md](audit_2026-09.md) | 2026-09 — current |
| [audit_2026-08.md](audit_2026-08.md) | 2026-08 |
| [assessment.md](assessment.md) | 2026-06, addendum 2026-08 |
| [code_audit_2026-07.md](code_audit_2026-07.md) | 2026-07 |
| [efficiency_audit_2026-07.md](efficiency_audit_2026-07.md) | 2026-07 |
| [next_ideas_2026-07.md](next_ideas_2026-07.md) | 2026-07 |
| [tooling_landscape.md](tooling_landscape.md) | 2026-07 — 17 tools compared |
| [video_creation_stack.md](video_creation_stack.md) | 2026-07 |
| [strategy_2026H2.md](strategy_2026H2.md) | 2026-H2 strategy memo |
| [tool_integration_plan.md](tool_integration_plan.md) | 2026-08-25 — top 7 |
| [agent_reach_evaluation.md](agent_reach_evaluation.md) | 2026-08 — free/keyless backends |
| [case_study.md](case_study.md) | Pipeline case study |

## Logs — append-only

| Doc | |
|---|---|
| [change_log.md](change_log.md) | What shipped, by theme |
| [planning_log.md](planning_log.md) | Brainstorming and decisions, by session |
| [HANDOFF_SYNOPSIS.md](HANDOFF_SYNOPSIS.md) | Session state, newest wave first |

## Directory-scoped rules

Closer to the code and more specific than anything above — obey them when working in
that directory: [`tests/CLAUDE.md`](../tests/CLAUDE.md) (store isolation),
[`apis/CLAUDE.md`](../apis/CLAUDE.md) (signal contract, thread-safety, breaker layering).
