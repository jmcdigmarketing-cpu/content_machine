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
