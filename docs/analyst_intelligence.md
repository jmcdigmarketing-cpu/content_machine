# Analyst intelligence layer

> **Class:** reference · **Status:** living · **Reviewed:** 2026-09-26

Decision-useful outputs beyond "what's hot right now."

## Levers (implemented)

| Lever | Module | Report section |
|-------|--------|----------------|
| **Temporal trajectory** | `core/topic_trajectory.py` | Rising / peaking / decaying; velocity pts/hr |
| **Cross-source corroboration** | `apis/signal_corroboration.py` | Confidence % + source count; optional score adjust |
| **Opportunity window** | `core/opportunity_window.py` | open / closing / closed from demand vs competitor overlap |
| **Explainability** | `core/analyst_explain.py` | Why now, why this, contrarian hook, signals fired |
| **Self-measurement** | `core/analyst_accuracy.py` | Hit-rate backtest (volume-gated until ≥5 publishes w/ metrics) |

Snapshots append to `data/topic_trajectory.json` on each intelligence report. Re-run the same topic over hours/days to unlock trajectory.

## Env

```env
CORROBORATION_BOOST=true          # ±~4 pts from corroboration confidence (default on)
CORROBORATION_MIN_SCORE=12        # Min signal score to count as corroborating
ANALYST_FLAG_THRESHOLD=60         # Score floor for "flagged opportunity" in accuracy report
WIKIPEDIA_PAGEVIEWS_ENABLED=true  # Leading public-interest signal (free)
```

## Portfolio artifacts to build next

1. **Live demo** — FastAPI page: topic in → `intelligence_report` out. *Parked* with #147
   (no operator need has appeared; see [master_plan.md](master_plan.md) "Parked").
2. **Backtest PDF** — once `YOUTUBE_ANALYTICS_SYNC` fills `publish_log.metrics_json`.
3. **Competitor-gap matrix** — visualize `opportunity_window` across a topic batch.

## Data sources roadmap (by unlock)

| Priority | Source | Why |
|----------|--------|-----|
| Done | Wikipedia pageviews | Leading indicator, free |
| Done | Twitch viewership (`twitch`, `apis/twitch_api.py`) + IGDB (`igdb`) | Gaming demand — wired; both returned nothing on the last 38 live runs (#810/#811), so wiring is not yet value |
| Not started | GDELT | Narrative/event scale |
| Catalog-only | YouTube comment mining (`youtube_comments`, `enabled: false`) | Angle + sentiment; paid Apify actor, off with the other retired actors |
| Later | PAA / breakout queries | Question-shaped angles |

See [adding_a_data_source.md](adding_a_data_source.md) for the extension recipe.

## Genre expansion

New genre = weight profile + RSS feeds + channel profile + optional `script_brief` matrix. Sequence by **data availability × paying audience**. Depth in combat-sports / gaming / sports beats fifteen shallow verticals.
