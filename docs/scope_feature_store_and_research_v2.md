# Scope — Feature Store (Priority #0) + Research Engine v2

Grounded in the current code, not theory. No implementation here; this is the design
to build against. Research v2 scope is intentionally light pending the live-run feedback.

---

## Part 1 — Feature Store / Outcome Schema  (Priority #0, the moat substrate)

### What exists today
`core/run_recorder.record_content_run` persists to `content_runs`:
`channel_id, input_topic, selected_topic, status, composite_score, signals_json,
variants_json, title, description, tags_json, brief_version, prompt_version,
script_preview, mp3/mp4_path, timings_json, abort_reason`.
Outcomes live separately (`publish_log`, analytics sync). **There is no structured,
queryable feature row per video, and no clean join from a run to its real outcomes.**

### The gap (why no intelligence agent can learn yet)
The fields that *explain* performance are unstructured or absent:
- **Hook** text + `hook_score` (exists at generation, not persisted structured)
- **Title structure** (number / question / callout / listicle) — not classified/stored
- **Format / length** choice (buried in `timings_json` as `length_preset`)
- **Angle** (recap / ranking / fraud / prediction) — implied by brief, not stored
- **Brief signals**: `controversy_score`, `audience_sentiment`, `recommended_format` — only `brief_version` is stored
- **Post-time slot**, **key-facts used / fact source**, **asset IDs** — not linked
- **Outcomes**: impressions, CTR, avg-view-duration, retention, watch-time, revenue — not joined to the run

### Design (minimal, additive — no big-bang migration)
1. **`content_run_features` (1:1 with `content_runs`)** — a normalized, typed feature row written at publish time:
   `content_run_id (FK), channel_id, anchor, domain, format, length_preset, angle,
   title_structure, hook_text, hook_score, controversy_score, audience_sentiment,
   recommended_format, post_slot, fact_source (none/manual/obsidian/web/signals),
   key_facts_count, brief_version, prompt_version`.
   *Why separate table:* keeps `content_runs` stable; features evolve independently; clean to query.
2. **`content_run_outcomes` (1:many, time-series)** — append metrics snapshots from analytics sync:
   `content_run_id (FK), captured_at, impressions, ctr, avg_view_pct, watch_time_sec,
   views, subs_gained, revenue`. Latest-per-run is a view.
3. **The join key.** Add `content_run_id` FK onto `publish_log` (already on the Phase-H prerequisite list in roadmap.md) so run → upload → video_id → metrics is a single path. This is the one piece that unlocks everything.
4. **Derived labels** (computed, not stored raw): `overperformer/underperformer` vs a rolling per-channel baseline (e.g. median CTR & avg-view-% over trailing N videos). Baselines must be **per channel** and **sample-gated**.

### Database requirements
- Alembic migration adding the two tables + the `publish_log.content_run_id` FK (Alembic baseline `0001–0002` already exists — extend it, don't hand-DDL).
- Keep JSON-repository parity (the project runs Postgres-or-JSON); the feature/outcome writers must degrade to JSON like the existing repos.
- Backfill: best-effort from existing `content_runs` (parse `timings_json` for length, classify title/hook retroactively where possible). Partial backfill is fine.

### Scalability
- OLTP volume is tiny (videos/day). No perf concern near-term.
- The outcomes table grows with each analytics sync × video — prune or roll up snapshots older than N days to "daily last value." Revisit a separate analytical store only at much higher volume.

### Risks
- **Feature drift / definition churn** — version the feature schema (a `feature_version` column) so a redefinition of "angle" doesn't silently corrupt history.
- **Confounding** — these are observational features; correlation ≠ causation. The experimentation harness (roadmap §6) is the eventual fix; until then, label findings "observational."
- **Classifier quality** — title-structure/angle classification (LLM or rules) introduces label noise; keep the raw text so labels can be recomputed.

### Implementation order (when built)
1. `publish_log.content_run_id` FK + backfill mapping (unlocks the join).
2. `content_run_features` write at publish time + retroactive classifier for existing rows.
3. `content_run_outcomes` writer hooked into `analytics.sync_metrics`.
4. Baseline + label view. → Analytics Intelligence Agent reads from here.

---

## Part 2 — Research Engine v2  (highest ROI, smaller than it looks)

### What exists today (`core/research_brief.py`, `research_brief_v3`)
`ResearchBrief` already emits **narrative, audience_sentiment, controversy_score (0–1),
debate_angles, supporting_evidence, recommended_format**, plus RSS/community/competitor/stats
context, freshness steering for over-covered anchors, and an LLM build with a fallback.
Web search now flows in via `enrich_facts` → `format_signal_facts` (confirmed: `core/fact_enrichment.py:265`) — so live web facts already reach both the brief and the content engine's VERIFIED FACTS.

### The delta to "v2" (per the Principal-Architect desired output)
Only two fields are genuinely missing from the brief object:
1. **`title_direction`** — a suggested SEO-aware title angle (not the final title).
2. **`suggested_hook`** — a candidate first-line hook (< 12 words), reusing the existing
   `hook_score` heuristic to self-rank 2–3 candidates and keep the best.

Plus three quality upgrades:
3. **Persist the brief's structured fields** into `content_run_features` (Part 1) so the
   Analytics Agent can later correlate controversy/sentiment/format with outcomes.
4. **Confidence + provenance** on `controversy_score`/`audience_sentiment` (cite which
   signals drove them) — turns subjective fields into auditable ones.
5. **Feed channel memory back in** once Channel Intelligence exists (e.g. inject "fraud
   beats recaps" beliefs into the brief prompt). Stub the read path now.

### Architecture / complexity
- Mostly additive to the existing dataclass + prompt JSON contract; bump `BRIEF_VERSION`
  to `v4`. No DB work required for the brief itself (the persistence is Part 1's job).
- `recommended_format` already exists — extend the enum if the run feedback shows gaps.

### Dependencies / risks
- Title/hook generation overlaps with `content_engine` (which already produces a title +
  hook). **Decide the boundary:** brief proposes *direction*; content_engine produces the
  *final* copy. Avoid duplicating/conflicting copy generation.
- LLM-judged controversy/sentiment remain subjective until validated against outcomes
  (Part 1) — ship as `v4`, validate later.

### Why this is highest ROI
It improves the input quality of *every* video immediately, reuses everything, needs no
migration, and the two new fields directly target the live failure modes (weak hooks,
off-angle framing). It is the fast win while Part 1's substrate is built in parallel.

---

## Recommended sequencing
- **Now:** Part 1 step 1–2 (the join + feature row) and Part 2 fields 1–2 can proceed in
  parallel — they don't conflict (different files).
- **Hold for your run feedback:** the exact Research v2 priorities (hook style, format enum,
  anti-filler emphasis) should be tuned to what the real script actually got wrong. The
  scaffolding above is provider/representation-stable regardless.
