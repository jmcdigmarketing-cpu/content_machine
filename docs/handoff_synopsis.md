# Handoff synopsis — 2026-10-03: wave 54, next five

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-10-03

Use in a fresh session to continue `content_machine` without re-reading the full thread.

GPT-6 playground review (2026-09-08, briefing-based): [gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md) and [gpt6_part2_upgrades_2026-09-08.md](gpt6_part2_upgrades_2026-09-08.md). Not a recorded operator decision.

> Older waves and the 2026-07/08 shipped-notes are frozen verbatim in
> [handoff_synopsis_archive.md](handoff_synopsis_archive.md); this file keeps the newest three
> waves plus the standing operator sections (docs_standard.md §7).

## Last wave — 2026-10-03 (Claude Code): wave 54 #934 #935 #936 #937 #114 (+ #939)

The operator's goal is **views**; this wave tracks it and asks for their part in it.

- **#934** `config/goals.json` (placeholder numbers - set yours) and `ops scoreboard`: so far, the
  weekly pace needed vs the last four weeks, where that pace lands, uploads this week, best and
  weakest. The sync keeps the channel's views by day; the banner and weekly report show it.
- **#935 / #936** `ops review-week`: rate each of the week's videos 1-5 with a line of why, set next
  week's focus, get `output/<ch>/reviews/<YYYY>-W<ww>.md`. `ops verdicts`: your gut vs the views.
- **#937** the script prompt shows your top videos by views once 8+ are measured (`ops winners`;
  `WINNERS_IN_PROMPT=false` turns it off).
- **#114** `ops mailbag`: viewers' questions on your uploads, clustered; 2+ askers -> a best bet.
- **#939** `ops signal-audit`'s "cited" column was always 0; it reads the real script now.

**Verify:** `python -m unittest tests.test_wave54_success`; `py -m scripts.ops scoreboard`.

## Previous — 2026-10-03 (Claude Code): wave 53 #930-#933 #929 #591 #573 #586 (#587 closed)

- **#930** the suite skips your `.env` and blanks secret-shaped variables: the 9 failures that only
  your PC showed were seven tests reaching the network with your real keys, plus two harness checks.
- **#931** an all-lowercase overview seeds on the names it mentions ("premier league champions
  league"), and the menu asks `Search for this?` - Enter keeps it, or type a better seed.
- **#932** angles that miss the scoring deadline stay, scored on the seed; the menu says how many.
- **#933** Headroom prints once. **#929** every measured run counts in the best bet.
- **#591** `ops signal-audit` prints seconds p50 / p90 per signal. **#573** one RSS fetch per run.
- **#586** `ops signal-diff <A> --run-id <B>`. **#587** closed: no per-call retries exist to pool.

**Verify:** `python -m unittest tests.test_wave53_five tests.test_soccer_run_fixes
tests.test_suite_env_isolation`; `py -m scripts.ops signal-audit`.

## Previous — 2026-10-01 (Claude Code): wave 52 #927 #585 #574 #570 #571 (+ #928)

- **#927** seeding is idempotent; every past `all-setup` had added the 44 seeded videos again.
  Post time and the view-curve backfill skip seeded rows (their publish times are invented);
  engagement averages keep them. **Run `ops dedupe-seed`, then `--apply`.**
- **#928** the JSON publish log no longer truncates itself on a datetime (Postgres unaffected).
- **#585** discovery's health block: "Fed the script (last N runs)" per signal; `v` adds it per line.
- **#574** `ops signal-audit --skip news --note ...` (your call, with evidence); `--unskip` reverses.
- **#570** each run keeps what the recommenders read; `ops analytics-diff <run>` says data or code.
- **#571** over `PROJECTED_COST_MAX_USD`: Pillow thumbnail, then a shorter longest length; refuses
  only if Short is over.

**Verify:** `python -m unittest tests.test_seed_history tests.test_signal_usefulness
tests.test_analytics_snapshot tests.test_cost_cap_degrade`; `py -m scripts.ops dedupe-seed`.

## Pipeline order (operator)

```
Topic → Discovery (signals + editorial ANGLES) → pick angle → length → KEY FACTS → [fact conflicts] → script → TITLE → grounding → [trade check] → tier warnings → claim verifier → authenticity → [thin facts / event not in facts] → report card → render → [vault dossier]
```

**Titles are NOT chosen at discovery.** Discovery returns short angle lines; `core/title_generator.py` writes the YouTube title after key facts + script + grounding.

**Vault mirror (Pillar 4):** when `OBSIDIAN_VAULT_PATH` is set, every drafted/rendered run writes `{channel}/_runs/{run_id}_{slug}.md` (layout: [vault.md](vault.md)); `daily_sync` / `ops vault-sync` refresh dossiers with post-sync actuals. Strategy notes feed a bounded `CHANNEL PLAYBOOK` block in the script prompt (style, not facts).

---

## Key facts (operator ground truth)

| Feature | Where |
|---------|--------|
| Multi-line paste | Type `paste` at key-facts prompt |
| Vault save (all facts) | typed lines -> `vault/<channel>/_operator_facts/` (`tier: operator`); pasted-link lines -> `_link_facts/` (`tier: link`, since run 98) |
| LLM packing | Char budget 12000 (`OPERATOR_KEY_FACT_CHAR_BUDGET`), line cap 150 (`MAX_OPERATOR_KEY_FACTS`); only lines typed this run pin |
| Priority | typed → links → vault; pasted-link lines with no contact with the angle are listed first (Enter drops, `k` keeps) |
| Conflicts | Operator facts win — contradicting signal/web lines dropped pre-prompt (`FACT_CONFLICT_FILTER`) |
| Playbook | Strategy/belief notes → `CHANNEL PLAYBOOK` prompt block (NOT facts) |
| Run dossiers | `vault/<channel>/_runs/` — records of what we made, never read back as facts |
| Link scrape | Yahoo/list items OK; ESPN WAF → use `paste`; Bing search/captcha blocked; `ck/a` unwraps |
| Sports on TapIn | domain from the topic (`infer_topic_domain`); football is TapIn's (`soccer`, §34); NBA/NFL/UFC/soccer matrices; pasted sport facts still override |
| **Headless** | `auto_generate --facts-file <paste-block.txt> --fact "..."` (repeatable) |

---

## Credit / speed

- **O1–O11 backlog complete** ([credit_efficiency.md](credit_efficiency.md)). `core/quota_governor.py`
  is the single façade over `data/quota_state.json`: Apify exhaustion + usage cache, LLM daily
  spend, persisted signal disables (key-hash invalidated), `snapshot()` for the dashboard.
- Apify 403 = auth (30m TTL), 402 = credits — persists until the real monthly cycle reset
  (`core/reset_window.py`, `APIFY_RESET_DAY`, O10)
- `SIGNAL_BACKEND=apify|free|auto` — `free`/`auto` serve `youtube_competitors` via yt-dlp and
  `reddit` via official OAuth (free script app) at $0; Twitter/TikTok stay Apify
- The claim verifier adds **one extract-tier LLM call per script** (free-first chain, §14);
  `CLAIM_VERIFIER_ENABLED=false` opts out
- Vault reads are **mtime-cached in-process** (`core/vault_index.py`) — no extra cost, big win
  for `batch-drafts` (N ideas × `load_facts` per run)
- `py -m scripts.ops reliability` — dashboard (breakers, budgets, persisted disables, resets, cache)

---

## Best 5 terminal commands (outside `py main.py`)

1. `py -m scripts.ops daily-brief` — morning one-shot: fresh data → ideas → quota → queue
2. `py -m scripts.ops traces` / `ops dossier --run-id N` — run ledger viewers
3. `py -m scripts.ops vault-sync --channel tapin` — beliefs + dossier refresh into vault
4. `py -m scripts.ops batch-drafts --channel tapin --count 3` — unattended draft scripts (feeds A/B)
5. `py -m scripts.ops reliability` — credit/quota/breaker/cache dashboard
6. `py -m scripts.ops feeds` — RSS source health (ok/stale/dead); run monthly, feeds die quietly

Setup path (fresh machine): `py -m scripts.ops all-setup --channel tapin`.

---

## Open (roadmap next)

The live list is [roadmap.md](roadmap.md) "Recommended next five"; this is the standing context.

1. **Operator:** set `config/goals.json`, then `ops review-week` once a week; listen to the next render at 0.95; one debate and one quotes run (#889);
   `ops backfill` to see what history is behind, then `ops backfill all --apply` if it agrees.
2. **Product next (by epic, backlog.md "Epics"):** #849 fact-fit waits on 5+ measured runs (E1)
   · #863 waits on ten runs (E3) · #851 best-bet domain.
3. **Structural:** #914 emoji font off Windows · #459 dead code (operator call) · #938 views as the recommenders' target (decision) · #940 lifetime views.
   Any live-run defect: add a corpus case.
4. **App:** #860 facts room shipped wave 46; next Stage 3 panel per [desktop_app.md](desktop_app.md).
5. **Operator calls, standing:** `positioning.md` still pitches a micro-SaaS surface, which
   contradicts the private-tool constraint in [roadmap.md](roadmap.md) - the charter is yours
   to rewrite or archive. One OAuth consent then `ops playlists --apply`; gameplay files for
   the empty niches (#786); remote branch deletions this environment cannot do.

**Parked / excluded:** Phase M (Instagram + TikTok) · Benable bot · Edge TTS as default (§28).

---

## Docs to read first

- `docs/decisions.md` §15 (pillar reorientation), §16 (Fact Engine), **§17b (vault OS)**, **§34 (topic domain, football, link tier, v5)**
- `docs/vault.md` — the vault end to end
- `docs/master_plan.md` — the forward plan, with the sample schedule in M4
- `docs/credit_efficiency.md` — O1–O11 (all ✅)
- `docs/roadmap.md` — Pillars 1–7 ✅ (Pillar 6 backends parked on CUDA torch); post-wave-4 pickup shipped
- `docs/providers_runbook.md` — Pillar 6 tool → module → env → proof index
- `docs/debugging.md` — playbook vs facts, hallucination triage

---

## Key files

```
apis/mma_stats_api.py       — API-SPORTS MMA fighter records (replaced Tapology)
core/feed_health.py         — RSS ok/stale/dead checker behind `ops feeds`
core/signal_facts.py        — per-signal -> prompt formatting (add a branch for new data keys)
core/vault_dossiers.py      — Pillar 4: run dossiers + weekly report into vault
core/vault_index.py         — Pillar 4: mtime-cached vault parse
core/obsidian_facts.py      — load_facts + load_playbook/playbook_block
core/fact_store.py          — Pillar 3: FactRecord, tiers, freshness
core/claim_verifier.py      — Pillar 3: claim verifier + GROUNDING_GATE
core/run_trace.py           — Pillar 1: per-run traces
core/video_grade.py         — Pillar 2: pre-publish report card
core/quota_governor.py      — O11 façade
core/providers.py           — Pillar 6: provider-slot contract (ProviderResult, run_chain)
core/link_facts.py          — goose3-first article extraction (+ BeautifulSoup fallback)
docs/providers_runbook.md   — Pillar 6: tool → module → env → proof index
scripts/ops.py              — ~40 subcommands (vault-sync, traces, dossier, batch-drafts)
main.py                     — interactive flow + gates + report card
```
