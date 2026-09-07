# Ops command reference

Generated from `scripts/ops.py` `COMMANDS` by `py -m scripts.ops command-ref`.
`ops list` is the live catalog; this file must match it.

| Command | What it does |
| --- | --- |
| `agents` | Agent hand-off: who signed what, and whether the mailbox is stale |
| `all-analytics` | Seed, schedules, weights, sync metrics |
| `all-checks` | Validate channels + unit tests + feed health |
| `all-setup` | First-time / fresh machine setup (non-interactive) |
| `analyst` | Weekly analyst briefing — LLM over the pillars -> lever changes (Pillar 5) |
| `apify-trueup` | Compare synthetic Apify invoice vs $0.02/run model (no network) |
| `artifact-retention` | Report old drafts, traces, and vault _runs clones (dry-run only; never deletes) |
| `artifacts` | Cap output/ by GB (dry-run default; --apply deletes oldest) |
| `backfill-cost` | Repair missing TTS cost on runs that rendered before the fix |
| `backfill-features` | Reconstruct features_json for historical runs |
| `batch-drafts` | N ideas -> N draft scripts, unattended (no render/publish) |
| `blocking` | One-sentence: what's blocking publish (existing gates only) |
| `booth` | Last-run review booth (play + grade + authenticity + cost) |
| `booth-shortcut` | Install Desktop shortcut for the persistent review booth |
| `calibration` | Pre-publish grade vs realized engaged-rate (Pillar 2) |
| `caption-still` | Overlay captions on a still so names can be proofread before burn (--path image, --file script) |
| `channel-go-live` | Fail until OAuth + SEO + feeds + brand kit exist (MoneyWise / any channel) |
| `check-youtube` | Verify YouTube OAuth + upload env |
| `coach` | Daily creator coach — ranked ideas + why, post time, length, patterns |
| `command-ref` | Write docs/ops_commands.md from the live ops list |
| `competitor-health` | Flag dead/unverified competitor YouTube UC ids (RSS probe, no Data API) |
| `competitor-sync` | Fetch recent videos from competitor channels |
| `daily-brief` | Morning one-shot: fresh data, coach ideas, quota health, queue |
| `daily-sync` | Daily competitor + SEO refresh (run once per day) |
| `demonetization` | estimatedRevenue cliff vs channel baseline (missing is unmeasured) |
| `diff-runs` | Compare grade/cost/ungrounded/disputed for two run ids |
| `doctor` | One shot: free stack + feeds + oauth + quota + CUDA + RAM + secrets |
| `dossier` | One run end-to-end: quality, cost, metrics, trace (--run-id required) |
| `economics` | Per-video cost vs revenue -> contribution margin (Pillar 1) |
| `end-card-preview` | Render the channel end card as a PNG still before a full encode (--path dest.png) |
| `experiment` | Script-lever A/B report (start/stop: py -m core.experiments) |
| `feeds` | Check every configured RSS feed — dead/stale sources starve grounding |
| `free-doctor` | Check the truly-free ($0) stack: Ollama, Piper, signals, DuckDuckGo |
| `gen-skills` | Regenerate skills/content-ops/SKILL.md from the ops registry (Agent Skills) |
| `grade` | Pre-publish report card for a run (--run-id required, Pillar 2) |
| `grounding-corpus` | Replay frozen grounding verdicts (no LLM) |
| `health` | Channel health — Green/Yellow/Red across engagement/cadence/cost (Pillar 5) |
| `incidents` | Rank recent signal/provider failures by count x recency |
| `ingest` | Ingest a URL / PDF path / YouTube link into the vault as a provenance note |
| `ingest-clips` | Copy capture clips into video/backgrounds (dry-run default; --apply remuxes) |
| `init-db` | Create SQL tables (Postgres) |
| `intelligence-report` | Content Intelligence Report (signals + brief + competitors, no render) |
| `intro-waveform` | Draw a waveform of the intro sting and print duration vs the 2.15s offset (--path audio) |
| `learn-schedule` | Show static vs learned post slots |
| `lightbox` | Thumbnail lightbox for the last Pillow thumb |
| `list` | List all operator commands |
| `list-uploads` | Rendered MP4s not yet on YouTube |
| `migrate-layout` | Move root runtime files into data/ and config/secrets/ |
| `migrate-schema` | Apply incremental DDL on existing Postgres |
| `moat-backup` | Plan pg_dump + vault + traces backup (secrets excluded; dry-run) |
| `next` | One action to take now across gates, quota, and vault decay |
| `overnight` | Overnight operator — best-bet drafts + grade + vault dossiers (Pillar 5) |
| `paid-signals` | Attribute tiktok_trends / youtube_competitors lift; recommend keep/disable (no catalog write) |
| `pick-thumbnail` | Pick text_on or face_forward for a dual-thumbnail run |
| `playbook-lint` | Warn when untagged strategy bullets can still feed facts |
| `policy-canary` | Hash YouTube inauthentic-content page (local fixture; no HTTP default) |
| `policy-runbook` | Print the strike / Content ID / appeal runbook path |
| `postmortem` | Slowest phase, failed signals, ungrounded claims, cost (--run-id) |
| `prompt-eval` | Golden-topic prompt evals: run (LLM cost) or compare last two |
| `publish-dry-run` | Print the YouTube videos.insert body (no upload; tokens redacted) |
| `publish-ics` | Write an .ics of scheduled publishes beside HTML dumps |
| `queue-manage` | Re-queue after deleting scheduled YouTube video |
| `recommend-length` | Recommend video length from engagement history |
| `recommend-time` | Recommend next post time from engagement history |
| `reliability` | Credit/quota dashboard (Apify + LLM budgets, breakers, cache hit-rate) |
| `render-preview` | Render a 480p ultrafast review copy without changing publish media (--run-id) |
| `requeue-upload` | Queue upload for a rendered run (--run-id required) |
| `retention` | Audience-retention curve + drop-off point (pacing intelligence) |
| `reveal` | Reveal last mp4 (or --kind thumb\|trace) in Explorer |
| `roadmap-index` | Counts per roadmap file and by size, read from the docs |
| `secrets-doctor` | Keys present/missing/placeholder (never prints values) |
| `seed` | Seed TapIn performance + publish history |
| `sendto-facts` | Install Explorer Send-to shortcut targeting facts.txt |
| `seo-refresh` | Refresh trending tag hints (YouTube + RSS) |
| `shell` | Localhost FastAPI operator shell (GET only; no TTS/Apify/publish) |
| `shortcut` | Install Start Menu shortcut via pythonw / content_os.pyw |
| `signal-canary` | Probe every signal at $0 — a dead source found before a real run needs it |
| `skillopt` | SkillOpt-Sleep — gated skill-directive optimizer (frozen prompt-evals gate) |
| `status` | Queue, uploads, recent runs, SEO/competitors |
| `studio-deleted` | Cancel publish_log rows whose YouTube videos were Studio-deleted |
| `sync-metrics` | Pull YouTube Analytics into performance memory |
| `tapology-test` | Scrape Tapology fight card for a topic string |
| `test` | Run unit tests |
| `title-patterns` | Title patterns that engage (A/B variant loop leaderboard) |
| `topic-clone` | Seed a new draft from a winner run (--run-id; angles/facts refresh) |
| `topic-db` | Topic Winners (clone these) + Graveyard (avoided flops) |
| `traces` | Recent run traces — timings, LLM cost, quality, hotspots (Pillar 1) |
| `tray` | System-tray / quota chip (uploads-left + TTS chars + Apify breaker) |
| `tts-arms` | ElevenLabs vs Piper Bayesian report (no auto-switch) |
| `validate` | Validate config/channels.json |
| `vault-decay` | List vault notes whose expires date is in the past |
| `vault-eval` | Vault subject-relevance evals: precision/recall, or compare last two |
| `vault-sync` | Write machine beliefs + run dossiers into the Obsidian vault |
| `voices` | List TTS voices — ElevenLabs account + local Piper — and what each channel uses |
| `weekly-report` | Rules-based weekly intelligence (winners/losers by feature) |
| `weights` | Print learned signal weights for channel |
| `worker` | Process one upload/render job (or use --loop N) |
| `ypp` | YPP / membership readiness: watch-hours proxy, disclosure, cadence |
