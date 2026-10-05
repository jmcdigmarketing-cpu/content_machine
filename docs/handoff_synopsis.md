# Handoff synopsis — 2026-10-05: wave 59, next five

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-10-05

Use in a fresh session to continue `content_machine` without re-reading the full thread.

GPT-6 playground review (2026-09-08, briefing-based): [gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md) and [gpt6_part2_upgrades_2026-09-08.md](gpt6_part2_upgrades_2026-09-08.md). Not a recorded operator decision.

> Older waves and the 2026-07/08 shipped-notes are frozen verbatim in
> [handoff_synopsis_archive.md](handoff_synopsis_archive.md); this file keeps the newest three
> waves plus the standing operator sections (docs_standard.md §7).

## Last wave — 2026-10-05 (Claude Code): wave 59 #970 #971 #972 #968 #962

From run 113 (an NBA Short that went to "Default", queued public) and the operator's ask.

- **#970** Enter at the channel menu takes the last real channel; "Default" is labelled, warned,
  and a public upload on it needs a yes. `CONTENT_CHANNEL_ID=tapin` in `.env` still wins.
- **#971** `ops all` checks the YouTube sign-in first: one line with the fix, `sync-metrics` and
  `backfill` skipped, the rest run. Same line at startup and in `ops status`.
- **#972** "Somebody" is not a name; the description drops a sentence restating an unbacked claim;
  auto-research falls back to Google News when every page times out; no empty preview heading.
- **#968** `ops crosspost` - a Buffer folder per rendered video (mp4, TikTok / Instagram captions,
  slot); `crosspost list`, `crosspost done --run-id N`.
- **#962** footage follows the run's own topic and sport when the angle names neither.
- A test's fixed date (`test_backlog`) turned red with time; fixed.

**Verify:** `python -m unittest tests.test_channel_menu tests.test_signin_health tests.test_crosspost`;
`py -m scripts.ops all`; `py -m scripts.ops crosspost`.

## Previous — 2026-10-05 (Claude Code): wave 58 #963 #964 #965 #966 #967 (research by need)

The operator: "i shouldnt have to fact intake" a known topic (what team LeBron is on), but would
paste for a game that just came out - "obviously not hardcoded".

- **#963** who's who on every run: Wikidata (current team / title / head coach, release date,
  developer, platforms - dated, signal tier) and the Wikipedia intro, keyless, for up to four
  names in the topic and angle (aliases: "Wemby"). Batch drafts get it too.
- **#964** settled or fresh from evidence (a release in 30 days, a new or missing article, a 48 h
  news burst, event research on a miss); a fresh topic gets recent-news research for its name;
  no web results -> Google News headlines instead of nothing.
- **#965** the facts prompt: "Settled ... nothing to paste" or "Fresh ... a link would help".
  `ops batch-review` names fresh drafts nobody pasted for.
- **#966** no team or title from memory: prompt rule, the verifier asks about affiliations and a
  brief-only line backs nothing strict, the expansion sees the verified facts.
- **#967** `ops auto-research` counts pastes per verdict. Accents fold in `content_tokens`.
- Phase M changed mid-wave: Buffer for TikTok and Instagram (#968); #952's direct APIs parked.

**Verify:** `python -m unittest tests.test_entity_lookup tests.test_freshness tests.test_research_prompt`;
a run on a known topic; `py -m scripts.ops auto-research`.

## Previous — 2026-10-04 (Claude Code): wave 57 #954 #947 #955 #946 #951 #956 (#948 closed)

From the operator's Studio screenshots and first $10 ad campaign (76.3% of 28-day views were ads).

- **#954** ads apart from organic: the sync keeps paid views by day and by traffic source; the
  7-day target, winners, verdicts, the scoreboard ("+N paid, not counted") and performance memory
  read organic. `ops ypp` reads YouTube's own numbers (Shorts views 90 days, long-form hours 12
  months, subscribers), ads excluded. **Run `ops backfill view-curve --apply` once** - until then a
  video synced before this wave counts none of its views as paid. **#947** the backfill no longer
  re-fetches small videos.
- **#955** footage must match the topic: keyword, playlist alias, the topic's own sport, then the
  model with NONE allowed - no random game. Unmatched -> stock or a plain branded background.
  `ops footage-gaps`: what to record, and past videos that may show another game.
- **#946** athlete names read as their sport (`config/domain_names.json` + names learned from runs).
- **#951** `ops packaging`: Shorts stayed (not swiped away) and feed share; long-form impressions
  and CTR via the Reporting API (enable it in Cloud Console). **#948** closed: the Analytics API
  has no impressions metric.
- **#956** `ops policy-site --name --email --output-dir`: the privacy / terms / data-deletion pages.
  TikTok refuses personal apps in review - its route is the operator's call (#952).

**Verify:** `python -m unittest tests.test_paid_views tests.test_footage_match tests.test_packaging`;
`py -m scripts.ops footage-gaps`; `py -m scripts.ops packaging`.

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
   · #863 waits on ten runs (E3) · #851 best-bet domain.
3. **Structural:** #914 emoji font off Windows · #459 dead code (operator call) · #958 a metrics refresh drops other writers' keys · #957 an organic engaged rate.
   Any live-run defect: add a corpus case.
4. **App:** #860 facts room shipped wave 46; next Stage 3 panel per [desktop_app.md](desktop_app.md).
5. **Operator calls, standing:** `positioning.md` still pitches a micro-SaaS surface, which
   contradicts the private-tool constraint in [roadmap.md](roadmap.md) - the charter is yours
   to rewrite or archive. One OAuth consent then `ops playlists --apply`; gameplay files for
   the empty niches (#786); remote branch deletions this environment cannot do.

**Next:** #958 · #957 · #49 · #945 · #969 (wave 60), then #973 #974 #551 #339 #863. **Parked / excluded:** Benable bot · Edge TTS as default (§28).

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
