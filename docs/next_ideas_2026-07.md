# What's next — roadmap item + 5 new ideas (2026-07-29)

> **Harvested 2026-08-17 from PR #32 (`claude/next-ideas`), which was closed unmerged.**
> Kept because its lead item — the router vision path feeding multimodal rendered-video
> review (Pillar 2) — is **still open** on the roadmap, with useful effort notes. The rest
> is a 2026-07 idea list: check anything here against [roadmap.md](roadmap.md) before
> acting, since several adjacent items have shipped.

*Documentation only. Part 1 answers **"what's next on the roadmap"**; Part 2 proposes
**five ideas that are deliberately NOT on the roadmap**, each verified as genuinely
unbuilt. Nothing here is committed work — this is a decision menu.*

---

## Part 1 — What's next on the roadmap

[roadmap.md](roadmap.md) "Next up" is grouped by area, not strictly ordered. One item
stands out as next **by dependency and by damage**:

### ⭐ Router vision path → multimodal rendered-video review (Pillar 2)

*Listed under "Video creation quality".* Three reasons it's the one to do:

1. **It blocks another listed item.** *"Router vision path → multimodal rendered-video
   review (Pillar 2)"* can't start until the router can carry an image.
2. **It isn't just unbuilt — the existing capability is broken.**
   `assets/thumbnail_scorer._vision_score` builds base64 `image_url` blocks and sends
   them through the **legacy `core/llm_client`** (raw OpenAI SDK), bypassing the router
   *and* `cost_meter`. It guards on `OPENAI_API_KEY`, so with paid chat off it returns
   `None` and `score_thumbnail` silently falls back to `_heuristic_score` — **thumbnail
   vision scoring is dead right now, with no error or log.**
3. **The fix pays four ways.** Claude (paid, in hand) supports vision, but the router
   can't send an image — `_normalize_messages` is typed `list[dict[str, str]]`. Adding an
   image path: restores the capability on an already-paid provider · meters that spend ·
   closes the free-mode guard gap for vision · unblocks Pillar 2. It also makes
   `core/llm_client.py` deletable.

**Effort:** `[M]` — `core/llm_router.py` (image content-blocks in `complete`),
`assets/thumbnail_scorer.py` (call the router instead of the legacy client), plus tests.

### Then, in order
1. **Cost / quota dashboard (O9)** — per-run API spend surfaced in status; the pieces
   (`cost_meter`, `quota_governor.snapshot()`) already exist.
2. **Governor follow-ups (O12)** — YouTube units under a governor scope; per-provider LLM
   spend in the cost line.
3. **`youtube_comments` signal** — templated in the Apify catalog, not wired; audience
   language is the cheapest hook research available.

### Housekeeping
**`SEMANTIC_TRADE_VALIDATION` default-on can be ticked off** — done in PR #27
(domain-gated to NBA/NFL). The roadmap line under *Recommenders & calibration* is stale.

---

## Part 2 — Five ideas NOT on the roadmap

Each was checked against the tree; the "Verified gap" line is the evidence.

### Idea 1 — Semantic near-duplicate detection ⭐ *highest value*

**Verified gap:** the authenticity variation guard is **purely lexical** —
`core/authenticity.py:23` imports `difflib.SequenceMatcher` and line 135 compares
normalized strings against recent uploads' `script_preview`. There is **no embedding or
semantic comparison anywhere** in the codebase.

**The problem:** the 2026 authenticity policy targets *substantive* repetition — the
same video made again. A **paraphrase of last week's script passes today's check**,
because character-level similarity is low while meaning is identical. The guard catches
copy-paste, not rehashing, and rehashing is the actual risk.

**Build:** compute an embedding per published script (local sentence-transformers model,
or the existing free LLM tier) and store it alongside `script_preview`; compare cosine
similarity against the last N and warn above a threshold. Reuse the existing
warn-never-block posture and the recent-uploads loader `core/authenticity.py` already
has. Effort `[M]`; needs one small dependency or an embedding endpoint.

**Why it matters:** this is a live hole in the compliance moat — the thing the whole
Phase-O layer exists to protect.

### Idea 2 — Recommender simulation harness

**Verified gap:** no synthetic-data validation exists for the recommenders. A large block
of roadmap work is explicitly *volume-gated* ("do not build until publish volume supports
correlations"), and *"Backtest recommender accuracy vs. realized engagement"* is itself
marked volume-gated — so the learning loop, the moat, is **currently unvalidatable**.

**Build:** a test-only harness that feeds `core/best_bet.py`,
`core/length_recommender.py` and `analytics/post_timing.py` **synthetic engagement
histories** with known ground truth, then asserts behaviour: does best-bet converge on
the planted high-performing domain? does the confidence layer
(`core/recommender_confidence.py`) correctly mark a 2-sample base as low-confidence? does
the post-time learner resist the weekend bias that was fixed on 2026-07-22? Effort `[M]`,
**zero runtime risk** — tests only.

**Why it matters:** it validates the loop *before* volume exists, which is the direct
answer to the volume paradox in [strategy_2026H2.md](strategy_2026H2.md) *(arrives with
PR #29)*. It would also catch a recommender regression that real data can't reveal for
months.

### Idea 3 — Integration incident ledger

**Verified gap:** no failure history is recorded anywhere — `data/` has no incidents
file, and nothing logs signal failures durably. Yet
[assessment.md](assessment.md) names *external-API fragility* the **#1 ops cost**, listing
Apify `set_cache` crashes, actor 404s, `sortVideosBy` 400, Wikipedia 429, IGDB 400, SEC
500, YouTube RSS 404 — all **anecdotes, none measured**.

**Build:** every signal/provider failure appends `{ts, source, status, http_code,
message}` to `data/incidents.json` (capped/rotated), plus an `ops incidents` view that
ranks integrations by failure count and recency. The signal contract already classifies
failures (`classify_http`, status constants in `apis/signal_contract.py`), so this is
mostly a write-and-aggregate layer, not new detection. Effort `[S–M]`.

**Why it matters:** turns "our biggest ops cost" from a feeling into a ranked list, so
retirement/replacement decisions (e.g. drop a chronically-broken scraper) are evidence-based.

### Idea 4 — Per-stage cost attribution

**Verified gap:** `core/cost_meter.py` has **zero** occurrences of a stage/phase concept —
it prices a run in total (llm/tts/apify/web), not by pipeline step.

**Build:** tag each LLM call with the stage that made it (discovery, research brief,
script, insight injection, grounding regen, claim verifier, title, grading) and roll the
existing token ledger up per stage. The router already records real per-call usage, so
this is a label plus a group-by — then the run summary can say *which prompt* costs the
most. Effort `[S–M]`.

**Why it matters:** the pipeline makes many LLM calls per video (several are
regenerate-on-condition passes). Right now there's no way to know whether the script, the
regen passes, or the verifier dominates spend — so prompt-trimming is guesswork.

### Idea 5 — Docs freshness lint in CI

**Verified gap:** `.github/workflows/ci.yml` has **no** markdown/link/metric checking.

**The problem:** doc drift is a *demonstrated, recurring* failure here — stale test
counts and LOC figures were found and corrected **three separate times in one session**,
and a whole branch (`claude/docs-optimization-review-a4l104`) is now un-mergeable
specifically because its metrics went stale.

**Build:** a CI step that (a) checks every relative markdown link resolves, and (b)
compares metric claims in docs against generated values, failing when they disagree —
enforcing the counting convention now recorded in
[HANDOFF_SYNOPSIS.md](HANDOFF_SYNOPSIS.md) *(arrives with PR #31)*. Effort `[S]`.

**Why it matters:** it converts a discipline problem into a mechanical one. Every audit so
far has spent effort re-deriving numbers that a script could assert.

---

## Ranking (my recommendation)

| # | Idea | Value | Effort | Risk |
|---|---|---|---|---|
| 1 | Semantic near-duplicate detection | **High** — live compliance hole | `[M]` | Low (warn-only) |
| 2 | Recommender simulation harness | **High** — validates the moat pre-volume | `[M]` | **None** (tests only) |
| 3 | Integration incident ledger | Med–High — measures the #1 ops cost | `[S–M]` | Low |
| 4 | Per-stage cost attribution | Med — ends spend guesswork | `[S–M]` | Low |
| 5 | Docs freshness lint | Med — kills a recurring drift class | `[S]` | None |

**If picking one:** Idea 1 (a real compliance gap, live today).
**If picking a safe one:** Idea 2 (tests only, and it de-risks everything downstream).
**Against the roadmap item:** the router vision path is still the better *first* build —
it repairs something currently broken, whereas all five ideas add new capability.

---

## Cross-references
[roadmap.md](roadmap.md) · [assessment.md](assessment.md) ·
[HANDOFF_SYNOPSIS.md](HANDOFF_SYNOPSIS.md) · and, arriving with open PRs:
`code_audit_2026-07.md` (#28) · `efficiency_audit_2026-07.md` (#30) ·
`strategy_2026H2.md` (#29).
