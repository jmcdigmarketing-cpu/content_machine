# Handoff synopsis — 2026-10-13: a clean script, a morning command, honest monetization numbers (waves 81-82)

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-10-09

Use in a fresh session to continue `content_machine` without re-reading the full thread.

GPT-6 playground review (2026-09-08, briefing-based): [gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md) and [gpt6_part2_upgrades_2026-09-08.md](gpt6_part2_upgrades_2026-09-08.md). Not a recorded operator decision.

> Older waves and the 2026-07/08 shipped-notes are frozen verbatim in
> [handoff_synopsis_archive.md](handoff_synopsis_archive.md); this file keeps the newest three
> waves plus the standing operator sections (docs_standard.md §7).

## Last wave — 2026-10-13 (Claude Code): waves 81-82, the script that comes out and where the channel stands

Built 10-11, landed 10-13. The overnight task runs the working tree, so this code wrote runs
137-139 before it was committed.

**The script.** A finished script is checked as a whole and the result is stored on the run
(`script_clean`): the idea's stance held on every sentence, not two (#1141); the operator's
typed points counted and the missing one named (#1142); one or two sentences the facts still
do not back after the rewrite are cut and listed (#1139, the operator's "cut it, tell me
which"); an angle's label never reaches a title (#1138). One line on the review screen;
overnight renders only a clean one; `ops script-check` gives the rate over recorded scripts
(13 of the newest 30) or writes one draft of an idea with no voice (#1143).

**Mornings.** `ops morning` syncs, says what overnight rendered and where each one is, lists
the shelf and walks the drafts (#1140) - `ops all` is weekly and never had it. Run live it
crashed: on Windows `isatty()` is true for the NUL device, so a scheduled task looked like a
console. It asks the console itself now.

**The numbers.** `ops ypp` had read 0 since it was added - YouTube writes `shorts`, the code
compared with `SHORTS` (#1147). Real: 69 subscribers, 1,797 organic Shorts views in 90 days,
10 long-form hours. It now prints how far each bar is at the pace of the last 28 days (#1144)
and `ops growth` says which videos brought a subscriber: 2 from 43 (#1146). The first live
print of the pace was wrong as labelled (64 subscribers in 28 days under "ads excluded", with
4,544 paid views counted and 2 from the videos); it says both paces now.

**Found by the 10-13 overnight run, filed as #1148-#1157 (next):** two videos rendered and both
were wrong - run 139 written as a win before the game, run 136 a preview rendered two days
late with a last line ending "on tennessee". Both pulled (uploads cancelled, renders retired).
The claim check called nine true claims unsupported on run 137. The YouTube sign-in expired.

Suite 5531 -> 5595, mypy 98, corpus 188 -> 201. `roadmap-index`: open 315, done 872,
highest #1157. Decisions: decisions_2026-10.md §42-§44.

## Previous — 2026-10-11 (Claude Code): waves 79-80, the record and the last mile

**The numbers in the entry below were wrong.** All 43 videos are public; the log said 32
because a video's privacy was written at upload and never read back (#1128). The operator
found it. The metrics sync now asks YouTube and corrected 11 rows; the shelf is 2, not 7.

What was really in the way: a queued upload nothing was sending (run 132, due 9:30 pm on
10-10) and 69 drafts nobody rendered. The header names an overdue upload and
`ops worker-task --install` makes a scheduled task send them every 15 minutes (#1129 #1130;
the install line is the operator's). `ops shelf` lists each unpublished video with its exact
command (#1131). Overnight renders up to 2 clean drafts and queues them unlisted - the
operator's call, reversing "render-free" (#1078 first half, decisions_2026-10.md §40); `ops
overnight-plan` shows tonight's two and why 29 wait. `ops status` counts the drafts (#1132),
the header says "week 4 of 3-5" (#1133), MoneyWise is parked (#1134, decisions_2026-10.md §41),
competitor searches keep to the niche's own words and `add --name` needs no id (#1127).
`ops sync-metrics` no longer dies under a pipe or a scheduled task (#1135).

Suite 5460 -> 5531, mypy 98, corpus 188. `roadmap-index`: open 308, done 861,
highest #1139. Filed open: #1136 (runs 92 and 119 are public with a claim never confirmed),
#1137 (the header's last video reads 0 views), #1138 (a label in a draft title), #1139 (2 of
31 drafts are clean).

## Previous — 2026-10-10 (Claude Code): waves 77-78, the next ten

Ten shipped. Finished videos that are not public now have a line: the startup header ends
"7 finished, not public" and `ops status` lists 5 unlisted uploads (2 held for a claim) and 2
renders never uploaded, each with its command (#1122). The Reporting API line names the Google
project and prints the link that enables it (#1123) - it was ticked "on" two days earlier and
is still off. `ops backfill stayed --apply` put "who stayed" on 39 of 43 videos, from 5
(#1124). The internet being down reads as one line and one incident (#393). A game covered
three times or more is neutral unless a take is asked for (#1088, the operator's call).
`ops competitors suggest` prints a sized shortlist per niche and keeps it; `add` approves one;
stored competitor videos carry view counts (#1120). The outlier watch reads them - nothing to
find until channels are approved (#1063). Steam patch notes are dated facts, and the Steam
lookup asks again by the game's name (#1119). One function attaches a description's blocks,
a blank line apart (#1051). A signal never active on 5+ of the last 20 runs sits out two runs
in three: today `sports` and `twitch` (#1073; `SIGNAL_DEMOTION=false` turns it off).

Suite 5347 -> 5460, mypy 98, corpus 184. `roadmap-index`: open 306, done 851,
highest #1127. Filed open: #1125 (YouTube's feed 404s for every channel), #1126 (15 runs stuck
at "scheduled"), #1127 (the NFL search returns soccer). **The next stage is a ship stage**
(roadmap.md): clear the shelf, five public a week, click-through flowing, the intro test on.

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
