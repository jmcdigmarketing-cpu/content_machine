# Planning log

A durable record of planning/brainstorming sessions so ideas aren't lost when the
ephemeral plan files (`~/.claude/plans/*.md`) are cleared. **Newest first.** Each entry
captures the prompt, the brainstorm/decisions, and what actually shipped — the tactical
backlog itself lives in [roadmap.md](roadmap.md).

> Convention: when a planning session happens (plan mode, or a substantial "what should we
> build" discussion), append a dated section here with the options considered, the
> decision, and — once built — the outcome. See [../CLAUDE.md](../CLAUDE.md).

---

## 2026-08-20 (evening) — Next 5 pickup order + 35 cost/viability/success candidates

**Prompt:** the next 5 roadmap items, plus 35 more ideas, all around *future
viability*, *short-term success*, and *real-world cost*.

**Not built.** Pickup order only; Phase M, volume-gated backtest, and the $0 TTS
voice judgment stay out. None of 56–90 restates Next-up, the morning 20, or
candidates 21–55.

**Recommended next 5** (existing open lines, sequenced for those three axes):

1. Pre-run completion gate `[S]` — short-term (run-70 class).
2. `youtube/oauth.py` tests + `coverage` extra `[S]` — short-term (paused
   coverage wave, last sequenced item).
3. Pronunciation lexicon for local TTS `[M]` — cost (unblocks the $0.25–0.31
   TTS line on *ears*, captions already being fixed).
4. Allocated vs marginal unit economics `[S]` — cost (~$1 allocated vs $0.31
   metered on the Creator plan).
5. Numeric/record grounding `[M]` — viability (invented ranks/dates/purses
   still pass the name-gate; 2026-policy event on a UFC short).

**35 new candidates (56–90)** grouped on [roadmap.md](roadmap.md):

| Axis | Items | Through-line |
|---|---|---|
| Short-term success | 56–65 | Next publish happens and earns a measured data point (quota, thin-facts abort, MoneyWise go-live, operator minutes) |
| Real-world cost | 66–77 | Meter the true bill (Flux, Apify invoice, GPU power, TTS cache) and stop paying for drafts that will fail |
| Future viability | 78–90 | Stay a media OS: intelligence-report SKU, holdouts, policy canary, non-ad spike with a kill criterion, backup the dataset |

**Rejected this session:** implementing the five; restoring Phase M; treating
clip-from-source / avatar / Instagram as "next" (they fail the cost and
viability tests until volume and authenticity are earned).

**Numbers this ranking used (already measured, not assumed):** TTS is ~91% of a
rendered run ($0.25–0.31 metered, ~$1 allocated at 21/90 Creator-plan
utilisation); Apify remaining paid tier is two actors; YouTube upload ≈ 1,600
units of 10k/day; recommenders still sit at 10 measured vs a 15-sample gate.

---

## 2026-08-20 — Next 5 shipped + 35 more candidates (no Phase M)

**Prompt:** close the five sequenced build items from the afternoon plan, then
append 35 new roadmap candidates. Phase M, volume-gated backtest, and $0 TTS
voice judgment stay out.

**Built (uncommitted on `fix/live-run-69-70`)**

1. **Run-70 probes.** `llm_router.ollama_probe()` is the single `/api/tags`
   helper. `_ollama_ready` already delegated; `ops free-doctor` now says **pull**
   when the daemon is up and empty (not "server unreachable"), **serve** when
   down, and names OpenRouter as throttled fallback. RUF012 gone
   (`tests/test_run69_fixes.py`).
2. **`process_one` + `_defer_for_quota` tests** — quota-exhausted claims only
   render jobs; a deferral does not consume a retry
   (`tests/test_job_worker_process.py`). No product change.
3. **`build_render_ffmpeg_command` assertions** — amix under VO, VO-only
   identity, `-t`, escaped subtitles, music-bed failure retries VO-only.
   `youtube/oauth.py` and the `coverage` extra stay for a follow-up.
4. **Semantic variation.** Stdlib content-word cosine folded into
   `_variation_check` (`AUTHENTICITY_SEMANTIC`, default-on). Paraphrase of a
   TapIn-shaped script fails; unrelated topic passes; exact duplicate still
   fails lexical first. Warn-never-block. No persisted embeddings.
5. **Router vision.** `complete` accepts OpenAI-style image parts; Anthropic /
   DeepSeek / Ollama / Groq / Doubao are skipped, not flattened. Thumbnail
   scorer uses the extract tier; Free mode heuristic + warning.
   `core/llm_client.py` deleted.

**Docs:** ticked the five on [roadmap.md](roadmap.md). Candidates **21–55**
appended (aesthetics, operator surface, efficiency, long-term). Architecture
table and decisions §14 no longer claim a `llm_client` holdout.

**Still parked:** Phase M; `youtube/oauth.py` tests; `coverage` extra; Pillar 2
multimodal review; overnight still cannot take facts; CUDA torch (`2.8.0+cpu`
on a 4070 Ti).

---

## 2026-08-20 — Post-merge orientation, 20 ideas (no Phase M), grand audit

**Prompt:** refamiliarize after committed + uncommitted work; brainstorm 20 more
roadmap ideas that are not multi-platform; then a grand audit.

**Where we actually are**

- **Branch:** `fix/live-run-69-70` at `6a6ec96` (same commit as `main` /
  `origin/main`). PR #34 merged 2026-08-19. CI green on trunk.
- **Committed since the 2026-08-15 audit:** caption retext; fail-open visibility
  (S110/S112); alembic logging fix; intro-step never loses the render; coverage
  wave paused after that; orphan-doc harvest; stale PRs #26–#32 closed; handoff
  rewritten as merged.
- **Uncommitted (important):** `core/run_mode.py` + `tests/test_run69_fixes.py`.
  Live run 70 (Cejudo, Free) died after 71s of discovery because Free mode printed
  `llm=ollama OK (local $0)` when the daemon answered `/api/tags` with **zero
  models pulled**. `_ollama_ready` was a weaker copy of `llm_router.ollama_installed_models`.
  The patch delegates. **Do not commit as-is:** (1) `ops free-doctor` still prints
  "server unreachable" whenever `OLLAMA_MODEL` is set and not ready — the run-70
  case is "pull a model"; (2) the new test's `ENV = {...}` trips **RUF012**.

**Audit headline (see [audit.md](audit.md) 2026-08-20 + canvas):** health held
(1,433 tests committed / 1,440 with wip, 62.7k LOC, mypy 123/73 unchanged,
silent `pass` still 0). New debt is the run-70 class again (lying readiness),
thumbnail vision still silently dead on `llm_client`, overnight still cannot take
facts, and the roadmap contradicts itself in three shipped items.

**20 ideas added as not-committed candidates** on [roadmap.md](roadmap.md).
Phase M excluded. None restates Next-up (no clip-from-source, avatar, MoneyWise
depth, router vision, Instagram). Highest-leverage three if picking:

1. Finish the run-70 branch (free-doctor diagnosis + ClassVar) then commit.
2. Semantic near-duplicate authenticity — lexical `SequenceMatcher` is the live
   hole in the 2026 compliance moat.
3. Pronunciation lexicon + `CAPTION_ALIGN` default-on — what actually makes the
   $0 TTS flip survivable, now that caption *text* is fixed.

**Rejected this session:** implementing the 20; merging
`origin/claude/docs-optimization-review-a4l104` (old base, same shape as #27).

---

## 2026-08-14/15 — Six roadmap waves: the silent-failure session

**Prompt:** a sequence of *"next roadmap task"* passes, punctuated by two pasted live-run
logs (runs 64/65, then run 66). Each pass began as a normal roadmap item and turned into
the same discovery, which became the session's organising idea:

> **Things were failing quietly, and the system reported "nothing found" instead of
> "I am broken."** Nothing was crashing. Every run looked fine.

**What that pattern actually cost, once measured:**

| Source | Reported as | Truth |
|---|---|---|
| Tapology scrape | "no event match" | Cloudflare 403 for **33 days**, 10/10 empty cache |
| `twitter` signal | `inactive` | **19/19 runs, zero facts**, slowest phase (~32s), billing Apify each time |
| 11 of ~37 RSS feeds | quiet news day | 404 / 403 / 501 / dead host |
| Federal Reserve feed | 0 items | alive with 20 items — killed by a **UTF-8 BOM** parse error |
| API-SPORTS rate limit | `results: 0` | HTTP 200 **with** `errors.rateLimit` |
| `features_json.cost.tts` | `0.0` | TTS is **91% of run cost** — margin overstated ~19× |
| `"If Netflix"` | possible hallucination | sentence-initial "If"; cost the run a grade (A→B) |
| OpenRouter cheap slug | test green | retired model, **404 every day** for weeks |

**Decisions made (recorded in [decisions.md](decisions.md) §18–§22):** a dead source must
report failure, not "no match"; retire a paid signal that produces nothing rather than
repair it; derive values that can drift instead of storing them beside their source;
never pin a rotating vendor id in a test; price from the operator's real plan.

**Waves shipped:** research-intake repair + `ops feeds` monitoring · `twitter` retired ·
`youtube_comments` via the official API + O12 complete · post-render cost persisted
(+ 38 historical runs repaired) · whisper CPU caption backend · run-66 fixes.

**Deliberately stopped mid-item:** the whisper work landed its backend and measurements
but **not** the caption-text fix — whisper transcribes blind, so captions carry ASR text
("Salkilld" → "Salkal"), and fighter names are the channel's whole subject. Stopping with
the blocker written down beat shipping something that looks finished.

**Rejected / not built:** restoring Reddit (operator declined); retuning preset *word*
counts to hit their advertised durations (would change output length and break
length-label continuity in the analytics); paying down the 420 broad `except Exception`
handlers (sized in the audit, not fixed).

**Open, highest-value next:** the caption-text fix, which unblocks the **$0 TTS switch** —
the single biggest cost lever left at **$0.25/video**.

**Surprise worth acting on:** the box has an **RTX 4070 Ti (12 GB)**, but `torch` is
installed as `2.8.0+cpu`, so `torch.cuda.is_available()` is False. Every roadmap item
marked *"parked — needs a GPU box"* (WhisperX, MusicGen, ComfyUI/Wan-LTX, YOLO reframe,
avatar, Real-ESRGAN/RIFE, XTTS/Kokoro voice cloning) is blocked by a **CPU-only install,
not by hardware**. See [audit.md](audit.md).

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
