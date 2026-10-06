# Handoff synopsis — 2026-10-06: wave 63, hook learning, one header line, Analytics

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-10-06

Use in a fresh session to continue `content_machine` without re-reading the full thread.

GPT-6 playground review (2026-09-08, briefing-based): [gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md) and [gpt6_part2_upgrades_2026-09-08.md](gpt6_part2_upgrades_2026-09-08.md). Not a recorded operator decision.

> Older waves and the 2026-07/08 shipped-notes are frozen verbatim in
> [handoff_synopsis_archive.md](handoff_synopsis_archive.md); this file keeps the newest three
> waves plus the standing operator sections (docs_standard.md §7).

## Last wave — 2026-10-06 (Claude Code): wave 63 #985 #986 #984 #978 #979 (the recommended five)

The five wave 62 recommended, built cheapest first.

- **#985** `analytics/hook_learning`: which opening-line traits held viewers past the swipe; the
  opt-in hook rewrite uses it once 10 videos are measured; one line in `ops growth`.
- **#986** one header line at startup (channel, sign-in, spent, uploads left, queue, last video);
  INFO logs go to `data/logs/content_machine.log` (`CONTENT_LOG_FILE`, blank = off).
- **#984** an Analytics page in the app: tiles, views per video shaded by who stayed, the lines.
- **#978** the date check reads the title and description too.
- **#979** Buffer packed / posted this week in the weekly report and `ops status`.
- The back-home list gained "Pause the YouTube ads"; the Story page was updated to 10-06.

**Verify:** `python -m unittest tests.test_hook_learning tests.test_quiet_terminal tests.test_analytics_page`;
`py main.py` (the header); `py -m desktop` -> Analytics.

## Previous — 2026-10-06 (Claude Code): wave 62 #980 #981 #982 #983 #976 (the operator's asks)

From the operator's message while away: a tick-list, a spend total, a real app, why views are low.

- **#980** `ops spend add/end` and "Spent so far: $X" at startup, in `ops status` and on Home.
- **#981** one app window: sidebar (Home, New video, Review, Queue, Costs, Studio, Brand), Home
  cards for money, sign-in, queue and the last five videos.
- **#982** `content_os.pyw` and the `ops shortcut` Start Menu / Desktop shortcuts open it, no
  console; `--chip` for the old chip.
- **#983** `ops growth` - views, stayed split, feed share, cadence, paid share, three levers.
- **#976** angles lose an "X, not Y" frame.
- The back-home tick-list is an artifact page; the brainstorm is
  [growth_review_2026-10.md](growth_review_2026-10.md).

**Verify:** `python -m unittest tests.test_spend_total tests.test_growth_report tests.test_desktop_shell`;
`py -m scripts.ops spend`; `py -m desktop`.

## Previous — 2026-10-05 (Claude Code): wave 61 #973 #974 #551 #339 #863 (script honesty)

The second half of the operator's next 15, as planned.

- **#973** a title loses an "X, not Y" frame ("a trap, not a peak" -> "a trap"); the angle that
  carried run 113's frame is #976.
- **#974** from day 6 of a sign-in, `ops all`, startup and `ops status` say renew now; every step
  still runs. Only a sign-in made after this update is stamped - sign in once to start it.
- **#551** "18 months since" is checked against the dates in the sentence and the facts; a wrong
  count joins the flagged specifics and the dossier.
- **#339** a fresh topic with thin facts is written in unconfirmed mode - what is not confirmed is
  labelled, not dropped; the dossier and `ops batch-review` say so.
- **#863** `ops auto-research` makes its own keep / retune / switch-off call at ten runs.

**Verify:** `python -m unittest tests.test_title_frames tests.test_signin_reminder tests.test_date_math`;
`py -m scripts.ops status`; `py -m scripts.ops auto-research`.

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

1. **Operator:** cancel job 50 (`scripts.queue_manage --channel default --cancel N`), `CONTENT_CHANNEL_ID=tapin` in `.env`, `py -m youtube.oauth_setup --channel tapin`; then a run on a known topic, then one on a new game - say if "Settled"/"Fresh" is wrong (#963-#965); connect TikTok and Instagram in Buffer (#968); the policy site and Google's Publish app (reminder 2026-10-07); `ops backfill view-curve --apply` once (paid views, #954); enable the YouTube Reporting API (#951); `ops footage-gaps` (#955); set `config/goals.json`, then `py -m scripts.ops all` once a week; listen to the next render at 0.95; one debate and one quotes run (#889);
   `ops backfill` to see what history is behind, then `ops backfill all --apply` if it agrees.
2. **Product next (by epic, backlog.md "Epics"):** #849 fact-fit waits on 5+ measured runs (E1)
   · #863's call prints itself at ten runs (E3).
3. **Structural:** #914 emoji font off Windows · #459 dead code (operator call) · #975 the organic rate on a real boosted video.
   Any live-run defect: add a corpus case.
4. **App:** #860 facts room shipped wave 46; next Stage 3 panel per [desktop_app.md](desktop_app.md).
5. **Operator calls, standing:** `positioning.md` still pitches a micro-SaaS surface, which
   contradicts the private-tool constraint in [roadmap.md](roadmap.md) - the charter is yours
   to rewrite or archive. One OAuth consent then `ops playlists --apply`; gameplay files for
   the empty niches (#786); remote branch deletions this environment cannot do.

**Next:** #988 · #987 · #989 · #990 · #977 (reordered by `ops growth`). **Parked / excluded:** Benable bot · Edge TTS as default (§28).

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
