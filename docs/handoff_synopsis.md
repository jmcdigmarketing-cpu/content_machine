# Handoff synopsis — 2026-09-30: wave 49, next five

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-09-30

Use in a fresh session to continue `content_machine` without re-reading the full thread.

GPT-6 playground review (2026-09-08, briefing-based): [gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md) and [gpt6_part2_upgrades_2026-09-08.md](gpt6_part2_upgrades_2026-09-08.md). Not a recorded operator decision.

> Older waves and the 2026-07/08 shipped-notes are frozen verbatim in
> [handoff_synopsis_archive.md](handoff_synopsis_archive.md); this file keeps the newest three
> waves plus the standing operator sections (docs_standard.md §7).

## Last wave — 2026-09-30 (Claude Code): wave 49 #918 #598 #564 #919 #917

- **#918** the metrics sync pulls every live video younger than `SYNC_YOUNG_DAYS` (8), then the
  newest few - first-day snapshots and views by day stop being missed.
- **#598** `ops weekly-report` has a "By upload_mode" block: scheduled vs immediate, with actions.
- **#564** `MIN_OUTCOME_VIEWS` (off): videos under it stop teaching every recommender;
  `ops predictions` says how many sit under 50 views. YouTube cannot separate your own views.
- **#919** a script, a thumbnail and a post-time experiment run together;
  `py -m core.experiments stop post_time` stops one.
- **#917** a fact conflict names the signal section that lost; `ops source-trust` counts them.

**Verify:** `python -m unittest tests.test_sync_young_videos tests.test_upload_mode_report
tests.test_view_floor tests.test_experiments_per_kind tests.test_conflict_sections`;
`py -m scripts.ops weekly-report`; `py -m scripts.ops predictions`.

## Previous — 2026-09-30 (Claude Code): wave 48 #915 #913 #916 #912 #560 #563 #342

- **#915** a scheduled upload stayed `scheduled` forever, so it was never synced, scored or learned
  from and dropped out of the cadence window after its slot. A scheduled row past its time now
  counts (`publish_log.counts_as_live`, read-side). Recommendations shift once these count.
- **#916 / #912** the ledger scores the slot a video used (`post_timing.slot_claim`), not the next
  one; `py -m core.experiments start post_time` alternates on-slot and 4 h off (opt-in).
- **#913** overnight and auto_generate best-bet picks recorded (`by`: batch / auto / operator).
- **#560** `ops predictions` headlines forward rows only; backfilled claims leave the video out.
- **#563** views by day at each sync; `ops predictions` shows time to 100 views;
  `ops backfill view-curve --apply` fills past videos.
- **#342** two or more post-publish corrections lower a source's weight (floor x0.85);
  `ops source-trust`. Rejects shown, never applied.

**Verify:** `python -m unittest tests.test_scheduled_outcomes tests.test_auto_best_bet_pick
tests.test_post_slot_arm tests.test_forward_error_bars tests.test_first_views
tests.test_source_trust`; `py -m scripts.ops sync-metrics`, then `py -m scripts.ops predictions`.

## Previous — 2026-09-29 (Claude Code): wave 47 #910 #911 #909 #504 #386

- **#386** every run saves its signals beside its trace; `ops replay <run>` re-scores it offline
  (composite recorded vs today, the facts block, event coverage). `RUN_SIGNAL_SNAPSHOT=false` off.
- **#504** emoji in captions are drawn from Segoe UI Emoji (`CAPTION_EMOJI_FONT`); word mode with
  emoji burns `.ass`. No-emoji output byte-identical.
- **#909** the best-bet pick is kept (`features["best_bet"]`) and scored in `ops predictions`.
- **#910** the facts room reads all pasted links at once; **#911** the dossier prints fact confidence.

**Verify:** `python -m unittest tests.test_run_replay tests.test_caption_emoji
tests.test_best_bet_pick tests.test_room_parallel_links tests.test_dossier_fact_confidence`;
`py -m scripts.ops replay <last run>`.

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

1. **Operator:** listen to the next render at 0.95; one debate and one quotes run (#889);
   `ops backfill` to see what history is behind, then `ops backfill all --apply` if it agrees.
2. **Product next (by epic, backlog.md "Epics"):** #849 fact-fit waits on 5+ measured runs (E1)
   · #863 waits on ten runs (E3) · #851 best-bet domain.
3. **Structural:** #920 one scale for engaged rate · #914 emoji font off Windows · #459 dead code (operator call).
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
