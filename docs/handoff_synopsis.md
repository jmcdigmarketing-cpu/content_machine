# Handoff synopsis — 2026-10-09: wave 67, angles and chapters checked

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-10-09

Use in a fresh session to continue `content_machine` without re-reading the full thread.

GPT-6 playground review (2026-09-08, briefing-based): [gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md) and [gpt6_part2_upgrades_2026-09-08.md](gpt6_part2_upgrades_2026-09-08.md). Not a recorded operator decision.

> Older waves and the 2026-07/08 shipped-notes are frozen verbatim in
> [handoff_synopsis_archive.md](handoff_synopsis_archive.md); this file keeps the newest three
> waves plus the standing operator sections (docs_standard.md §7).

## Last wave — 2026-10-09 (Claude Code): wave 67 #1008 #1009 #1010 #1013 #1014 (runs 119-120)

The operator, afk: "make sure the to do list is updated ... can we work towards the next 5?". The
to-do list was current; Claude reads its ticks each session (no notification on a change). The
roadmap's five, the defects runs 119-120 exposed:

- **#1010** a chosen chapter is written: the trim used the Long ceiling on Extended (run 120 lost
  chapter 5 and the closer); now the Extended ceiling, the closer kept, a missing chapter written once
  from the facts or left out and said so; Shorts need 20 s.
- **#1008** stale angles ("by 2025", "UFC 305") dropped before the menu, with a "! N angles dropped"
  line; the angle prompt and the video title carry the date check.
- **#1009** chapter titles come from the chapter and are checked ("Chapter N retitled" on the card).
- **#1014** no per-angle signal fetch (`VARIANT_SIGNAL_RESCORE` brings it back); the judge sees facts
  and today's date; a shared score prints once.
- **#1013** `ops verify-claim --run-id N`: confirm a flagged claim with a source (or reject it) and
  the hold lifts - no re-render; go-public names it when it refuses.

**Verify:** `python -m unittest tests.test_chapters_complete tests.test_angle_dates tests.test_chapter_titles_checked tests.test_angle_scores_signal tests.test_verify_claim`;
`py -m scripts.ops regressions`; `py -m scripts.ops verify-claim --run-id 120`.

## Previous — 2026-10-09 (Claude Code): wave 66 #1016 #1001-#1005 #1003 #1012 #1017 #1018 (run 124's idea)

The operator's run 124 ("How the 0-4 chargers can turn it around this year") was "a good video,
just not what i intended"; they will rerun the same idea. Asked: speed 1.05, stock only as a last
resort, angle 1 = "100% the intention of my idea ... worded with more seo velocity", Cursor both
(media first). Correction: run 119's "19-0 with 8 KOs and 10 submissions" is right (a decision win).

- **#1016** angle 1 is your idea worded for search, Enter keeps it (option 1 and 5); no take pushed
  onto it; `plan` intent; the script checked against the idea (`KEEP_TO_IDEA`).
- **#1001 #1002 #1005 #1004** "yes" is a yes; lower-case teams are names ("Los Angeles Chargers");
  no who's-who for "Next"/"People"; news and auto-research search the subject.
- **#1003** ESPN NFL: record, standing, next game, dated, at signal tier.
- **#1012 #1017** pasted page junk dropped at `Fact N`; an uncertain vault fact must name the subject.
- **#1018** a hook must be a fact: history superlatives and stock openers rebuilt from facts; the
  hook pass is on by default.
- Riders: **#1000** flagged render never scheduled public, **#1019** CC BY credits, **#1020**
  `local_first` (TapIn), speed 1.05. The next 100: optimization_plan_2026-10.md; Cursor:
  cursor_brief_2026-10.md.

**Verify:** `python -m unittest tests.test_idea_stays_yours tests.test_hooks_solid_ground tests.test_typed_fact_filter tests.test_uncertain_vault_subject tests.test_subject_names tests.test_subject_queries tests.test_espn_nfl tests.test_flagged_schedule tests.test_local_first_footage tests.test_footage_credits tests.test_seed_prompt_yes`;
`py -m scripts.ops regressions`; then rerun the Chargers idea and press Enter on angle 1.

## Previous — 2026-10-08 (Claude Code): wave 65 #996 #992 #998 #997 #994 (a careful ads budget)

The operator spent $40 on ads in about four days and wants spending "calculated and worth it":
a $20 monthly ceiling, nothing new until the Oct 24 decision; the campaign was still spending
(advice: stop it in Studio today; the to-do list says so first).

- **#996** `ADS_MONTHLY_CAP`: "Ads this month: $40.00 of your $20.00 cap - over; no new campaign
  until Nov 1" in `ops spend`, `ops promotions`, `ops status`, Home, and startup when over.
  `ADS_MAX_PER_SUB`: stop once a paid subscriber costs more, also mid-campaign.
- **#992** `ops spend result --entry N --subs N [--amount CHARGED]`: the campaign page's
  subscribers; `ops promotions` shows the cost per paid subscriber; the charge counts in the total.
- **#998** before -> during -> after the ads: did organic views hold once they stopped.
- **#997** "Worth promoting": at most two videos that held organic viewers, a test sized to the cap.
- **#994** the first caption time on the run card; LATE after 0.5 s (`FIRST_CAPTION_MAX_S`).

**Verify:** `python -m unittest tests.test_ads_cap tests.test_campaign_result tests.test_after_the_ads tests.test_promote_candidates tests.test_first_caption`;
`py -m scripts.ops spend`; `py -m scripts.ops promotions`.

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

1. **Operator:** `git pull`, `pip install -e ".[app]"`; in ElevenLabs lower Stability (~35-45) and raise Style (~20-30) on the TapIn voices; rerun the Chargers idea (Enter on angle 1); record Madden / UFC 5 gameplay (`ops footage-add`) - stock is now a last resort; confirm runs 119 and 120's claims with `ops verify-claim --run-id N` (run 119's chapter line: Studio by hand), then `go-public`; hand Cursor `docs/cursor_brief_2026-10.md`; `ops spend add` for what was paid; `CONTENT_CHANNEL_ID=tapin` and `youtube.oauth_setup --channel tapin` if not done; Buffer for TikTok and Instagram (#968); the Reporting API (#951); `ops backfill all --apply` if `ops backfill` agrees.
2. **Product next (by epic, backlog.md "Epics"):** #849 fact-fit waits on 5+ measured runs (E1)
   · #863's call prints itself at ten runs (E3).
3. **Structural:** #914 emoji font off Windows · #459 dead code (operator call) · #975 the organic rate on a real boosted video.
   Any live-run defect: add a corpus case.
4. **App:** #860 facts room shipped wave 46; next Stage 3 panel per [desktop_app.md](desktop_app.md).
5. **Operator calls, standing:** `positioning.md` still pitches a micro-SaaS surface, which
   contradicts the private-tool constraint in [roadmap.md](roadmap.md) - the charter is yours
   to rewrite or archive. One OAuth consent then `ops playlists --apply`; gameplay files for
   the empty niches (#786); remote branch deletions this environment cannot do.

**Runs 119-120:** wave 67 - see planning_log 2026-10-09. **Next:** #1007 · #1006 · #1011 · #1033 · #1060. **Oct 24:** the ads decision - does November get one $20 test (`ops promotions`). **Parked / excluded:** Benable bot · Edge TTS as default (§28).

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
