# Holistic code audit — 2026-07

> **Class:** snapshot · **Status:** frozen · **Reviewed:** 2026-09-20

> **Harvested 2026-08-17 from PR #28 (`claude/code-audit-2026-07`), which was closed
> unmerged.** Superseded as a health snapshot by the **2026-08 Grand Audit**
> ([audit.md](audit_2026-08.md)) — kept as the before half of a genuine before/after. Its headline
> trend, *"broad-except count and `core/ui.py` size are both growing"*, was acted on in
> 2026-08: all 98 silent handlers now log and `S110`/`S112` are enforced in ruff
> ([decisions.md](decisions.md) §24). Its other findings — the layering smell, and
> `core/llm_client.py` as a legacy holdout — have **not** been actioned.

*Report only — no code changed by this audit.* A whole-repo health pass at the
Pillars 1–7 milestone. Every number below is reproducible with the command shown, and
every finding cites a real path/symbol. Findings already tracked in
[roadmap.md](roadmap.md) are listed separately in §10 so this doesn't re-propose known
work.

---

## 1. Health snapshot

| Metric | Value | Command |
|---|---|---|
| Python files | **388** (255 excl. tests) | `find . -name '*.py' -not -path './.git/*' \| wc -l` |
| LOC (Python) | **56,222** | `… \| xargs wc -l \| tail -1` |
| Test files / functions | **132** / **1,139** | `ls tests/test_*.py \| wc -l`; `grep -rh "def test_" tests/ \| wc -l` |
| Bare `except:` | **0** ✅ | `grep -rn "except:" --include="*.py" . \| grep -v "except Exception"` |
| Broad `except Exception` | **383** | `grep -rn "except Exception" --include="*.py" . \| wc -l` |
| …of which **silent** (`except`→`pass`) | **86** | `grep -rn -A1 "except Exception" … \| grep -c "pass"` |
| `TODO`/`FIXME`/`HACK` | **0** ✅ | `grep -rn "TODO\|FIXME\|XXX\|HACK" --include="*.py" .` |
| ruff (CI-pinned **0.8.4**) | **All checks passed**; 370 files formatted | `python -m ruff check . && python -m ruff format --check .` |
| mypy (CI dirs) | **106 errors / 68 files** (201 checked) | `mypy analytics apis core config storage` |
| Secrets committed | **0** ✅ | see §6 |

**Trend worth noting:** broad-except count and `core/ui.py` size are both growing
(`ui.py`: 796 → 951 → **1,420** LOC across the last three audits). Neither is a defect
today; both are compounding.

> **Environment caveat (important for reading §7).** The full suite **cannot be
> installed in a clean container** — 148 of the collection errors below are missing
> heavy dependencies, not test failures. Counts above are static; the run in §7 is
> partial. This is itself a finding (§8).

## 2. Architecture & boundaries

Largest non-test modules:

| Module | LOC | Note |
|---|---|---|
| `core/ui.py` | **1,420** | Mixes spinner, art, health display, prompts, cost-mode prompt, queue UI. The long-standing split recommendation is now 2× the size it was when first raised. |
| `core/best_bet.py` | 949 | Cohesive but large. |
| `core/content_engine.py` | 940 | Prompt assembly + inject/reground/recenter passes in one module. |
| `core/llm_router.py` | 773 | Dense but single-purpose; well-documented. |

**Layering smell — a classifier that requires the database.**
`apis/topic_scorer.py` is a *text classification* module, but it cannot be imported
without the storage stack (it reaches `storage`→`sqlalchemy` through its
engagement-adjusted profile path, `_engagement_adjusted_profile` →
`get_performance_memory_repository`). Consequence: **pure domain inference is
unavailable in any environment without a DB**, which is exactly what produces the two
test failures in §7. Splitting the pure classifier from the engagement-weighted
profile lookup would make the common path dependency-free.

**Legacy holdout.** `core/llm_client.py` (raw OpenAI SDK) is the client that
`core/llm_router.py`'s own docstring says the router replaced. It survives for exactly
**one** consumer: `assets/thumbnail_scorer.py` (the only other reference is that
docstring). See §3 — this is the same file behind the most significant finding.
`legacy/` itself is correctly gone.

## 3. Provider / cost-seam integrity ⭐ *headline section*

Free mode's promise ("never falls back to a paid provider") is enforced by an
`FREE_MODE_STRICT` check **duplicated at each paid seam**:

| Paid seam | Guard | Metered in `cost_meter`? |
|---|---|---|
| LLM — `core/llm_router.py` | ✅ `_free_mode_strict()` (:272), chain filter, raises | ✅ |
| Voice — `core/tts.py` | ✅ `_free_mode_strict()` (:253, own copy) | ✅ (via pipeline) |
| Signals — `apis/apify_client.py` | ✅ inline env check (:240, third copy) | ✅ |
| **Vision — `assets/thumbnail_scorer.py`** | ❌ **none** | ❌ **not metered** |

### Finding 3.1 — the guard is copy-pasted, so new paid seams opt out by default
There is no shared `is_free_mode_strict()` helper; each seam re-implements the env
read. That is *why* a fourth paid call site exists with no guard at all: nothing forces
a new paid integration to participate. Centralizing the check (and asserting in a test
that every module importing a paid SDK consults it) converts a convention into a
guarantee.

### Finding 3.2 — the only vision path is unguarded, unmetered, and currently dead
`assets/thumbnail_scorer._vision_score` builds base64 `image_url` blocks and sends them
via `core/llm_client.get_openai_client()` — bypassing the router entirely. Therefore it
is outside Free mode's guard **and** invisible to `core/cost_meter.py`.

It guards on `OPENAI_API_KEY` and returns `None` when absent, so
`score_thumbnail` falls back to `_heuristic_score`. With paid chat currently off this
means **thumbnail vision scoring is silently inactive** — no error, no log, the score
just quietly becomes heuristic. Meanwhile Claude (the live paid provider) supports
vision, but the router cannot carry an image: `_normalize_messages` is typed
`list[dict[str, str]]`.

**One change fixes four things:** restores vision on an already-paid provider, brings
that spend under the cost meter and failover, closes the Free-mode guard gap, and
unblocks the open Pillar-2 "router vision path" roadmap item. It would also let
`core/llm_client.py` be deleted.

## 4. Dead code & duplication
- `core/llm_client.py` — removable once §3.2 lands (single consumer).
- `_free_mode_strict()` — **3 near-identical definitions** (§3.1).
- No `legacy/`, no dead-marker debt (`TODO`/`FIXME` = 0).

## 5. Error handling — a demonstrated failure mode, not just style

383 broad `except Exception` (86 silent). Most are legitimate resilience around
network/provider calls. But this audit found a concrete case where a broad catch turns
an **infrastructure error into silently wrong content**:

```python
# core/engagement.py:32
def safe_infer_domain(topic, channel_id) -> str:
    try:
        from apis.topic_scorer import infer_domain
        return infer_domain(topic, channel_id)
    except Exception:
        return "neutral"
```

When `apis.topic_scorer` can't import (§2 layering — e.g. the DB layer is missing or
briefly broken), every topic silently classifies as **`neutral`**. Downstream that
re-opens **tag pollution**: `tests/test_seo_tags.py` then observes
`['TapIn','gaming','UFC','MMA','shorts','esports']` — UFC/MMA tags on a *gaming* topic,
the exact bug class the roadmap records as fixed. No warning is emitted.

**Recommendation:** narrow this catch (or at minimum `logger.warning` on the fallback)
so a systemic failure is loud rather than quietly degrading output quality. Treat it as
the template for auditing the other silent handlers.

## 6. Security & secrets — clean ✅
- **0** committed `.env` / OAuth / token files (`git ls-files` check).
- `.gitignore` covers `.env` and `config/secrets/` (6 matching rules).
- **0** hardcoded key-shaped literals (`sk-…`, `AIza…`) in Python.
- Note: still **no automated secret-scan hook** at the commit boundary — defense
  currently relies on `.gitignore` discipline alone.

## 7. Test suite

| | |
|---|---|
| Ran in this container | **863** tests, 2 failures, 148 errors |
| Errors | **all missing-dependency collection failures**, not logic |
| Failures | **2** — environment-caused (see below) |
| Skips | 4 |
| Isolation compliance | **13 / 13** ✅ |

**Isolation is genuinely good.** Every test touching persisted quota state patches
`QUOTA_STATE_FILE` or uses the `GovernorCase`/`_IsolatedStateCase` bases, exactly as
`tests/CLAUDE.md` requires — 13 of 13. That rule is being followed.

**The 2 failures are environmental, not regressions.** `test_engagement`
(`safe_infer_domain` → `'neutral' != 'gaming'`) and `test_seo_tags`
(UFC tags on a gaming topic) both stem from `apis.topic_scorer` failing to import
without `sqlalchemy`, swallowed per §5. In a fully-installed environment they should
pass — consistent with the repo's "1125 tests green". *They are, however, a useful
canary: they show what breaks in the field if that import ever fails.*

## 8. Dependencies
- **18 pinned (`==`) / 2 unpinned** in core — good determinism, no lockfile.
- **Install fragility is the top DX cost.** Collection blockers by module:
  `sqlalchemy` **90**, `bs4` 16, `elevenlabs` 8, `googleapiclient` 7, `moviepy` 3,
  `openai` 2, `google` 1. Installing four light-ish packages would unlock ~121 of 148;
  only `moviepy` (3 tests) is genuinely heavy and it fails to build on modern Python.
- **Implication:** a `[test]` extra (or lazy/guarded imports for the media/DB layers)
  would make the logic suite runnable — and CI faster — without the full media stack.

## 9. Prioritized findings

| # | Finding | Impact | Effort | Where |
|---|---|---|---|---|
| 1 | Vision path unguarded, unmetered, silently dead | **High** | `[M]` | `assets/thumbnail_scorer.py`, `core/llm_router.py` §3.2 |
| 2 | Free-mode guard copy-pasted → new paid seams opt out silently | **High** | `[S]` | 3 seams, §3.1 |
| 3 | Broad catch turns import failure into wrong content (tag pollution) | **High** | `[S]` | `core/engagement.py:32`, §5 |
| 4 | Classifier hard-depends on the DB layer | Med | `[M]` | `apis/topic_scorer.py`, §2 |
| 5 | Suite un-runnable without the full media stack | Med | `[S–M]` | `pyproject.toml`, §8 |
| 6 | `core/ui.py` at 1,420 LOC and accelerating | Med | `[M]` | §2 |
| 7 | No secret-scan at the commit boundary | Med | `[S]` | §6 |
| 8 | `core/llm_client.py` removable after #1 | Low | `[S]` | §4 |

**Suggested order:** #2 and #3 are small, high-value, and independent — do them first.
#1 is the structural one that also closes #2's gap for vision and enables #8.

## 10. Already tracked — not re-proposed here

Per [roadmap.md](roadmap.md) "Next up": mypy baseline tightening (106 errors here is
the current number), annotating/retiring broad `except Exception` handlers, raising
render/publish test coverage, Alembic FKs, the cost/quota dashboard (O9) and governor
follow-ups (O12), and the router vision path (Pillar 2 — which finding #1 above is the
concrete prerequisite for). This audit adds evidence and prioritization to those; it
does not restate them as new.
