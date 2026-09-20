# Content Machine — Vision & 12-Month Architecture

> **Class:** charter · **Status:** living · **Reviewed:** 2026-09-20

**North star: stop building features, start building an intelligence system that operates media businesses.**
Content generation is one subsystem. The durable asset is the proprietary
performance dataset and the decision-making built on top of it.

This doc has two halves:
1. **The vision** (the operator's intent, captured verbatim in intent).
2. **The engineering response** — a senior-level challenge of that vision,
   what's already built, the weak points, the missing systems, complexity
   estimates, and a **revised 12-month plan** prioritized for *defensibility,
   revenue, and learning advantage* over content volume.

Tactical phase tracking still lives in [roadmap.md](roadmap.md); strategy scoring
in [content_intelligence_roadmap.md](content_intelligence_roadmap.md). This is the
north star they ladder up to.

---

## 1. The vision

```
v1 (today)                      v3 (target)
Research          →             Market Intelligence
Generate                        Research Intelligence
Render                          Content Intelligence
Upload                          Asset Intelligence
Learn                           Monetization Intelligence
                                Channel Intelligence
                                Portfolio Intelligence
                                Business Intelligence
```

**End goal: not "make videos" — "operate media businesses."** The system should
ultimately answer, without manual analysis:

> What should we make? · Why? · How? · When should we publish it? · How should we
> monetize it? · What should we do next?

**Mission:** an autonomous content OS that identifies opportunities, launches and
manages channels, learns from performance, monetizes audiences, and scales — with
minimal manual intervention.

**Intelligence layers (the operator's phasing):**

| Phase | Layer | Operator timeline |
|------|-------|-------------------|
| A | Research Intelligence (reusable briefs, Topic DB, Graveyard, Winners) | 0–30d |
| B | Channel Intelligence (Channel DNA, Health Agent, Recommendation Agent, Voice Evolution) | 30–90d |
| C | Analytics Intelligence (exec reports, Hook/Title/Thumbnail intelligence) | 60–120d |
| D | Competitor Intelligence (Competitor Genome, opportunity & trend detection) | 90–150d |
| E | Asset Intelligence (clip memory, search, performance ranking) | 120–180d |
| F | MoneyWise (ticker/earnings/sentiment/conviction) | 120–210d |
| G | Benable Intelligence (product matching, revenue attribution, revenue-per-topic) | 150–240d |
| H | Knowledge Intelligence (Obsidian vault, prompt evolution, content encyclopedia) | 180–270d |
| I | Business Intelligence (portfolio dashboard, opportunity scanner, launch framework, market map) | 240–360d |
| J | Autonomous media company | 360d+ |

---

## 2. Reality check — most of "Phase A–C" already has foundations

The vision is framed as greenfield; the codebase says otherwise. Mapping intent
to what already ships on `main`:

| Vision item | Status today | Where |
|---|---|---|
| Research Brief (narrative, controversy, sentiment, debate angles, title direction, hook) | **Built** — missing only an explicit `confidence_score` + audience-profile fields | `core/research_brief.py` (`ResearchBrief`) |
| Topic Database (topic/score/script/channel/performance, "every LeBron topic ever") | **Built** — `content_runs` + `publish_log.metrics_json` join; needs query ergonomics | `storage/models.py`, `storage/repositories/content_runs.py` |
| Topic Winners DB | **~80%** — data exists (features↔engagement join); needs a ranked view + "clone this" path | `analytics/weekly_report.py`, `content_runs.features_json` |
| Topic Graveyard | **~60%** — failures are recorded (status, low engagement); no explicit avoid-list wired into discovery | `content_runs`, `publish_log` |
| Channel DNA (which angles get A+/F) | **~70%** — per-domain/angle/format engagement already computed | `analytics/weekly_report.py`, `core/run_features.py`, learned topic weights |
| Channel Recommendation (next topic/time/length) | **Built (v1)** | `core/best_bet.py`, `analytics/post_timing.py`, `core/length_recommender.py` |
| Weekly Executive Report | **Built (v1)** | `analytics/weekly_report.py` → `scripts.ops weekly-report` |
| Hook / Title / Thumbnail Intelligence | **Partial** — `hook_score` exists; title_structure is a feature; `thumbnail_scores` table exists but CTR-correlation not closed | `core/hook_score.py`, `assets/thumbnail_scorer.py`, `storage/models.py` |
| Asset Memory | **Foundation** — `assets` table records render assets; no retention-impact ranking yet | `storage/models.py`, `core/asset_recorder.py` |
| Knowledge / Obsidian + prompt versions | **Built (v1)** — vault read + machine-belief writeback; `prompt_version` persisted | `core/obsidian_facts.py`, `core/vault_writeback.py`, `content_runs.prompt_version` |
| Cost / unit economics | **Built (v0)** | `core/cost_meter.py` |

**Implication:** the next 30–60 days are mostly *consolidation and surfacing* of
existing data into decisions, not net-new engines. Treating Phase A as greenfield
would rebuild what exists and waste the lead.

---

## 3. Challenge — weak points in the roadmap

A senior review, ordered by how much they threaten the plan:

1. **Everything is gated on data volume the channel doesn't have yet.** "Channel
   DNA," "hook leaderboard," "title intelligence," "asset performance ranking" all
   need N≥30–100 *published* videos *per dimension* before the signal beats noise.
   At ~9–44 videos total per channel, most "intelligence" would be **overfitting
   to ~3 samples** — the exact failure the just-shipped confidence surfacing
   guards against. **The roadmap's first job is to earn data, not model it.**

2. **Correlation is treated as causation.** "Fraud narratives = A+" assumes the
   narrative caused the views, not the topic, timing, thumbnail, or luck. Without
   a **controlled experimentation harness** (hold one variable, vary another),
   the system will confidently learn superstitions and optimize toward them. This
   is the single biggest threat to the "learning advantage" thesis and is *absent*
   from the phase list.

3. **Retention/CTR data access is assumed, not verified.** Hook/title/thumbnail
   intelligence needs YouTube Analytics *retention curves* and *impressions CTR*
   — which require the Analytics API (different scope/quota from the Data API) and
   only populate after a video has impressions. The plan should de-risk data
   access in week 1, not month 3.

4. **YouTube API quota is a hard ceiling.** Competitor Genome + trend monitoring
   across "Reddit/YouTube/TikTok/News/Trends" will blow the default 10k/day Data
   API quota fast. Apify is already a cost/credit pain point (see the 402 guard).
   Cross-platform monitoring is a *cost-bounded* problem, not a build problem.

5. **Autonomy vs. the 2026 policy gate are in tension.** "Minimal manual
   intervention" pushes toward fully-automated publishing; the authenticity gate
   (Decision §9) exists *because* shallow synthetic volume is now an existential
   ban risk. More automation without stronger originality signals increases
   platform risk. Defensibility ≠ volume.

6. **Cold-start for new channels has no plan.** "Channel Launch Framework" assumes
   transferable intelligence, but a fresh channel has zero history; the launch
   recommendation would lean entirely on competitor data, which is the weakest
   (scraped, noisy) signal. Needs an explicit cross-channel-prior model.

7. **Benable/affiliate revenue attribution is the hardest data problem in the
   list, scheduled mid-stream.** Closing video→click→sale requires link-level
   tracking, an affiliate API or dashboard scrape, and identity stitching. High
   value, but treat it as a spike with a kill criterion, not a guaranteed phase.

8. **No data-quality / observability layer.** The whole thesis rests on the
   performance dataset being *trustworthy*. Garbage metrics (mis-joined runs,
   timezone bugs in post-timing, stale syncs) silently poison every downstream
   "intelligence." There's no monitoring for the data the system reasons over.

---

## 4. Missing systems (recommend adding)

- **Experimentation harness (A/B + holdouts).** The causal backbone. Vary one
  lever (hook style, title format, length, thumbnail) with everything else held;
  attribute lift. Without it, §3.2 sinks the learning advantage. **This is the
  moat, not the content.**
- **Data-quality monitor.** Assertions on the run↔metrics join, freshness of
  analytics sync, sanity bounds on engagement; a red flag when a recommender's
  inputs are stale or thin. Cheap; protects everything.
- **Unit-economics ledger (RPM / cost / margin per video & per topic).** `cost_meter`
  is the cost half; pair it with realized RPM so decisions optimize *margin*, not
  views. This is what turns "make videos" into "operate a business."
- **Quota & spend governor.** A single budget layer over YouTube/Apify/LLM/TTS
  with per-day ceilings and graceful degradation (the 402 guard, generalized).
- **Idempotent backfill / replay.** As schemas and features evolve, the ability
  to recompute history is what keeps the dataset usable (already partly there:
  `backfill_features.py`).
- **Evaluation set for prompt/model changes.** Before "prompt evolution," a frozen
  set of topics + a scoring rubric so prompt changes are measured, not vibes.

---

## 5. Engineering complexity (rough)

S = days · M = 1–2 weeks · L = 3–6 weeks · XL = quarter+. "Data-gated" = blocked
on accumulating published videos regardless of build effort.

| System | Build | Notes |
|---|---|---|
| Confidence-score field on Research Brief; audience profile | S | brief already exists |
| Topic DB query layer (winners/graveyard views + "clone") | S–M | data exists; add views + discovery avoid-list |
| Channel DNA report (A–F grades per angle) | M (data-gated) | computation cheap; *trust* needs volume |
| Channel Health Agent (nightly Green/Yellow/Red) | M | trends + thresholds; reuse weekly_report |
| Experimentation harness | **L–XL** | the hard, high-value one; design first |
| Data-quality monitor | S–M | assertions + a status panel |
| Hook/Title/Thumbnail intelligence | M (data-gated) | needs Analytics API + impressions |
| Competitor Genome + trend detection | L (cost-gated) | quota/credit-bounded; cache hard |
| Asset performance ranking | M (data-gated) | needs retention attribution per clip |
| MoneyWise intelligence (ticker/earnings/sentiment/conviction) | L | mostly free APIs; sentiment is the fuzzy part |
| Benable attribution (video→click→sale) | **L–XL** | hardest data plumbing; spike with kill criteria |
| Portfolio/Business dashboard | M | aggregation over existing per-channel data |
| Channel Launch framework | L (data-gated) | needs cross-channel priors + cold-start model |

---

## 6. Revised 12-month plan — defensibility · revenue · learning (not volume)

Reordered so each quarter compounds the moat (proprietary, *causal* performance
data) and moves toward *margin*, while respecting that intelligence is data-gated.

### Q1 (months 1–3) — Earn trustworthy data; surface what exists
*Theme: don't model noise; make the existing data decision-grade.*
1. **Data-quality monitor** + run↔metrics join assertions + analytics-sync freshness checks. *(protects everything downstream)*
2. **Topic DB query layer**: winners view, graveyard avoid-list wired into discovery, "show me every X topic," clone-a-winner path. *(cheap, immediate operator value)*
3. **Unit-economics ledger**: realized RPM beside `cost_meter` → margin per video/topic.
4. **Experimentation harness v1** (design + first lever): one controlled variable (e.g. hook style) with holdout attribution. *(start the causal flywheel early — it needs runway)*
5. Research Brief: add `confidence_score` + audience-profile; make briefs explicitly reusable/cached.

### Q2 (months 4–6) — Channel Intelligence that's honest about confidence
1. **Channel DNA** (A–F per angle/format/title) — gated behind confidence thresholds; "insufficient data" is a first-class output.
2. **Channel Health Agent** (nightly Green/Yellow/Red on CTR/views/retention/cadence trends).
3. **Hook/Title intelligence** once impressions/retention data flows (de-risk Analytics API access in Q1).
4. Experimentation harness v2 — second lever (title/length); begin a verified "what actually works" ledger that replaces superstition.

### Q3 (months 7–9) — Monetization & the second channel
1. **MoneyWise intelligence** (ticker/earnings/sentiment/conviction) — proves the platform is multi-vertical (defensibility via repeatability).
2. **Benable attribution spike** (video→click→sale) with an explicit kill criterion; if tracking is feasible, build revenue-per-topic.
3. **Thumbnail intelligence** (close the `thumbnail_scores`→CTR loop).
4. Quota & spend governor generalized across all providers.

### Q4 (months 10–12) — Competitive edge & portfolio view
1. **Competitor Genome + emerging-trend detection** — cost-gated, hard-cached; opportunity (white-space) detection.
2. **Asset performance ranking** (retention impact per clip) once retention attribution exists.
3. **Portfolio/Business dashboard** — channels × revenue × growth × margin in one view.
4. **Channel Launch framework** built on cross-channel priors + the cold-start model.

**Deferred past 12 months (intentionally):** full autonomy / "autonomous media
company." Autonomy is the *output* of trustworthy data + causal learning + spend
governance + policy safety — earn those first; flipping on autonomy before them
multiplies mistakes and platform risk.

---

## 7. Revised priority order (and why it differs)

Operator's order → engineering's order, with the reasoning:

| # | Project | vs. operator | Why |
|---|---|---|---|
| 1 | Data-quality monitor + Topic DB views | new / raised | every "intelligence" is worthless on untrusted/illegible data; cheap |
| 2 | Experimentation harness | **new, top-tier** | the actual moat; correlation-only learning will learn superstitions |
| 3 | Unit-economics (RPM + margin) | new | turns "views" into "business"; aligns with revenue goal |
| 4 | Research Intelligence polish | =1 (kept high) | mostly built; finish confidence + reuse |
| 5 | Channel Intelligence (DNA/Health/Rec) | =2 | high value but data-gated; confidence-gated rollout |
| 6 | Analytics Intelligence (hook/title/thumb) | =3 | needs Analytics API + volume first |
| 7 | MoneyWise intelligence | raised from 7 | proves multi-vertical repeatability = defensibility |
| 8 | Benable attribution | =8 (spike) | highest-value revenue, hardest data; gate with kill criteria |
| 9 | Competitor Genome | lowered from 6 | cost-gated, noisy scraped signal; powerful but not foundational |
| 10 | Asset Intelligence | =9 | data-gated; depends on retention attribution |

**The moat thesis:** competitors can copy prompts, voices, and pipelines in a
weekend. What they cannot copy is a *causally-validated, per-channel performance
dataset* and the decision layer trained on it. Every quarter above is chosen to
widen that dataset's trustworthiness and turn it into margin — that, not video
count, is the defensible business.
