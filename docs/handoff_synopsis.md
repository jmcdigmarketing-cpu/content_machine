# Handoff synopsis — 2026-10-15: a 500 is not a dead channel, run ids on the log, brand file, jitter, dead air

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-10-09

Use in a fresh session to continue `content_machine` without re-reading the full thread.

GPT-6 playground review (2026-09-08, briefing-based): [gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md) and [gpt6_part2_upgrades_2026-09-08.md](gpt6_part2_upgrades_2026-09-08.md). Not a recorded operator decision.

> Older waves and the 2026-07/08 shipped-notes are frozen verbatim in
> [handoff_synopsis_archive.md](handoff_synopsis_archive.md); this file keeps the newest three
> waves plus the standing operator sections (docs_standard.md §7).

## Last wave — 2026-10-15 (Cursor): the five left from 10-10

A YouTube 500, and a 404 from every competitor channel, was reported as a dead UC id, and the
sync then spent 3 Data API units per channel (#1121, #1125). The probe now keeps the HTTP
status. When every channel returns 404 or 5xx, `ops competitor-health` prints one "channel
feed is down" line and `sync_competitors` records `feed_down` and makes no Data API call. A
200 with no videos is still a dead id. One 404 beside a 200 is still that id.

Log lines written after `record_content_run` include `run=<id>` and still contain ` [WARNING] `
(#462). The id does not exist before that, so discovery lines stay unbound. This interpreter's
pool does not copy context; discovery submits through `submit_in_run`.

`config/brand_safety/tapin.txt` drops a sentence containing "guaranteed profit", "deposit bonus"
or "risk-free bet" (#409). "fan favorite" and "lock it in" stay. A one-word line is not a phrase.
A channel with no file is unchanged.

A 429 cooldown is half to one-and-a-half of 900s, so two signals that trip together do not share
a wake time (#388). `youtube`, `youtube_comments` and `youtube_competitors` share one host cap
(`DISCOVERY_HOST_CONCURRENCY`, default 2). Trip statuses and the Apify breaker are unchanged.

After the sentence concat, leading and trailing silence are removed and an internal gap longer
than 0.4s shrinks to 0.15s (#404). Word timings move by the seconds removed. Missing ffmpeg
leaves the file unchanged and logs nothing at warning.

**Next:** #1195-#1199, one video on three feeds. New tests errored on import before the functions
existed. Re-run: 5861 passed. Claude's untracked `tests/test_arc_and_titles.py` is wave 92
and is not in this commit. mypy 96, corpus 250. Live: `ops competitor-health --channel tapin`
printed Marques Brownlee, 4 recent via rss.

## Previous — 2026-10-15 (Claude Code): waves 91-92, TikTok/Instagram and the morning

**Wave 91.** A video posted by hand in Buffer is found and left on that platform (#1200, §57 -
Topuria, Chargers and Minecraft were); `crosspost done` records one (#1201); the worker starts
the crosspost round after a public upload (#1202); `ops morning` and `ops all` offer queued
uploads (#1203); `ops all` ends with the morning (#1204, §56). The live Buffer draft found that
Buffer cannot read a presigned R2 link (HEAD answers 403): the video is read from the bucket's
public address now (#1207, §58). Crossposting switched on (44 videos left as they are).

**Still the operator's:** `R2_PUBLIC_BASE_URL` (public access on the bucket) and `.env` lines
35-36; then `crosspost selftest`; the consent screen; `ops worker-task --install`;
`schedule-drafts --wake`; whether Cursor starts #1194. Suite 5861 (5823 + my 38; Cursor's uncommitted tests ran with it), mypy 98. Claude has
#1205, #1181, #1182, #1183, #1206 claimed (wave 92).

## Previous — 2026-10-14 (Claude Code): waves 89-90, TikTok and Instagram through Buffer

**Wave 89.** Each video made public on YouTube now goes to TikTok and Instagram through
Buffer's API (#1185-#1190, decisions_2026-10.md §54): new videos only, one post a day per
platform at the suggested slot, the AI label on. R2 hosts the video (Buffer fetches from a
link). It runs at the end of `go-public --apply`, in `ops morning` (`crosspost-send`) and in
the overnight report; `ops crosspost status` / `send` / `cancel` / `channels` / `selftest`.
Nothing can go out yet: the R2 keys are not in `.env`.

**Wave 90, what you raised.** At most 2 of 5 best bets are games (#1191, §55); `py main.py`
menu 6 shows the overnight videos with their files and links (#1192); unreadable `.env` lines
are named by number (#1193). **Offered to Cursor:** #1194, learning per platform from TikTok and
Instagram results - `docs/initiative_cross_platform.md`.

**Still the operator's:** the R2 keys and `.env` lines 35-36; `crosspost selftest` and
`crosspost channels --apply`; the 2 overdue uploads (`ops worker`); the consent screen;
`ops worker-task --install`; `schedule-drafts --wake`; whether Cursor starts #1194. Suite
5780 -> 5823, mypy 98, corpus 244. Claude has nothing claimed.

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
