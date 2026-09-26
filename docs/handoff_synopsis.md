# Handoff synopsis — 2026-09-26: wave 36, own review

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-09-26

Use in a fresh session to continue `content_machine` without re-reading the full thread.

GPT-6 playground review (2026-09-08, briefing-based): [gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md) and [gpt6_part2_upgrades_2026-09-08.md](gpt6_part2_upgrades_2026-09-08.md). Not a recorded operator decision.

> Older waves and the 2026-07/08 shipped-notes are frozen verbatim in
> [handoff_synopsis_archive.md](handoff_synopsis_archive.md); this file keeps the newest three
> waves plus the standing operator sections (docs_standard.md §7).

## Last wave — 2026-09-26 (Claude Code): wave 36, own review #871

The operator dropped the Codex/Astra review and asked for one: what can be consolidated, where
did a newer idea erase a fix, is a new system needed. [review_2026-09-26.md](review_2026-09-26.md).

- **Found:** five fixes erased by later work (#745 stopwords, #783 caption size, #840 TTS
  double billing, #676, #323); run 98's question-word fix in 1 of 7 tokenizers and #852's name
  query in 1 of 11 builders; 13 private stopword lists.
- **Built:** `tests/regression_corpus.json` + `ops regressions [file]` (28 cases, 15 failed on
  `4e4261e`); tokenizers and query builders on `apis/topic_tokens`; a test refusing new private
  stopword lists; the rule in CLAUDE.md and the next-five / tdd skills.
- **Backlog:** epics E1-E6; #866 domain (deferred), #867-#870 filed.

**Verify:** `py -m scripts.ops regressions`; `python -m unittest tests.test_regression_corpus
tests.test_topic_text_shared`.

## Previous — 2026-09-26 (Claude Code): wave 35 #864 #861 #863 #839 #830

The operator asked why uploads land unlisted: `YOUTUBE_UNLISTED_REVIEW` (#109, default on) holds
an *immediate* public upload unlisted for one look, and #754 holds a grounding override; nothing
flipped a held video back. That became #864.

- **#864** `ops go-public [video_id] [--apply]` (no id = newest unlisted hold): status-only
  `videos.update`, refuses a grounding override; the hold message prints the command.
- **#861** kept auto-research lines printed (`auto_research.report_lines`); reports carry
  `kept_lines`.
- **#863 (tool)** `ops auto-research`: pages, lines, off-topic, lines a supported claim cited.
  Verdict after ten runs.
- **#839** commit hook: non-ASCII subject refused, body warned.
- **#830** `tts_cache_store` refuses the default dir under a test runner.
- Found: **#865** `rollback-publish --apply` sends a half snippet.

**Verify:** `python -m unittest tests.test_go_public tests.test_auto_research_view
tests.test_commit_msg_ascii tests.test_tts_cache_guard`.

## Previous — 2026-09-26 (Claude Code): wave 34 #859 #852 #850 #836 #848

The roadmap's five, cheapest first. The operator's PC turned out to be on a local-only branch
(`codex/p0-test-integrity`), so `git pull` fetched `main` without merging it and wave 33 never
reached the machine; the switch instructions are in the handoff slot.

- **#859** `domain_rss.soccer`: BBC Sport Football + The Guardian Football (unverifiable from the
  container; `ops feeds` checks them).
- **#852** `apis/topic_tokens.title_phrases`: API-SPORTS searches `Manchester City`; Wikipedia
  tries `Manchester_City` first.
- **#850** the research brief takes `key_facts`: prompt block, fallback evidence, cache digest.
- **#836** `ops backfill-angles`: offline `rank_angles(llm_judge=False)` over `variants_json`,
  stamped `angle_backfilled`; calibration counts them.
- **#848** `core/auto_research.py`, on by default: reads the top 3 result pages for the angle
  (thread-safe `link_facts._article_extract`, 20 s deadline, 3h per-URL cache), drops off-topic
  lines, attaches `web_research` at web tier with score 0. Suite pins it off. Decisions §35.

**Verify:** `python -m unittest tests.test_auto_research tests.test_backfill_angles
tests.test_brief_sees_key_facts tests.test_wave34_queries_feeds`.

## Pipeline order (operator)

```
Topic → Discovery (signals + editorial ANGLES) → pick angle → length → KEY FACTS → [fact conflicts] → script → TITLE → grounding → [trade check] → tier warnings → claim verifier → authenticity → report card → render → [vault dossier]
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

1. **Operator, after switching to `main`:** `ops backfill-quality --force --apply`,
   `ops backfill-angles --apply`, `ops calibration`, `ops feeds`. #849 waits on that output.
2. **Product next (by epic, backlog.md "Epics"):** #849 (E1) · #866 domain (E2) · #863 (E3).
3. **Structural:** #869 status verbs (E4) · #870 backfills (E6) · #867 unread keys (E5) · #865 ·
   #832 · #831 ruff bump · #834 `core/` seams. Any live-run defect: add a corpus case.
4. **App:** #860 facts room is the proposed next panel ([desktop_app.md](desktop_app.md)).
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
