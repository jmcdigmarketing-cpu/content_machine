# Documentation index

> **Class:** index · **Status:** living · **Reviewed:** 2026-09-26

Every doc in this repo, by what it is for. Conventions:
[docs_standard.md](docs_standard.md). Current verdict on the system:
[audit_2026-10-17.md](audit_2026-10-17.md). What happens next:
[master_plan.md](master_plan.md).

**Status keys.** `living` = kept true at HEAD · `frozen` = true on its date, never
edited after · `archived` = superseded, kept for the reasoning.

## Start here

| Doc | For |
|---|---|
| [../README.md](../README.md) | What the product is and how to run it |
| [../CLAUDE.md](../CLAUDE.md) · [../AGENTS.md](../AGENTS.md) | Agent entry points — read before editing code |
| [master_plan.md](master_plan.md) | The canonical forward plan (M0–M5) |
| [audit_2026-10-17.md](audit_2026-10-17.md) | Where the system actually stands, with evidence |
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
| [decisions_2026-10.md](decisions_2026-10.md) | Decisions 40 onward: overnight may render (§40), a parked channel (§41) |
| [vault.md](vault.md) | The Obsidian vault end to end: layout, tiers, what is read back, ops verbs |
| [credit_efficiency.md](credit_efficiency.md) | Credit, quota and spend efficiency (O1–O12) |
| [llm_provider_strategy.md](llm_provider_strategy.md) | Router tiers, providers, what each adds |
| [data_sources.md](data_sources.md) | Stats, blogs and APIs behind the signals |
| [signals_and_sources.md](signals_and_sources.md) | Signals, zeros, expanding sources |
| [apify_data_sources.md](apify_data_sources.md) | The paid Apify layer |
| [analyst_intelligence.md](analyst_intelligence.md) | The analyst layer |
| [post_scheduling.md](post_scheduling.md) | Scheduling and the upload queue |
| [agent_collaboration.md](agent_collaboration.md) | How Cursor and Claude Code split work here |
| [data_sourcing_strategy.md](data_sourcing_strategy.md) | Sourcing policy: APIs vs scrapers, per source |
| [ops_commands.md](ops_commands.md) | Generated `ops` command reference (`ops command-ref`) |
| [docs_standard.md](docs_standard.md) | The rules this index obeys |

## Runbooks — how do I do X

| Doc | |
|---|---|
| [operator_guide.md](operator_guide.md) | How a video gets made, step by step, one command each |
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

## Plans — what happens next

| Doc | |
|---|---|
| [master_plan.md](master_plan.md) | **Canonical.** Horizons M0–M5 |
| [roadmap.md](roadmap.md) | Item-level open/shipped ledger |
| [operating_plan.md](operating_plan.md) | *archived* → hands_off_plan.md (pace, cost, channels, ops as of 2026-06) |
| [backlog.md](backlog.md) | Full open-item inventory (roadmap.md stays short) |
| [desktop_app.md](desktop_app.md) | The Windows application programme |
| [hands_off_plan.md](hands_off_plan.md) | **Current.** The Story's 22 shortfalls, one section each - where it stands, how it is addressed, who acts, the command for done, its ten ideas in the backlog - then H0/H1/H2 |
| [optimization_plan_2026-10.md](optimization_plan_2026-10.md) | *archived* → hands_off_plan.md (the next 100; backlog epic E7) |
| [cursor_brief_2026-10.md](cursor_brief_2026-10.md) | Cursor's run: media first (footage, thumbnails, voice, Shorts), then the app |
| [cloud_brief_2026-10.md](cloud_brief_2026-10.md) | Tonight's default for a Claude cloud session (2026-10-24): wave 128, with each fix's test data - the cloud has no `data/` |
| [bridge_plan.md](bridge_plan.md) | The bridge (decision 82, 2026-10-27): the race to monetization or big views for little money - the measured state, the lanes and the gate, 300 ideas in twelve sections, the waves in order |
| [bridge_calendar.md](bridge_calendar.md) | The bridge's calendar to 2027-02-01: week by week, the wave, the dated moments (GTA 6 11-19, UFC cards, The Game Awards), the targets and the checkpoints |
| [bridge_scores.md](bridge_scores.md) | The bridge's 300 ideas scored (effect x confidence x urgency / effort), 2026-10-28 - the source of bridge_plan.md's top 30 |
| [cloud_brief_wave133.md](cloud_brief_wave133.md) | Wave 133 for a cloud or PC session: the GTA 6 window - the countdown series, a 16:9 long-form draft kind, affiliate links, launch week |
| [cloud_brief_wave134.md](cloud_brief_wave134.md) | Wave 134: the bridge's scoreboard - the dated YPP bars, engaged views, organic subscribers, the race clock, cost per 1,000 views |
| [cloud_brief_wave135.md](cloud_brief_wave135.md) | Wave 135: speed and volume - Shorts that loop, the breaking-news and results fast lanes, three a day, previews 24-48 hours ahead |
| [cloud_brief_wave136.md](cloud_brief_wave136.md) | Wave 136: money and reach outside YouTube - Facebook Reels, a link-in-bio page, income beside spend, TikTok that can earn |
| [cloud_brief_wave132.md](cloud_brief_wave132.md) | The default for a Claude cloud session (2026-10-26): wave 132 - more interesting topics (decision 81), a 5-8 minute Week in Review, tonight's defects, with each item's fixtures |
| [initiative_cross_platform.md](initiative_cross_platform.md) | Offered to Cursor (2026-10-14): learn per platform from TikTok and Instagram results (#1194-#1199) |
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
| [moneyprinter_vs_content_os.md](moneyprinter_vs_content_os.md) | 2026-08-26 — the clip pipeline against MoneyPrinter's (decisions §26) |
| [cursor_audit_prompt.md](cursor_audit_prompt.md) | the one-off audit prompt handed to Cursor at `e6d5c9c` |
| [backlog_audit_2026-10-18.md](backlog_audit_2026-10-18.md) | 2026-10-18 — 258 open items read: 92 merged into a later entry, 83 retired, 13 shipped, 70 kept |
| [audit_2026-10-17.md](audit_2026-10-17.md) | 2026-10-17 — **current**; CI red six days, the suite reached the real database, Cursor's commits read |
| [audit_2026-09-26.md](audit_2026-09-26.md) | 2026-09-26 — before→after of the 09-20 findings |
| [review_2026-09-26.md](review_2026-09-26.md) | 2026-09-26 — own review: fixes erased by later work, fixes that reached one copy, the regression corpus |
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
| [growth_review_2026-10.md](growth_review_2026-10.md) | 2026-10-06 — why about 500 views, ads, what similar tools do, the one-window app |

## Logs — append-only

| Doc | |
|---|---|
| [project_timeline.md](project_timeline.md) | the official timeline, 2025-05 → today, each entry tagged by its evidence |
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
