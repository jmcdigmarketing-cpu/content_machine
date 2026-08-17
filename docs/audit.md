# Grand Audit — Content Machine (2026-08-15)

Scope: **(A)** correctness review of the six-wave silent-failure cycle on
`feat/research-intake-repair` (12 commits, 74 files, +6079/−243, none previously
reviewed), and **(B)** platform health + tech debt + alignment to the vision.

Previous audit: 2026-06 (kept below for the delta).

Health snapshot: **1382 tests green** (0 failures), **61,497 LOC** across 405 tracked
Python files — 142 test files / 16,970 LOC (**28% of the codebase is tests**),
**0 TODO/FIXME markers**, **0 bare `except:`**, ruff clean, mypy 123 errors across 73
files (non-blocking baseline, up from 93 as the codebase more than doubled).

> Measure LOC with `git ls-files '*.py'`, not a filesystem walk. A naive `**/*.py`
> recursion reports **336k LOC** because it sweeps in the four gitignored tool checkouts
> (`ComfyUI/`, `ai-marketing-skills/`, `qiaomu-anything-to-notebooklm/`,
> `system_prompts_leaks/`). The 2026-06 figure (~26.5k) was tracked-only, so the
> comparison below is like-for-like.

---

## A. This-cycle code review

### The cycle's organising finding

Six roadmap passes converged on one defect shape, now recorded as
[decisions.md](decisions.md) §18: **sources were failing quietly and reporting "nothing
found" instead of "I am broken."** Nothing crashed. Every run looked healthy. The cost:

| Source | Reported as | Truth | Duration |
|---|---|---|---|
| Tapology | "no event match" | Cloudflare 403 | **33 days** |
| `twitter` | `inactive` | zero facts, ~32s/run, billed each time | **19/19 runs** |
| 11 of ~37 RSS feeds | quiet news day | 404 / 403 / 501 / dead host | months |
| Federal Reserve feed | 0 items | 20 items, killed by a UTF-8 BOM | unknown |
| API-SPORTS rate limit | `results: 0` | HTTP 200 **with** `errors.rateLimit` | n/a |
| `cost.tts` | `0.0` | 91% of run cost | every rendered run |
| OpenRouter cheap slug | test green | 404 daily | weeks |

### Verified this audit

| Area | Check | Result |
|---|---|---|
| **Alembic `0004`** (live DB) | stamp, FK presence, delete rules, orphans | stamp `0004`; **4/4 FKs** correct (`SET NULL` ×3, `CASCADE` on `thumbnail_scores`); **871 publish_log rows, 836 NULL links, 0 orphans** |
| **Cost backfill** (mutated 38 rows) | flags honest, `total` = Σ lines, re-run | 38/38 have TTS; **0** rows where `total ≠ sum(lines)`; 11 flagged `cost_estimated`, 18 `cost_partial`; re-run is a **no-op** |
| **Signal retirements** | genuinely inert | `reddit`/`twitter` catalog-disabled and **not scheduled** on any topic; `tapology.scrape_enabled()` False |
| **Grounding gate** (loosened) | adversarial: invention hidden behind each leading stopword | **0 misses** across 6 probes (`But`/`If`/`When`/`That`/`This`/`Which` + invented entity) |
| **LLM chain** | dead slugs gone | cheap chain = `openrouter → deepseek → openai`; persisted dead-model records **cleared**; ollama correctly absent (no models pulled) |
| **Feeds** | live health | **37/37 ok**, 0 stale, 0 dead |

### Findings

**A1 — FIXED this audit: a fabricated hyphenated name was invisible to the grounding
gate.** `_PHRASE` requires two space-separated capitalised words and `_MONONYM` only
fires in sports context, so a standalone hyphenated compound matched *neither*:

```
find_ungrounded_entities("Nova-Strike launches soon.", facts)  ->  []   # before
extract_entities("Take-Two's CEO called it strategy.")         ->  []   # before
```

A false **negative** in the anti-hallucination gate — worse than the false *positive*
fixed in the run-66 wave, because it was silent. `_CAP` now admits hyphenated compounds
and `_HYPHEN_NAME` catches standalone ones, with nested matches suppressed so
`"Jean-Luc Picard"` doesn't also yield `"Jean-Luc"`. Real names still ground
(`Take-Two` → `[]`), inventions now flag, and the earlier fixes hold. Tests:
`tests/test_run66_fixes.py::TestHyphenatedNamesReachTheGate`.

**A2 — Deliberate, recorded: the whisper caption backend is half-shipped.** Timing is
good (43–56 ms median line-start error, 12–15× realtime on CPU) but captions carry ASR
text, so proper nouns mangle ("Salkilld" → "Salkal"). Stopped with the blocker written
down rather than shipped looking finished. It is the gate on the **$0 TTS switch**, the
largest remaining cost lever.

**A3 — Two tests were green over dead code.** `test_openrouter_anchors_cheap_tier` pinned
a retired model id while production 404'd daily; `test_nba_domain_feeds` asserted an ESPN
URL answering `202`-with-empty-body. Both now assert the contract, not a vendor value
([decisions.md](decisions.md) §21). **Worth a sweep:** other tests may pin third-party
identifiers the same way.

**A4 — Accepted risk: `ops backfill-cost` rewrote history.** 38 rows changed. Mitigated
by flagging what was estimated (`cost_estimated`, 11 rows — character count derived from
`word_count` because `script_preview` truncates at 2000) and what remains incomplete
(`cost_partial`, 18 rows predating cost metering, which gained TTS but still have no
`llm`/`apify` lines). A pre-change dump went to `.db_backups/` (gitignored). The
alternative — leaving every historical margin ~19× wrong — was worse.

**A5 — No source-level defects found** in `cost_meter` / `run_features` / `run_trace`
merge helpers, `feed_health`, `mma_stats_api`, `caption_align`, or the `llm_router`
provider gating. All are fail-open, all have tests, and each carries the reasoning for
its non-obvious guards (API-SPORTS' 200-with-error body, the wrong-Topuria name match,
the `noResults` sentinel).

---

## B. Platform health

### Delta since 2026-06

| | 2026-06 | 2026-08 | |
|---|---|---|---|
| Tests | 199 (2 failing) | **1382 (0 failing)** | 6.9× |
| LOC (tracked) | ~26.5k | **61.5k** | 2.3× |
| Test share of LOC | — | **28%** | |
| TODO/FIXME | 0 | **0** | held |
| Bare `except:` | 0 | **0** | held |
| mypy errors | 93 / 57 files | 123 / 73 files | grew slower than LOC |

Test growth outpaced code growth ~3:1. The two failing tests from 2026-06 are gone.

### The broad-exception debt, sized honestly

**420** `except Exception` handlers in non-test code — a standing roadmap item. Sampling
what each does next:

| Follow-on | Count | Read |
|---|---|---|
| logs | 136 (32%) | deliberate fail-open, diagnosable |
| fail-open `return` | 78 (19%) | deliberate, the project's dominant idiom |
| *other* | 113 (27%) | mixed; needs eyes |
| silent `pass` | **93 (22%)** | **the real debt** — swallows without a trace |

So roughly half are the intended pattern (a signal or provider must never raise —
[apis/CLAUDE.md](../apis/CLAUDE.md)), and the ~93 silent `pass` handlers are where a
future failure will hide. Given this cycle's entire theme, that is the shape of the next
silent failure. **Recommendation:** don't retire the idiom — require a `logger.debug` in
every handler, so fail-open stays fail-*visible*.

### Cost reality, now that it is measured

| | |
|---|---|
| Per video | **$0.31** (was reported as $0.02) |
| TTS share | **91%** ($0.25–0.31) |
| Everything else | llm ~$0.005, apify $0.02, web $0.008 |

One lever dominates: local TTS meters **$0**, blocked only by caption text (A2). Note the
*marginal* rate ($0.22/1k, matching how Apify and LLM are priced) is right for
`cost_meter`, but the ElevenLabs Creator quota covers ~90 videos/month against ~21 made —
the **allocated** cost is nearer $1/video. Worth its own economics pass.

### Coverage gaps

- **Render + publish paths** remain the acknowledged thin spot (standing roadmap item).
  The cycle added an integration test for `run_media_only`'s persistence, but the ffmpeg
  and YouTube-upload paths are still mostly untested.
- **Volume-gated and genuinely blocked:** the recommender backtest needs 15 measured
  run-linked videos; there are **10**. Not a defect — do not build it yet.

### Alignment

The moat ([vision.md](vision.md)) is *verified substance + a closed learning loop*. This
cycle strengthened both sides of it: intake was repaired so grounding has real sources,
and the ledger was corrected so the loop measures true cost. The two remaining
false-alarm/false-negative fixes to the grounding gate matter disproportionately — a gate
that cries wolf gets ignored, and one with a blind spot is worse than none.

### Notable: the "needs a GPU box" items are not blocked by hardware

`nvidia-smi` reports an **RTX 4070 Ti (12 GB, driver 591.86)**, but torch is installed as
**`2.8.0+cpu`**, so `torch.cuda.is_available()` is `False`. Every roadmap item marked
*parked — needs a GPU box* (WhisperX alignment, MusicGen, ComfyUI/Wan-LTX AI video, YOLO
auto-reframe, avatar, Real-ESRGAN/RIFE upscaling, XTTS/Kokoro voice cloning) is waiting
on a **CUDA torch install**, not on new hardware. That is a materially different backlog
than the docs have described for months.

### Housekeeping owed

- Neither branch is merged and **no PR exists** (12 commits).
- `origin/claude/trade-validation-default-on` is **superseded and should be deleted** — it
  carries a pre-#33 CI time-bomb test that would revert the fix if merged.
- PRs #29–#32 have been open since late July. *(Corrected 2026-08-17: it is **seven**
  PRs, **#26–#32**, and **#27** is the superseded trade-validation branch above — close
  it rather than merge it.)*
- 17 test-fixture notes remain in the operator's vault (harmless; they no longer
  regenerate now the suite is isolated).

---

## Appendix — reproducing these numbers

```powershell
git ls-files '*.py' | % { (Get-Content $_).Count } | Measure-Object -Sum   # LOC
python -m unittest discover -s tests                                       # suite
mypy analytics apis core config storage                                    # type baseline
py -m scripts.ops feeds                                                    # source health
py -m scripts.ops economics --channel tapin                                # unit economics
py -m scripts.bench_script_duration                                        # words/sec drift
py -m scripts.bench_caption_align                                          # caption accuracy
nvidia-smi ; python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

---
---

*Retained in full for the delta above.*

# Grand Audit — Content Machine (2026-06)

Scope: (A) correctness review of the recency-intelligence cycle just shipped, and
(B) platform health + tech-debt + alignment to the Content Intelligence Platform vision.

Health snapshot: **199 tests** (2 pre-existing failures, unrelated), **~26.5k LOC**,
**0 bare `except:`**, **0 TODO/FIXME debt markers**, ruff clean, mypy 93 errors across
57 files (non-blocking, pre-existing type debt).

---

## A. This-cycle code review

### Fixed during the audit
1. **Obsidian fact leak (real bug).** `_is_evergreen` matched the substring `"facts"`,
   so every `tags:[facts]` note was treated as always-on — `ufc-current.md` would have
   surfaced on gaming topics. Fixed to require the explicit `evergreen` tag; added two
   regression tests (leak + evergreen-still-surfaces) and verified on the real vault
   (0 UFC facts leaked into a Zelda topic; playbook still surfaces).
2. **Vault errors could break video creation.** `prompt_key_facts` now wraps `load_facts`
   in try/except so a malformed vault can never block a run.
3. **mypy cleanups** in new `ui.py` code (franchise-art Optional type; dedup idiom).

### Accepted / noted (not blocking)
- **Circuit breaker is process-global with no TTL.** Correct for the CLI (one run). For a
  long-lived `jobs.worker`, a transient quota at hour 1 disables a signal until restart.
  *Recommendation:* add an optional per-entry TTL (e.g. re-probe after N minutes) before
  relying on the worker for multi-hour sessions.
- **Disabled signals vanish from the health display** after the breaker trips (they're
  removed from results). Minor UX: the operator stops seeing the "quota/auth" reason on
  later runs. *Recommendation:* surface a "disabled this session" line.
- **Web search double-caches** (signal-internal cache + `register_signals` cache share the
  same key) — redundant but harmless.
- **Web search recency params** are conservative (Tavily `topic:news`, Brave `freshness:pw`).
  Good for breaking news; may under-serve evergreen queries. Revisit if gaming evergreen
  topics return thin.
- **`load_facts` reads the whole vault every run** (`rglob`). Fine at current vault size;
  cache or index if the vault grows to thousands of notes.

---

## B. Platform health & tech debt

### Strengths
- Clean signal contract (`signal_contract.py`) with uniform status taxonomy — this is what
  made the generalized circuit breaker a small change. Good architecture.
- Strong separation: `core/` pipeline logic is largely UI-agnostic (enables the future web
  app with a thin adapter, not a rewrite).
- Disciplined testing culture and ruff/CI baseline; no debt markers or bare excepts.
- Provenance already partly present (`prompt_version`, `brief_version` on `content_runs`).

### Debt & risks (prioritized)
1. **No feature store / outcome schema (highest-leverage gap).** The single thing blocking
   every "intelligence" project. See `content_intelligence_roadmap.md` §1. Priority #0.
2. **93 broad `except Exception`** across apis/core/analytics. Most are defensive around
   network/LLM calls (legitimate), but some swallow silently. *Recommendation:* ensure each
   logs at debug+ and never hides a programming error; audit the silent ones.
3. **`core/ui.py` is 796 LOC and growing** (this cycle added to it). It mixes spinner,
   art, health display, prompts, queue UI. *Recommendation:* split into `ui/spinner.py`,
   `ui/art.py`, `ui/prompts.py`, `ui/display.py` before the web layer lands.
4. **mypy: 93 errors / 57 files** (non-blocking by design). Tracked debt; chip away,
   especially in `core/` which the intelligence agents will depend on.
5. **Recency now depends on external paid/keyed services** (Tavily/Brave/Apify). The
   circuit breaker + graceful no-key degradation mitigate outages, but add a cost meter
   (roadmap §5) so spend is visible.
6. **The 2 pre-existing `test_ascii_art` failures** (Luffy art loads empty) — already
   spawned as a separate task. Low impact (cosmetic mascot) but red CI locally.

### Security / secrets
- `.env` correctly gitignored; verified no secrets staged. Vault notes live outside the
  repo. Tavily/Brave keys + Obsidian path are in `.env` only. No exposure found.
- *Note:* if LLM-in-Obsidian plugins are added, their API keys live in Obsidian plugin
  settings (not the repo) — keep them out of any synced/committed vault.

---

## C. Alignment to the vision & recommended next move

The recency cycle was the right *tactical* work (it fixes the live failure mode), but it is
**input-side**. The moat is **output-side**: the feature store → analytics agent → channel
memory loop. The optimal next move after this audit is **Priority #0: the feature store /
outcome schema**, immediately followed by **Research Engine v2** (fast ROI). Do not start
Asset or Monetization intelligence until the measurement substrate exists.

**Verdict:** platform is healthy, well-architected for its stage, and now has a working
recency layer. The gap between "content generator" and "content intelligence platform" is
not code quality — it is the missing measurement loop. Build that next.
