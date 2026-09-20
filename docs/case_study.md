# Case Study — Content Intelligence Pipeline

> **Class:** snapshot · **Status:** frozen · **Reviewed:** 2026-09-20

*Independent project · Python · Multi-source opportunity engine*

---

## 1. Problem

Creators and niche media brands face a recurring decision: **which topics are worth acting on right now?** Manual research across YouTube, Reddit, trends, news, and competitor channels is slow, inconsistent, and hard to defend with data. Most tools either generate content without scoring opportunity, or show dashboards without a clear “make this next” recommendation.

## 2. Approach

Build an **intelligence-first pipeline** that:

1. Aggregates disparate signals into one normalized contract (`signal_contract`)
2. Scores topic variants with domain-weighted models plus outcome-based learning boosts
3. Produces a structured research brief (sentiment, controversy, angles, evidence)
4. Tracks competitor title/timing patterns on a daily cadence
5. Defers high-variance ML (e.g. CTR thumbnail models) until publish volume justifies it

The production tail (TTS, FFmpeg render, YouTube upload) exists for operator use but is **decoupled** from the analyst-facing output.

## 3. System

```
Topic → register_signals (12+ APIs, cache, quota)
     → topic_variants + composite_score (per-domain weights, learning boosts)
     → research_brief (RSS, Reddit, competitors, stats)
     → Intelligence Report (Markdown/JSON)
```

Key subsystems:

| Layer | Responsibility |
|-------|----------------|
| Signal registry | Parallel fetch, TTL cache, graceful degradation |
| Topic scorer | `infer_domain`, weight profiles, historical boosts |
| Research brief | LLM JSON brief with provenance version |
| Competitor sync | YouTube snapshot → angle hints |
| Persistence | Dual JSON/Postgres, Alembic migrations |
| Report | `core/intelligence_report.py` |

## 4. Sample output

A live report is generated with:

```powershell
py -m core.intelligence_report --topic "Cyclops Marvel Rivals" --channel tapin
```

A static example matching the report format: [samples/intelligence_report_example.md](samples/intelligence_report_example.md).

## 5. What I learned

**Generation before measurement.** Early composite scores and briefs ship value immediately; outcome-linked weight learning and CTR modeling wait until enough published videos exist. Building a CTR predictor on three uploads would optimize noise — the system gates those features explicitly.

**Niche config beats hard-coded domains.** UFC-specific script rules live in `script_brief.py`; scoring, briefs, and competitors are driven by `channels.json` profiles so the same engine demos for gaming, sports, or neutral verticals.

**Provenance is an analyst feature.** `brief_version` and `prompt_version` on runs are not bureaucracy — they enable attribution when comparing prompt or brief changes against performance later.

## 6. Evidence map (interview prep)

| Question | Answer in code |
|----------|----------------|
| How are signals weighted? | `topic_scorer.get_weights` + `LEARNED_PROFILES` + outcome boosts |
| How do you avoid learning from noise? | Volume-gated deferrals in `docs/roadmap.md`; no CTR model until data supports it |
| How is competitor intel used? | Daily `competitor_sync`; titles feed brief + report, not copy-paste |
| What would you add with more data? | Thumbnail→CTR correlation (`thumbnail_scores` table already migrated) |

## 7. Scope honesty

This is a **self-initiated engineering artifact**, not a funded product. It demonstrates analyst-track capability (aggregation, scoring, competitive intel, measurement hooks) built with ~1 year professional context — positioned for content/media/marketing **analyst** roles, not as a substitute for senior tenure.
