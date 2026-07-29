# Planning log

A durable record of planning/brainstorming sessions so ideas aren't lost when the
ephemeral plan files (`~/.claude/plans/*.md`) are cleared. **Newest first.** Each entry
captures the prompt, the brainstorm/decisions, and what actually shipped — the tactical
backlog itself lives in [roadmap.md](roadmap.md).

> Convention: when a planning session happens (plan mode, or a substantial "what should we
> build" discussion), append a dated section here with the options considered, the
> decision, and — once built — the outcome. See [../CLAUDE.md](../CLAUDE.md).

---

## 2026-07-26 — LLM strategy CORRECTED (operator feedback)

**Prompt:** *"I did mean paid is CURRENTLY off for only chat and apify… paid is on for
claude, and for quality sake i wouldn't turn the paid version off permanently… you do know
that ollama isn't free anymore either right?"*

**What was wrong:** the previous entry generalized "chat + Apify paid off" into "the project
is running strict Free mode." It isn't. Corrected framing = **three states**: (a) **today** —
Standard *with gaps* (OpenAI + Apify keys off, **Claude available and paid**), (b) **Free
mode** — a strict per-run tool (`RUN_COST_MODE=free`), (c) full Standard. Paid is not being
disabled permanently; quality is the priority.

**The correction improved the headline finding.** Verified: `_vision_score` guards on
`OPENAI_API_KEY` → returns `None` → `score_thumbnail` falls back to `_heuristic_score`. So
with chat paid off, **thumbnail vision scoring is silently dead** — a *dead capability*, not
the "never-pay leak" previously claimed (that framing rested on the wrong premise; the latent
leak case is narrow — key present *and* `FREE_MODE_STRICT`). Meanwhile **Claude supports
vision and is paid for**, but the router can't carry images (`_normalize_messages` is
`list[dict[str, str]]`). One fix restores the capability on an already-paid provider, meters
it, and unblocks the Pillar-2 vision item.

**Ollama (verified):** the **local runtime is still free/open-source (MIT)** — the
`localhost:11434` path `free_mode.md` uses — but **Ollama Cloud is now paid** (~$0 / ~$20 Pro
/ ~$100–200 Pro Max; sources disagree on the top tier). "Ollama = free" is no longer
unqualified; caveat added to `free_mode.md`.

**Reordered verdict:** (1) refresh the **Anthropic** default model IDs (`claude-sonnet-4-…`
pinned while Claude 5 exists — live paid provider, config-only change), (2) give the router
an image path, (3) local-model A/B only when running Free mode, (4) Gemini/Grok/Kimi optional.

## 2026-07-26 — LLM strategy reevaluated for Free mode (analysis only)

**Prompt:** *"reevaluate with the understanding that chat and apify paid is off. show use
case for free and paid, and provide two more llms to compare to in the same doc"* →
then *"add all of them… also note that kimi is open weight and free? (verify)"*.
Rewrote [llm_provider_strategy.md](llm_provider_strategy.md); **12 models**, no code.

**The reframe:** `core/run_mode.py` Free mode is *strict* — under `FREE_MODE_STRICT` the
router filters to zero-cost candidates and **raises** rather than falling back to paid. So
with paid chat off, **every frontier model is blocked at the seam**; the only live LLM
decision is which model to `ollama pull`. Frontier analysis is a Standard-mode contingency.

**Verified (the user's ask): Kimi K3 is open weight but NOT free.** Modified-MIT weights
(2026-07-27, permissive at our scale) — but **1.56 TB weights / ~1.68 TB VRAM / 8×H100
minimum**, and **no free API tier** ($3/$15 on direct + OpenRouter, no `:free` variant).
Open weight ≠ free: it cannot serve Free mode.

**Upgraded finding — latent never-pay gap:** `assets/thumbnail_scorer.py` calls paid OpenAI
directly via the legacy `core/llm_client`, bypassing the router *and* `FREE_MODE_STRICT`
(`run_mode.py` has zero vision references). Latent, not live — the scorer is opt-in
(`THUMBNAIL_SCORER_ENABLED`) and needs an OpenAI key — but it's exactly the config of a
Standard user switching to Free. Routing it through the router closes the gap **and**
unblocks the Pillar-2 vision path.

**Also reframed:** Grok was pitched as displacing the paid `twitter` signal — but Free mode
already *skips* `twitter`, so it would restore a dropped capability, not remove a cost.

**Verdict (paid off):** (1) close the never-pay gap, (2) A/B the local model
(`llama3.1:8b` vs `qwen2.5:7b` — both already named in `free_mode.md`), (3) only when paid
returns: refresh stale `_DEFAULT_MODELS` IDs → Gemini (only native video reader) → Grok
(gated on citable URLs) → Kimi last.

## 2026-07-26 — Big-5 LLM provider strategy (analysis only)

**Prompt:** *"what could, including kimi, each of the big 5 llms do for this project and which
is most necessary? note if anything crosses over with my existing framework or is
unnecessary."* Plan mode; scope = **analysis/documentation only**, folding the Kimi doc into a
wider comparison ([llm_provider_strategy.md](llm_provider_strategy.md)).

**Findings (verified against the tree):**
- **GPT and Claude are already wired** (`core/llm_router._PROVIDERS`) — for those two, the
  "what could it do" answer is "it's already available." Nothing to build.
- **Gemini / Grok / Kimi are reachable today with zero code** via the wired `openrouter`
  provider. Native entries buy billing/latency/params, **not access** — the biggest
  "unnecessary" item.
- **The vision path already exists but is stranded**: `assets/thumbnail_scorer._vision_score`
  goes through the legacy `core/llm_client` (hardcoded OpenAI, bypassing the router → no cost
  ledger, no failover). This is *why* the Pillar-2 "router vision path" item is still open.
- **Grok uniquely touches the data layer** — live X/web access vs the paid `twitter` Apify
  signal (`_APIFY_PAID_SIGNALS`) — but LLM summaries aren't citable sources, so it's gated on
  returning attributable URLs.
- `_DEFAULT_MODELS` still pins `gpt-4o` / `claude-sonnet-4-…` while the field moved to GPT-5.6
  and the Claude 5 family.

**Verdict:** the most necessary work is **not a model purchase** — (1) route the thumbnail
vision scorer through `core/llm_router` (unblocks *any* vision model, $0 spend), (2) evaluate
refreshing the stale default model IDs on the already-wired providers, then (3) Gemini (only
native *video* reader) if Pillar-2 video review is the priority, (4) Grok (gated), (5) Kimi
(nice-to-have).

**Shipped:** [llm_provider_strategy.md](llm_provider_strategy.md) (renamed from
`kimi_k3_evaluation.md`) + `tooling_landscape.md` rows #18–19. No code.

## 2026-07-26 — Kimi K3 fit evaluation (analysis only)

**Prompt:** *"in what ways could kimi k3 be of use to this project, in addition to the
other github adds found recently (in docs)."* Plan mode; scope chosen =
**documentation/analysis only** (no code, no router edits).

**Finding:** the 2026-07 GitHub adds (ComfyUI, ai-marketing-skills, anything-to-notebooklm,
system_prompts_leaks, goose3, the `[providers]` backends) are *tools/backends*; Kimi K3 is
the **LLM brain** that drives/grades them — complementary, not overlapping. It plugs into the
free-first router (`core/llm_router.py`) as an **opt-in premium** provider (OpenAI-compatible;
or zero-code via the `openrouter` provider), bounded by the existing `LLM_DAILY_BUDGET_USD`
governance. Highest-leverage fits map to **open** roadmap items: the **router vision path →
rendered-video/thumbnail review (Pillar 2)** — K3's native vision covers text+image in one
seam — and **1M-context** work (clip-from-source Phase R, vault-wide synthesis Pillar 4,
SkillOpt Pillar 7, prompt-eval Pillar 2). Verdict: **complement (premium)** — reserve for
vision + long-context + grading; never displace the free cheap/extract tiers.

**Shipped:** the Kimi evaluation (since folded into
[llm_provider_strategy.md](llm_provider_strategy.md) §3.5) + a verdict-table row (#18) in
[tooling_landscape.md](tooling_landscape.md). No integration built — left for a future task.

## 2026-07-24 — Pillar 7: Self-improving skills (Agent Skills + SkillOpt)

**Prompt:** *"continue pillar 7 and from there advance as scheduled."* Built autonomously
(safe-by-design) rather than pausing for a fresh approval gate.

**How it maps to what already existed:** the `scripts/ops.py` `@_register` registry is a
skill catalog; `core/prompt_evals.py` is a frozen validation gate; `core/overnight.py` is the
nightly runner; the Pillar 4 vault `playbook_block` is the "ship" surface. Pillar 7 just names
and closes those loops.

**Shipped:**
- **C1 — Ops-as-skills** — `core/ops_skills.py` renders `skills/content-ops/SKILL.md` (Agent
  Skills frontmatter + a command table) from the live registry; `ops gen-skills` regenerates
  it so it never drifts from the CLI.
- **C2 — SkillOpt-Sleep** — `core/skillopt.py` scores the live prompts vs curated candidate
  STYLE DIRECTIVEs on the frozen `prompt_evals` rubric across the golden topics (new
  `extra_directive` seam in `content_engine`), keeps only a gate-beater
  (`SKILLOPT_MIN_MARGIN`), and writes a reviewable **proposal** record to the vault +
  `skillopt_proposal` event. Runs in `overnight` when `SKILLOPT_ENABLED=true`.

**Key safety decision:** C2 **never auto-edits live prompts**. It proposes a gate-validated
directive; the operator promotes it to a `[strategy]` playbook bullet. This delivers the full
SkillOpt "validated optimization" value with zero autonomous prompt-mutation risk. Follow-ups
(deferred): LLM-proposed directives; optional auto-apply behind a flag.

---

## 2026-07-22 — Best Bet breadth

**Prompt:** *"best bet needs more options"* — the startup best-bet picker returned too few,
too-similar topics, especially on a single-domain channel (tapin = gaming).

**Findings:** `core/best_bet.py get_best_bets()` drew fresh candidates only from RSS, capped
one pick per domain in Phase 1, applied a per-**anchor** franchise cap in Phase 2, and had
`n=3` hardcoded at `main.py:282` (prompt `[1-3]`). Hard constraint: best-bet runs at
**startup before discovery**, so any new candidate source must be **$0/keyless** and never
trigger paid Apify.

**Decision (operator, asked & answered):** build Best Bet breadth next, then Pillar 7, then
roadmap items — continuing until usage runs out; and **document every planning session in
the repo** (this file).

**Shipped:**
- **Configurable count** — `best_bet_option_count()` (`BEST_BET_OPTIONS`, default 5, clamp
  1–8); `main.py` uses it + a dynamic `[1-N]` prompt.
- **Angle multiplexing** (the core fix) — `_angle_options()` fills leftover slots with
  *distinct angles* on the dominant franchise (tier list / what's broken / meta evolution)
  reusing `_KEYWORD_ANGLE_MAP` + `_FALLBACK_ANGLES`. $0; no filler for no-anchor channels.
- **Opt-in keyless breadth** — `BEST_BET_SIGNALS` (csv, default `rss`) can add keyless
  `reddit` (hot) + `youtube` (view-velocity) candidates via `apis/free_backends`, through
  the same commerce/dedup filter, fail-open, never paid Apify. Off by default (latency).

**Not done (deliberate):** rebalancing configured slot lists; a ranked slot menu.

---

## 2026-07-22 — Scheduling mechanics

**Prompt:** *"the best times are always on a weekend which makes it useless"* + *"make the
individual just take a time input instead of minutes from now."*

**Findings:** Upload Option 3 (`core/ui.py`) took "minutes from now". The learned post-slot
picker (`analytics/post_timing.learn_slots_from_analytics`) ranked by **summed** engagement,
so the highest-volume day (already weekend-leaning) kept winning — a weekend feedback loop.

**Decision (operator):** fix the learner bias **only** — leave the configured default slots
and Option 4 untouched; the manual time input is the weekday lever.

**Shipped:** `parse_local_time_input()` (clock time / tomorrow / ISO datetime → UTC, in the
channel tz); learner now ranks by **average** engaged-rate per bucket with a min-sample
floor; `free-doctor` distinguishes "Ollama running, set OLLAMA_MODEL" from "no free LLM".
*Caveat surfaced:* learner only overrides once ≥8 timed samples exist.

---

## 2026-07 — Next-level roadmap assessment (local $0 stack → Best Bet → run-without-PC → Pillar 7)

**Prompt:** a planning-only strategy pass triggered by (1) HuggingFace model buckets
published to the operator's account, (2) real PC specs (Ryzen 7 7800X3D, 32 GB, RTX 4070 Ti
12 GB), (3) *"best bet needs more options"* + *"run without the PC?"*, and (4) a reference to
Microsoft/GitHub **"skill ops"** (Agent Skills + SkillOpt).

**Bucket verdicts:** ★ **Qwen3-TTS-12Hz-1.7B-CustomVoice** (local $0 voice cloning — WIN);
★ **Bonsai-27B-gguf** (local LLM via Ollama, ends the retired-free-model crash class; vision
unlocks rendered-video review — WIN, use the ternary variant for 12 GB); ◐ mT5 XLSum
(multilingual summariser — maybe, for multi-language); ◐ tabfm (tabular FM — maybe, data-
gated); ✗ MusaCoder-27B / LLaMA-Mesh / Bernini-R (not content-pipeline or won't fit 12 GB).

**Sequenced plan (operator-locked):** (1) **Local $0 stack** — A1 Qwen3-TTS provider
[shipped], A2 Bonsai/Ollama enablement [operator pulls the model]; (2) **Best Bet breadth**
[shipped, see above]; (3) *run-without-PC* (FastAPI panel + Tailscale + two-layer split) —
**parked**, honest reality: the GPU/render/TTS half is PC-bound, cloud/phone Claude Code is a
*dev* surface, not a *run-the-factory* surface; (4) **Pillar 7 — Self-improving skills**:
expose `scripts/ops.py @_register` as `SKILL.md` Agent Skills (C1) + a **SkillOpt-Sleep**
nightly loop in `core/overnight.py` that ships prompt/skill edits only when they beat the
frozen `core/prompt_evals.py` gate (C2) — compounds with the local frozen Bonsai into a
self-improving $0 factory.

**Excluded throughout:** multi-platform distribution (Phase M) stays parked.
