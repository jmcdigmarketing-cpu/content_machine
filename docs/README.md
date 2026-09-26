# Documentation index

> **Class:** index · **Status:** living · **Reviewed:** 2026-09-26

Every doc in this repo, by what it is for. Conventions:
[docs_standard.md](docs_standard.md). Current verdict on the system:
[audit_2026-09-26.md](audit_2026-09-26.md). What happens next:
[master_plan.md](master_plan.md).

**Status keys.** `living` = kept true at HEAD · `frozen` = true on its date, never
edited after · `archived` = superseded, kept for the reasoning.

## Start here

| Doc | For |
|---|---|
| [../README.md](../README.md) | What the product is and how to run it |
| [../CLAUDE.md](../CLAUDE.md) · [../AGENTS.md](../AGENTS.md) | Agent entry points — read before editing code |
| [master_plan.md](master_plan.md) | The canonical forward plan (M0–M5) |
| [audit_2026-09-26.md](audit_2026-09-26.md) | Where the system actually stands, with evidence |
| [handoff_synopsis.md](handoff_synopsis.md) | State as of the last working session |

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
| [vault.md](vault.md) | The Obsidian vault end to end: layout, tiers, what is read back, ops verbs |
| [credit_efficiency.md](credit_efficiency.md) | Credit, quota and spend efficiency (O1–O12) |
| [llm_provider_strategy.md](llm_provider_strategy.md) | Router tiers, providers, what each adds |
| [data_sources.md](data_sources.md) | Stats, blogs and APIs behind the signals |
| [signals_and_sources.md](signals_and_sources.md) | Signals, zeros, expanding sources |
| [apify_data_sources.md](apify_data_sources.md) | The paid Apify layer |
| [analyst_intelligence.md](analyst_intelligence.md) | The analyst layer |
| [post_scheduling.md](post_scheduling.md) | Scheduling and the upload queue |
| [agent_collaboration.md](agent_collaboration.md) | How Cursor and Claude Code split work here |
| [moneyprinter_vs_content_os.md](moneyprinter_vs_content_os.md) | Clip pipeline, compared |
| [data_sourcing_strategy.md](data_sourcing_strategy.md) | Sourcing policy: APIs vs scrapers, per source |
| [ops_commands.md](ops_commands.md) | Generated `ops` command reference (`ops command-ref`) |
| [docs_standard.md](docs_standard.md) | The rules this index obeys |

## Runbooks — how do I do X

| Doc | |
|---|---|
| [debugging.md](debugging.md) | Operator troubleshooting, hallucination triage |
| [startup_powershell.md](startup_powershell.md) | Windows/PowerShell command cheat-sheet |
| [free_mode.md](free_mode.md) | Running at $0 |
| [providers_runbook.md](providers_runbook.md) | Pillar 6 seams: tool → module → env → proof |
| [adding_a_data_source.md](adding_a_data_source.md) | Adding a signal end to end |
| [domain_expansion.md](domain_expansion.md) | Standing up a new domain/channel |
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
| [backlog.md](backlog.md) | Full open-item inventory (roadmap.md stays short) |
| [desktop_app.md](desktop_app.md) | The Windows application programme |
| [content_quality_plan.md](content_quality_plan.md) | Five quality issues, traced and planned |
| [spec_quality_fixes_1_to_4.md](spec_quality_fixes_1_to_4.md) | Code-ready specs for quality fixes §1–§4 |
| [spec_background_query_entity_anchor.md](spec_background_query_entity_anchor.md) | Code-ready spec for entity-anchored background queries |
| [engineering_standards_backlog.md](engineering_standards_backlog.md) | Hygiene/standards backlog |
| [content_intelligence_roadmap.md](content_intelligence_roadmap.md) | *archived* → master_plan.md |
| [groundwork_q3_2026.md](groundwork_q3_2026.md) | *archived* → master_plan.md |
| [intelligence_phase.md](intelligence_phase.md) | *archived* → roadmap.md |
| [scope_feature_store_and_research_v2.md](scope_feature_store_and_research_v2.md) | *archived* → master_plan.md |

## Snapshots — true on their date, never edited after

| Doc | Date |
|---|---|
| [audit_2026-09-26.md](audit_2026-09-26.md) | 2026-09-26 — **current**; before→after of the 09-20 findings |
| [audit_2026-09.md](audit_2026-09.md) | 2026-09-20 |
| [audit_2026-08.md](audit_2026-08.md) | 2026-08 |
| [assessment.md](assessment.md) | 2026-06, addendum 2026-08 |
| [code_audit_2026-07.md](code_audit_2026-07.md) | 2026-07 |
| [efficiency_audit_2026-07.md](efficiency_audit_2026-07.md) | 2026-07 |
| [next_ideas_2026-07.md](next_ideas_2026-07.md) | 2026-07 |
| [tooling_landscape.md](tooling_landscape.md) | 2026-07 — 17 tools compared |
| [video_creation_stack.md](video_creation_stack.md) | 2026-07 |
| [strategy_h2_2026.md](strategy_h2_2026.md) | 2026-H2 strategy memo |
| [tool_integration_plan.md](tool_integration_plan.md) | 2026-08-25 — top 7 |
| [agent_reach_evaluation.md](agent_reach_evaluation.md) | 2026-08 — free/keyless backends |
| [case_study.md](case_study.md) | Pipeline case study |
| [audit_2026-06-25.md](audit_2026-06-25.md) | 2026-06-25 — optimization ideas |
| [brainstorm_directions.md](brainstorm_directions.md) | 2026-06-25 — ranked directions |
| [external_sources_review.md](external_sources_review.md) | 2026-06-25 — candidate sources |
| [idea_quality_diagnosis.md](idea_quality_diagnosis.md) | 2026-08-30 — why the ideas are bad |
| [strategy_next_level.md](strategy_next_level.md) | 2026-08-30 — where this can go |
| [gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md) | 2026-09-08 — external review |
| [gpt6_part2_upgrades_2026-09-08.md](gpt6_part2_upgrades_2026-09-08.md) | 2026-09-08 — external upgrade list |
| [run_76.md](run_76.md) | 2026-09-13 — live-run postmortem |
| [engine_upgrades.md](engine_upgrades.md) | 2026-09-20 — measured against 38 run traces |
| [tooling_review_2026-09-26.md](tooling_review_2026-09-26.md) | 2026-09-26 — extractors, JS pages, football data, vault API; verified that day |

## Logs — append-only

| Doc | |
|---|---|
| [change_log.md](change_log.md) | What shipped, by theme |
| [planning_log.md](planning_log.md) | Brainstorming and decisions, by session |
| [handoff_synopsis.md](handoff_synopsis.md) | Session state, newest wave first |
| [handoff_synopsis_archive.md](handoff_synopsis_archive.md) | Waves older than the newest three, frozen |
| [planning_log_2026-08.md](planning_log_2026-08.md) | August 2026 planning entries, frozen |
| [planning_log_2026-07.md](planning_log_2026-07.md) | July 2026 planning entries, frozen |
| [handoff.md](handoff.md) | The mailbox — read first when starting work |
| [roadmap_archive.md](roadmap_archive.md) | Completed roadmap items, never edited again |

## Directory-scoped rules

Closer to the code and more specific than anything above — obey them when working in
that directory: [`tests/CLAUDE.md`](../tests/CLAUDE.md) (store isolation),
[`apis/CLAUDE.md`](../apis/CLAUDE.md) (signal contract, thread-safety, breaker layering).
