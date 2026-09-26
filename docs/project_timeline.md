# Project timeline — Content Machine / Content OS

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-09-26

The official timeline of the project from its first conversation to today, newest last.
The same timeline with charts of the repository's growth is the operator's private page
"Content OS Story" (https://claude.ai/artifact/8gPYFQqVvp7BgAJXU7iLeH). Every entry names its **evidence**: `git` (a commit), `doc` (a dated heading in
[planning_log.md](planning_log.md), [planning_log_2026-08.md](planning_log_2026-08.md),
[planning_log_2026-07.md](planning_log_2026-07.md), [roadmap_archive.md](roadmap_archive.md)
or [change_log.md](change_log.md)), or `operator` (the operator's own records, including the prototype source files they supplied on 2026-09-26). Append new
eras at the bottom; correct an entry only when better evidence arrives, and say so.

**Where the evidence stops.** Git history starts on 2026-07-10 with a commit that is already
"Pillar 6", and the oldest dated doc is from 2026-06. The work before that is known in order
(the Phase 1-4 and D-G checklists in `roadmap_archive.md`) but not in date. Those rows are
marked *date not recorded*; the operator's dates go in the slot below.

## Era 0 — the ChatGPT origin (2025-05 → 2026-05)

| When | What | Evidence |
|---|---|---|
| 2025-05 | The project begins as ChatGPT conversations | operator |
| 2025-05 (NBA playoffs) | **The first prototype**: 9 files, 291 lines. You type a topic; a `sports/` router picks NBA data (ESPN standings for playoff topics, balldontlie for a player, SportsData.io standings otherwise); GPT-4o-mini writes "aggressive sports debate scripts", 60-120 s, ending "Tap In"; ElevenLabs voices it to an MP3. No video, no upload, no database | operator files |
| 2025-05 → today | Its `sports/espn.py` `get_scoreboard()` is still in the repo, and `apis/live_scores_api.py` still calls it - the one line of the prototype that never changed | git |
| *operator's slot* | Move from the prototype to a local codebase with video; first render; first upload; TapIn and MoneyWise start; Cursor / Claude Code join | operator (to fill) |
| date not recorded | **Phase 1 Foundation** - discovery → content → optional render; OpenAI, TTS, FFmpeg vertical video, CLI | doc |
| date not recorded | **Phase 2 Database** - PostgreSQL with JSON-file repositories side by side | doc |
| date not recorded | **Phase 3 Efficiency & UI** - parallel signals, cache, the signal contract, health UI | doc |
| date not recorded | **Phase 4 Assets** - local / Pexels / Pixabay provider chain, Pillow thumbnails | doc |
| date not recorded | **Phases D-G** - YouTube OAuth upload, idempotent publish log, job worker, CI, analytics sync, learned weights, channel profiles, the operator CLI, UFC research | doc |

## Era 1 — intelligence and the first honest look (2026-06)

| When | What | Evidence |
|---|---|---|
| 2026-06 | **Phases H-K** - research-brief engine, competitor tracking, status view, thumbnails | doc |
| 2026-06 | **Phase L / L2 / L3** - closed-loop recommenders, the Apify data layer, idea intake | doc |
| 2026-06 | Engineering quality baseline; the first honest assessment ([assessment.md](assessment.md)) | doc |

## Era 2 — the pillars (2026-07)

| When | What | Evidence |
|---|---|---|
| 2026-07-02 | Themeable skins | doc |
| 2026-07-06 | Reorientation to seven internal-systems pillars: run ledger, grading, fact engine, Obsidian, agents, video providers, self-improving skills | doc |
| 2026-07-07 | Pillar 5, the agent layer | doc |
| **2026-07-10** | **Git history begins** - Pillar 6 dual-format render. 953 test functions, 47 ops commands, 34 docs | git |
| 2026-07-22 | Best Bet breadth; scheduling mechanics | doc |
| 2026-07-24 | Pillar 7, self-improving skills | doc |

## Era 3 — waves, honesty, a second agent (2026-08)

| When | What | Evidence |
|---|---|---|
| 2026-08-14/15 | Six waves in one session: the silent-failure session | doc |
| 2026-08-20 | Post-merge grand audit; four waves in a day; the 180-idea brainstorm | doc |
| 2026-08-21/22 | Honesty + leave-the-terminal waves 1-4 | doc, git |
| 2026-08-23 | The MoneyWise persona | doc |
| 2026-08-27 | The vault relevance engine finished | doc |
| 2026-08-28 | The agent mailbox (`handoff.md`) and signed commits; Cursor's first signed commits (week 34); live run 73 | git, doc |
| 2026-08-30 | The idea-quality wave: "the framing is an accretion, not the charter" | doc |
| 2026-08 total | 101 commits, the busiest month | git |

## Era 4 — the operator loop, live runs and reviews (2026-09)

| When | What | Evidence |
|---|---|---|
| 2026-09-05 | The four-step session written down (the next-five skill) | doc |
| 2026-09-06/07 | Claude reviews Cursor's waves; the desktop app Stages 0-3 (run window, look, review room) | doc |
| 2026-09-08 | The GPT-6 external review archived; review 4 | doc |
| 2026-09-09/12 | Reviews 6-7; waves 9-10 (the desktop panel) | doc |
| 2026-09-13 | Live runs 76-78; waves 11-16; the #745 stopword regression found and restored | doc, git |
| 2026-09-15/16 | Waves 17-18: publish safety, the voice bill, batch review; the operator's call that a run forced past the grounding gate stays unlisted (#754) | doc |
| 2026-09-18/19 | Drafts 88-90 rejected ("the clips need to be much shorter"); the pacing reversal (waves 21-24) | doc |
| 2026-09-20 | Waves 25-30: the ideas measured against the run record; the 09-20 audit; the composite score measured anti-predictive at n=12 | doc |
| **2026-09-26** | The grand audit executed and waves 31-37 in one day: order-independent tests, the mypy ratchet, run 98 (TTS billed once, football as football), auto-research, `ops go-public`, the own review and the regression corpus, one domain per run | git |
| 2026-09-26 | 3,686 tests, 142 ops commands, 81 docs, 443 source files, 200+ commits | git |

## Live runs that changed the code

| Run | Date | What it exposed |
|---|---|---|
| 66 | 2026-09 | "Why" read as part of a name (restored after #745 erased it) |
| 69 | 2026-09 | The queue said public; the upload landed unlisted |
| 73 | 2026-08-28 | Four defects from a GTA 6 reaction run |
| 74 | 2026-08-29 | Fact intake had character limits for no reason |
| 76 | 2026-09-13 | A GTA 6 thesis aborted at TTS |
| 77 | 2026-09-13 | Karaoke captions burned at a tenth of their size, on YouTube |
| 78 | 2026-09-13 | All angles in one long video, Shorts from its chapters |
| 88-90 | 2026-09-18 | Drafts rejected for slow pacing |
| 98 | 2026-09-26 | Double TTS billing; football routed as gaming; facts off-topic; football filed as Gaming on YouTube |
