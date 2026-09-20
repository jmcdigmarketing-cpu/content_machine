# Engine upgrades — script generation, idea grading, resource use

**Written:** 2026-09-20 · **HEAD:** `0d5d23c` · **Branch:** `consolidate/2026-08-27`

Operator: *"generate ideas surrounding improved script generation, idea grading, and resource
utilization."*

This is the idea list for the three areas, with the evidence each rests on. Every number below
was measured on 2026-09-20 from the **38 run traces on disk** (`data/traces/47-90.json`), the
operator's `.env`, and the repository itself — not from the docs, which predate most of those
runs.

Read the diagnosis first if you have not: [idea_quality_diagnosis.md](idea_quality_diagnosis.md)
explains *why* the output has the shape it has. This file is narrower: what to build next, in
what order, and what to leave alone. Direction and horizons:
[strategy_next_level.md](strategy_next_level.md).

---

## 1. The measured baseline

### Money and time per run

| measurement | value | where |
|---|---|---|
| total cost per run, median | **$0.11** | `cost.total` across 38 traces |
| TTS share of all spend | **$6.09 of $7.27 — 84%** | `cost.tts` summed |
| LLM spend per run, median | **$0.0071** (9 calls, ~16k input tokens) | `llm_calls`, `llm_cost_usd` |
| Apify per run | **$0.02** flat, $0.56 total | `cost.apify` |
| discovery wall clock | median **58.7 s**, max **114.6 s** | `timings.signals_and_variants` |
| research brief | median 11.2 s, max **138.2 s** | `timings.research_brief` |
| content package (script + passes) | median 34.4 s, max 74.5 s | `timings.content_package` |
| variant scoring | median 0.9 s, max **185.2 s** | `timings.variant_scoring` |

**The cost story is one line: TTS is 84% of spend and the LLM is 0.1% of it.** Any idea that
saves tokens is not worth the change it costs to make. Ideas that save *synthesis* are.

### The TTS cache is built and switched off

`TTS_CACHE` is **absent from the operator's `.env`**, `data/tts_cache/` **does not exist**, and
`tts_cached` is `false` on every trace that records it. Both caches — whole-script (#71,
2026-08-20) and sentence-level (#402, 2026-09-06) — are finished, tested and idle. Every
re-render of an unchanged script re-pays ElevenLabs.

### Script quality, as the machine currently sees it

| metric | median | range | note |
|---|---|---|---|
| hook score | 78 | 55 – 93 | the one component that discriminates |
| **authenticity** | **100** | 35 – 100 | **100/100 on 22 of 38 runs** |
| claim support | 0.833 | 0.0 – 1.0 | unsupported claims: median 1 |
| similarity to previous script | 0.291 | up to 0.547 | only compares against **one** prior script |
| angle intent recorded | — | — | 10 runs carry it; **9 of the 10 read `default`** |

Authenticity carries **28%** of the report card (`core/video_grade.py:_WEIGHTS`) and sits at its
ceiling for 58% of runs. A component that cannot go down cannot rank anything; it converts 28%
of the grade into a constant. This is the same defect the diagnosis found by reading the code
(§3.6) — now confirmed by the distribution.

### Which signals actually return anything

| signal | ok / runs | signal | ok / runs |
|---|---|---|---|
| `twitch` | **33/33** | `wikipedia` | 24/38 |
| `youtube_competitors` (paid) | 32/38 | `youtube_comments` | 6/19 |
| `blog_rss` | 31/38 | `news` | 9/38 |
| `trends` | 29/38 | `autocomplete` | 8/38 |
| `web_search` | 29/36 | `steam` | **1/33** |
| `tiktok_trends` (paid) | 28/38 | `igdb` | **1/33** (+6 http errors) |
| `youtube` | 28/38 | `trendingnow` | **0/22** |
| `rawg` | 27/33 | `tapology`, `stats_context`, `tvmaze`, `tmdb` | **0** |

Six signals have produced nothing across every run that called them, while discovery takes a
median of 58.7 s. `reddit` and `twitter` are already retired (`enabled: false`).

### Disk

`output/` **4.3 GB** (300 files) · `video/backgrounds/` 9.2 GB (the library, intended) ·
`data/` 1.6 GB after wave 24 swept 2.6 GB of stale composed backgrounds (#797).
`core/artifact_retention.py` exists, prints **"DRY RUN ONLY"**, and is wired to no scheduler.

---

## 2. Script generation

Ordered by expected effect on what the operator is willing to publish. The next build wave
weights this section (operator, 2026-09-20).

1. **#799 — a per-pass rewrite ledger.** *(shipped wave 26)* Five passes can rewrite a finished script
   (`_maybe_improve_hook`, `_maybe_reground_script`, `_maybe_rewrite_unsupported_claims`,
   `_maybe_inject_insight`, `_maybe_recenter_on_key_facts`), four of them on the premium tier.
   Nothing records which fired, what each changed, or what it cost. Run 74 lost words to one of
   them and it took a live investigation to see it. Record pass, word delta, hook delta and cost
   in the trace, and print the line on the report card. **This is the prerequisite for every
   other script change: today you cannot tell which pass produced the sentence you dislike.**
   `[S]`
2. **#800 — hedge density beside claim support.** *(shipped wave 26)* `decisions.md` §25 has been open since run 58
   shipped four consecutive weasel sentences at 30% support: the claim rewriter converts a bare
   assertion into an attributed one and the re-check then passes, so "12/12 backed" can be
   bought with hedging. Count hedge phrases per 100 words, print it next to claim support, and
   let the grade fall. This *decides* §25 rather than deferring it again. `[S]`
3. **#801 — intent coverage replay.** *(shipped wave 26)* `core/angle_intent.py` is the one change in project
   history that moved output quality on its own (run 75, the best grade on record), but of the
   10 runs that record an intent, **9 read `default`**. Replay all 38 recorded topics through
   the detector, count what each returns, and widen the cues where a calm or explanatory idea
   reads as a take. Cheap, and it measures a fix already shipped. `[S]`
4. **#802 — a latency budget for generation.** The research brief has taken 138 s and variant
   scoring 185 s on single runs, against medians of 11 s and 0.9 s. Give each stage a deadline
   with a documented fallback (skip the brief, keep the facts) so a slow provider costs seconds,
   not minutes. `[M]`
5. **#803 — style memory across runs.** Similarity is measured against **one** previous script.
   Compare each draft against the last N published scripts and flag repeated openers, closers
   and sentence shapes — the "recurring nightmare" opener shape appears across several GTA runs.
   `[M]`

Also relevant and already filed: **#374** premium tier for the hook only (hook median 78 is the
component with room), **#50** learned insight markers, **#339** "unconfirmed" as a script mode.

---

## 3. Idea grading

The theme: the report card is currently unable to rank its own output, so every quality change
is judged by an instrument that does not move.

1. **#804 — fix the saturated authenticity component.** *(shipped wave 26; #50 still open)* 100/100 on 22 of 38 runs, 28% of the
   grade. Either rescale it against the observed distribution or replace the substring-match
   scorer with something that can distinguish two good scripts. Pair it with #50. `[M]`
2. **#805 — print the report card's own hit rate.** Correlate grade and composite against
   `engaged_rate` over every measured publish, and print `r` with `n` on the card. The one
   dataset that exists says composite is uncorrelated with engagement (40% hit rate; the
   lowest-scored topic beat two 100.0s). A card that reports its own accuracy stops being
   believed more than it deserves. Distinct from **#561**, which is the recommender's accuracy.
   `[M]`
3. **#806 — capture the rejection reason in `ops batch-review`.** The operator has rejected six
   drafts in two weeks (88-90 and three before), and the reason exists only as prose in this
   repo's planning log. One keystroke at rejection — pace, facts, angle, hook, topic — builds
   **the only operator-labelled dataset the project could have**, and it costs one column in the
   review store. `[S]`
4. **#807 — offline re-score replay.** The variant tie (five angles, identical score) was fixed
   for the thesis case in wave 14 (#744). Nothing proves it is gone for the ordinary case.
   Re-score the recorded runs' variants offline and report the spread; a tie that reappears is
   then a test, not a discovery. `[S]`
5. **#808 — snapshot grade inputs.** `core/grade_calibration.py` re-grades history with today's
   code, and `GRADE_VERSION` stamps *that* a change happened, not what the inputs were. Store
   the inputs beside the scores so a re-grade is reproducible and a component change is
   measurable against the archive. `[S]`

Also relevant and already filed: **#83** holdout videos, **#560** hold-out set, **#561** loop
accuracy, **#351** confidence intervals (shipped 2026-08-30).

---

## 4. Resource use

Cheapest wins in the project, and two of them are configuration rather than code.

1. **#809 — switch the TTS cache on.** *(shipped wave 26)* 84% of spend, a finished cache, zero hits. Default it on
   in production (pin it off in the suite, the pattern `BACKGROUND_FAST_CUT` already uses), and
   print the hit rate on the nightly line so a silent miss is visible. `[S]`
2. **#810 — retire or flag the zero-yield signals.** `trendingnow` 0/22, `igdb` 1/33 with six
   http errors, `steam` 1/33, `tapology`/`stats_context`/`tvmaze`/`tmdb` 0. Each still costs a
   thread and a timeout inside a 58.7 s median. This is the measurement **#575** asked for;
   retiring follows `decisions.md` §19 and the `reddit`/`twitter` precedent. `[S]`
3. **#811 — a discovery deadline.** Signals already run concurrently, so the run waits for the
   slowest. Take the first N good results past a deadline and record which signals were dropped,
   rather than waiting on a signal that has never returned. `[M]`
4. **#812 — wire artifact retention.** 4.3 GB in `output/`, a retention module that only ever
   prints a dry run, and no schedule. Give it an `--apply` and a place in the nightly task, with
   published renders exempt. `[S]`

Also relevant and already filed: **#380** Apify cost per usable fact, **#384** per-signal SLO,
**#390** signal dependency graph, **#445** resume a run from the ledger, **#611** parallelise the
remaining render passes (wave 24 did the shot encodes; a 140 s video still takes 108 s).

---

## 5. Not worth doing

Written down so a future session does not rediscover them as good ideas:

- **Optimising LLM token spend.** $0.0071 per run, 9 calls. Halving it saves under a cent and
  costs prompt quality. Route *more* to premium where it helps (#374), not less.
- **Adding more discovery signals.** Six of the current ones return nothing; `decisions.md` §26
  already says more APIs are not a quality upgrade. Fix yield before adding sources.
- **A second cache anywhere in the signal path.** `register_signals._fetch_one` already caches
  every call; a second layer hides staleness (root `CLAUDE.md` hard rule).
- **Re-tuning the grade weights.** #804 made authenticity able to move; re-weighting before a
  live distribution exists still just moves the constant around.
- **Chasing statistical significance at n≈10 published.** Per `strategy_next_level.md` §3, the
  way out is more measured dimensions per publish, not more confident arithmetic on ten rows.
