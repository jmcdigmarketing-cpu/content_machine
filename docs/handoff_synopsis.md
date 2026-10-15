# Handoff synopsis — 2026-10-14: what overnight drafts, and what you see in the morning (waves 87-88)

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-10-09

Use in a fresh session to continue `content_machine` without re-reading the full thread.

GPT-6 playground review (2026-09-08, briefing-based): [gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md) and [gpt6_part2_upgrades_2026-09-08.md](gpt6_part2_upgrades_2026-09-08.md). Not a recorded operator decision.

> Older waves and the 2026-07/08 shipped-notes are frozen verbatim in
> [handoff_synopsis_archive.md](handoff_synopsis_archive.md); this file keeps the newest three
> waves plus the standing operator sections (docs_standard.md §7).

## Last wave — 2026-10-14 (Claude Code): waves 87-88, what overnight drafts and the morning

**Wave 87, what overnight drafts.** The operator keeps the schedule in the batch; a scheduled
game ahead is now drafted as a preview (#1169, decisions_2026-10.md §52) - the first one, run 152
(Ravens at Browns, 10-18), says "watch the inactive list before kickoff", no score. A game name
knows its sport, so Last.fm, MusicBrainz and SEC filings stay off it (#1170); the claim check
reads twice the facts (#1171); a topic with no RSS feed is `inactive`, not a tripped key (#1172);
a game draft is set aside once its game starts (#1173).

The operator's three ideas, drafted again: two clean, one with a sentence hard to say - yesterday
2, 1 and 1 unbacked claims. Clean is not good: run 150's new opener has no full stop (#1179), run
149's says the next sentence again (#1180) and its title reads "Denver Loss Angeles" (#1181).

**Wave 88, the morning.** A correction is checked only against a page that names the claim
(#1174): the 32 notes on file covered 5 pairs, 4 read against pictures and 1 against an article
about someone else, and the rule files none of them. `ops morning` lists open corrections one
line each (#1175) and offers the sign-in when it has ended (#1176, §53). `c` in `batch-review`
cuts the flagged sentences and says why when it cannot (#1177) - on a copy, run 144 comes out
with no flagged claim. Thumbnail words go on a dark plate, not nowhere (#1178). The two opener
defects are fixed (#1179-#1180).

**Still the operator's:** sign in (`ops morning` now asks); publish the consent screen;
`ops worker-task --install`; `schedule-drafts --wake`. Suite 5746 -> 5780, mypy 98, corpus
242. Claude has nothing claimed.

## Previous — 2026-10-14 (Claude Code): waves 85-86, your own idea's script and the morning

**A correction to the entry below.** The three "drafts of your own ideas" in wave 83 were
written from generated angles: `ops script-check --idea` passed the first generated angle, not
angle 1. Fixed (#1159): the command now writes the idea itself, the way Enter on angle 1 does,
and keeps it as a draft `batch-review` can render (decisions_2026-10.md §50).

- **One model writes the whole script again (#1163, §48).** Since #374 a free small model had
  written every body - a local 8B one on the run overnight rendered. The operator's call.
- **Names are read whole (#1160).** "Court Mc", "Vonta Smith" and a sentence's first word
  ("Losing") had been reported as names the facts lack; two drafts waited on that alone.
- **An unbacked claim in the first sentence is repaired (#1161)** - the hook is rebuilt from
  the facts once and kept only when the check then finds fewer.
- **A cut may leave a script 15% short (#1162, §49)**; the review line says how short.
- Found on the corrected drafts and fixed: a flagged claim's sentence was not found when it
  used a possessive ("Wemby's +200") or ran across two sentences.

The corrected drafts (runs 143-145) are waiting in `batch-review`: 2, 1 and 1 unbacked claims,
each named. None clean; yesterday's generated-angle version of the hope idea had 4.

**Wave 86 (10-14), the morning screen.** `ops recheck-claims` re-checked the waiting drafts:
14 of 29 flagged claims were backed by their own saved facts (#1164; run 126 became clean). The
sign-in is one line except where it is read in full (#1165). A pulled run says pulled and why
(#1166). `ops overnight-last` says when overnight ran - on 10-14 the 5:00 AM run did not start
until 5:54 PM (#1167; `schedule-drafts --wake` prints the fix). Drafts past twice their window
are set aside each night, about 20 of 35 the first time (#1168, §51). That 5:54 PM run rendered
run 126; three new game drafts narrate games not yet played and wait (filed #1169).

**Still the operator's:** sign in (`py -m youtube.oauth_setup --channel tapin`); publish the
consent screen; `ops worker-task --install`; `schedule-drafts --wake`. Suite 5689 -> 5746,
mypy 98, corpus 227. Claude has nothing claimed.

## Previous — 2026-10-13 (Claude Code): waves 83-84, the 10-13 overnight run

Overnight rendered two videos on 10-13 and both were wrong. Run 139 was titled and written as
a Thunder win over Indiana before the game; run 136 previewed a Texans game two days after it
was played and ended "in convincing fashion on tennessee." The operator pulled both (upload
jobs 56 and 57 cancelled, renders retired). Five fixes, each from that run:

- **Why drafts were blocked (#1148).** Not thin facts. When the research brief restated the
  facts, the claim checker cited the brief, and the rule that a brief backs nothing strict
  (#966) called every such claim unsupported: 5 of 5 on a replay of run 137, with the sources
  two lines away. The brief is no longer shown to the check as a fact to cite
  (decisions_2026-10.md §47). A narrow second look carries a numbered claim that one fact line
  states (3 of 50 recorded blocking claims). The stored check says how many fact lines it was
  sent.
- **"on torontos" (#1149).** `payoff_closer` appended a lowercased hook word to the last line.
  It reports now and changes nothing. Cursor's pass.
- **A flagged title blocks the overnight render (#1150)** - the flag never reached the draft.
- **A game draft renders before its game or waits (#1151, §45).** The board's start time is on
  the draft; a result stated before the game, a game already started, or a fixture with no
  known time all wait for a person.
- **Overnight stops at 3 finished videos waiting (#1152, §46)** - `OVERNIGHT_SHELF_MAX`.

Three live drafts of the operator's own ideas (no voice): the prediction came back clean; the
plan 6 of 8 claims backed by named sources, 2 flagged; the hope kept its stance with 4 claims
flagged. `ops script-check --idea "..."` is the command (the guide said `--idea`, the parser
only knew `--topic`; both work now).

**Wave 84, the same day's smaller findings (#1153-#1158).** With the sign-in dead, an
overdue upload says "sign in", not "run the worker". The 7-day reminder already existed
(#974); it now starts on day 5, says the days left and leads the overnight report. A fact
told twice is cut or named (run 136). `ops growth` prints one paid number that agrees with
`ops ypp`. 50 of 71 stored source links were pictures or ended in a quote - cleaned where
they are read. An angle no longer keeps its lens name ("Factual read:", run 142). Found on the
way: the correction scan's script/style pattern held a backspace where `\b` was meant and
had never matched.

**Still the operator's:** sign in (`py -m youtube.oauth_setup --channel tapin`) - it expired
10-13 and nothing uploads or syncs; publish the consent screen so it stops expiring weekly;
`ops worker-task --install`. Suite 5595 -> 5689, mypy 98, corpus 201 -> 218. Claude has
nothing claimed.

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

1. **Operator:** `git pull`, `pip install -e ".[app]"`; in ElevenLabs lower Stability (~35-45) and raise Style (~20-30) on the TapIn voices; rerun the Chargers idea (Enter on angle 1), then try "M" on the angle screen; record Madden / UFC 5 gameplay (`ops footage-add`) - stock is now a last resort; confirm runs 119 and 120's claims with `ops verify-claim --run-id N` (run 119's chapter line: Studio by hand), then `go-public`; hand Cursor `docs/cursor_brief_2026-10.md`; `ops spend add` for what was paid; `CONTENT_CHANNEL_ID=tapin` and `youtube.oauth_setup --channel tapin` if not done; Buffer for TikTok and Instagram (#968); the Reporting API (#951); `ops backfill all --apply` if `ops backfill` agrees.
2. **Product next (by epic, backlog.md "Epics"):** #849 fact-fit waits on 5+ measured runs (E1)
   · #863's call prints itself at ten runs (E3).
3. **Structural:** #914 emoji font off Windows · #459 dead code (operator call) · #975 the organic rate on a real boosted video.
   Any live-run defect: add a corpus case.
4. **App:** #860 facts room shipped wave 46; next Stage 3 panel per [desktop_app.md](desktop_app.md).
5. **Operator calls, standing:** `positioning.md` still pitches a micro-SaaS surface, which
   contradicts the private-tool constraint in [roadmap.md](roadmap.md) - the charter is yours
   to rewrite or archive. One OAuth consent then `ops playlists --apply`; gameplay files for
   the empty niches (#786); remote branch deletions this environment cannot do.

**Next:** the ship stage (roadmap.md). Cursor: #1121 · #462 · #404 · #388 · #409. **Oct 24:** the ads decision - does November get one $20 test (`ops promotions`). **Parked / excluded:** Benable bot · Edge TTS as default (§28).

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
