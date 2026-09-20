# Content Machine → Content Intelligence Platform

> **Class:** plan · **Status:** archived · **Reviewed:** 2026-09-20 · **Superseded by:** [master_plan.md](master_plan.md)

*Strategic roadmap. Author voice: founder + principal architect + media operator.*
*Thesis: generation is commoditizing; the moat is a proprietary, compounding performance-data flywheel.*

Last updated: 2026-06.

---

## 0. The core thesis (and what it implies)

You are right that script/voice/thumbnail/video generation collapse to a commodity within 12–24 months. When everyone can generate, the differentiator is **judgment**: knowing *what* to make, *why* it works, *why* it fails, and *what to make next* — per channel, backed by data nobody else has.

That judgment is not a feature. It is a **data asset that compounds**: every published video, joined to its structured features (topic, angle, hook, title structure, format, assets, post-time) and its real outcomes (views, CTR, retention, watch-time, revenue), becomes a labeled training example. Competitors cannot copy this because it is *your* history on *your* channels. This is the only asset on the list that gets stronger every day without you shipping new code.

**Implication that reframes the whole roadmap:** the four "intelligence" projects are not peers. They are an assembly line around one flywheel:

```
        ┌─────────────── RESEARCH INTELLIGENCE ───────────────┐
        │  signals → research brief → "what to make + why"     │
        ▼                                                      │
   GENERATION (commodity)                                      │
        │                                                      │
        ▼                                                      │
   PUBLISH + INSTRUMENT  ──►  FEATURE STORE (the substrate)    │
        │                         every video = features+IDs    │
        ▼                                                      │
   ANALYTICS INTELLIGENCE  ──►  outcomes joined to features    │
        │  "why it worked / failed"                            │
        ▼                                                      │
   CHANNEL INTELLIGENCE  ──►  persistent per-channel memory  ──┘
        "fraud beats recaps; rankings beat highlights"
```

The moat is the loop closing. Most of this roadmap is about **instrumenting and closing that loop**, then exploiting it.

---

## 1. The missing system nobody listed: the Feature Store / Outcome Schema

Before any "intelligence agent" can learn, every published video must be a **structured, versioned record** linking:

- **Inputs/features**: channel, topic, franchise/anchor, format (short/long), angle (recap/ranking/fraud/prediction), hook text + hook_score, title + title structure (number/question/callout/listicle), thumbnail style, asset IDs, post-time slot, brief_version, prompt_version.
- **Outcomes** (time-series, refreshed): impressions, CTR, avg-view-duration, retention curve, watch-time, subs gained, revenue, and derived labels (overperformer / underperformer vs channel baseline).
- **Provenance**: you already have `prompt_version` / `brief_version` on `content_runs` — extend to full lineage so a regression is traceable to the exact prompt/brief/signal mix.

You partly have this (`content_runs`, `publish_log`, `assets`, analytics sync). **What's missing is the explicit, normalized feature schema and the disciplined join between a content run and its evolving metrics.** Without it, "winning hooks" is a manual eyeball exercise; with it, every agent below becomes a query.

**This is the true 30-day foundation. It is unglamorous and it is the whole game.** Treat it as Priority #0.

---

## 2. The four projects — scored

For each: business value · engineering complexity · dependencies · risks · scalability · order.

### Priority #1 — Research Intelligence Engine  *(you already have the seed: `core/research_brief.py`)*

- **What changes**: upgrade the brief from "facts + evidence" to a decision object: **main narrative, controversy level (0–1), audience sentiment, debate angles, supporting evidence, suggested format, title direction, hook**. You already aggregate YouTube/Reddit/News/Trends/Sports/Odds and now live web search — this is mostly a synthesis-and-classification layer over existing signals (an LLM-judge + a few heuristics), not new infrastructure.
- **Business value**: HIGH and *immediate*. Improves the input quality of every single video the day it ships. Directly attacks your live failure modes (filler drift, recency gaps, wrong angle).
- **Engineering complexity**: MEDIUM. Synthesis prompt + typed schema + caching (you have brief caching already). Controversy/sentiment scoring is the only genuinely new modeling.
- **Dependencies**: existing signals; live web search (now live); Reddit intelligence (have). No DB migration required to start.
- **Risks**: LLM-judged fields (controversy/sentiment) are subjective — version them and validate against outcomes later. Don't let the brief hallucinate; it must cite signal provenance.
- **Scalability**: trivial; it's per-topic and cached.
- **Order**: **First.** Fastest ROI, lowest disruption, reuses everything.

### Priority #2 — Analytics Intelligence Agent

- **What changes**: scheduled job that joins outcomes ↔ features (the schema in §1) and emits a **weekly intelligence report**: winning/losing topics, winning hooks, winning title structures, optimal post windows — per channel, with confidence and sample size.
- **Business value**: HIGH, and it is the **moat engine** — it manufactures the labeled knowledge that becomes your data advantage.
- **Engineering complexity**: MEDIUM→HIGH. Start **rules/statistics-based** (group-by + baselines + significance gating), not ML. ML is premature until volume supports it.
- **Dependencies**: **the feature store (§1) is a hard prerequisite.** Also needs analytics sync (have) running reliably and enough publish volume.
- **Risks**: **correlation ≠ causation** (a "winning hook" may just have ridden a hot topic or a good thumbnail). Small-sample false positives. Mitigate with baselines, minimum-sample gates, and §6 experimentation.
- **Scalability**: batch/weekly; cheap. Graduates to a warehouse as volume grows.
- **Order**: **Second**, immediately after the schema. It is the highest-moat project but it *cannot precede instrumentation*.

### Priority #3 — Channel Intelligence System

- **What changes**: persistent **per-channel memory profile** ("TapIn: fraud > recaps; rankings > highlights; Team X over-indexes"). It is the *storage and application* layer for what the Analytics Agent learns — and it feeds back into Research (brief) and Scoring (`learned_weights`).
- **Business value**: HIGH, and it is where the moat becomes *operational* — the system starts making channel-aware decisions automatically.
- **Engineering complexity**: MEDIUM. A profile schema (structured "beliefs" with confidence + evidence pointers) + read paths into brief/scoring + write paths from the analytics agent. You already have `learned_weights` and channel profiles to build on.
- **Dependencies**: Analytics Agent (the source of beliefs) → so it trails #2.
- **Risks**: **stale or overfit beliefs** ("teamX always wins" until it doesn't). Beliefs need decay, confidence, and re-validation. Cross-channel leakage (gaming belief bleeding into finance).
- **Scalability**: linear in channels; profiles are small. Cross-channel **transfer learning** (priors from a mature channel seed a new one) becomes a *meta-moat* at 270 days.
- **Order**: **Third.** Strongest *applied* moat, but downstream of measurement.

### Priority #4 — Asset Intelligence

- **What changes**: track asset usage → performance (retention/CTR impact) → recommendation engine for backgrounds/clips.
- **Business value**: MEDIUM. Real, but second-order; asset choice moves retention less than topic/hook/title.
- **Engineering complexity**: MEDIUM (you have the `assets` table + post-render recording).
- **Dependencies**: feature store + **substantial publish volume** to separate asset effect from confounders.
- **Risks**: **the worst signal-to-noise of the four.** Asset effect is small and heavily confounded; you will chase noise if you build this early. Your own roadmap already marks asset effectiveness as volume-gated — correct.
- **Scalability**: fine.
- **Order**: **Delay (last).** Volume-gated; build only after the loop produces clean labels at volume.

---

## 3. The five required calls

1. **Strongest moat** → **Analytics Intelligence Agent + Channel Intelligence**, *sitting on the feature store*. Together they are the only components that produce a proprietary, compounding data asset. (If forced to name one: the **Analytics Agent**, because it *manufactures* the labeled history; Channel Intelligence is where that history is exploited.)
2. **Highest ROI / fastest** → **Research Intelligence Engine v2.** It improves every video immediately, reuses existing signals, needs no migration, and directly fixes current quality failures.
3. **Delay** → **Asset Intelligence.** Volume-gated, worst signal-to-noise, second-order impact. Building it early burns effort chasing confounded noise.
4. **Missing systems** (not on the stated roadmap):
   - **Feature store / outcome schema (§1)** — the substrate; everything depends on it.
   - **Experimentation harness (§6)** — deliberate variance to turn correlation into causation.
   - **Attribution / confounder layer** — separate topic vs time vs thumbnail effects.
   - **Cost & unit-economics observability (§5)** — per-video cost (LLM+TTS+Apify+search+render) vs revenue; you cannot do "monetization intelligence" without it.
   - **Human-in-the-loop capture** — operator accept/reject/edit decisions (e.g. the key-facts and variant picks) are free training signal; log them.
   - **Continuous policy/authenticity drift monitor** — extend Phase O from a pre-upload check to an ongoing watch as platform rules shift.
   - **Knowledge layer (Obsidian) as a first-class input** — see §7.
5. **Optimal evolution path** → **Instrument → Close the loop → Add deliberate variance → Monetize on top of proven memory → Platform-ize across brands.** Concretely: feature store → analytics agent → channel memory feeding brief+scoring → experimentation → Benable/monetization intelligence → cross-channel transfer learning → multi-brand control plane (out of the terminal, §8). *Do not* build monetization or asset intelligence before the measurement substrate exists.

---

## 4. 30 / 120 / 270-day plan

### 30 days — highest leverage, fastest ROI, minimal disruption
- **Feature store / outcome schema (Priority #0).** Normalize features on `content_runs`; harden the content-run ↔ analytics-metrics join; backfill what you can. *Unglamorous, foundational.*
- **Research Intelligence Engine v2.** Brief emits controversy/sentiment/debate/format/title-direction/hook. Wire into generation. Immediate quality lift.
- **Analytics report v1 (rules-based).** Even a weekly group-by with baselines and sample-size gating. Starts the habit and exposes schema gaps early.
- **Cost meter v0.** Log per-run cost of LLM+TTS+Apify+web-search+render. Cheap to add, informs everything later.

### 120 days — intelligence systems, multi-channel, learning, advantage
- **Analytics Intelligence Agent (proper).** Statistical winners/losers per channel with confidence; feeds Channel Intelligence.
- **Channel Intelligence profiles.** Persistent beliefs (with decay + confidence + evidence) feeding brief + `learned_weights`.
- **Experimentation harness.** Controlled hook/title/thumbnail variants with holdouts so attribution becomes causal, not correlational.
- **Multi-channel expansion.** Bring `moneywise` fully live; prove the loop replicates across domains.
- **Cost/observability dashboard.** Unit economics per channel and per content type.

### 270 days — moat, automation maturity, monetization, platform
- **Benable monetization intelligence (§9)** layered on proven performance memory.
- **Cross-channel transfer learning.** Mature-channel priors seed new channels — the meta-moat.
- **Asset Intelligence** (now volume permits clean labels).
- **Platform-ization.** The intelligence layer becomes a multi-brand control plane with a real app surface (§8). Automation maturity: the system proposes the week's slate, you approve.

---

## 5. Cost & unit-economics (the silent prerequisite for "monetization intelligence")

You cannot optimize monetization you cannot measure. Track per-video **fully-loaded cost** (LLM, TTS, Apify, web search, render compute, thumbnail) against **revenue** (AdSense + affiliate/Benable). This yields contribution margin per content unit and per channel — the number that decides which channels and content types to scale. It is cheap to instrument now and impossible to reconstruct later. Add it in the 30-day window at v0.

---

## 6. Experimentation: the difference between "we noticed" and "we know"

The Analytics Agent will find *correlations*. To earn a real moat you need *causation*, which requires **deliberate variance**: ship controlled variants (two hook styles, two title structures, same topic/time) and compare against a baseline. Without this you will repeatedly mistake "hot topic" for "good hook." A lightweight experiment registry (variant → hypothesis → outcome) turns your history from anecdotes into evidence. This is the single biggest force-multiplier on the data flywheel and it is currently absent.

---

## 7. Obsidian as a first-class knowledge layer (and the "pull from Obsidian vs local metadata" question)

**Now live:** `OBSIDIAN_VAULT_PATH=C:\Users\jonma\Documents\allopus`. Channel-scoped notes (`tapin/_facts.md`, frontmatter `channel:` + `tags:[facts]`) auto-pull topic-relevant bullets into the key-facts prompt as ground truth. Verified working.

**Should Content Machine pull config/metadata from Obsidian instead of local JSON?** Partly — draw the line by *who owns the data*:

- **Obsidian = the human knowledge layer.** Anything a *person* curates and reasons about in prose: current-fact sheets, channel playbooks ("fraud beats recaps"), banned/sensitive angles, evergreen context, narrative libraries, do/don't notes. Markdown is perfect here: fast to edit, versionable, linkable. **Yes, make this a first-class, expanding input** — it's a cheap, high-trust complement to scraped signals.
- **Postgres/JSON = the machine system-of-record.** Structured config (`channels.json`), analytics, performance memory, the feature store, job state. These need transactions, joins, and schema guarantees Obsidian can't give. **Do not move these into Obsidian.**

The elegant synthesis: **Channel Intelligence has two faces** — machine-learned beliefs (Postgres, from the Analytics Agent) and human-authored beliefs (Obsidian playbooks). The research brief reads both. Human knowledge seeds the system before you have data; machine knowledge takes over as data accrues; the human layer remains for nuance the metrics can't capture (taste, brand voice, legal sensitivity).

**To feed it well:** keep one `_facts.md` per channel updated with *current* ground truth (champions, rosters, prices), plus topical notes named for their subject (the matcher keys on filename/headings/bullets). Tag durable notes `tags:[facts, evergreen]`. **What I need from you:** keep those notes current — the system is only as fresh as the vault. Optional next step: a second vault folder convention for *playbook* notes (angles/voice) that feed the brief's strategy fields, separate from *facts* notes that feed ground truth.

---

## 8. Out of the terminal: what an app looks like

The terminal is right for *now* (operator-speed, scriptable). The intelligence platform, though, is a **dashboard product**. Evolution path, lowest-effort first:

1. **Local web control panel** (FastAPI + a light React/HTMX front end) reusing the existing pipeline as the backend. Same Python, new surface. Gives you: a discovery/approve queue, the weekly intelligence report rendered visually, channel profiles, the publish calendar, cost/margin charts.
2. **Multi-brand control plane.** One dashboard, N channels, per-channel intelligence, a unified "this week's recommended slate" you approve. This is the natural home for everything in §1–§6.
3. **Desktop wrapper** (Tauri/Electron) only if you want a installable app feel; the web panel covers 90%.

Sequence it for **270 days**, not now — the app is a *presentation* of the intelligence layer, so build the intelligence first. Architecturally, the win you can bank early: keep `core/` pipeline logic UI-agnostic (it largely is) so the eventual web layer is a thin adapter, not a rewrite.

---

## 9. Benable — verdict

**Recommendation: start as a recommendation/monetization *layer*, graduate to a *channel type*, eventually a *standalone affiliate-intelligence module* — in that order, gated on measurement.**

- **Now (layer):** affiliate-aware research briefs and an optional product slot in scripts on existing Sports/Gaming/AI channels. The funnel **Research → Product → Script → Video → Benable** is real and reuses your pipeline; the product-match step is the only new piece.
- **120–270d (channel type):** dedicated affiliate channels (Tech/AI buying guides, gaming gear, etc.) once unit economics (§5) prove conversion. Affiliate content has different success metrics (click→conversion, not just retention) — it *needs* the cost/revenue instrumentation to evaluate.
- **270d+ (affiliate-intelligence module):** a product-recommendation engine that learns which products/niches convert per audience — but only after the Analytics Agent exists to measure it. **Do not build affiliate intelligence before you can measure affiliate outcomes.**

Best near-term niches for Benable: **AI/Technology** (high-intent, high-commission, evergreen) and **Gaming gear** (clear products, engaged audience). Sports is harder (fewer natural product tie-ins outside betting, which carries policy risk).

---

## 10. One-paragraph executive summary

Generation is a commodity; your moat is a compounding, proprietary performance-data flywheel. The work, in order, is: **(0) instrument** — build the feature store / outcome schema that links every video to its features and results; **(1) feed it better** — Research Intelligence Engine v2 (fast ROI, ships now); **(2) learn from it** — Analytics Intelligence Agent (the moat engine, rules-based first); **(3) remember per channel** — Channel Intelligence profiles feeding briefs and scoring, fused with the Obsidian human-knowledge layer; **(4) prove causation** — an experimentation harness; **(5) monetize on top** — Benable as a layer first; **(6) platform-ize** — a multi-brand web control plane out of the terminal. Delay Asset Intelligence until volume yields clean labels. The day the loop closes is the day you stop being a content generator and start being a content-intelligence platform competitors cannot clone.
