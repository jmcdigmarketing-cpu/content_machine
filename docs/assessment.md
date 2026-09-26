# Content Machine — strengths, weaknesses & fixes

> **Class:** snapshot · **Status:** frozen · **Reviewed:** 2026-09-20

Honest assessment of the system as of 2026-06. Scored 1–5 per dimension with
evidence from the code and from live runs observed this month. The goal is a
prioritised fix list, not a victory lap.

## Scorecard

| Dimension | Score | One-line verdict |
|---|---|---|
| Learning loop | 4 / 5 | The differentiator — three analytics-driven recommenders |
| Compliance & monetisation | 4 / 5 | Ahead of the market on the 2026 authenticity policy |
| Architecture & maintainability | 4 / 5 | Real tooling, 363 tests, green CI, modular signals |
| Content quality | 3.5 / 5 | Good hooks/prose; visuals and stance still thin |
| Scalability | 3.5 / 5 | Multi-channel works; multi-platform deferred |
| Competitive position | 3.5 / 5 | Unique full loop; behind on captions + reach |
| Reliability & ops | 2.5 / 5 | External-API fragility is the operational tax |
| Grounding & accuracy | 2.5 / 5 | Recency is the Achilles heel |

**Overall: ~3.4 / 5** — a genuinely differentiated engine with two soft spots
(recency grounding, external-API reliability) that cap its current ceiling.

---

## Strengths (evidence)

1. **Closed analytics learning loop.** Best-bet (topic), recommended length, and
   recommended post-time all learn from real `engaged_rate` and share one
   pattern (`core/best_bet.py`, `core/length_recommender.py`,
   `analytics/post_timing.py`). No single competitor (vidIQ decides, TubeBuddy
   optimises, OpusClip clips) runs the whole loop.
2. **Compliance layer is early and real.** Authenticity self-check, AI
   disclosure, cadence guardrail, outlier surface (`core/authenticity.py`,
   `core/description_extras.py`, `core/cadence.py`). The Jul-2025 / Jan-2026
   "inauthentic content" enforcement makes this existential, and most rivals
   ignore it.
3. **Engineering hygiene.** `pyproject.toml`, ruff + mypy + pre-commit, CI on
   3.11, 363 tests, repository pattern, Alembic, a signal registry. Above a lot
   of shipped "production" code.
4. **Multi-channel domain architecture.** A finance channel (MoneyWise) was
   added almost entirely from config + domain weights, alongside TapIn.
5. **Research / anti-hallucination spine.** Verified-facts split, thin-facts
   mode, gaming + (now) sports anti-hallucination rules — strong *when the
   signals deliver facts*.

## Weaknesses (evidence)

1. **Recency / event grounding — the #1 content risk.** A topic about a just-
   happened event (UFC "Freedom 250", 6/14) produced "Topuria, the featherweight
   champion" and invented opponents, because the event is past the LLM's cutoff
   *and* the signals returned no results. The system has no "this looks newer
   than my facts" guard.
2. **External-API fragility — the #1 ops cost.** In one month we hit: Apify
   `set_cache` crash, 201 handling, actor 404 (`bebity`), `sortVideosBy` 400,
   `scrape_enabled` import error, Wikipedia 429, IGDB 400, SEC EDGAR 500,
   YouTube RSS 404. Many brittle dependencies, and failures degrade quietly.
3. **Signal relevance noise.** RAWG matched the *game* "UFC 4" and
   "TransOcean 2: Rivals" for UFC/Marvel-Rivals topics; odds matched CFL; sports
   matched a cricket club. Wrong-entity matches dilute the facts block.
4. **Visual / caption depth.** Captions are now proportional but not word-level
   animated; background is one looped clip. Faceless long-form would look thin.
5. **Volume-starved learning.** Recommenders fire on 2–3 samples (e.g. "ufc
   averages 30.6% across 2 videos"). Confidence isn't surfaced, so early signals
   look more authoritative than they are.

---

## Prioritised fixes

Ordered by impact ÷ effort. `[S]` small, `[M]` medium, `[L]` large.

### Now (high impact)
1. **Recency grounding for dated events** `[M]` — enable Tapology for UFC
   (`TAPOLOGY_SCRAPE_ENABLED=true`); weight fresh RSS/Reddit *result* items into
   the facts block; add an operator "key facts" prompt when a topic names a
   dated event so the script is grounded in supplied facts, not memory. This is
   the single biggest quality lever.
2. **Signal relevance gating** `[S]` — require the matched entity to actually
   appear in the topic (RAWG "UFC 4" must not satisfy "UFC 250"); a token/fuzzy
   guard before a signal contributes facts.
3. **Confidence surfacing** `[S]` — show sample size / a confidence tag on each
   recommender; raise the min-samples floor so 2-video averages read as tentative.

### Next (quality + reach)
4. **Word-level animated captions** `[M]` — Whisper/ElevenLabs timestamps →
   karaoke-style highlight (Phase Q next). Biggest single visual upgrade.
5. **Scene-matched b-roll** `[M]` — pick stock/asset per script beat instead of
   one looped clip.
6. **Observability + cost dashboard** `[M]` — structured run trace and per-run
   API spend (OpenAI / Apify / YouTube units). We only caught the Apify
   credit-burn by reading raw logs; this should be a surfaced metric.

### Later (scale)
7. **Long-form deep-dive mode** `[M]` — weekly Extended video on a well-grounded
   topic; pairs with clip-from-source for Shorts spin-offs. Launch on MoneyWise
   (high CPM).
8. **Multi-platform publishing** `[L]` — TikTok publisher (keys present,
   unimplemented), then Reels. Deferred until captions + grounding are solid.
9. **Tighten the mypy baseline + retire broad excepts** `[M]` — ~94 mypy errors
   and ~18 silent `except Exception` remain as tracked debt.

---

## The one-paragraph take

Content Machine's moat is real: it's the only pipeline that decides, *researches
with verified facts*, generates, publishes, and learns — with a compliance layer
built for the 2026 policy reality. Its ceiling is held down by two things that
are fixable: it doesn't yet know when an event is newer than its facts (so it
guesses), and it leans on a lot of brittle third-party APIs that fail quietly.
Fix recency grounding and add observability, and this moves from "impressive
prototype that occasionally embarrasses itself on fresh topics" to "dependable
daily operator."

---

## Addendum — 2026-08-20 (keep the June body)

The June scorecard is a snapshot. What changed by 20 Aug, without rescoring from
scratch:

**Shipped against the June weaknesses.** Operator key facts + vault + claim
verifier (recency is still a risk, but the operator now has a paste path).
Captions are word-timed and **retexted from the script** (fighter names spell
correctly). `ops reliability` + O11/O12 + fail-open-made-visible (the quiet API
failures that scored reliability 2.5/5 now report as failures). Post-render cost
reaches the ledger: a rendered run is **~$0.31 metered**, TTS **~91%**, allocated
nearer **$1/video** at 21/90 Creator-plan utilisation. Semantic authenticity
(paraphrase arm) is default-on, warn-never-block. 1,433+ tests, not 363.

**Ceiling that remains.** Volume-starved learning (10 measured run-linked videos
vs a 15-sample predictor gate). TTS still dominates real-world cost until the
operator judges Piper. 2026 inauthentic-content policy is still existential —
substance over volume. Pickup: [roadmap.md](roadmap.md) recommended next 5.
Honest session state: [handoff_synopsis.md](handoff_synopsis.md). Audit:
[audit.md](audit_2026-08.md).

## Addendum — 2026-08-30 (idea quality)

The June scorecard rated **Content quality 3.5/5** on *"good hooks/prose; visuals and
stance still thin."* A code-level trace of the "why are the ideas bad" question found the
opposite failure: **stance is not thin, it is compulsory**, and three of the numbers this
scorecard trusts are measuring the wrong thing and reporting clean.

- The **composite score does not rank** — all five angles scored 100.0 on run 71 and
  92.14 on run 72, so `Enter = best` is arbitrary — and does not predict engagement
  (hit rate 40%; the lowest-scored topic beat two 100.0s).
- The **report card is blind** to what the operator reacts to: A 91 on a factually wrong
  title, A 87 on a 277-word script with a hook of 61, authenticity 100/100 on a phrase
  its own linter flagged.
- **Claim support is bought with hedging**, not evidence (decisions §25; wave 26 prints density and lets the grade fall, render gate unchanged).

Full trace and the fix order: [idea_quality_diagnosis.md](idea_quality_diagnosis.md).
Direction: [strategy_next_level.md](strategy_next_level.md).

## Addendum - 2026-09-20 (measured, not estimated)

The June scorecard and the 2026-08-30 addendum were written from code reading. There are now 38
run traces on disk, and they settle three of the open arguments. Full tables and the ideas that
follow: [engine_upgrades.md](engine_upgrades.md).

- **Content quality 3.5/5 is unmeasurable as scored.** Authenticity was **100/100 on 22 of 38
  runs** while carrying **28%** of the report card. Wave 26 (#804) made the numeric scorer
  continuous (`GRADE_VERSION` v4); the gate is still the binary sum. Hook (median 78, range
  55-93) remains the component with the most room. #50 is still the next input.
- **Cost is one line item.** TTS is **$6.09 of $7.27** across 38 runs - **84%** - and the LLM is
  **$0.0071 per run**. Wave 26 (#809) defaulted the TTS cache on; `ops reliability` now prints
  the hit line (`TTS cache: on, 0 file(s), 0/3 hits (0%)` until a live synth writes it). Nothing
  about token spend is worth optimising.
- **Reliability 2.5/5 understates the waste.** Six signals - `trendingnow`, `igdb`, `steam`,
  `tapology`, `stats_context`, `tvmaze`, `tmdb` - have returned nothing on every run that called
  them, inside a **58.7 s median** discovery (#810, #811).
