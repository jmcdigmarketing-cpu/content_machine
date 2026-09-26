# Next level — where this can realistically go

> **Class:** snapshot · **Status:** frozen · **Reviewed:** 2026-09-25

**Written:** 2026-08-30 · **HEAD:** `73671ce`

Companion to [idea_quality_diagnosis.md](idea_quality_diagnosis.md), which answers *why
the output is bad*. This answers *what to do with the thing once it isn't*.

The operator asked for options both inside and outside the roadmap, and explicitly
opened the **private/local/single-operator** constraint ([roadmap.md](roadmap.md)) for
re-examination. So §5 breaks it. §1–§4 do not.

---

## 1. The honest read

Strip the intelligence vocabulary and this is what exists:

| | measured |
|---|---|
| runs recorded | 36 dossiers, 28 traces |
| published + measured | ~10 |
| best-bet hit rate | **40%** (4 of 10 beat channel average) |
| composite score vs engagement | **uncorrelated** — the lowest-scored topic beat two 100.0s |
| marginal cost per video | **$0.31**, of which 91% is TTS |
| operator time per run | **25.6 min at prompts**, 5.0 min machine (live-run 71 — which produced no video) |
| learned priors | `n=1` and `n=5` in `_machine-beliefs.md` |

That is not a failing project. It is a **well-engineered pipeline with a thin,
untrustworthy evidence layer bolted to a decision layer that pretends the evidence is
thick.** Every "intelligence" surface downstream inherits that.

The single most important number above is the operator's 25.6 minutes. This is not a
compute-bound system, a cost-bound system, or a model-bound system. It is bound by one
person's attention, and that is what any "next level" has to move.

---

## 2. Three contradictions to settle first

These are cheap to fix and they block coherent planning, because each makes an opposite
argument live in the docs at the same time.

**(a) Is generation quality a lever or not?**
[decisions.md](decisions.md) §17 (2026-07-07) explicitly reverses `operating_plan.md`
§8: *"Generation quality is now a competitive lever."* But
[strategy_h2_2026.md](strategy_h2_2026.md) §9 still reads: *"**Don't add more generation
features.** Faceless script→TTS→render is commodity; more of it doesn't widen the
moat."* Both are on disk, unmarked. **§17 is newer and is the operator's call — mark §9
superseded.**

**(b) Is this a product or a private tool?**
[positioning.md](positioning.md) (micro-SaaS wedges, a freelance ladder, a portfolio
artifact) and [vision.md](vision.md) (*"operate media businesses"*, a ten-phase
intelligence ladder to an autonomous media company) were **retired in substance** by the
2026-08-29 private/local constraint — which retired #143, #468, #467 outright — but
neither doc carries a supersession header. A future session will read them as current.
**Head both files, or fold their still-live parts into `vision.md` and archive the
rest.**

**(c) Does `12/12 claims backed` mean anything?**
§25 documents that the claim rewriter converts unsupported assertions into hedged ones
and the re-check then passes — and explicitly leaves *"what to do about that"* open.
It has now been open through runs 58, 73 and 75, and it is the reason run 58 shipped
four consecutive weasel sentences at 30% support. **Decide it.** The cheapest honest
answer is to report both numbers on the report card and let the grade fall.

Also stale and worth one commit: `vision.md:156` lists *"Evaluation set for prompt/model
changes"* as a **missing** system. It shipped — `core/prompt_evals.py` +
`config/prompt_evals.json`. What is actually missing is the LLM-judge layer and the
frozen regression corpus (#350).

---

## 3. The real constraint, and the only three ways past it

[strategy_h2_2026.md](strategy_h2_2026.md) §2 names the trap precisely: the learning loop
is **rate-limited by our own compliance layer**. Volume-gated analytics need n≥15+
published per dimension; the cadence guardrail caps volume deliberately; so the moat
waits on something the project has chosen not to do.

There are exactly three ways out, and only three:

1. **Extract more per publish** (the recorded reframe, and correct). More measured
   dimensions per video, honest confidence, a hold-out set. Levers that need no volume:
   `core/prompt_evals.py` (built), **#350** frozen regression corpus in CI, **#560**
   hold-out set, **#561** loop accuracy printed beside the loop's own advice,
   **#351** confidence intervals.
2. **Raise the ceiling on what the operator will publish.** Cadence isn't the binding
   cap today — *willingness* is. 36 runs produced ~10 publishes. If the output were
   reliably good, the same guardrail would allow meaningfully more. **This is why the
   quality work in the diagnosis is strategy, not polish.**
3. **Multiply samples per script without multiplying scripts** — i.e. publish the same
   asset to more than one surface. That breaks the private/local constraint's Phase-M
   parking; see §5.

Everything else is decoration on n=10.

---

## 4. Horizon 1 and 2 — inside the current constraint

### H1 · Now → ~3 months: make one video genuinely good, and prove it

Not a new subsystem. Four things, in this order:

1. **The diagnosis fixes** ([idea_quality_diagnosis.md](idea_quality_diagnosis.md) §8) —
   selection tie, playbook ranking, intent as a first-class dimension (#533 expanded),
   option 5's idea made authoritative, gate agreement extended.
2. **Make the report card honest.** Add length (#645 — yes, it changes the meaning of
   historical grades; version the rubric and say so). Report the pre-repair claim number
   beside the post-repair one (§25). Read the title (run 71 shipped a wrong one under an
   A 91). A grade that cannot be trusted is worse than no grade, because it ends the
   conversation.
3. **The Craft wave already in [roadmap.md](roadmap.md).** Video craft is the right call
   — contrast, caption balancing, motion presets, font pairing, end cards. It is burned
   into every video and no toolkit change touches it. Add the two config-only loopholes
   that make shipped features real: **#642** empty voice pool (the June *"same voice
   every video"* complaint was never actually fixed) and **#641** six unreachable ANSI
   themes.
4. **Extend the eval corpus to ~15–20 real ideas with intent labels.** This is what makes
   3 provable instead of vibes, and it is lever 1 from §3 at the same time.

**Realistic outcome:** the operator stops rejecting drafts for reasons the machine can't
see, and publish rate rises because the drafts are worth publishing — not because a
guardrail moved.

### H2 · ~3 → 9 months: get the operator off the critical path

Stage 0 Seams is the next wave and it is correctly placed — the `ask()`/`emit()` seam is
what makes everything after it cheap, and `main.py`'s 15 blocking `input()` calls are
why two `Ctrl+C`s destroyed whole runs in run 73.

The strategically important thing in the desktop programme is not the window. It is
**[strategy_h2_2026.md](strategy_h2_2026.md) §8's async approval surface** — *"review a
queued draft from a phone — not full autonomy, which the authenticity posture doesn't
want anyway."* That is the single highest-leverage item in the entire backlog, because
it attacks the 25.6-minute number directly and it does not require relaxing any
compliance position.

Pair it with **`ops batch-drafts`** (already built) so the machine drafts N ideas
unattended and the operator's role compresses to judgement rather than transcription.

Add, in the same window: **#536** an editable outline step before prose, and **#537**
per-section regeneration. Both convert "regenerate the whole thing and re-bill it" into
"fix the hook" — which is what the operator actually wants at review time.

**Realistic outcome:** run time drops from ~30 minutes of attention to a handful of
judgement calls, publish rate rises on throughput rather than quality, and — for the
first time — n grows fast enough that the analytics layer is worth building.

---

## 5. Horizon 3 — the options that break the private/local constraint

The constraint retired real work (#143 Web OS, #468 standalone fact engine, #467 second
seat, Phase M multi-platform). It was a good call: it converted an unbounded product
backlog into a finite tool backlog. Most of it should stand. But three of its
consequences are worth re-pricing, and one is worth reversing.

### 5a. Multi-platform publishing (Phase M) — **the one worth reversing**

Currently parked. It is the only lever that increases measurement samples *without*
increasing scripts, cost, or compliance exposure per script — the asset is already
rendered vertical; TikTok and Reels are a publish surface, not a production line.

- **What it costs:** a publish adapter per platform, per-platform policy/disclosure
  handling ([policy_incident_runbook.md](policy_incident_runbook.md) already exists), and
  metrics ingestion per platform. Real, but bounded — it is the same shape as the
  existing YouTube publisher.
- **What it buys:** 3× the outcome samples per publish, and cross-platform variance is
  itself signal (a hook that works on Shorts and dies on Reels says something a single
  platform cannot). It attacks the volume paradox from the only side that doesn't
  require publishing more.
- **What it risks:** it is also the fastest way to triple the blast radius of a bad
  script. **Do it after H1, not before.**

This does not break "private, local, single-operator" at all — the *tool* stays private.
It only un-parks a publishing target. That is the cheapest constraint break available and
it should be re-priced now.

### 5b. A second channel, for statistics rather than reach

`moneywise` exists in config and has barely run. Cross-channel pooling
([strategy_h2_2026.md](strategy_h2_2026.md) §2) is the recorded answer to thin per-channel
n, and it needs a real second channel to pool. The honest framing: a second channel is a
**statistical instrument** before it is a business. Its value is that it doubles the
dimensions the recommenders can learn from and gives the cold-start prior something to
transfer from ([vision.md](vision.md) §3.6 flags cold-start as unplanned).

Cost: operator attention, which §4's H2 is what frees up. **Sequence it after H2, not
before** — a second channel run by hand doubles the bottleneck rather than the data.

### 5c. Publishing the tool — **still no, and for better reasons than before**

`positioning.md`'s micro-SaaS wedge assumed the moat was the intelligence layer. The
evidence now says the intelligence layer is the *weakest* part (40% hit rate,
uncorrelated scores, n=1 priors). Selling it would be selling the part that does not yet
work. The parts that genuinely lead —
[tooling_landscape.md](tooling_landscape.md): *"**Grounding + closed loop together** —
the one combination no tool in this scan ships"* — are also the parts that are worthless
without the operator's own vault, footage, and history.

**Keep it retired.** Revisit only if the loop ever demonstrates predictive accuracy on a
hold-out set (#560) — that, not feature count, is the thing that would be worth selling.

### 5d. What §17 actually licenses on the generation side

§17 (*generation quality is a competitive lever; "all's fair, competition is a copycat
game"*) is live and un-acted-on. [video_creation_stack.md](video_creation_stack.md)
lists twelve provider slots with AI video generation named as the *biggest gap*.

The honest sequencing note: **do not open the AI-video slot before H1.** A better-looking
video built on an arbitrary angle and a hedged script is a more expensive version of the
current problem. The slot that pays first is the cheap one already identified — TTS
(91% of cost) and word-level alignment — followed by owned gameplay over stock
(decisions §26, #416 scene-beat cuts).

---

## 6. What not to do

- **Don't build volume-gated analytics before the volume exists.**
  ([strategy_h2_2026.md](strategy_h2_2026.md) §9 — this clause is still correct even though
  its "no generation features" neighbour isn't.)
- **Don't add a second scoring system.** The failure mode this repo keeps hitting is *a
  check measuring the wrong thing, then reporting clean* (run-73 post-mortem). Another
  scorer is another thing to disagree with the first three.
- **Don't add signal sources to fix idea quality.** The diagnosis shows the ideas are bad
  at the angle and selection stage, not the evidence stage. More sources would have made
  run 71's corpus of 1990s Wolverine games larger.
- **Don't trust `_machine-beliefs.md` or `playbook.md` until the loop confirms them.**
  One of those beliefs — *"number title style under-performs"* — was learned from a
  leaked discovery menu index (`"2. "`) surviving into published titles. The machine
  learned a lesson about numbers from a bug about numbering.

---

## 7. The realistic 12-month picture

Not the autonomous media company in `vision.md`. This:

> A private Windows application where the operator types or pastes an idea, sees five
> genuinely *different* angles scored on something that predicts something, picks one or
> keeps their own, pastes facts into a real text area, watches five gates run as buttons
> rather than console spam, approves from their phone, and publishes to three surfaces
> from one render — with a grade they believe, on a corpus large enough that the
> recommenders can finally say something with an interval attached.

That is reachable from here. It requires no new intelligence layer, no model the project
doesn't already route to, and no revenue assumption. It requires the quality work in H1,
the seams and async approval in H2, and one parked decision re-priced in §5a.

The thing standing between the project and that picture is not ambition. It is that four
of its most load-bearing numbers — the composite score, the report card, the claim
support rate, and the playbook — are currently measuring the wrong thing and reporting
clean.

Fix the measurements and the rest of this roadmap becomes ordinary work.
