# Master plan

> **Class:** plan · **Status:** living · **Reviewed:** 2026-09-26

The canonical forward plan. Supersedes `content_intelligence_roadmap.md`,
`groundwork_q3_2026.md` and `scope_feature_store_and_research_v2.md` as *the* answer to
"what are we doing next". [roadmap.md](roadmap.md) stays as the item-level ledger —
this doc says which horizon an item belongs to and why. Evidence:
[audit_2026-09.md](audit_2026-09.md).

## The thesis

Two months of fast building produced a system whose capability now outruns its
*verification*: the tests, the types, the docs and the package structure all report
healthier than they are. [decisions.md](decisions.md) §18 named this shape a year of
incidents ago — *something reports healthy while being broken* — and the audit found six
instances of it, in the suite, the docs, the mypy baseline, the lint pin, the
environment and the error handling.

So the sequencing rule for the next quarter is:

> **Restore verification before adding capability, and land every rule as a check.**

Not a freeze. M0 is days, M1–M2 are structural and already half-done, and product work
resumes at M3. But no wave ships a rule that lives only in prose — `AGENTS.md` already
records what happened the last time one did (`e4d2242` violated the no-AI-attribution
rule the commit *after* the rule was written; it took `.githooks/commit-msg` to stop it).

Each wave below has an **exit criterion** that is a command, not a judgement.

**Status 2026-09-26 (wave 31).** M0, M1 and M2 are **done**; their exit commands pass and
are now CI legs, so they stay done. M3.2 (the mypy ratchet) is done; the rest of M3 is
re-sequenced below. Evidence and before→after numbers:
[audit_2026-09-26.md](audit_2026-09-26.md). Item ledger: [backlog.md](backlog.md)
#827–#834. Main had independently landed the `roadmap.md` split (M2.1) and generated
counts before this wave.

---

## M0 — Test integrity · **done 2026-09-26** (#827–#829)

**Why now.** [audit_2026-09.md](audit_2026-09.md) §1.3: `tests/test_run69_fixes.py`
passes 13/13 alone and fails 5 in the full suite. Those five guard the run-70 outage
(Free mode advertising an empty Ollama, killing a run 71 seconds into discovery). Right
now, green does not mean that guard holds. Nothing else on this plan is trustworthy
until the suite is.

1. **One reset point for process-global state.** `core/llm_router._ollama_probe_cache`
   (`core/llm_router.py:217`) is a hand-rolled module global; `test_run_mode.py` and
   `test_free_doctor_probe.py` reset it by hand, `test_run69_fixes.py` forgets to.
   Either give it a `cache_clear()`-style reset and call it from one shared test base, or
   convert it to `functools.lru_cache` and reset it centrally. Same sweep for every other
   module-level mutable: `grep -rn "^_[a-z_]*cache[a-z_]* *[:=]" core/ apis/`.
2. **Prove order-dependence is gone.** Run the suite in a shuffled order and in reverse;
   both must match the default run. A one-line `ops` subcommand or a CI matrix leg is
   enough — it does not need `pytest-randomly`.
3. **Optional deps skip, not error.** §1.4: a partial environment yields 263 errors, 221
   of them `ModuleNotFoundError`. Guard the optional imports (`sqlalchemy`, `bs4`,
   `googleapiclient`, `elevenlabs`, `PIL`) with `unittest.skipUnless`, so a contributor or
   agent sees skips and reads real failures.
4. **Re-check the two collateral failures.** `test_engagement` and `test_seo_tags` fail
   only because `apis.topic_scorer` cannot import `sqlalchemy`. Confirm they pass on a
   full install; if either is a genuine bug, it has been hiding behind the noise.

**Exit (passed 2026-09-26):** `python -m unittest discover -s tests -t .`,
`py -m scripts.ops test --order reverse` and `--order shuffle --seed 1` report the identical
result; CI runs the reversed leg on every push. On a bare install the run prints one line
naming the missing modules. What actually caused the run-69 symptom — a half-built
`ExitStack` in `tests/test_ops_doctor`, not the probe cache — is in the audit §1.1.

**Not in this wave:** raising coverage, adding tests, touching any feature.

---

## M1 — Finish the docs standard · **done 2026-09-26**

**Why now.** Half of it landed with the audit; the half-measure is worse than either
end state, because a partially-applied convention teaches that conventions are optional.

Already done: [docs_standard.md](docs_standard.md), [README.md](README.md),
`tests/test_docs_standard.py` (11 checks, CI-blocking), doc cards on all 46 docs, four
superseded plans marked `archived`, `audit.md` → `audit_2026-08.md`, volatile test counts
out of `living` docs.

All five items that were listed as remaining are done: `LEGACY_NAMES` drained (ten
renames, links rewritten), one product name per layer (decisions §33), the never-revised
docs read against HEAD, the oldest adopted into the `Reviewed` cycle, and the metric rule
widened to subcommand, signal and module counts.

**Exit (passed 2026-09-26):** `python -m unittest discover -s tests -t .`,
`py -m scripts.ops test --order reverse` and `--order shuffle --seed 1` report the identical
result; CI runs the reversed leg on every push. On a bare install the run prints one line
naming the missing modules. What actually caused the run-69 symptom — a half-built
`ExitStack` in `tests/test_ops_doctor`, not the probe cache — is in the audit §1.1.

**Not in this wave:** raising coverage, adding tests, touching any feature.

---

## M1 — Finish the docs standard · **done 2026-09-26**

**Why now.** Half of it landed with the audit; the half-measure is worse than either
end state, because a partially-applied convention teaches that conventions are optional.

Already done: [docs_standard.md](docs_standard.md), [README.md](README.md),
`tests/test_docs_standard.py` (11 checks, CI-blocking), doc cards on all 46 docs, four
superseded plans marked `archived`, `audit.md` → `audit_2026-08.md`, volatile test counts
out of `living` docs.

Remaining:

1. **Drain `LEGACY_NAMES`** — ten grandfathered filenames in
   `tests/test_docs_standard.py`. Rename to `snake_case`, update inbound links in the
   same commit (`data_sources.md` has 6, `signals_and_sources.md` 3), leave a redirect
   stub only where an outside link might exist — the [ROADMAP.md](../ROADMAP.md) pattern.
   The set may only shrink; the lint fails if a name in it no longer exists.
2. **One product name.** Three are in circulation: "Content Machine" (19 docs), "Content
   OS" (14), "Content Intelligence Platform" (8). Pick one, record it as a `§` in
   [decisions.md](decisions.md), sweep the `living` docs, leave `frozen` and `archived`
   ones alone — they were true when written.
3. **Review the 15 never-revised docs.** Untouched since the first commit
   (2026-07-10). Each gets exactly one of: a bumped `Reviewed` date after being read,
   `Status: archived` with a successor, or deletion. No doc keeps a `living` card by
   default.
4. **Adopt the 15 oldest into the `Reviewed` cycle.** Reviewing a doc means reading it
   against HEAD. Bumping the date without doing so makes the whole card worthless — say
   so in review.
5. **Extend the metric rule beyond test counts.** The lint currently catches `N tests`.
   Subcommand counts (`~38` in `CLAUDE.md`, `~40` in `handoff_synopsis.md`), signal
   counts and module counts drift the same way. Widen `VOLATILE_METRIC` once the
   corpus is clean enough to pass.

**Exit (passed 2026-09-26):** `python -m unittest tests.test_docs_standard
tests.test_docs_lint` green with `LEGACY_NAMES` empty; the nine never-reviewed docs read
against HEAD (verdicts in the audit §3.1); one product name per layer (decisions §33).
Still open from this wave: the 90-day `Reviewed` staleness check is not yet a lint rule.

---

## M2 — Split the oversized docs · **done 2026-09-26**

**Why now.** Five files are 48% of the corpus, and `roadmap.md` has a single 1,084-line
section. Agents load these files to answer one question and spend a large fraction of a
context window doing it. This is a direct tax on every future session.

1. **`roadmap.md` (1,774 lines → a ledger).** Keep open items and the current focus.
   Move `## Completed`, `## Intelligence phase (H → K) — complete`, `## Recently shipped`
   and the two `(proposed)` sections into `change_log.md` or a new
   `roadmap_archive_2026.md` snapshot. Target under 600 lines.
2. **`handoff_synopsis.md` (757 lines) → newest three waves.** It is a handoff; the
   fourth-oldest wave is history and belongs in `change_log.md`. This file is read at the
   start of nearly every session, so its size is paid repeatedly.
3. **`decisions.md` — wrap and re-level.** Median line length 235 characters, and it
   jumps H1 → H3. Wrap to the repo's ~88-column prose style and promote the numbered
   decisions to `##`, so diffs are reviewable and the anchors survive. Do this in one
   mechanical commit that changes no words — it is cited by section number from 23 docs.
4. **Size budget as a check.** Add a `living`-doc line-count ceiling to
   `tests/test_docs_standard.py` (logs and snapshots exempt by class — they are supposed
   to grow). Set the ceiling at the post-split reality, not aspirationally.

**Exit (passed 2026-09-26):** no `living` doc over 800 lines (`backlog.md` exempt by
design), links resolve after the moves, `decisions.md` word-identical with 36 sections.
Logs roll over by period instead of being trimmed (docs_standard §7):
`handoff_synopsis.md` 1,849 → 244 lines, `planning_log.md` 5,268 → September only.

---

## M3 — Structural debt (2–4 sessions, parallelisable) · **M3.2 done**

**Why now.** These compound quietly and none of them blocks a feature today — which is
exactly why they need a scheduled slot rather than good intentions.

1. **Seams in `core/`.** The largest package and flat (prefix clusters listed in #834). Do not big-bang
   this. Introduce sub-packages along the boundaries the code already has —
   `core/llm/`, `core/vault/`, `core/video/`, `core/ops/` — moving files in small
   commits with re-export shims so imports keep working, and a rule in `CLAUDE.md` about
   where a new module goes. The rule matters more than the move.
2. **Ratchet mypy — done 2026-09-26 (#833).** `scripts/mypy_ratchet.py` + `mypy_baseline.txt`
   hold CI's list at 129 and fail on increase; the typecheck job is blocking. Still open:
   extend the scope to `video`, `publishing`, `youtube`, `scripts`, `jobs` and delete the
   dead `video.*`/`publishing.*` override. That turns a number nobody watches into a
   number that cannot grow, without a blocking rewrite. Then pick off the 89 files by
   subsystem.
3. **Upgrade ruff.** Pinned at 0.8.4 across CI, `pyproject.toml` and
   `.pre-commit-config.yaml` — consistent, and nine months old. Current ruff reports 28
   lint findings and 28 files needing reformat. One commit for the format sweep, one for
   the pin bump, one per rule family for the findings. The bill only grows.
4. **Broad excepts.** 627 across the source tree, against "~18 silent" tracked in June.
   Do not attempt all of them. Inventory them, classify into *deliberate fail-open*
   (the O11/O12 pattern, which is correct here) versus *accidental swallow*, and fix
   only the second group. Publish the split so the number stops being alarming.

**Order for the rest of M3:** the ruff bump first (#831 — one format sweep, one pin bump,
one commit per rule family), then `core/` seams (#834), then the broad-except inventory
(M3.4). The `apis/scrapers` packaging gap (#832) is an hour and can ride any of them.

**Exit:** ruff on a current pin with CI green; `core/` sub-packages documented in
`CLAUDE.md`; broad-except inventory in `docs/`; mypy scope covers every package that ships.

---

## M4 — The volume problem (product; gated on M0)

**Why now.** The learning loop is the moat and it is starved, not broken. June recorded
recommenders firing on 2–3 samples; August recorded 10 measured run-linked videos against
a 15-sample predictor gate. Every intelligence feature built on top of it inherits that
ceiling, so this outranks new capability.

1. **Close the measurement gap first.** Get run-linked measured videos from 10 past the
   15-sample gate. That is a cadence and attribution problem, not a modelling one — find
   where runs lose their link to published analytics before building anything new.
2. **Surface confidence everywhere a recommendation appears.** Carried from June and
   still open: a 2-video average must not read with the same authority as a 40-video one.
3. **MoneyWise depth + the cross-channel prior.** The second channel exists and is thin.
   A cross-channel prior is the cheapest way to make both channels' recommenders usable
   before either has volume on its own.
4. **Grounding, continued.** Vault relevance is scored and landed (holdout 1.0/1.0). The
   remaining recency risk is the same one June named: the system still cannot tell that an
   event is newer than its facts. The operator paste path mitigates; it does not solve.

5. **Retune by logic until the sample can speak.** Run 98's calibration (2026-09-26): 23
   measured tapin videos, grade r=-0.01, composite r=-0.05. At n=23 a correlation needs
   |r|>=0.41 to clear p<0.05, and the 95% interval for the grade is about -0.42..+0.40:
   strong predictors are ruled out, weak ones are invisible. Videos needed at 80% power:

   | true r | 0.5 | 0.4 | 0.3 | 0.2 |
   |---|---|---|---|---|
   | videos | 30 | 47 | 85 | 194 |

   So rubric and weight changes are made on logic (a component that is the same for every
   angle, a signal that measures Twitch instead of the topic) and stamped with
   `GRADE_VERSION`; statistical retuning waits for n≈85. `ops calibration` prints the n
   each correlation still needs.
6. **Pull the facts the pipeline already finds (#848)** and **measure something per angle
   (#849)**. Run 98 read only the pages the operator pasted, and scored five angles
   identically because nothing about an angle is measured.
7. **Operator time is the other volume cost.** Run 98 took 11.2 operator minutes, 7.9 of
   them at the key-facts prompt. The app's next slot is the facts room (#860,
   [desktop_app.md](desktop_app.md) Stage 3) - the first app work this plan schedules.

**Exit:** predictors off the volume gate on at least one channel - **met on tapin
2026-09-26** (the card's predictor printed n=23 in run 98) - and every recommendation
surfaced with its sample size.

---

## M5 — Reach (deliberately last)

Multi-platform publishing (TikTok keys present and unimplemented, then Reels), long-form
deep-dive mode on MoneyWise, clip-from-source, storyboard. All were correctly deferred
behind captions and grounding, and both of those have since landed — so this wave is now
*unblocked*, not *ready*. It stays last because reach multiplies whatever quality and
verification exist underneath it, in both directions.

---

## Parked, with the reason

Carried from [handoff_synopsis.md](handoff_synopsis.md) so that "parked" is a decision
with a stated condition, not drift:

| Item | Parked because |
|---|---|
| #146 tray daemon | No operator need yet (#147's FastAPI shell shipped 2026-08-28; the XL apps became the [desktop_app.md](desktop_app.md) programme) |
| Phase M (Instagram + TikTok linking) | Belongs with M5, not before |
| NVENC, CUDA torch build | Waiting on a `2.8.0+cpu` → CUDA rebuild, not on hardware |
| Heavy Pillar 6 backends | Seams live; blocked on the same CUDA build |
| Edge TTS as the default voice | decisions §28: shipped as an unmodified `[free]` extra, never the default; Piper judgement first |
| `SCENE_MATCHED_BROLL` on TapIn, Coverr as a quality lever | [decisions.md](decisions.md) §26 — more unrelated stock is not a quality lever |
| Flipping TapIn to `background_mode: local` | Operator call, pending owned-gameplay volume |
| Merging `origin/claude/docs-optimization-review-a4l104` | 9 commits, no PR, old base, last touched 2026-07-21 — same shape as #27 |

**Standing operational items** (not waves, but not forgotten): reinstall the venv after
the Pillow 11.3 / requests 2.32.4 / moviepy-drop pin change before any real render;
re-auth `youtube.readonly` for tapin; `oauth_setup` for MoneyWise.

---

## How this plan stays honest

1. **Every rule is a check.** If a wave's exit criterion cannot be a command, the wave is
   specified wrong.
2. **Baselines ratchet one way.** mypy count, `LEGACY_NAMES`, doc size ceiling — each
   may shrink, never grow. A baseline nothing enforces is a number that grows (§1.2).
3. **This doc is `living`; the evidence is `frozen`.** When the situation changes, edit
   here and write a new dated audit — never edit [audit_2026-09.md](audit_2026-09.md).
4. **A wave is done when its exit command passes**, not when its items look done. That
   distinction is the entire subject of the audit.
