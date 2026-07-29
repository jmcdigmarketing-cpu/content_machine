# Strategy & brainstorm — 2026 H2

*A wide planning pass at the Pillars 1–7 milestone. Tactical checklist stays in
[roadmap.md](roadmap.md); the 12-month north star stays in [vision.md](vision.md).
This is the layer between them: **what to optimize for next, and why.***

> **External claims** (platform API rules) are from a **July-2026 scan — rules drift**,
> with sources inline. Repo claims cite verified paths.
>
> **Note:** `code_audit_2026-07.md` and `llm_provider_strategy.md` are linked below and
> land via PRs **#28** and **#26** — those links resolve once those PRs merge.

---

## 1. Where we are

Pillars 1–7 are shipped: run ledger, video grading, Fact Engine 2.0, the Obsidian
knowledge OS, provider seams, the video-creation provider layer, and self-improving
skills. ~56k LOC, ~1,139 test functions, ruff clean, secrets clean, test isolation
fully compliant.

Three PRs are open from the 2026-07-29 session: the LLM provider strategy doc, the
domain-gated `SEMANTIC_TRADE_VALIDATION` change, and a holistic code audit
([code_audit_2026-07.md](code_audit_2026-07.md)) whose live findings are folded into
§4 below.

**The machine works.** The open questions are no longer "can it produce a video" but
"what compounds," "what's actually blocked," and "what should we refuse to build."

---

## 2. The volume paradox — and the reframe

Read the roadmap closely and a contradiction appears:

- A large block of work is explicitly **volume-gated** — *"do not build until publish
  volume supports correlations"* (thumbnail→CTR, prompt-performance analysis, asset
  effectiveness, full attribution).
- But **Phase O deliberately caps volume**. The cadence guardrail
  (`MAX_VIDEOS_PER_WEEK`) and the authenticity/variation checks exist precisely
  *because* the 2026 policy environment punishes volume-over-substance.

So the learning loop — the moat — is **rate-limited by our own compliance layer**, and
waiting for volume means waiting on something we've chosen not to do.

### The reframe: optimize information per publish, not publishes

If we can't publish much more, extract much more from each publish. Three levers,
all of which already have scaffolding:

1. **Richer instrumentation per run** — the Pillar 1 run ledger already persists
   traces and quality scores. Every additional *measured* dimension per video is worth
   more than another video, because it multiplies against the whole history.
2. **Within-publish experiments** — the title-pattern A/B loop already attributes
   engagement to *structural* features rather than needing head-to-head publishes.
   That pattern generalizes: hook archetype, length preset, post slot, thumbnail
   style. One video can inform several hypotheses.
3. **Cross-channel pooling** — `tapin` and `moneywise` are separate channels but share
   an architecture. Learnings that are *structural* (hook shapes, pacing, post-time
   physics) should pool across channels; only domain-specific effects should stay
   siloed. Two channels at 5/week is a 10/week learning rate if pooled correctly.

**This is the strategic thesis for H2: learn more per video instead of making more
videos.** It respects the compliance moat instead of fighting it.

---

## 3. Direction: both futures, sequenced

There are two plausible futures for this codebase, and it already supports both:

| | **Media operator** | **Intelligence product** |
|---|---|---|
| Output | published videos | research/analyst reports |
| Needs | publish volume | depth + grounding |
| Ceiling | capped by policy/cadence | uncapped by platform rules |
| Already built | the full pipeline | `core/intelligence_report.py`, [positioning.md](positioning.md), [case_study.md](case_study.md) |

**Chosen direction (operator, 2026-07): both, sequenced.**
Near term, raise **quality + reliability** so the volume we *do* publish compounds
properly (§2). Long term, build out the **intelligence/analyst line** as the depth play
that doesn't need volume — and which leverages the grounding moat directly.

The two aren't in tension: the intelligence layer is *upstream* of the video. Every
improvement to grounding and research serves both.

---

## 4. Short term (next weeks)

Concrete, mostly small, high leverage. The first three come out of
[code_audit_2026-07.md](code_audit_2026-07.md).

1. **Merge the three open PRs** (#26 docs, #27 trade validation, #28 audit).
2. **Centralize the free-mode guard** *(audit #2)* — `FREE_MODE_STRICT` is
   re-implemented at three paid seams with no shared helper, so a *new* paid call site
   opts out of Free mode silently. One helper + a test that every paid seam consults it
   turns a convention into a guarantee. `[S]`
3. **Narrow `safe_infer_domain`'s catch** *(audit #3)* — it currently returns
   `"neutral"` on *any* exception, so an import/DB hiccup silently re-opens tag
   pollution (UFC tags on gaming topics) with no warning. At minimum log it. `[S]`
4. **Give the router an image path** *(audit #1)* — the only vision capability is
   pinned to the legacy OpenAI client, outside the router, outside the cost meter, and
   **currently inactive** because that key is off. Claude (already paid) does vision.
   One change restores the capability, meters it, closes the guard gap, and unblocks
   the Pillar-2 rendered-video item. `[M]`
5. **Refresh the Anthropic default model IDs** — `_DEFAULT_MODELS` still pins
   `claude-sonnet-4-…` while the Claude 5 family exists, on the live paid provider.
   Config-level; *evaluate, don't blind-bump*. `[S]`
6. **`ops reddit-setup` guided flow** — see §6. `[S]`
7. **A `[test]` extra** so the logic suite runs without the full media stack — 90 of
   148 collection errors are just `sqlalchemy`. Dev velocity + faster CI. `[S–M]`

## 5. Medium term (1–3 months)

- **Pillar-2 rendered-video review** — needs #4 above first; then a real
  quality gate before publish rather than heuristics.
- **`youtube_comments` signal** (templated in the Apify catalog, unwired) — audience
  language is the cheapest hook research available, and it feeds §2's "more per
  publish."
- **Cross-channel learning pooling** (§2 lever 3) — decide what generalizes vs what
  stays domain-siloed; the recommenders already carry domain awareness.
- **MoneyWise depth wave** — earnings calendar, ticker watchlist, finance brief
  sections. Higher CPM than gaming; the second channel is where pooling gets tested.
- **`core/ui.py` split** — 1,420 LOC and accelerating (796 → 951 → 1,420 across three
  audits). Mechanical, but do it before any new surface lands on it.
- **Cost/quota dashboard (O9)** + governor follow-ups — per-run spend visible.
- **Recommender backtest** — the moment sample sizes allow; this is the honest test of
  whether the loop actually works.

## 6. The two named blockers — verified reality

### 6.1 Reddit setup — irreducible, so fix the UX instead
`apis/free_backends.py` documents it plainly: **keyless `www.reddit.com` JSON endpoints
are 403-blocked for bots.** So the free "script app" OAuth
(`REDDIT_CLIENT_ID`/`REDDIT_CLIENT_SECRET`) is the *only* $0 path — there is no clever
way around it, and the setup is a genuine one-time ~2-minute cost.

**Therefore the fix is UX, not elimination:** an `ops reddit-setup` command that prints
the exact click-path (reddit.com/prefs/apps → script app → copy id/secret), accepts the
values, **validates them with a live token call**, and writes them; plus a clear
`free-doctor` line when they're missing. Turns undocumented friction into a two-minute
guided step. *(The paid Apify reddit backend still exists as the alternative, but is
currently off.)*

### 6.2 Multi-platform — the eligibility concern is well-founded
**Decision: Phase M stays parked.** Recorded here so that if it's ever revisited, it
starts from facts rather than another research round.

**TikTok** — there *is* an unblocked path, but it isn't full automation:
- **Upload to Inbox / Creator's Draft** needs **no audit**. The video lands in the
  creator's TikTok drafts; a human publishes it (and can add native sounds/effects
  first). [source](https://developers.tiktok.com/doc/content-posting-api-get-started)
- **Direct Post** requires an audit — 2–4 weeks, multiple review rounds — and
  **unaudited Direct Post is private-only**, i.e. useless. Unaudited clients are also
  capped at ~5 posting users / 24h with accounts private at post time.
  [source](https://www.netrows.com/blog/tiktok-content-posting-api-guide-2026)

**Instagram** — heavier: an IG **Business/Creator** account **linked to a Facebook
Page**, a Meta developer app, and app review for `instagram_business_basic` +
`instagram_business_content_publish` (2–4 weeks; the review screencast must show a full
interactive connect-and-publish journey). Dev mode allows ≤25 test users — whether the
operator's own account qualifies **without** full review is **unverified**.
[source](https://postproxy.dev/blog/post-to-instagram-via-api/)

**The structural friction, stated plainly:** both audit processes are designed for
*interactive, multi-tenant apps* — show the creator's username and avatar before
posting, offer a privacy picker, demo an account-connect flow. A **single-operator
headless pipeline does not have that shape**. The concern about eligibility is a
correct read of the rules, not excessive caution.

**If revisited, the honest sequencing** would be: TikTok inbox mode first (no audit, no
eligibility risk, human-in-the-loop publish — which also fits the Phase-O authenticity
posture), then *maybe* verify the Instagram dev-mode question. Direct Post and full
Meta app review are the parts worth refusing.

## 7. Long term (6–12 months)

- **The intelligence / analyst product line** — the depth play. Scheduled per-topic or
  per-vertical reports delivered as a page or email, built on the existing
  `core/intelligence_report.py`. Revenue that doesn't depend on publish volume *or* on
  YouTube's policy weather. This is the hedge, and it's already half-built.
- **Feature store + causal attribution** — the long-identified "highest-leverage gap."
  Per [operating_plan.md](operating_plan.md) §8, the durable defense is *proprietary,
  causally-validated performance data*. Everything in §2 feeds this.
- **Clip-from-source (Phase R)** — strategically interesting because it's a **different
  content supply**: it sidesteps generation volume entirely by mining existing footage.
  Needs local Whisper.
- **A rising $0 quality floor** — local open-weight models keep improving, and Free
  mode already routes to them. The cost floor drops for free over time; the work is
  keeping the seams ready (which Pillar 6 already did).
- **Async approval surface** — see §8; the operator, not the machine, is the throughput
  limit.

## 8. Risks & hedges

| Risk | Reality | Hedge |
|---|---|---|
| **Single-platform dependency** | Everything monetizes through YouTube; one policy change resets the business | The intelligence product line (§7) — revenue without the platform |
| **The operator is the bottleneck** | Key facts, cost mode, and publish approval all need a human present; that caps throughput more than compute does | An **async approval surface** (review a queued draft from a phone) — *not* full autonomy, which the authenticity posture doesn't want anyway |
| **Volume-gated analytics never unlock** | If volume stays capped, correlations stay thin forever | §2's reframe: more measured dimensions per publish + cross-channel pooling |
| **Provider/API churn** | Scrapers and actors break constantly; it's the #1 ops cost | Already mitigated by breakers/governor; keep the API-first ladder |
| **Platform audits don't fit a solo pipeline** | Verified in §6.2 | Refuse them; use human-in-the-loop modes where they exist |

## 9. What to explicitly NOT do

Saying no is most of the value here.

- **Don't add more generation features.** Faceless script→TTS→render is commodity
  ([tooling_landscape.md](tooling_landscape.md)); more of it doesn't widen the moat.
- **Don't build volume-gated analytics before the volume exists.** It's the most
  seductive category and the least useful today.
- **Don't chase platform audits designed for multi-tenant apps** (§6.2).
- **Don't turn paid off permanently.** Free mode is a *tool* for cost control, not the
  standing posture — quality is the priority, and Claude is the provider in hand.
- **Don't try to eliminate the Reddit setup.** It's irreducible (§6.1); make it guided.
- **Don't let `core/ui.py` absorb the next surface.** Split it first.

---

## Cross-references
[roadmap.md](roadmap.md) (tactical queue) · [vision.md](vision.md) (12-month north
star) · [operating_plan.md](operating_plan.md) (cost/pace, competitive analysis) ·
[code_audit_2026-07.md](code_audit_2026-07.md) (the §4 findings) ·
[llm_provider_strategy.md](llm_provider_strategy.md) (model choice) ·
[free_mode.md](free_mode.md) · [positioning.md](positioning.md) ·
[case_study.md](case_study.md).
