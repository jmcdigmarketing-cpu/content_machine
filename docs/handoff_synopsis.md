# Handoff synopsis — 2026-09-27: wave 43, next five

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-09-27

Use in a fresh session to continue `content_machine` without re-reading the full thread.

GPT-6 playground review (2026-09-08, briefing-based): [gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md) and [gpt6_part2_upgrades_2026-09-08.md](gpt6_part2_upgrades_2026-09-08.md). Not a recorded operator decision.

> Older waves and the 2026-07/08 shipped-notes are frozen verbatim in
> [handoff_synopsis_archive.md](handoff_synopsis_archive.md); this file keeps the newest three
> waves plus the standing operator sections (docs_standard.md §7).

## Last wave — 2026-09-27 (Claude Code): wave 43 #895 #857 #862 #887 #825 #898

- **#895** recency guard: `core/event_coverage.py` checks that one verified fact or pasted key
  fact names what the topic names (the `search_query(mode="entity")` name). If none does, the
  script prompt gets an EVENT NOT IN FACTS note and `main.py` stops before TTS with a y/N
  (`EVENT_COVERAGE_GATE=false` turns the stop off). `ops blocking` lists it; selftest gate nine.
- **#857** `ops vault-retier` lists old `_operator_facts/` notes holding scraped page lines;
  `--apply` moves each whole note to `_link_facts/` at link tier. Never overwrites.
- **#862** `AUTO_RESEARCH_SAVE=true` keeps the kept auto-research lines in
  `_link_facts/{day}_{slug}-auto-research.md` (default off).
- **#887** the review prompt (`VAULT_FACTS_AUTO=false`): Enter takes the confident lines, `a` all.
- **#825** closed; **#898** art for soccer / pop culture / anime / music plus five franchises.
- **Filed:** #896 sports team not in the topic, #897 odds signal topic-blind (weakness 3).

**Verify:** `python -m unittest tests.test_event_coverage tests.test_vault_retier
tests.test_auto_research_save tests.test_vault_prompt_default tests.test_domain_art`;
`py -m scripts.ops selftest` (9/9); `py -m scripts.ops vault-retier`.

## Previous — 2026-09-27 (Claude Code): wave 42 #853 #851 #868 #894 #833

- **#853** Anthropic premium default `claude-sonnet-5`; `.env.example` no longer pins every tier
  with `ANTHROPIC_MODEL` (delete it from your `.env` if it is there).
- **#851** best-bet headlines use `infer_topic_domain` - no fallback through the env channel.
- **#868** `ops reback-short` (was `preview-render`, which now only prints the new name).
- **#894** `ops package-audit` retries the wheel in isolation; it completes on this container.
- **#833** mypy over every shipped package; `video/__init__.py`; baseline 123.

**Verify:** `python -m unittest tests.test_llm_defaults tests.test_best_bet_headline_domain
tests.test_package_audit_build tests.test_mypy_targets`; `py -m scripts.ops package-audit`.

## Previous — 2026-09-27 (Claude Code): wave 41 #888 #892 #893 #832 + #831

- **#888** the dossier is rewritten when the render finishes; it names the voices and the pace.
- **#892** the suite writes nothing under `data/` or `output/`; `ops test` fails and names the
  files if a run ever does (CI's reversed leg runs through it).
- **#893** chapter and duration estimates use `spoken_words_per_second` (3.3 x pace).
- **#832** the wheel ships `assets` (+ branding), `apis.scrapers` and `scripts`.
- **#831** ruff 0.15.8 in `pyproject.toml`, CI and pre-commit; one format sweep, then one
  commit per rule family. `pip install ruff==0.15.8` on the PC.

**Verify:** `py -m scripts.ops test --order reverse` (ends "Suite hygiene: ... untouched");
`python -m unittest tests.test_suite_hygiene tests.test_spoken_pace tests.test_wave13`.

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
3. **Structural:** #825 `--force` · #834 `core/` seams · #857 / #862 fact-intake tidy-ups.
   Any live-run defect: add a corpus case.
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
