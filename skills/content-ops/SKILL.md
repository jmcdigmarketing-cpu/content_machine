---
name: content-ops
description: Operate the Content OS short-form video pipeline via its operator CLI (py -m scripts.ops <command>): discovery, batch drafts, status and reliability dashboards, analytics sync, publish queue, voice catalog, and unattended overnight runs. Use when asked to run, check, or automate Content OS operations.
---

# Content OS operator skill

Run any operator command with:

```bash
py -m scripts.ops <command> [--channel tapin] [--count N] [...]
```

`py -m scripts.ops list` prints this catalog live. Most-used: `all-checks`, `status`, `reliability` (credit/quota/cache), `weekly-report`, `batch-drafts`, `overnight`.

## Commands

| Command | What it does |
| --- | --- |
| `all-analytics` | Seed, schedules, weights, sync metrics |
| `all-checks` | Validate channels + unit tests + feed health |
| `all-setup` | First-time / fresh machine setup (non-interactive) |
| `analyst` | Weekly analyst briefing — LLM over the pillars -> lever changes (Pillar 5) |
| `backfill-features` | Reconstruct features_json for historical runs |
| `batch-drafts` | N ideas -> N draft scripts, unattended (no render/publish) |
| `calibration` | Pre-publish grade vs realized engaged-rate (Pillar 2) |
| `check-youtube` | Verify YouTube OAuth + upload env |
| `coach` | Daily creator coach — ranked ideas + why, post time, length, patterns |
| `competitor-sync` | Fetch recent videos from competitor channels |
| `daily-brief` | Morning one-shot: fresh data, coach ideas, quota health, queue |
| `daily-sync` | Daily competitor + SEO refresh (run once per day) |
| `dossier` | One run end-to-end: quality, cost, metrics, trace (--run-id required) |
| `economics` | Per-video cost vs revenue -> contribution margin (Pillar 1) |
| `experiment` | Script-lever A/B report (start/stop: py -m core.experiments) |
| `feeds` | Check every configured RSS feed — dead/stale sources starve grounding |
| `free-doctor` | Check the truly-free ($0) stack: Ollama, Piper, signals, DuckDuckGo |
| `gen-skills` | Regenerate skills/content-ops/SKILL.md from the ops registry (Agent Skills) |
| `grade` | Pre-publish report card for a run (--run-id required, Pillar 2) |
| `health` | Channel health — Green/Yellow/Red across engagement/cadence/cost (Pillar 5) |
| `ingest` | Ingest a URL / PDF path / YouTube link into the vault as a provenance note |
| `init-db` | Create SQL tables (Postgres) |
| `intelligence-report` | Content Intelligence Report (signals + brief + competitors, no render) |
| `learn-schedule` | Show static vs learned post slots |
| `list` | List all operator commands |
| `list-uploads` | Rendered MP4s not yet on YouTube |
| `migrate-layout` | Move root runtime files into data/ and config/secrets/ |
| `migrate-schema` | Apply incremental DDL on existing Postgres |
| `overnight` | Overnight operator — best-bet drafts + grade + vault dossiers (Pillar 5) |
| `prompt-eval` | Golden-topic prompt evals: run (LLM cost) or compare last two |
| `queue-manage` | Re-queue after deleting scheduled YouTube video |
| `recommend-length` | Recommend video length from engagement history |
| `recommend-time` | Recommend next post time from engagement history |
| `reliability` | Credit/quota dashboard (Apify + LLM budgets, breakers, cache hit-rate) |
| `requeue-upload` | Queue upload for a rendered run (--run-id required) |
| `retention` | Audience-retention curve + drop-off point (pacing intelligence) |
| `seed` | Seed TapIn performance + publish history |
| `seo-refresh` | Refresh trending tag hints (YouTube + RSS) |
| `skillopt` | SkillOpt-Sleep — gated skill-directive optimizer (frozen prompt-evals gate) |
| `status` | Queue, uploads, recent runs, SEO/competitors |
| `sync-metrics` | Pull YouTube Analytics into performance memory |
| `tapology-test` | Scrape Tapology fight card for a topic string |
| `test` | Run unit tests |
| `title-patterns` | Title patterns that engage (A/B variant loop leaderboard) |
| `topic-db` | Topic Winners (clone these) + Graveyard (avoided flops) |
| `traces` | Recent run traces — timings, LLM cost, quality, hotspots (Pillar 1) |
| `validate` | Validate config/channels.json |
| `vault-sync` | Write machine beliefs + run dossiers into the Obsidian vault |
| `voices` | List TTS voices — ElevenLabs account + local Piper — and what each channel uses |
| `weekly-report` | Rules-based weekly intelligence (winners/losers by feature) |
| `weights` | Print learned signal weights for channel |
| `worker` | Process one upload/render job (or use --loop N) |

## Notes

- Windows/PowerShell dev box; command output is ASCII-safe (cp1252).
- Paid signals (Apify) and LLM calls cost credits: check budget first with `reliability` / `free-doctor`; `RUN_COST_MODE=free` pins $0 backends.
- Generated from the ops registry by `py -m scripts.ops gen-skills` (core/ops_skills.py) — edit the registry, not this file.
- Claude Code users can also symlink this folder into `.claude/skills/`.
