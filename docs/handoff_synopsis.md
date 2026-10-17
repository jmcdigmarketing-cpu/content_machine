# Handoff synopsis — 2026-10-16: the backlog five (#1235 #499 #1046 #1056 #1039)

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-10-09

Use in a fresh session to continue `content_machine` without re-reading the full thread.

GPT-6 playground review (2026-09-08, briefing-based): [gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md) and [gpt6_part2_upgrades_2026-09-08.md](gpt6_part2_upgrades_2026-09-08.md). Not a recorded operator decision.

> Older waves and the 2026-07/08 shipped-notes are frozen verbatim in
> [handoff_synopsis_archive.md](handoff_synopsis_archive.md); this file keeps the newest three
> waves plus the standing operator sections (docs_standard.md §7).

## Last wave — 2026-10-16 (Cursor): #1235 #499 #1046 #1056 #1039

Claude sent no new five after #1221 #1227 #1228 #1043 #1229. This wave is the
five the roadmap already named.

`footage-tag` writes a team onto a clip that is already in the index. `chargers`
becomes Los Angeles Chargers, and a Chargers topic then returns that GameClip.
A path that is not indexed is refused and no row is created. A folder with no
tags still returns the untagged clips (#1235). A one-shot voice file is
silence-trimmed after its words exist and before it is cached; a cache hit is
left alone (#499). TapIn karaoke highlights the spoken word in `#E53935`; a
skin with no highlight stays yellow, and TapIn's margin stays 260 (#1046).
The hook sentence is on screen from 0.00 to 1.00 at the top (#1056). The first
paragraph is requested at 1.10 instead of 1.05, an asterisked word is style
0.35 and is not spoken, and an ellipsis holds the next word 0.3s (#1039).

Finished output changed: one-shot voice files, TapIn captions, and the first
spoken paragraph. Not pushed. Next: #429 #438 #489 #492 #422.
`roadmap-index`: open 288, done 1180, numbered open 236, highest open #1136.

## Previous — 2026-10-16 (Cursor): #1221 #1227 #1228 #1043 #1229

The Dr Food headline stayed neutral on a gaming feed, so it is not a best bet (#1221).
A stored URL that still contains a quote, a brace, or an image host is not fetched;
the quoted Last.fm page that #1157 used to strip and retry is refused (#1227). A 6.8s
fast cut no longer dies at 120s: `-nostdin`, a timeout of 204s, one `ultrafast` retry
only after a timeout (#1228). "How the 0-4 chargers can turn it around" returns the
Chargers clip and not the four untagged Madden files; a topic with no team keeps the
folder (#1043). Each overnight draft is its own child; a crash names that draft and
the set-aside pass and the renders still run (#1229).

Finished output changed: a timed-out shot may finish on `ultrafast`. A team video
with only untagged Madden gets no local folder footage. A stored quoted URL is no
longer fetched. A neutral headline is no longer adopted by a single-domain feed.
Not pushed. Next: #1235 #499 #1056 #1039 #1046. `roadmap-index`: open 293, done 1175,
numbered open 241, highest open #1235.

## Previous — 2026-10-16 (Cursor): #1215 #514 #418 #463 #545

An untagged Contender Series headline was nba on the word "contender"; "contender series"
is ufc, and a Lakers contender stays nba (#1215). The duration and caption benches printed
a miss and exited 0; past 5% or past 150ms they exit 1, and no sidecars exits 0 (#463).
A 1.08 zoom enlarged a frame that was already 1080x1920; the filter pre-scales first
(#418). The intro sting met the first caption at full volume; intro audio fades out over
its last 0.25s (#514). A franchise with a correction now says what it got wrong, and that
sentence is not a veto (#545).

Finished output changed: hook-motion frames, and an intro that has audio. Not pushed.
Next: #1221 #1227 #1228 #1229 #1043. #1215 left the old corpus case expecting nba;
Claude retargeted it to ufc in `ab9677f`. Claude's wave 99 is `0e4582c`. #1233 and
#1234 were still uncommitted when this was written.

## Previous — 2026-10-16 (Claude Code): waves 97-98, five for Claude, five more for Cursor

**Wave 97.** After the operator ran overnight by hand, the stop line said "stopped after 4 of 3
drafts"; `ops overnight` now records its start and finish, the line is quiet once a later run
finished and counts only the run that stopped (#1223). `ops blocking` read a pulled run, then a
trace's stale scores; it reads the shelf and the run's record (#1222).

**Wave 98.** Run 159 came back "New York Jets vs England Patriots" - the angle prompt was told
"York, Jets, England"; whole names now, and a broken team name fails the title check (#1224).
Run 158 kept "Long-term outlook:" and ended its title in "..." (#1225). The check read neither of
run 158's takes, and calm drafts were held for one they never got; they get a "what to watch"
beat now (#1226).

**Cursor:** after its five (#1215 #514 #418 #463 #545), the operator added #1221 #1227 #1228
#1229 #1043. Claude reviews, corrects and pushes Cursor's work in the next prompt.

**Still the operator's:** `R2_PUBLIC_BASE_URL`; `.env` lines 35, 36, 39; the worker (runs 155,
126 queued - the shelf is full, so overnight is paused); the consent screen; `schedule-drafts
--wake`. Suite 5965, forward and reversed.

## Previous — 2026-10-16 (Claude Code): waves 95-96, what the morning said that was not so

**Wave 95.** Overnight woke with the PC at 4:30 PM, made run 156 and crashed at 4:32 (0xC0000374,
heap corruption in ntdll, no traceback); the morning said it ran. It now says when it stopped,
after how many drafts, why, and the command to run it again; `faulthandler` is on in overnight
and the worker (#1216). Every run had recorded 0 facts - the pasted ones - so health read
authenticity RED at 49; runs record `fact_lines` now, and the 14 recent ones were re-scored:
GREEN, 89 (#1217).

**Wave 96.** Every command printed dotenv's warning for line 34, which is blank; it names lines
35, 36 and 39 now (#1218). The morning counted 1 draft past its window when 8 were; a dead draft
says so first, and **n** sets it aside (#1219). Health no longer flags the anime signal from four
old game runs (#1220).

**Still the operator's:** `R2_PUBLIC_BASE_URL`; `.env` lines 35, 36, 39; run 126 waits for the
worker; the consent screen; `ops worker-task --install`; `schedule-drafts --wake`. Overnight's
other two drafts were not made today. Suite 5943, forward and reversed.

## Previous — 2026-10-15 (Claude Code): waves 93-94, why clean drafts waited

**Wave 93.** The authenticity check read clean drafts as neutral recaps - "Here's my call anyway.
I'm taking the double" did not count as a take - so overnight rendered none of them. A
first-person call or a "what people miss" frame counts now (#1210); six waiting drafts went to
ok. A draft from the arc counter (run 153, "week four") and a title that breaks a name (run 149)
wait for a person (#1211). Tonight renders run 155, the Titans-Colts preview.

**Wave 94.** A "fans react" angle loses points when nothing carried reactions (#1212, run 154).
The review names the failing check - "no take found", "too few facts" (#1213). `ops crosspost
buffer-check` tries Buffer end to end with a draft it deletes (#1214); it waits on
`R2_PUBLIC_BASE_URL`.

**Still the operator's:** `R2_PUBLIC_BASE_URL` (public access on the bucket) and `.env` lines
34 and 36 (unparsed); the consent screen; `ops worker-task --install`; `schedule-drafts --wake`. Suite 5914, forward and reversed.

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
