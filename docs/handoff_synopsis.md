# Handoff synopsis — 2026-10-17 late night: a headline preview knows its event, menu 7 schedules, health says why

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-10-09

Use in a fresh session to continue `content_machine` without re-reading the full thread.

GPT-6 playground review (2026-09-08, briefing-based): [gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md) and [gpt6_part2_upgrades_2026-09-08.md](gpt6_part2_upgrades_2026-09-08.md). Not a recorded operator decision.

> Older waves and the 2026-07/08 shipped-notes are frozen verbatim in
> [handoff_synopsis_archive.md](handoff_synopsis_archive.md); this file keeps the newest three
> waves plus the standing operator sections (docs_standard.md §7).

## Last wave — 2026-10-17 late night (Claude Code): #1286 #1271 #1270 #1272 #257

A preview whose draft has no `event_at` is matched to the week's games and UFC cards by its title
(`seasonal_calendar.event_for`), so the shelf, menu 7 and the crosspost kickoff know run 160's
card has started. `ops health` gives a `why:` line under a soft engagement - a trait the last five
share, else the weakest of them (live: run 120, NBA, 406 s, at 11%). Menu 7's `s` sets YouTube's
`publishAt` at the next free noon/10 PM slot. The drafts line says how many to decide before
overnight drafts again. The booth takes a dropped facts `.txt`. Suite: 6,245 tests forward and reversed, the same verdict.

## Previous — 2026-10-17 night (Claude Code): #1283 #1284 #1285

`requeue_upload --queue` schedules the run public at the next free noon/10 PM slot (`--private`
keeps the old upload). The worker holds an OS lock for its life; alone, it frees a dead worker's
"running" job at once. The shelf skips slots other uploads already hold and gives news that
would miss its window a 6 PM slot. Correction on record: only run 156 of the queued three was
2-day news, and inside its window. Suite green forward and reversed on the committed tree.

## Previous — 2026-10-17 evening (Claude Code): decisions 63-66 and wave 105

**Live.** Crossposting works: runs 126, 155 and 157 are scheduled on TikTok and Instagram. The
angle-step crash is fixed. No spacing between crossposts and previews go before kickoff (§63);
the 10 PM evening slot and 3-minute Reels (§64); no YouTube cadence cap (§65); ten ideas, five
of them previews (§66).

**Wave 105.** `ops shelf --schedule` gave the seven stranded renders public slots two a day - six
queued (jobs 61-66, Sat 10 PM to Tue noon EDT); run 160 (tonight's UFC picks) left. Times in
EDT; scheduled videos crossposted as they go live; no bare-name follow-up; crosspost status says
why. The worker run is the operator's - job 61 waits for it (its stuck "running" is reclaimed).
Filed #1283-#1285. Suite green forward and reversed on the committed trees.

## Previous — 2026-10-17 (Claude Code): wave 104, Cursor's wave 103 finished

**Cursor is out of usage for the month.** Its wave 103 (my order of fifteen) was done and
uncommitted. Claude re-audited every diff, corrected six - a neutral topic on TapIn lost its
sports signals (run 98 again), a cooling LLM provider could fall back to a paid model, the
draft cap counted drafts the night sets aside, "at its slot" did nothing, Go public was one
click, explain printed lists as timings - and committed it.

**Wave 104.** `ops status` says when CI on `main` is red (#1263); a confirmed claim is not
listed again (#1262); an undated run is not "this week" (#1261); the `.env` warning once a run
(#1265); "Give" is not a name (#1266). Filed #1270-#1272. CI on `da4a4ed` was green on every
job, the first time since 10-10. Suite 6175 forward and reversed on the committed tree.

## Previous — 2026-10-17 (Claude Code): the grand audit

**Found and fixed.** CI on `main` had failed the type check on every push since 10-11 (Linux
plus old bs4 stubs counted 25 errors this PC never saw) - mypy now checks the Windows build
everywhere (§62). A bare test run could reach the real Postgres (#1247) - the suite refuses to
load after settings, and the database layer refuses a network database while tests run.

**The operator's calls.** Overnight renders wait for the operator (§60); TapIn keeps its colour
grade, which Cursor's `bef5a56` had swapped for a near-flat file (§61).

**Reviewed.** `29c280c` and `bef5a56` in full: the menu Enter, the colour, the Home changelog,
and a test that deleted `data/launch_state.json`. Filed #1263-#1269. Record:
`docs/audit_2026-10-17.md`. Suite 6128 forward and reversed; CI's type check green (90 < 92).

## Previous — 2026-10-17 (Cursor): wave 103, the fifteen from the mailbox

`ops roadmap-index` prints counts unless `--list`. `ops explain` prints `Words: N`
on its own line. The seven-day opening window sees `created_at` (an undated row
still counts, #1261). Ballon d'Or says Wed Oct 28. The Dubois weigh-in is boxing
and an MMA feed does not rename it to ufc. A follow-up that would repeat the last
topic is not offered. A neutral topic on tapin runs gaming signals only. A 429
cools that provider in-process. Stale vault lines are judged once per day.
Overnight drafts `min(requested, 8 - waiting)` and says when it drafted fewer.
Menu option 7 is one pass over unlisted videos; nothing goes public without a
choice. The review room lists each flagged claim, confirms with a source, cuts,
and keeps Go public off until the claim is settled. #1255 and #1247 stayed open.

`roadmap-index`: open 260, done 1235, numbered open 208, highest #1262.
Next: #421 #425 #450 #457 #257.

## Previous — 2026-10-16/17 (Claude Code): wave 102 + the review of 29c280c

**Wave 102.** Ideas stopped being bare game names: only marquee NFL and NBA games, each with its
kickoff, network and records, competing for their league's place with no reserved slots
(decision §59); a follow-up waits until its video is public; a news story is never replayed.

**Review.** One correction to Cursor's `29c280c`: the Enter typed after a one-key menu answered
the next prompt. `bef5a56` is unreviewed and holds the push until the grand audit.

**Filed #1247-#1260**, among them #1247 (a bare unittest from the repo root reached the real
database - cleaned), menu option 7 "watch and publish" (#1248), the operator's auto-public call
(#1255). Cursor has an order of fifteen in the mailbox. Suite green forward and reversed on the committed tree.

## Previous — 2026-10-17 (Cursor): fifteen from the backlog

Claude had not queued a fifteen; wave 102 idea-menu files stayed unstaged.
This wave is the roadmap five plus ten unblocked backlog items.

TapIn and MoneyWise toasts use distinct sounds. The booth switches burned /
retext / proportional captions, edits tag chips onto the run and the queued
package, and fits a phone-width viewport. Home shows `git log` since last
launch. Copy panel puts the active Qt page on the clipboard. A tall portrait
thumbnail keeps the upper focal area. Dual thumbs can vary only the headline.
Shipped `.cube` LUTs replace the eq scalars (finished colour changes).
`ops teaser` cuts five seconds. `ops footage-ledger` names licence, expiry
and runs. Unit sanity flags "80 hours" from "80 minutes". `normalize_signal`
always fills the contract. Golden ffmpeg argv covers LUT/no-LUT paths.
LLM calls store latency; reliability reports it without tripping a breaker.

`roadmap-index`: open 259, done 1215, numbered open 207, highest open #1136.
Next: #421 #425 #449 #450 #457.

## Previous — 2026-10-16 (Cursor): fifteen from the backlog

Claude had not queued a fifteen. Menus take one key. The last topic is
recalled. `--quiet` keeps gates. A gate rings once on a TTY. URLs, paths and
run ids are links. Reading grade is measured. Upload language is the
channel's. A moat backup restores into a temp directory. Thumbnails wrap.
A repeated opening is dropped once. A pin waits for the next peak. A
feed-wide RSS 404 can fill from yt-dlp.

`roadmap-index` then: open 274, done 1200, numbered open 222, highest #1136.

## Previous — 2026-10-16 (Claude Code): review of Cursor's eight commits (fifteen items) + wave 101

**Review.** Cursor's commits passed the suite but five changed what reaches a viewer: team topics
lost every untagged gameplay clip (Titans-Colts 0 of 13), a draft child's output (and its crash
traceback) was thrown away, a stuck shot could hold a render seven minutes, the correction
sentence would follow the CTA on every script, and the hook card showed "*emphasis*" marks. All
corrected, tested, pushed with Cursor's work.

**Wave 101.** NFL angles no longer get tech titles as "in-niche" pulse, and the watch follows
MMA/NFL/NBA channels (#1236); `ops status` stops offering to requeue run 114 (#1237); health
leaves out videos under 20 views (#1238); one question sets old drafts aside (#1239); missing
playlists are said (#1240).

**Still the operator's:** `R2_PUBLIC_BASE_URL`; run 155 waits for the worker, run 126 for
go-public; the 11 playlists (`ops playlists --apply`); `.env` lines 35, 36, 39. Suite 6047, forward and reversed.

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

**Next:** #421 #425 #450 #457 #257 (roadmap.md). **Oct 24:** the ads decision - does November get one $20 test (`ops promotions`). **Parked / excluded:** Benable bot · Edge TTS as default (§28). #1255 and #1247 are open and not next.

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
