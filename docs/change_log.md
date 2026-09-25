# Content OS — Changelog

> **Class:** log · **Status:** frozen · **Reviewed:** 2026-09-20

Initial changelog summarizing major modifications present in the codebase as of documentation generation. Versions are grouped by theme rather than release tags (the project does not yet use semantic versioning or tagged releases).

---

## [Unreleased] — Content OS evolution (2026)

### Run 74 — the abort chain, and facts that stop being truncated - 2026-08-29

*2515 tests green, ruff clean, mypy unchanged in the touched files. TapIn Standard run
id 74 (GTA 6 extended look, Long). Drafted, not rendered — the run was discarded by a
stray word before render.*

- **A two-letter word threw away the run.** The operator pasted a 403-blocked article at
  the **Fact** prompt (where it belongs). The prompt reads one line per `input()`, the
  article's first blank line ended intake after two lines, and the rest sat in the
  Windows console buffer answering later prompts. `Proceed?` got **`by`** — Engadget's
  byline label — and `_looks_pasted("by")` is `False`, so candidate 325's re-prompt
  never fired. Fixed at all three points: `core/console_input.py` (new) exposes
  `input_pending` / `read_pending_lines` / `drain_stdin`; a blank line ends fact intake
  only when nothing is buffered, and leftovers are **offered back as facts**; `Proceed?`
  now stops only on `n` / `N` / `no` / Enter and drains stdin before asking.
  **Contract change:** a stray keystroke re-prompts instead of stopping — the deliberate
  run-71 rule, overturned by evidence.
- **Facts are no longer cut mid-sentence.** `_MAX_KEY_FACT_CHARS` was a runaway-blob
  guard implemented as `line[:400]`, producing lines like *"…will progress through a
  chapter-based"* — which reads to a model as a finished, vague statement rather than a
  truncation. It is now a splitter (`split_at_sentences`); a single over-long sentence
  survives whole, and only punctuation-free blobs are cut, at word boundaries, marked
  elided. The display lied the same way (`{ex[:90]}` with no ellipsis at all); `_elide`
  now names the hidden character count.
- **The prompt budget ranks instead of truncating.** Of run 74's 54 packed facts ~15
  were article furniture (*"Below, you'll find everything shown off…"*, *"Check out the
  five biggest takeaways below."*) while the six wanted stars, the Slim Jim minigame and
  the 80-hour playthrough sat in the dropped tail. `core/fact_selection.py` pins
  operator-typed facts, penalises scaffolding (never blacklists — a furniture line with
  a hard number still competes), and ranks the rest on recency (heaviest), novelty,
  specificity and relevance, reporting every exclusion. Link facts now carry the page's
  own publication date, without which "weight recency heavily" had no input.
  **Measured:** `score_vault_fact` scored the Slim Jim mechanic at **0.03** — it rewards
  echoing the signal corpus, which is backwards for a pasted article whose whole purpose
  is to add what the signals lack. Hence `novelty`, and hence relevance being the
  smallest weight.
- **Two gates disagreed about the same phrase.** `persona lint: but here's the thing` and
  `original_insight: has an authorial take ('here's the thing')`, four lines apart — the
  second is why the script scored authenticity 100/100, for a phrase banned by the linter
  *and* by the script prompt. Removed from `_INSIGHT_MARKERS`; `test_gate_agreement.py`
  keeps the three lists honest. The lint hit also now reaches the screen before
  `Proceed?` instead of only the log.
- **277 words against a 300-word floor, graded A.** The expansion loop runs before every
  pass that can shorten a script, so its exit condition was checked against text the
  operator never saw. `_relength_after_postprocessing` re-checks afterwards and reverts a
  late expansion that reintroduces unsupported specifics. *Not* fixed: the report card
  still does not weight length — adding a component would change every historical grade.
- **Two dead signals cost 30 of a 37.8s discovery.** `trendingnow.games` retired per
  decisions §19 (reason recorded in `apis/signals_bootstrap.RETIRED_SIGNALS`, module
  kept). `youtube` and `youtube_comments` each waited out the full 15s socket timeout
  against the same unreachable endpoint — cut to 8s, plus a process-level latch so the
  second call fails fast. A read timeout is transient, so the session breaker never fired.
- `link_facts` now sends browser-shaped headers (clears naive 403s, not a real WAF) and
  reports how many lines of a page it kept.

### Audit of the 2026-08-26 wave + a working agreement - 2026-08-26

*2118 tests green, ruff clean, zero `data/` mutation. All three findings were **green in
CI** - the fourth audit running for which that is true. Documented, not fixed:
candidates 326-328.*

- **The dependency wave was declared but never installed.** `pyproject.toml` moved to
  `Pillow==11.3.0` / `requests==2.32.4`; the environment still runs **9.5.0 / 2.32.3**.
  So the 26 Pillow CVEs are live on the machine that parses untrusted stock-footage and
  thumbnail bytes, **CI now runs a different Pillow major than the operator**, and the
  upgrade's entire risk - does the render still work - is untested because nothing has
  run on 11.3.0. The moviepy cut itself was done correctly
  (`_probe_video_duration` reused, `AudioFileClip` mocks removed), and moviepy 1.0.3 is
  still installed though nothing imports it. #326.
- **`spoken_numbers` mangles ranges on every render, with no off switch.** Measured:
  "5-10 years" -> "five ten years", "10-15%" -> "ten fifteen%", "9-5" -> "nine five".
  It runs unconditionally in `generate_audio` for every channel, so it is worst on
  **MoneyWise** - all ranges and percentages, and freshly given its own voice.
  `core/fact_grounding.py:47` had already solved that exact ambiguity 40 lines away by
  requiring a verb cue. The three shipped tests use no range and no percent. #327.
- **One bad match silently disables the whole expansion.** `UFC 2000` raises
  `IndexError`; the call site swallows it at `logger.debug`, so at the default WARNING
  level the operator sees nothing and *every* expansion stops for that script.
  decisions §24 shape. #328.

**What went right, recorded because a one-sided audit is not honest.** Cursor respected
the Edge TTS licence park (LGPL-3.0, pending a legal read) even though it was the top
item on its own list - `edge_tts` appears nowhere. It extended test isolation to a class
nobody had noticed (`DATABASE_URL` / `DATABASE_KEY` blanked before import,
`TOPIC_GRAPH_FILE` in the store patches, plus its own tripwire test). It improved on the
commit-msg hook by adding `prepare-commit-msg`, which strips an injected trailer instead
of only rejecting it. Every new `core/` module has a real production caller.
`demonetization.py` opens with "Missing is not $0". And in
[decisions.md](decisions.md) §26 it **overruled a Claude Code recommendation with
measured evidence** - Coverr, ranked the #1 borrow, does not fix TapIn's visual problem,
because ~55% of runtime is already stock behind a hard concat and a fourth keyword API
diversifies the same class of footage.

**New:** [agent_collaboration.md](agent_collaboration.md) - the doc to point an agent at
before starting a project. Who decides what gets built (the operator; §26 is why),
what each agent is reliably good and bad at including Claude Code's own misses, and the
one pattern behind both findings: *ask what else this catches, and whether the edit
actually took effect*. Distilled into two new rules in `.cursor/rules/content-machine.mdc`
and linked from `AGENTS.md`.


### 21-28 render wave + its audit - 2026-08-25

The aesthetics block every prior wave deferred as "needs a real render" (21 caption
skin, 22 safe-area, 23 end card, 24 lower thirds, 25 colour grade, 26 hook motion,
27 dual thumbnail, 39 draft preset). Committed as written, then audited. **Four
defects, none of which failed CI** - the same shape as the last two passes.

- **Lower thirds could never have rendered on Windows.** The filter graph carried two
  `subtitles=` entries escaped differently: the captions quoted manually
  (`'C\:/...'`), the lower third via Python `repr` (`'C\:/...'`). `repr` escaped
  the backslash `_escape_subtitle_path` deliberately puts before the drive-letter
  colon. Proved against real ffmpeg rather than argued - old form `-22 Invalid
  argument`, new form exit 0. `force_style` had the same `repr` bug, plus repr flips
  its delimiter to `"` on any apostrophe. **Green because the only test reaching that
  code passed `lower_thirds_path=None`** - the feature was switched off in the test
  covering it.
- **Hook motion and lower thirds were dead on the $0 local-TTS path.** The render read
  word timings from the ElevenLabs `.words.json` sidecar only; the whisper ->
  `retext_words_from_script` path lived inside `generate_subtitle_file` and never
  returned its result. On Piper / Free-mode runs both features silently no-opped while
  the captions burned into the same render carried real whisper timings. The skip note
  misread its own cause ("no real first-cue timing" when nothing had asked the
  aligner). `video.subtitles.resolve_word_timings` is now the shared seam, resolved
  once per render.
- **`ThumbnailSafeAreaCheck.threshold` did nothing** - `inspect_thumbnail` hardcoded
  18.0, so a caller passing its own value got default behaviour with a misleading
  number attached. Now a real parameter.
- **Both channels were pinned to one voice.** `validate_channels` had been warning;
  nothing acted. That undercuts the MoneyWise persona shipped the session before -
  "calm, plain-spoken" and "high-energy, irreverent" read by the identical synthetic
  voice, and channel-level sameness is what the 2026 policy assesses. MoneyWise moved
  to `XjLkpWUlnhS8i7gGz3lZ` (already in the default pool, so known-good against this
  account). Warnings 3 -> 2, both expected. **Listen to one sample before publishing.**

Also: the AI-attribution rule is now enforced by `.githooks/commit-msg`, not prose.
`e4d2242` landed a Cursor co-author trailer the commit *after* the rule was written
into `.cursor/rules`, which settles whether a paragraph is sufficient. Human co-authors
are unaffected; enable per clone with `git config core.hooksPath .githooks`. The
existing trailer stays in pushed history - not worth a force-push.


### Wave-4 audit: three green-but-broken fixes + agent rules - 2026-08-23

*Every defect below passed CI. None was a crash, a lint error, or a failing test.*

- **#292 quiet-hours toast DND muted nothing.** `_toasts_muted()` called
  `quiet_hours_reason()` with no channel; that resolves to `default`, which has no
  `quiet_hours` block (only `tapin`/`moneywise` do). Measured:
  `quiet_hours_reason(channel_id="tapin", when=3am ET)` returns a reason,
  `quiet_hours_reason(when=3am ET)` returns `None`. **It passed CI because the test
  mocked `quiet_hours_reason`** - proving "given a reason, mute", never that a reason
  could occur. Now resolved machine-level across every configured channel; breaker
  toasts pass `urgent=True` and bypass DND, since the overnight batch runs inside the
  1-8am window. `tests/test_toast_dnd.py` drives the clock and leaves the channel
  lookup live; it fails against the old code.
- **The public `Sources:` block cited off-topic notes.** It collected vault URLs with
  the default loose relevance - the gate that on run 71 attached Marvel Rivals and SEGA
  notes to a GTA 6 story. A description is public, so that is a visible error, not
  prompt noise. Vault path now requires a topic-distinctive token; pasted URLs are
  untouched. The ambiguous-token case is asserted as a **known gap** rather than
  claimed fixed - candidate 324's deferred vault-side sibling.
- **`docs/vault_templates/_sources.md` used the wrong frontmatter key.** It told
  operators to write `source_url:`; `note_metadata` reads `source:`. Every note copied
  from the shipped template lost its provenance URL and could never reach the Sources
  block. From candidate 34, and the test missed it for the same reason as #292: it
  asserted a *key existed* instead of asserting the parser extracted a URL. Template
  now uses the canonical `source:`, `note_metadata` accepts either so notes already
  written still resolve, and the test goes through `note_metadata`.
- **Agent rules, so this stops recurring.** [AGENTS.md](../AGENTS.md) and
  [.cursor/rules/content-machine.mdc](../.cursor/rules/content-machine.mdc) - Cursor
  never read `CLAUDE.md`, so it had been working without the repo's rules. They lead
  with the four green-but-broken defects and the rules that catch them: never mock the
  thing under test, watch the test fail first, assert behaviour not shape, exercise the
  shipped config, every helper needs a real caller.
  `docs/cursor_audit_prompt.md` is marked stale (it still cited a 363-test baseline).


### Honesty + leave-the-terminal wave 4 — 2026-08-22

*20 leftover `[S]` on the honesty / leave-the-terminal / operator-safety
theme. FastAPI #147 and tray daemon #146 still skipped.*

- Playbook lint (`ops playbook-lint`) warns when untagged strategy-shaped
  bullets also look fact-anchored (rank / year / `$`) — those currently feed
  `load_facts` as ground truth.
- Description **Sources:** block from vault `source_url` + pasted http(s)
  (`DESCRIPTION_SOURCES`).
- Booth: ungrounded numeric chips, authenticity semantic bar, grade
  breakdown, TTS cache-hit $0, Pillow vs Flux badge, signal-health dots,
  feed-stale strip (cached `ops feeds` only), overnight-render / RPM-deferred
  / yesterday-unsynced copy, copy unlisted URL + Obsidian dossier URI +
  postmortem markdown, sticky cost (`#costbar`) + quota (`#quotabar`), 16px
  type on buttons/inputs.
- Tray chip `Domain: UFC|GTA|NBA` (`CONTENT_TRAY_DOMAIN`). Toasts mute during
  quiet hours (`CONTENT_TOAST_DND`).
- `ops postmortem --md`. Post-render features/trace now record `tts_cached`
  and `thumbnail_provider` (not folded into cost totals).

### Live-run 71 documented — 2026-08-22

*TapIn Standard run id 71 (GTA 6 leak / Wolverine angle). Drafted, not rendered.*

- Operator pasted article/ad clipboard text at **Proceed?** (treated as stop) then
  at the PowerShell prompt (`CommandNotFoundException` on `Fast`, `Sponsored`,
  `user(s)`, store headings). Not a CLI crash. Write-up:
  [debugging.md](debugging.md#live-run-71-2026-08-21--pasted-article-hit-powershell-not-the-cli).
- Same run: MSN link scrape headline-only; vault auto-attached off-topic
  Marvel/SEGA bullets; YouTube + youtube_comments timed out; `trendingnow.games`
  unreachable.
- Claim verifier logged **7/12 unsupported**, then the claim-rewrite pass
  (`_maybe_rewrite_unsupported_claims`) restated them as attributed speculation
  and the re-check printed **12/12**. Same check, rewritten script — the claims
  were hedged, not evidenced. Corrected an earlier note that called these two
  different checks.
- Quality observations recorded, **not fixed**: the generated title attributed
  the subpoenas to Rockstar when the operator's own fact says Take-Two (titles
  run after every check and are never verified); RAWG matched three 1990s
  Wolverine games into the corpus behind the authenticity gate's "18 verified
  fact(s)"; all five angle variants tied at 100.0; 30.6 min wall (25.6 at
  prompts) produced no video.

### Living-doc sync + live-run 69/70 — 2026-08-20

*Honesty/cost wave after PR #34. Pickup is now the recommended next 5 on
[roadmap.md](roadmap.md).*

- **Run 70:** Free mode advertised `llm=ollama OK` with zero models pulled;
  discovery ran 71s then 404'd. `_ollama_ready` delegates to
  `llm_router.ollama_installed_models`. `ops free-doctor` distinguishes **pull**
  vs **serve** vs OpenRouter throttled fallback.
- **Coverage wave (partial):** `process_one` quota gate, `_defer_for_quota`, and
  `build_render_ffmpeg_command` (music bed under VO, VO-only identity, `-t`,
  subtitle escape, bed-mix retry). Remaining: `youtube/oauth.py` tests + `coverage`
  extra.
- **Semantic authenticity:** content-word cosine paraphrase arm
  (`AUTHENTICITY_SEMANTIC`, default-on, warn-never-block).
- **Router vision:** `llm_router.complete` accepts OpenAI-style image parts;
  thumbnail scorer uses the extract tier. `core/llm_client.py` deleted.
- **Docs:** living set (HANDOFF, architecture, project brief, assessment addendum,
  audit A1–A2/C1/C4, this changelog, operating_plan §9, CLAUDE.md Apify count,
  free_mode) synced to 20 Aug. Roadmap gained recommended next 5 + candidates
  56–90 (viability / short-term success / real-world cost). Phase M still parked.

### Branch + PR triage; the stack goes up as PR #34 — 2026-08-17

*Six weeks of work had never been reviewed or CI-validated. Suite 1433 green.*

- **21 commits opened as a single PR** (`feat/trade-validation-default-on` 6 →
  `feat/research-intake-repair` 15). It merges cleanly; merging to `main` is left to the
  operator.
- **CI paid for itself on the first run.** It had never executed on any of these commits —
  `.github/workflows/ci.yml` fires only on push-to-`main` and `pull_request` → `main` — and
  immediately failed with 3 errors: `test_caption_align` patched the **real**
  `torch.cuda.is_available`, but torch is in the optional `[providers]` extra, so those
  tests only ever passed on a machine that happened to have it. Now injects a fake torch
  and covers the absent-torch case. *Rule: never patch an optional dependency's real
  module in a test.*
- **All seven stale PRs closed (#26–#32), every branch deleted.** #27 was the dangerous
  one — superseded, and it still carried the expired `"2026-07-25 18:00"` that #33
  replaced, so merging it would have made CI permanently red.
- **Five orphan docs harvested before closing** (~1,000 lines that existed nowhere else):
  `llm_provider_strategy.md`, `strategy_2026H2.md`, `next_ideas_2026-07.md`,
  `code_audit_2026-07.md`, `efficiency_audit_2026-07.md`. Only the new files were taken —
  their edits to shared docs were superseded, which also avoided every conflict — and each
  carries a dated header naming what has since replaced it.
- **Hardened `tests/test_alembic_logging.py`**: it disables every logger on purpose to
  prove the footgun is real, and the restore was written *after* the assertion. A failure
  in between would have left the logger tree disabled for all later tests, silently
  breaking their `assertLogs`. The restore is now an `addCleanup` registered first.

### The intro step can no longer lose a render — 2026-08-17

*First step of the render/publish coverage wave (paused part-way — remaining design is
in [roadmap.md](roadmap.md) under the `[~]` entry). Suite 1432 green.*

- **`prepend_channel_intro` could destroy a just-rendered video.** It moves the finished
  mp4 aside (`os.replace` to a `.body.tmp.mp4`) before ffmpeg concatenates intro + body
  back to the original path, and the restore ran **only on a non-zero exit code**. ffmpeg
  missing from PATH raises before any exit code exists, so the render stayed parked under
  the temp name while `render_vertical_video` logged *"Channel intro skipped (render
  kept)"*. The pipeline then recorded an `mp4_path` with no file behind it, surfacing much
  later as an "invalid file" upload failure.
- Reproduced before fixing — the test failed with *"rendered video vanished from its
  path"*. The window is now a `try/finally` covering a non-zero exit, a raising
  subprocess, an empty output and Ctrl-C, and the output is checked for existence and
  non-zero size before the temp copy is deleted (exit 0 is not proof of an output).
- `tests/test_channel_intro.py` (15): the failure window, the success path, the concat
  command (a **silent** intro must still get synthesized `anullsrc` audio, or concat drops
  the track and the voiceover slides earlier by the intro's length), and resolution order.
- Also corrected `_probe_duration(...) or 3.0` → an explicit `None` check; `0.0` is a
  probe answer, not a miss.

### Fail-open made fail-visible — 2026-08-16

*The audit's "real debt", paid down. Suite 1421 green.*

- **All 98 silent handlers now log** (90 `try/except/pass` + 8 `try/except/continue`), and
  **`S110`/`S112` are enabled in ruff** so a new bare swallow fails CI. `BLE` stays off —
  it would flag all 420 broad handlers, and the correct ones outnumber the wrong ones.
- **Level policy over blanket-debug** (decisions §24). `CONTENT_LOG_LEVEL` defaults to
  `WARNING`, so the audit's own "add a `logger.debug` everywhere" would have produced 93
  lines nobody reads. `warning` where a guarantee is lost — `quota_governor.llm_add_spend`
  (a lost write makes the daily-budget guard under-count spend and stop guarding) and
  `pipeline`'s `write_run_trace` (a miss blinds `ops traces`, `ops dossier` and
  `data_quality` for that run); `debug` for best-effort enrichment.
- **Silence is tested too** — `tests/test_fail_open_visibility.py` asserts the warnings
  fire *and* that a healthy run emits none, because a warning that always fires teaches
  the operator to ignore warnings.
- **Migrations were switching off logging.** `alembic/env.py` called `fileConfig()` with
  the default `disable_existing_loggers=True`, disabling the entire `content_machine.*`
  tree; `migrate_schema` runs `upgrade_head()` in an ordinary process, so every log line
  after a migration was dropped in silence. Fixed and pinned
  (`tests/test_alembic_logging.py`) — found only because the new tests passed alone and
  failed under `unittest discover`.

### Captions spelled by the script, timed by whisper — 2026-08-16

*The last thing standing between the project and a $0 voiceover. Suite 1411 green.*

- **`video/caption_retext.py`** — whisper supplies the timing, the script supplies the
  words, aligned with `difflib.SequenceMatcher` (decisions §23). Local-TTS captions had
  been burning ASR text, which misspells precisely the fighter and game names the channel
  is about: run 65 rendered "Salkal" for "Salkilld" and "Mattius Gamarat" for "Mateusz
  Gamrot". One branch in `video/subtitles.py` wires it; the ElevenLabs sidecar path is
  untouched.
- **The matcher handles re-tokenisation, not just spelling** — whisper splits words
  (`Quillan` → `Quill and`), writes numerals as words (`10` → `ten`), and drops or invents
  tokens, any one of which desyncs a positional comparison permanently.
- **Free in timing, measured** — run 66 (243 words): word error p50 42→43ms, caption
  line p90 **117ms → 117ms**, while covering **243/243** script words instead of the
  243-of-251 whisper transcribed cleanly, and correcting **12 misheard words**.
  `scripts/bench_caption_align.py` gained `+retext` columns and now shares one matcher
  with the shipped code instead of its own lookahead walk.
- **Declines rather than guesses** — below `CAPTION_RETEXT_MIN_MATCH` (0.35, chosen from
  measurement: real audio 0.87, unrelated ~0.0) it returns None and captions fall back to
  the proportional estimate, since a transcript that doesn't match the script carries
  timings for different audio.
- **$0 path proven end to end** — a full Piper render with retexted burned captions was
  produced and checked as pixels. **Nothing was switched:** ElevenLabs stays the default
  pending the operator's voice judgement and a `bench_script_duration` re-run (Piper reads
  ~20% slower).

### Silent-failure repair — six waves — 2026-08-14/15

*Six roadmap passes that kept converging on one shape: **things were failing quietly and
reporting "nothing found" instead of "I am broken"** (decisions §18). Nothing crashed;
every run looked fine. Suite 1377 green.*

- **Research intake repair + source health** — Tapology retired (Cloudflare 403 for 33
  days while reporting "no event match"); **11 of ~37 RSS feeds** were dead and replaced
  with live-verified ones (**37/37 ok**); the Federal Reserve feed was alive but lost to a
  **UTF-8 BOM** parse error (`rss_feeds.decode_feed_bytes`). New `core/feed_health.py` +
  `ops feeds` classify ok/**stale**/dead with newest-item age, wired into `all-checks` and
  `ops reliability`. `apis/mma_stats_api.py` (API-SPORTS MMA) replaces Tapology's
  structured fighter data.
- **`twitter` retired** — `inactive` on **19/19 run traces**, never produced a fact, and
  as the slowest signal (~32s) it set the wall-clock floor for every discovery.
  `apify_client.is_no_results()` now reports a sentinel payload as a failure.
- **`youtube_comments` signal + O12 complete** — wired against the **official Data API**
  (~1 unit/video) rather than the catalog's billed actor; surfaces unanswered audience
  questions, labelled *unverified* so a viewer's guess can't become a claim. YouTube units
  moved under the governor scope, and `core/reliability_history.py` adds the daily trend
  the dashboard's snapshot could never show.
- **Post-render cost persisted** — both render paths finalized a run *before* rendering,
  so `features_json.cost.tts` was `0.0` on every rendered run and contribution margin was
  overstated by its largest component. `ops economics` went from *$0.32 total ($0.02/video)*
  to **$6.18 ($0.31/video, TTS 91%)**; `ops backfill-cost` repaired 38 historical runs.
  TTS repriced from the operator's real plan ($0.22/1k, not a $0.30 guess) — decisions §22.
- **Whisper CPU caption backend** — `faster_whisper` in `core/caption_align.py`, measured
  against ElevenLabs sidecars at **43–56 ms** median caption line-start error, 12–15×
  realtime. Landed deliberately **half-done**: captions still carry ASR text, which mangles
  proper nouns, so the $0 TTS switch stays blocked.
- **Run-66 fixes** — duration estimates were **38% wrong** (`WORDS_PER_SECOND` 2.4 vs a
  measured 3.32); a false hallucination alarm (`"If Netflix"`) cost a run a grade while the
  claim verifier said 12/12 backed; a timeout reported as a hard ERROR; an off-topic
  audience question; and both cheap-tier LLM slugs were dead ends — one **hardcoded**, so
  `.env` never fixed it (decisions §20, §21).
- **Earlier in the same session** — Alembic `0004` `content_run` foreign keys (836 sentinel
  rows preserved as `NULL`), vault fact-contamination cleanup, test-suite vault isolation,
  and O12 part 1.

### Pillar 5 — Agent layer — 2026-07-07

*Fifth/final pillar (decisions §15): agents that compose Pillars 1–4 into
verdicts and actions. All read-only + fail-open. Suite 869 green.*

- **Channel Health Agent** — `core/channel_health.py`: one Green/Yellow/Red per
  channel from six rules-based sub-scores (engagement trend vs baseline, cadence
  headroom, authenticity trend over `quality_json`, reliability breakers, cost/
  margin, data-quality warnings), each with a rationale; folds worst-first, thin
  data holds yellow (never green). `ops health` + added to the `daily-brief` batch.
- **Weekly analyst agent** — `core/analyst_agent.py`: bounds a context (weekly
  report + grade calibration + health + recent run traces + economics) → **premium**
  LLM tier → <220-word briefing with 3–5 concrete lever changes; writes
  `{channel}/_reports/{date}_analyst.md` and emits the `analyst_briefing` webhook.
  Fail-open to the weekly report's rules-based next-actions on any LLM/assembly
  error (no context ⇒ no spend). `ops analyst`.
- **Overnight operator** — `core/overnight.py`: best-bet topics → `run_batch`
  (graded + verified drafts, render-free ⇒ cadence-safe) → vault dossiers → health
  snapshot → `overnight_completed` webhook. `ops overnight` (`--count`/`--file`);
  schedulable like `daily_sync`.
- **Supporting:** `vault_dossiers.write_report_note()` generalizes the weekly-note
  writer (analyst notes reuse it, `fenced=False` for prose). Verifier stage already
  landed with Pillar 3.
- Tests: `tests/test_pillar5_agents.py`; `test_themes` daily-brief step list updated.

### Live-run fixes — TapIn sports drift + link/grounding hygiene — 2026-07-07

*Second live-run intake (NBA 2027 standings on TapIn): script drifted to Marvel
Rivals esports while operator key facts were NBA. Suite 860 green.*

- **Domain from key facts** — `infer_domain(..., key_facts=)` expands NBA topic
  keywords (`standings`, `award race`, `mock draft`, `power ranking`, …) and
  lets pasted NBA/NFL facts override the TapIn `gaming` channel default
  (`apis/topic_scorer.py`).
- **NBA/NFL script matrices** — `build_script_brief(..., key_facts=)` injects
  real-sports rules and suppresses the channel's "Primary franchise focus"
  gaming nudge on sports runs (`core/script_brief.py`, wired in
  `content_engine.generate_content_package`).
- **Video-game drift recenter** — `_video_game_drift()` + extended
  `_maybe_recenter_on_key_facts()` regenerate when the script pivots to
  Marvel Rivals / esports while key facts are NBA/NFL/UFC.
- **Link scrape guards** — block Bing search/captcha URLs, unwrap Bing `ck/a`
  redirects to the destination, reject junk titles ("Robot Challenge", "
  - Search"), cap article lines at 12 (`core/link_facts.py`).
- **Playbook noise** — filter "short-form punchy…" / "retention pivot…" from
  vault suggestions and link facts (`operator_facts`, `obsidian_facts`).
- **Mononym false positives** — skip common sports-script words (`Meanwhile`,
  `Rookie`, `Bottom`, …) in token grounding (`core/fact_grounding.py`).
- Tests: `tests/test_domain_key_facts.py` + extensions to link-facts, key-fact
  anchor, fact-grounding, operator-facts suites.

### Pillar 4 — Obsidian knowledge OS — 2026-07-07

*Fourth pillar (decisions §17b): the vault stops being a one-way sidecar. Runs
flow back into it as browsable dossiers, reads are cached, and strategy notes
finally have a read path. Suite 846 green.*

- **Run dossiers** — `core/vault_dossiers.py` writes `{channel}/_runs/{date}_
  {slug}-{id}.md` (topic, angle, report-card grade, quality summary, cost,
  script, post-sync actuals + video URL). Fail-open call in
  `pipeline._finalize_run` (module-level import — patchable in tests);
  `refresh_dossiers()` upserts actuals via `daily_sync` + `ops vault-sync`;
  weekly report copied to `{channel}/_reports/{date}_weekly.md`.
- **Vault index** — `core/vault_index.py`: per-process, mtime-keyed parse cache
  behind `obsidian_facts.load_fact_records()`. Unchanged notes are `stat()`ed,
  not re-read (batch-drafts re-called `load_facts` per idea). No on-disk index —
  avoids `data/` growth + cross-run staleness. Parsing byte-identical, so
  ranking/filtering unchanged; `tests/test_obsidian_facts.py` passes untouched.
- **Playbook layer** — `obsidian_facts.load_playbook()` + `playbook_block()`
  read exactly the strategy/belief bullets `load_facts` excludes and inject a
  bounded, clearly-non-factual "CHANNEL PLAYBOOK" block into the script prompt
  (beside the persona block; `""` without a vault). Fixed `_is_strategy_note`
  tag parsing (`_tag_set` strips `[ ]`/quotes — `[strategy]` notes were only
  excluded via their bullets before).
- Dossiers/reports live under `_runs/`/`_reports/`, excluded from `load_facts`
  (`_is_machine_record`) — records of what we made, never read back as facts.
- Tests: `tests/test_vault_pillar4.py`; pipeline smoke + key-facts injection
  tests isolate the vault (`OBSIDIAN_VAULT_PATH=""`).

### Pillar 3 — Fact Engine 2.0 — 2026-07-06

*Third pillar (decisions §16): facts gain provenance + TTL, the grounding corpus
gains trust tiers, and scripts get claim-level verification with an optional
gate. Every layer fails open. Suite 833 green.*

- **Structured fact store** — `core/fact_store.py`: `FactRecord`
  `{claim, tier, source_url, verified_at, expires}` from vault note frontmatter
  (no new DB); `obsidian_facts.load_fact_records()` drops expired notes and
  ranks relevance-first with a provenance+freshness tiebreak (bonus capped
  below one overlap token); `load_facts()` keeps its `list[str]` contract.
  Writers stamp frontmatter: operator capture → `tier: operator` +
  `verified_at`, `_sources.md` → `tier: link`.
- **Tiered grounding corpus** — `core/grounding_tiers.py`: every corpus line
  tagged `operator|link|web|signal|brief|context` (`full_text` byte-identical
  to the legacy corpus); YouTube titles/descriptions are context, not facts —
  entities grounding only there warn "treat as unverified"; high-stakes
  sentences (results/trades/records/champions) backed only by web/brief warn.
- **Claim-level LLM verifier** — `core/claim_verifier.py`:
  `verify_claims(script, facts)` on the extract tier → per-claim
  `{claim, supported, citation_line}`; default-on
  (`CLAIM_VERIFIER_ENABLED=false` to opt out), fail-open;
  `GROUNDING_GATE=warn|block` mirrors the authenticity gate in `main.py`
  (override prompt) and `auto_generate` (`--force`).
- **Pre-script contradiction detection** — `core/fact_conflicts.py`:
  trade-direction / reversed-result / champion conflicts between operator key
  facts and the signal+web corpus, caught **before** the LLM call; operator
  wins — losing source lines dropped (`FACT_CONFLICT_FILTER=false` keeps
  them); conflicts always reported.
- **Web-source capture** — `capture_web_sources()` writes `web_search` result
  URLs to `_sources.md`, where they re-rank as `link` tier on related topics.
- **Quality v2 + grading** — `quality_json` version bumps to v2 with
  `claim_support_rate`, `unsupported_claim_count`, `fact_conflict_count`,
  `tier_warning_count`; `video_grade` grounding component penalizes each;
  dossier, batch `meta.json` + summary, and the interactive Fact Engine report
  (`core/ui.display_fact_engine_report`) surface them.
- Tests: `tests/test_fact_store.py`, `tests/test_grounding_tiers.py`,
  `tests/test_claim_verifier.py`, `tests/test_fact_conflicts.py` + v2/penalty/
  pass-through coverage in the run-ledger, video-grade, pipeline, and
  source-capture suites.

### Pillar 2 — Video Grading System — 2026-07-06

*Second pillar (decisions §15): the six scorers roll up into one calibrated
grade. Data-gated stages ship structurally and activate with volume. Suite 761
green.*

- **Report card** — `core/video_grade.py`: weighted 0–100 + letter over the
  persisted quality dict (hook/authenticity/grounding/topic/thumbnail, missing
  components renormalize); interactive flow shows it before the render prompt;
  `ops grade --run-id N`.
- **Predicted engaged-rate (data-gated)** — `core/engagement_predictor.py`:
  explainable baseline+slopes model over measured runs with quality;
  `PREDICTOR_MIN_SAMPLES` (default 15); prediction frozen into `quality_json`
  at generation time.
- **Calibration loop (data-gated)** — `core/grade_calibration.py`: realized
  percentile per graded run, grade↔engagement Pearson r, prediction deltas,
  and the first reader for `thumbnail_scores` (overall vs engaged-rate);
  `ops calibration` + a weekly-report line.
- **`core/analyst_accuracy.py` realigned** — backtests engaged-rate (the
  loop's objective) when ≥5 measured runs carry it; views stay as a labeled
  legacy fallback.
- **Prompt-evolution eval set** — `core/prompt_evals.py` +
  `config/prompt_evals.json`: frozen golden topics/facts + heuristic rubric v1
  (hook, ungrounded-vs-frozen-facts, length fit, filler count); results saved
  to `data/prompt_evals/` tagged with `prompt_version`; `ops prompt-eval`
  runs, `--compare` diffs the last two.
- Tests: `tests/test_video_grade.py` (grade math, predictor gating + direction,
  calibration correlations, rubric, accuracy realignment).

### Pillar 1 — Run Ledger (metadata spine) — 2026-07-06

*First pillar of the internal-systems reorientation (decisions §15): the run
metadata that used to be write-only or in-process-lost is now persisted and
readable. Suite 743 green.*

- **Per-run trace** — `core/run_trace.py` writes `data/traces/<run_id>.json`
  from `_finalize_run` (fail-open): phase timings, per-signal status, the priced
  LLM call ledger, post-discovery cache counters (new
  `cache_manager.session_cache_stats()`), experiment arm (new
  `experiments.assignment_for_run()`), quality dict.
- **Quality persistence** — new `content_runs.quality_json` column (models,
  `migrate_schema`, Alembic `0003`); `core/run_quality.py` builds + persists
  hook/authenticity/grounding/trade quality for every generation path in
  `_finalize_run`; thumbnail score merged post-render via `merge_quality`.
- **Viewers** — `ops traces` + `ops dossier --run-id N` (`core/run_ledger.py`):
  recent-run table with hotspots, and a single joined run view (features,
  quality, cost, publish metrics, margin, experiment arm, LLM calls).
- **Data-quality monitor (was Phase V)** — `core/data_quality.py`: signal
  failure-rate + not-ok-streak checks over recent traces and
  run↔quality/features/metrics join assertions; warnings in `ops reliability`.
- **Unit economics (was Phase U)** — fail-open `estimatedRevenue` sync
  (separate query; missing monetary scope can never break the main sync) +
  `core/unit_economics.py` cost↔revenue join; `ops economics`, margin lines in
  `weekly-report`, per-video margin in the dossier.
- **Test hygiene** — pipeline-exercising tests must patch the ledger writes
  (`core.pipeline.build_quality`/`persist_quality`/`write_run_trace`) —
  documented in `tests/CLAUDE.md`; `tests/test_run_ledger.py` adds 23 tests.

### O11 complete: unified quota governor — 2026-07-06

*Closes the credit-efficiency backlog (O1–O11). Suite 720 green.*

- **`core/quota_governor.py` is now the single façade over the cross-run
  persistence store** (`core/quota_state.py` → `data/quota_state.json`). Per
  decisions.md §13 it unifies **state + persistence + reporting**, not the check
  points — the Apify global breaker, per-signal session breaker, and LLM provider
  breaker remain separate layers that now all read/write through the governor.
- **Apify migrated** — `apis/apify_client.py` `_sync_persistent` /
  `_persist_exhausted` + the O3 preflight usage cache now call
  `apify_is_exhausted` / `apify_mark_exhausted` / `apify_get_usage` /
  `apify_set_usage`. TTL/reset policy (auth 30m, 402 → O10 cycle reset) stays in
  `apify_client`.
- **LLM router migrated** — `_add_llm_spend` / `_over_llm_budget` /
  `reset_llm_spend` go through `llm_add_spend` / `llm_spend_today` /
  `llm_reset_spend`; `_today_spend_key` is a thin alias for the governor's
  `llm_today_spend_key` (key format has one owner). Budget guard stays in the
  router.
- **`snapshot()`** — one fail-open read of everything persisted
  (apify exhaustion + usage cache, LLM spend today, persisted signal disables);
  `core/reliability.py` sections now read via governor facades.
- No env/file-format changes; same scopes/keys — all pre-existing quota tests
  pass unmodified. New tests in `tests/test_quota_governor.py`: Apify facade
  roundtrips, LLM spend accumulate/reset, snapshot shape.

### Terminal UI themes + daily-brief batch — 2026-07-02

*The roadmap's "themeable skins" item, executed. Presentation-only: no pipeline
logic reads a theme, everything degrades to plain text. Suite 645 green.*

- **`core/themes.py`** — `Theme` registry: palette (16 + 256-color pairs,
  `CONTENT_UI_COLOR_DEPTH=auto|16|256` with Windows Terminal auto-detect),
  spinner frames + themed loading copy, section glyphs, meter chars, tagline,
  inline mascot, celebration key, ≥90-score hype tag. Resolution:
  `CONTENT_UI_THEME` env → channel `"ui_theme"` (channels.json, new
  `ChannelProfile.ui_theme` field, set at startup) → `default`.
- **Six skins**: `onepiece` (straw-hat palette, Luffy mascot stays), `zelda`
  (▲ spinner, heart meters, item-get celebration), `pokemon` (Pokéball spinner,
  level-up), `dbz` (Scouter copy, "IT'S OVER 9000!" at composite ≥ 90), `jjba`
  (ゴゴゴ spinner + mascot, "TO BE CONTINUED ➡" celebration), plus `plain`
  (no color/art — logs/CI) and `default`.
- **Positive-UI moments** — `meter()` block gauges in cadence, `ops reliability`
  (YouTube units), and `ops coach` (ASCII fallback on non-UTF stdout);
  `print_celebration()` themed publish flourish; `maybe_print_milestone()`
  (video #1/#5/#10/#25/... badge, fail-open); sections/banners now fill the
  terminal width (56 → up to 100 cols via `ui_theme.terminal_width`).
- **`ops daily-brief`** — 5th batch: `daily-sync` → `coach` → `reliability` →
  `status` (the morning "what should I do today" one-shot).
- Tests: `tests/test_themes.py` (registry, resolution, depth, meters, spinner
  theming, glyphs, mascots, milestones, batch). Docs + `.env.example` updated.

### 2026-07 focus wave: O10 + trade validation + creator coach + headless facts — 2026-07-02

*Closes the four "Current focus (2026-07)" roadmap items that remained after the
fact-first pipeline. Suite 613 green.*

- **O10 reset-window auto-re-enable** — `core/reset_window.py`: encodes real quota
  reset cadences (YouTube Data API daily 00:00 Pacific; Apify monthly cycle via
  `APIFY_RESET_DAY`; Odds monthly). A hard Apify **402/monthly-limit** exhaustion
  now persists until the actual cycle reset instead of re-checking every 6h
  (401/403 keeps the 30m TTL; the operator-budget trip keeps the flat TTL so a
  raised budget recovers fast). Quota-blocked YouTube uploads retry 5 min after
  the real reset. Reset times surface in `ops reliability`. Master switch
  `RESET_WINDOW_AUTO_ENABLE` (default on). Tests: `tests/test_reset_window.py`.
- **Semantic trade validation (opt-in)** — `core/trade_validation.py`: extracts
  `player → team` claims from the script and warns when the pair never co-occurs
  on a single fact line — the fused-trade failure token grounding passes (real
  Giannis→Heat fused with invented Butler→Celtics). `SEMANTIC_TRADE_VALIDATION`
  default **off** (higher false-positive rate); shown after Fact grounding in
  `main.py` + `auto_generate`; warns, never blocks. Tests:
  `tests/test_trade_validation.py`.
- **Creator coach (Phase S)** — `core/creator_coach.py` + `py -m scripts.ops coach`:
  daily "ideas + why" view — ranked best-bets each with a rationale, recommended
  length + post time, winning title patterns, retention pacing hint, cadence
  headroom. Read-only, fail-open per section. Tests: `tests/test_creator_coach.py`.
- **Weekly digest next actions (Phase S)** — `analytics/weekly_report.py` now
  derives numbered operator instructions from the per-dimension winners/losers
  ("Lead with the 'fraud' angle again (45% vs 25% baseline, n=3)"), noise-gated
  at ±3pp vs baseline; rendered under "Next actions:" with a pointer to `ops coach`.
- **Headless key facts for `auto_generate`** — `--facts-file` (parsed with the same
  paste-block parser as the interactive prompt; trade trackers work) + repeatable
  `--fact` lines. Deduped/tip-filtered, saved in full to the vault, injected as
  highest-priority ground truth, echoed in the grounding report. Tests:
  `tests/test_auto_generate_facts.py`.

### Scene-matched B-roll (Phase Q) — 2026-06-23

*The render looped one background clip; this cuts between several, one per script
beat (visual changes as the topic does — a retention lever).*

- **`video/scene_plan.py`** (pure, tested): `plan_scenes(script, topic, duration,
  words=…)` splits the script into ≤N timed beats, each with a `topic + beat-keyword`
  B-roll query. Uses real word timings for accurate beat boundaries when available,
  else proportional.
- **`assets/composite.build_multi_concat_command`**: generalises the 2-input hybrid
  concat to N normalised scene clips; `compose_scene_matched_background` runs it.
- **`assets/manager.get_scene_matched_background`** + render wiring: fetches a stock
  clip per beat and composes. **Default OFF** (`SCENE_MATCHED_BROLL`) — a render-path
  feature; **returns None → falls back** to the normal single/hybrid background on
  any missing clip or compose error, so it only ever upgrades, never breaks a render.
- **Tests:** `tests/test_scene_plan.py` (planning, contiguous windows, word-timed
  boundaries, N-input concat builder, missing-clip fallback). Suite 521 green.

*With this, Phase Q is functionally complete: timed + word-level animated captions
(keyword pop) and scene-matched cuts (beat-synced) cover the "dynamic emphasis"
checklist; a hook zoom-in remains an optional flourish.*

### Word-level captions from real TTS timing (Phase Q) — 2026-06-23

*Captions were timed by word-count estimate; the TTS step now gets real per-word
timing from ElevenLabs (free, same call) — no Whisper dependency.*

- **`video/caption_timing.py`** (pure, tested): `words_from_alignment` (char
  alignment → word timings), `build_srt_from_words` (accurately-timed,
  sentence/length-aware SRT), `build_ass_karaoke` (per-word `\k` highlight ASS —
  the animated-caption upgrade).
- **`core/tts.py`**: `convert_with_timestamps` captures alignment and writes a
  `<mp3>.words.json` sidecar (best-effort, `TTS_WORD_TIMESTAMPS`; any failure
  falls back to the plain stream).
- **`video/subtitles.generate_subtitle_file`**: prefers the sidecar — `CAPTION_STYLE`
  `word` (accurate SRT, **default**, safe strict upgrade) / `karaoke` (animated ASS,
  opt-in — verify with a render) / `plain` (old proportional). The existing
  `subtitles` ffmpeg filter burns both `.srt` and `.ass`, so no render-filter change.
- **Tests:** `tests/test_caption_timing.py` (word grouping, SRT/ASS, TTS sidecar +
  fallback) + word-timed branch in `tests/test_subtitles.py`. Suite 511 green.

### Retention-curve modelling → data-driven pacing (Phase P) — 2026-06-23

*Closes the Phase P retention item. We synced `averageViewPercentage` but never the
per-position curve; this adds it and the model that consumes it.*

- **Curve sync** (`analytics/youtube_metrics._fetch_retention_curve`): a second
  Analytics report (`audienceWatchRatio` by `elapsedVideoTimeRatio`) stored as
  `retention_curve` on the publish_log metrics blob. Best-effort
  (`RETENTION_CURVE_SYNC`, default on) — empty for low-watch videos, never breaks
  the main sync.
- **`core/retention.py`**: aggregates per-video curves into a channel-average
  curve and a **drop-off point** (first position below `RETENTION_DROPOFF_FLOOR`,
  default 50%). Strictly confidence-gated — no model until ≥ `RETENTION_MIN_VIDEOS`
  (default 3) curves exist, so it can't overfit a handful of videos.
- **Data-driven pacing**: `pacing_hint()` replaces the script prompt's static
  "~30-second mark" retention pivot with the channel's *measured* drop-off once
  data accrues (no-op until then).
- **`scripts.ops retention`** renders the average curve + drop-off.
- **Tests:** `tests/test_retention.py` (min-videos gate, average curve, drop-off
  detection, pacing-hint text, no-channel/no-data). Suite 500 green.

### A/B title-pattern loop (2026-06-23)

*Phase P "A/B variant loop", in the single-channel form: a faceless channel can't
double-publish without cannibalizing, so instead of head-to-head it **attributes**
realized engagement to the published title's structural pattern and biases future
picks.*

- **`core/title_features.py`** — `feature_tags(title)`: structural pattern tags
  (number / listicle / question / colon / versus / superlative / curiosity /
  callout / year / bracket / short / long). Pure + deterministic.
- **`core/title_experiments.py`** — joins each published title to its engagement
  (`content_runs.title` ↔ `publish_log`), aggregates by pattern into a
  `pattern_leaderboard()` ("colon titles average 18%"), and exposes `winning_tags()`
  (patterns above the channel's overall engaged-rate, cached per run,
  `TITLE_PATTERN_MIN_SAMPLES`).
- **Loop closes at selection**: `core/ui.display_variants(channel_id=…)` annotates
  any variant matching a winning pattern with "▲ <pattern>", so the analytics loop
  biases the operator's pick. Wired at both `main.py` variant prompts.
- **`scripts.ops title-patterns`** prints the leaderboard.
- **Tests:** `tests/test_title_experiments.py` (feature extraction, leaderboard
  ranking, winning-tags threshold, empty/min-samples). Suite 494 green.

### Topic Winners + Graveyard (2026-06-23)

*The data was already in `content_runs`↔`publish_log`; this surfaces it by topic.*

- **`core/topic_db.py`** — aggregates run history per topic into `TopicRecord`
  (runs, measured count, avg/best engaged-rate, last status). `winners()` ranks
  topics that engaged ("clone these"); `graveyard()` flags topics that measurably
  flopped (avg engaged-rate < `GRAVEYARD_RATE_FLOOR`, default 4%). Read-only,
  confidence-aware (`min_measured`), best-effort (empty on any storage error).
- **Avoid-list wired into discovery**: `graveyard_topics()` is folded into
  best-bet's exclude set (`GRAVEYARD_AVOID`, default on), so discovery stops
  re-pitching proven losers.
- **`scripts.ops topic-db --channel <id>`** prints Winners + Graveyard; also
  `py -m core.topic_db`.
- **Tests:** `tests/test_topic_db.py` (ranking, min-measured, floor, avoid-set,
  disabled, empty display). Suite 486 green.

### Human-context layer (Phase O) — persona + continuity (2026-06-23)

*The last open Phase O item. YouTube's 2026 policy rewards a consistent human voice
and continuity (a creator following a story), not fresh templated uploads.*

- **`core/channel_persona.py`** — `human_context_block(channel_id)` builds a prompt
  block from (1) an optional per-channel **persona** (`channels.json` "persona":
  perspective / tone / audience / recurring_segment / signoff) and (2) a
  data-driven **continuity** hint from real run history (`recent_input_topics` +
  `dominant_anchor`): "this channel has been covering X — acknowledge the ongoing
  storyline if it fits, never invent a prior video." Returns "" when there's
  nothing to add; bounded so it can't override anti-hallucination/grounding.
- **`config/channels.py`**: optional `persona` dict on `ChannelProfile`; a working
  persona added to the `tapin` channel.
- **`content_engine`**: the block is injected into the script prompt (after TOPIC).
- **Tests:** `tests/test_channel_persona.py` (persona rendering/order, arbitrary
  keys, anchor + theme continuity, thin-history no-op). Suite 480 green.

### Subject anchoring + future-dated-fact filter (2026-06-23)

*Live run: operator picked a "Kape" best-bet and pasted Kape facts, but the video
came out about a different fighter (Du Plessis) — variant generation generalised
the subject away ("the one fighter everyone is sleeping on") and the script then
followed a web-search tangent, silently abandoning the operator's key facts. The
same script also grounded on a web line claiming an event was "lost on July 18" (a
future date relative to the run).*

- **Subject preservation in variants** (`apis/topic_variants._subject_terms`):
  single-word proper-noun subjects (e.g. "Kape") that `extract_anchors`
  (franchise-only) misses are now pinned into the title rules — "keep the seed's
  subject, do not generalise to 'one fighter'".
- **Key-fact recenter** (`content_engine._maybe_recenter_on_key_facts`): if the
  finished script mentions *none* of the proper-noun subjects in the operator's
  pasted key facts, regenerate once to center it on them (accepted only if the
  rewrite covers a key-fact subject without gutting the script). Runs first, before
  insight/grounding. Default-on (`KEY_FACT_ANCHOR_ENABLED`).
- **Future-dated junk-fact filter** (`core/fact_recency.drop_future_dated`): drops
  corpus lines asserting a *completed* action on a date after today
  (`FACT_FUTURE_DATE_FILTER`, default on). High-precision — only fires when a
  future date co-occurs with a past-action verb, so legit previews survive.
- **`core/fact_grounding`**: public `specific_entities()` + `mentions()` helpers.
- **Tests:** `tests/test_fact_recency.py`, `tests/test_key_fact_anchor.py`
  (subject terms + recenter accept/noop/reject/disabled). Suite 474 green.

### Best-bet: confidence-weighted + diversified (2026-06-23)

*Same live run: for an NBA session, best-bet offered 3 stale UFC picks, all "low
confidence (1 sample)". Two root causes — fresh headlines were ranked by raw domain
rate (a 1-video 39% UFC domain outranked a 6-video 11% NBA domain), and NBA was
filtered out entirely because it isn't in the channel's configured on-brand set.*

- **Confidence-adjusted domain ranking** (`_adjusted_domain_rates`,
  `_domain_priority`): empirical-Bayes shrinkage toward the global mean, and
  adequately-sampled domains (≥ `MODERATE_SAMPLES`) rank above thin ones regardless
  of how high the thin average looks. Applied to both `get_best_bets` and the
  singular `get_best_bet` domain pick.
- **De-facto on-brand domains** (`_effective_allowed`): a domain the channel has
  actually published *with measured engagement* counts as on-brand even if it's not
  in the configured set — so NBA on a gaming/UFC channel is surfaced, not dropped.
- **Domain diversity** (`get_best_bets`): Phase-1 picks at most one per domain in
  confidence-first order (fresh headline preferred, else best historical run), so
  three 1-sample picks from one domain can't fill every slot; Phase 2 fills the rest.
  Historical rationales now carry the confidence note too.
- **Tests:** `tests/test_best_bet.py` — adjusted-rate shrink, domain-priority,
  well-sampled-leads-over-thin, no-single-domain-stacking. Suite 458 green.

### Original-insight injection (Phase O) — 2026-06-23

*Same live run flagged Authenticity 65/100: "no opinion/prediction/analysis beat —
reads as a neutral recap." The base prompt asked for opinion but a recap still
slipped past the gate's marker-based detector.*

- **`core/authenticity.has_insight()`** — public wrapper over the insight detector
  so generation can use the exact signal the gate scores on.
- **`content_engine._maybe_inject_insight`** — when a script has no take, inject one
  opinion/prediction/"why it matters" beat grounded **only** in the verified facts.
  Default-on (`INSIGHT_INJECTION_ENABLED`), premium tier; no-op when the script
  already has a take (most runs pay nothing); accepted only if it now reads as
  having a take and didn't shrink the script (≥90% word count). Runs **before** the
  grounding regen, so any specifics it introduces are still caught/cleaned.
- **Prompt**: added a detector-aligned STANCE bullet to the script prompt
  ("expect…", "here's why…", "my prediction…", grounded in the facts).
  `PROMPT_VERSION` → `content_engine_v7`.
- **Tests:** `tests/test_insight_injection.py` (inject / no-op-when-has-take /
  reject-no-take / reject-gutted / disabled) + `has_insight`. Suite 454 green.

### Anti-hallucination wave — regenerate-then-warn grounding + link cleanup (2026-06-23)

*From a live run where a script fused a real trade (Giannis→Heat, from pasted
links) with an invented one (Butler→Celtics): the grounding check flagged it but
the script shipped anyway, and link extraction had fed the model promo/teaser junk.*

- **Regenerate-then-warn grounding** (`core/content_engine._maybe_reground_script`):
  when the post-gen check flags specifics not in VERIFIED FACTS, regenerate **once**
  to strip/generalize the unsupported names/trades/numbers, accept the rewrite only
  if it reduces the unsupported count and keeps ≥60% of the word count, then warn on
  whatever remains. Default-on (`GROUNDING_REGEN_ENABLED`, `GROUNDING_REGEN_MIN`);
  premium tier; triggered only when something was flagged (most runs pay nothing).
- **Link-fact cleanup** (`core/link_facts._is_junk_line`): drop promo/nav
  boilerplate ("has the latest", "subscribe", "all rights reserved", …) and teaser
  questions ("Will the Bucks move Giannis?") from extracted article facts — index
  pages were poisoning the fact corpus, which is what the model then hallucinated
  around.
- **Tests:** `tests/test_grounding_regen.py` + link junk-filter cases in
  `tests/test_link_facts.py`. Suite 447 green.

### Credit-efficiency wave 3 — observability (2026-06-23)

*Third wave from [credit_efficiency.md](credit_efficiency.md) (O8 + O9): make the
credit layer visible.*

- **Cache-hit instrumentation (O8):** `apis/cache_manager.py` counts hits/misses
  per key-prefix (signal/source name); `flush_cache_stats()` merges in-process
  counters into `data/cache_stats.json` once per run (in `run_discovery`), so no
  per-lookup write. `get_cache_stats()` / `reset_cache_stats()` added; `get_cached`
  refactored to record each access.
- **Reliability dashboard (O9):** `core/reliability.py` (`gather`/`render`) +
  `py -m scripts.ops reliability` — Apify breaker/budget + persisted exhaustion,
  LLM disabled providers + daily spend vs budget, session-disabled signals, cache
  hit-rate by prefix, YouTube units. Read-only, fail-open. New public accessors:
  `llm_router.disabled_providers()`, `register_signals.disabled_signals()`.
- **Tests:** `tests/test_observability.py` (cache stats record/flush/persist/reset +
  reliability gather/render). Suite 433 green.

### Credit-efficiency wave 2 — operator spend ceilings (2026-06-23)

*Second wave from [credit_efficiency.md](credit_efficiency.md) (O4 + O7): graceful
degradation before the hard credit walls.*

- **Apify budget (O4):** `APIFY_MONTHLY_BUDGET_USD` — `apify_client._evaluate_apify_usage`
  trips (and persists) the breaker when monthly usage hits the operator's budget,
  before Apify's hard limit. Enforced on both the fresh and cached preflight paths;
  the status line shows the budget.
- **LLM daily budget (O7):** `LLM_DAILY_BUDGET_USD` — `core/llm_router` accumulates
  today's cross-run spend in `quota_state` (only when a budget is set), and once
  exceeded a `premium`/`extract` call downgrades to the free-first `cheap` chain.
  Pricing reuses `cost_meter.llm_cost_from_usage`; `reset_llm_spend()` test helper.
- **Tests:** Apify budget (trip-before-limit, persistence) in
  `tests/test_credit_efficiency.py`; LLM budget (spend tracking, downgrade,
  under-budget keeps premium) in `tests/test_llm_router.py`. Suite 425 green.

### Credit-efficiency wave 1 — persistence + LLM failover (2026-06-23)

*First implementation wave from [credit_efficiency.md](credit_efficiency.md) (O1/O2/O3/O5/O6).*

- **`core/quota_state.py`** (new): cross-run, TTL'd, fail-open store at
  `data/quota_state.json` — exhaustion records (`mark_exhausted`/`is_exhausted`) +
  a small TTL key/value cache (`set_value`/`get_value`). Seed of the eventual
  unified quota governor (O11). `config/paths.py` adds `QUOTA_STATE_FILE`.
- **Apify persistence (O2/O3):** `apis/apify_client.py` now seeds its breaker from
  persisted state (`_sync_persistent`), persists hard 401/402/403/limit failures
  (`_persist_exhausted`, `QUOTA_STATE_TTL_SECONDS`, default 6h), and caches the
  `/users/me` usage reading (`APIFY_USAGE_CACHE_TTL_SECONDS`, default 20m) so a
  fresh process skips the network preflight. A prior run's out-of-credits is
  remembered — no re-paid failing call next run.
- **Preflight skip (O1):** `apis/register_signals.will_use_apify(topic, channel_id)`;
  `core/pipeline.run_discovery` only preflights when a paid Apify signal actually
  survives skip/gating/breaker.
- **LLM failover + breaker (O5/O6):** `core/llm_router.complete` resolves a tier to
  a provider *chain* (`_resolve_chain`) and fails over on retryable errors
  (429/402/401/403/5xx/timeout); hard auth/quota disables that provider for the
  session (`_disable_llm`/`reset_llm_breaker`). Non-retryable errors propagate;
  explicit `provider=` pins one (no failover). Makes the free OpenRouter tier
  resilient (rate-limit → fall to DeepSeek).
- **Tests:** `tests/test_quota_state.py`, `tests/test_credit_efficiency.py`
  (Apify persistence + `will_use_apify`), router failover/breaker tests, and
  `tests/test_apify_client.py` isolated to a temp quota-state file. Suite 417 green.

### Multi-provider LLM router + credit-efficiency docs (2026-06-23)

- **`core/llm_router.py`:** unified router for every runtime LLM call. Task tiers
  — `cheap` / `extract` / `premium` — routed across **DeepSeek, OpenRouter, Ollama
  (local), OpenAI, Anthropic** (Groq wired but not default — signup gated; Doubao
  wired but skipped — China-region-locked). Free-first defaults: OpenRouter `:free`
  models anchor `cheap` (Ollama local fallback), DeepSeek-V3 anchors `extract` +
  `premium`. OpenAI-compatible providers share one client shape (different
  `base_url`); Claude uses the native messages API. Per-tier overrides
  `LLM_<TIER>_PROVIDER`/`_MODEL` and per-provider `{PROVIDER}_MODEL_<TIER>`; loads
  `.env` standalone; degrades gracefully (OpenAI-only behaves like the old code).
- **Call sites migrated** off the hardcoded OpenAI client: `core/content_engine.py`
  (final script/expand → premium; hook regen → cheap), `core/research_brief.py`
  (premium), `core/fact_enrichment.py` (extract — consolidated the duplicated raw
  Claude branch), `apis/topic_variants.py` (cheap), `assets/background_query.py`
  (cheap — merged the openai+anthropic duplicates), `assets/local_provider.py`
  (cheap). Only the multimodal thumbnail vision scorer stays on `core/llm_client.py`.
- **Cost meter:** real **per-provider token ledger** (`llm_router` records usage;
  `cost_meter.llm_cost_from_usage` prices it) replaces the word-count heuristic for
  LLM cost; free `:free`/Ollama calls priced at $0. `reset_usage()` per run in
  `run_discovery`. Pricing table for DeepSeek/OpenRouter/Llama/Ollama/OpenAI/Claude.
- **Config:** `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_MODEL`/`OLLAMA_BASE_URL`
  added to `settings` + `.env.example` (with the free-setup guidance).
- **Docs:** new [credit_efficiency.md](credit_efficiency.md) — credit/quota/spend
  optimization backlog (O1–O11); architecture, decisions (§14), debugging, roadmap,
  operating_plan updated.
- **Tests:** `tests/test_llm_router.py` (tier resolution, overrides, failover-ready
  routing, usage ledger, completion mocking) + `tests/test_cost_meter.py` ledger
  pricing. Suite green at 397.

### Multi-domain signal expansion (2026-06)

- **Finance:** `fred`, `sec_edgar`, `finnhub`, `coingecko` APIs.
- **Anime:** `anime` signal (AniList → Jikan chain).
- **Pop culture:** `tmdb`, `tvmaze`.
- **Music:** `lastfm`, `musicbrainz`.
- **Gaming+:** `twitch`, `igdb`, `trendingnow`.
- **Sports+:** `api_sports`; `stats_context` chain extended with nflverse/pybaseball.
- **Domains:** `finance`, `anime`, `popculture`, `music` in `infer_domain` + weight profiles; RSS in `data_sources.json`.

### Data reliability upgrade (2026-06)

- **Trends:** Removed archived **pytrends**; provider chain in `apis/trends_api.py` + `apis/signal_chain.py` (SerpApi → Glimpse → Wikipedia pageviews).
- **Stats:** `apis/balldontlie_api.py` + `STATS_PROVIDER_ORDER=balldontlie,scrapers` in `apis/stats_context_api.py`.
- **Competitors:** `analytics/youtube_rss.py` + RSS-first sync in `analytics/competitor_sync.py` (`COMPETITOR_SYNC_RSS=true`).
- **Reddit removed:** `apis/reddit_api.py`, `apis/reddit_intelligence.py` deleted; community context via `blog_rss` + `community_summary` in research brief.
- **Tapology:** scrape off by default (`TAPOLOGY_SCRAPE_ENABLED=false`).
- **Deps:** dropped `pytrends`, `praw`, `pandas` from `requirements.txt`.

### Analyst intelligence v2 (2026-06)

- **Trajectory:** `core/topic_trajectory.py` — snapshots in `data/topic_trajectory.json`, rising/peaking/decaying phases.
- **Corroboration:** `apis/signal_corroboration.py` — multi-source confidence; optional score adjustment in `composite_score`.
- **Opportunity window:** `core/opportunity_window.py` — demand vs competitor saturation (open/closing/closed).
- **Explainability:** `core/analyst_explain.py` — why now / why this / contrarian in reports.
- **Self-measurement:** `core/analyst_accuracy.py` — volume-gated hit-rate backtest.
- **New signal:** `wikipedia` pageviews (`apis/wikipedia_pageviews_api.py`).
- **Docs:** [analyst-intelligence.md](analyst-intelligence.md), [adding-a-data-source.md](adding-a-data-source.md).

### Intelligence layer & positioning (2026-06)

- **`core/intelligence_report.py`:** Markdown/JSON report from discovery + research brief + competitor pulse; CLI and `scripts.ops intelligence-report`.
- **`main.py`:** Menu option 3 (intelligence report only); `CONTENT_MODE=intelligence` skips production-tail warmup.
- **Docs:** [positioning.md](positioning.md), [case_study.md](case_study.md), [samples/intelligence_report_example.md](samples/intelligence_report_example.md).

### Codebase cleanup (2026-06)

- **Removed dead modules:** `legacy/` package, `core/signal_health.py` (duplicate of `core/ui.py`), orphaned `apis/community_analyzer.py` and `apis/query_optimizer.py`, unused `sports/router.py` + BallDontLie/SportsData helpers, broken `scripts/extract_luffy_art.py`, pre-Luffy `core/art/*.txt`, root `prospect_cache.json`, typo `sports/_init_.py`.
- **Trimmed:** `apis/api_registry.py` dead `execute_all`, `sports/espn.py` unused standings helpers.
- **Kept:** ASCII/Luffy startup UI (`core/ascii_art.py`, `core/data/luffy_ascii.txt`), `scripts/update_luffy_art.py` for refreshing bundled mascot art.

### Data sources expansion + brief v3 (2026-06)

- **Stats scrapers:** `apis/scrapers/` (Basketball Reference, Pro-Football-Reference, ESPN JSON) → signal `stats_context`.
- **Blog RSS signal:** `blog_rss` merges `config/seo/{channel}.json` + `config/data_sources.json` domain feeds.
- **Research brief:** `research_brief_v3` injects reference stat lines; RSS brief path uses expanded feeds.
- **Docs:** [data-sources.md](data-sources.md); architecture + roadmap updated.

### Phase K — YouTube thumbnail API (2026-06)

- **`youtube/thumbnails.py`:** Resolves thumbnail from `assets` row or `output/{channel}/thumbnails/`; calls `thumbnails.set` after successful upload (~50 quota units).
- **`YOUTUBE_THUMBNAIL_UPLOAD`:** `auto` (default) or `off`; ineligible channels log `ineligible` without failing the video upload.
- **Tests:** `tests/test_youtube_thumbnails.py`.

### Phase H + YouTube SEO tags (2026-06)

- **Research brief:** `core/research_brief.py` runs once after variant selection; RSS + Reddit intel; cached.
- **SEO:** `config/seo/tapin.json`, LLM `tags` in content package, upload via `enqueue_upload_job` / worker.
- **Refresh:** `py -m analytics.seo_refresh` → `data/seo_hints_{channel}.json`.
- **Provenance:** `tags_json`, `brief_version`, `prompt_version` on `content_runs` (`py -m storage.migrate_schema`).
- **Modules:** `apis/rss_feeds.py`, `apis/reddit_intelligence.py`, `core/signal_facts.py`, `core/seo.py`.

### Intelligence phase roadmap adopted (2026-06)

- **`docs/intelligence_phase.md`:** Post D–G plan — generation before measurement; Phases H–K; feature triage; architectural prerequisites (brief after variant selection, caching, provenance).
- **`docs/roadmap.md`:** Restructured — completed D–G; next H→K with prerequisites; volume-gated deferrals.
- **Prerequisites (since shipped):** research brief, RSS, Reddit intel, competitor sync, and Alembic baseline were documented here before implementation; see Phase H and Alembic entries above.

### Operator tooling, UFC research, and stability (2026-06)

- **`scripts/ops.py`:** Batch and individual operator commands (`all-setup`, `all-checks`, `all-analytics`, validate, seed, worker, tests).
- **`scripts/requeue_upload.py`:** List rendered-but-not-uploaded `content_runs`; queue upload jobs by `--run-id`.
- **Hybrid backgrounds (TapIn default):** `background_mode: hybrid`, `hybrid_local_ratio`, FFmpeg concat in `assets/composite.py`; local gameplay from `video/backgrounds/` plus stock B-roll.
- **UFC script accuracy:** `apis/ufc_context_api.py` (news + Reddit MMA), `apis/tapology_api.py` (event scrape + `data/tapology_cache.json`), `core/script_brief.py` (UFC matrix), stricter prompts in `core/content_engine.py` with JSON mode and signal facts injection.
- **Signals:** `tapology` and `ufc_context` registered in `apis/signals_bootstrap.py`; weights in `apis/topic_scorer.py` and `apis/learned_weights.py`.
- **`config.validate_channels`:** Validates root-level `background_mode`, `hybrid_local_ratio`, `asset_provider_order`; numeric-only `weight_overrides`.
- **Bug fixes:** `apis/register_signals.py` import path (`apis.cache_manager`); `youtube/upload.py` secrets under `config/secrets/`; truncated `content_engine.py` restored; signal cache atomic writes + retries + non-fatal failures (`apis/cache_manager.py`).
- **Docs:** `docs/debugging.md` — operator debugging guide; README and architecture updated for layout and new modules.

### Project root cleanup (2026-06)

- **Layout:** `config/channels.json`, `config/secrets/`, `data/` for runtime JSON; `core/content_engine.py`, `core/tts.py`, `apis/cache_manager.py`.
- **Removed from root:** duplicate facades, unused scripts → `legacy/`.
- **Migration:** `py -m storage.migrate_layout` moves legacy root files into `data/` and `config/secrets/` on first run.
- **README.md** at repo root; `ROADMAP.md` points to `docs/roadmap.md`.

### Analytics learning sprint (2026-06)

- **`learn_slots_from_analytics`:** Engagement-weighted weekday/hour slots from `publish_log` timed outcomes; `USE_LEARNED_POST_SLOTS=auto` in `get_post_schedule`.
- **`py -m analytics.learn_schedule`:** Compare static vs learned post schedules.
- **`py -m config.validate_channels`:** Validate `channels.json` (TTS, weights, post_schedule, OAuth paths).
- **Seed:** TapIn seed staggers `published_at` across slot windows for timing learning.
- **Tests:** Learned post timing, job `scheduled_at` claim gate, learned weight profile, channel validation.
- **`tzdata`:** Windows dependency for `zoneinfo` (America/New_York).

### Publish path hardening (2026-06)

- **Idempotency:** Unique `idempotency_key`; reuse single `publish_log` row per run; heal `pending` via YouTube uploads playlist title match before `videos.insert` (crash-window safe).
- **Quota:** `record_upload_usage()` on upload attempt, not only success.
- **Metrics:** Removed immediate post-upload `refresh_publish_metrics` from upload path and worker (use delayed `py -m analytics.sync_metrics`).
- **Migration:** `migrate_schema` dedupes duplicate keys and adds partial unique index on `idempotency_key`.

### Upload queue & slot reservation (2026-06)

- **`analytics/upload_queue.py`:** Reserved `youtube_publish_at` times from jobs + `publish_log`; CLI **Publish queue** in `main.py` and before upload prompts.
- **`next_optimal_post_time`:** Skips slots already in the queue; video 2+ get the next optimal time after prior reservations.
- **YouTube `publishAt`:** Option 4 uploads once; YouTube publishes at the reserved slot (PC off after upload).
- Docs: **`docs/post_scheduling.md`**

### Roadmap 1–2–3 — Upload, worker, analytics (2026-06)

- **`py -m youtube.check_setup`:** Validates TapIn OAuth, env, token scopes.
- **`youtube/oauth_setup`:** Requests `youtube.upload` + `yt-analytics.readonly` by default.
- **`analytics/youtube_metrics.py`:** YouTube Analytics API v2 `fetch_video_metrics`; worker + upload hook sync.
- **`py -m analytics.sync_metrics`:** Batch refresh for uploaded `publish_log` rows.

### Render + channel outputs (2026-06)

- **`video/render_video.py`:** `filter_complex` uses **`[0:v]` only** (stock audio stripped); **`-stream_loop -1`** + **`-t` audio duration**; vertical 1080×1920. Tested via **`tests/test_render_video.py`**.
- **`core/output_paths.py`:** Per-channel dirs `output/{channel}/audio|video|thumbnails`.
- **`analytics/youtube_metrics.py`:** Stub for post-upload metrics sync (`YOUTUBE_ANALYTICS_SYNC`).
- **`channels.json`:** TapIn `output_subdir`, OAuth token path, default privacy.

### Phase D–G — Upload, assets, signals, scaling (2026-06)

- **YouTube upload (Phase D):** OAuth flow (`youtube/oauth.py`, `py -m youtube.oauth_setup`), resumable `videos.insert` in **`youtube/upload.py`**, quota guard via **`apis/youtube_quota.py`**, idempotent **`publish_log`** rows (`idempotency_key`). Upload jobs complete only on `uploaded`; terminal failures mark **`jobs`** as failed.
- **Asset intelligence (Phase E):** **`Asset`** model, **`storage/repositories/assets.py`**, **`core/asset_recorder.py`** hooks after render; Pillow title-card thumbnails in **`assets/flux_thumbnail.py`**. **`storage/migrate_schema.py`** adds `idempotency_key` and `assets` on existing Postgres DBs. Asset DB writes log warnings and no longer fail the render path after successful ffmpeg output.
- **Research intelligence (Phase F):** **`apis/signals_bootstrap.py`** registers all providers on **`SignalRegistry`**; **`register_signals.py`** reads from registry. Optional **`USE_SIGNAL_SYNTHESIS`** adds `_synthesis` metadata. Removed unused **`draft_aggregator.py`**, **`prospect_scraper.py`**, **`video/background_selector.py`**.
- **Scaling (Phase G):** **`reclaim_stuck_running()`** on job repo + worker (`JOB_STUCK_MINUTES`). GitHub Actions **`.github/workflows/ci.yml`** runs `unittest discover`. Render path uses structured logging in **`video/render_video.py`**.

### Pipeline architecture

- Introduced **`core/pipeline.py`** as the single orchestration layer decoupled from CLI I/O.
- Added **`run_discovery()`** to fetch signals and score variants in parallel without generating content.
- Added **`PipelineResult`** / **`DiscoveryResult`** dataclasses with timings, variants, abort reasons, `channel_id`, and `run_id`.
- Split interactive flow in **`main.py`**: discovery → user variant choice → content preview → optional render via **`run_media_only()`**.
- Integrated **`core/run_recorder.py`** to persist every pipeline completion to **`content_runs`** and trigger learning updates.

### Signal scoring and learning loop

- Standardized signal shape in **`apis/signal_contract.py`** (`connected`, `active`, `score`, `status`, `status_detail`).
- Implemented domain-aware static weights in **`apis/topic_scorer.py`** (`infer_domain`, `get_default_weights`).
- **Wired learning into scoring:** `composite_score()` now applies:
  - Per-channel weight overrides from **`channels.json`**
  - Historical topic boost via **`channel_memory`** / `topic_scores`
  - Domain performance multiplier via **`performance_memory`** / `performance_entries`
- **Wired learning into pipeline:** `record_learning_outcome()` on successful runs (drafted/rendered).
- Single-active-signal penalty (0.75×) retained when only one signal is active.

### Database integration

- Added SQLAlchemy models: **`TopicScore`**, **`PerformanceEntry`**, **`ContentRun`**, **`PublishLog`**, **`Job`** (`storage/models.py`).
- Dual-write repository pattern: PostgreSQL when `DATABASE_URL` set, else JSON under **`data/`**.
- **`storage/init_db.py`** creates all tables via `create_all` (no migration history).
- **`storage/migrate_json.py`** for one-time import from legacy JSON memory files.
- Per-channel topic memory: Postgres filters by `channel_id`; JSON uses **`data/channel_memory/{channel_id}.json`** (default channel keeps **`channel_memory.json`**).

### Channel profiles and multi-channel

- Added **`channels.json`** and **`config/channels.py`** (`ChannelProfile`, `resolve_channel_id`).
- **`CONTENT_CHANNEL_ID`** env and **`main.py --channel`** flag.
- Pipeline and asset manager accept **`channel_id`**; per-channel asset provider order supported.

### Asset management (Phase 4)

- **`AssetProvider`** ABC and **`AssetResult`** type (`assets/base.py`, `assets/types.py`).
- Providers: **local** (`video/backgrounds/`), **Pexels**, **Pixabay** with download cache (`assets/cache/`).
- **`assets/manager.py`**: ordered fallback chain from env or channel profile.
- **`assets/catalog.json`**: deduplication metadata for stock downloads.
- **`assets/category.py`**: topic → search category for stock APIs.
- **`video/background_selector.py`**: removed; use **`assets/manager.py`** directly.
- **`assets/flux_thumbnail.py`**: Pillow title cards after render (Flux API optional).

### Performance optimizations

- **Parallel signal fetch** in `build_registry()` (`ThreadPoolExecutor`, one future per source).
- **Parallel variant scoring** in `run_discovery()` (up to 5 workers).
- **Parallel discovery bootstrap**: signals + variant generation concurrently (2 workers).
- **Signal cache** (`cache_manager.py`): 3-hour TTL in `signal_cache.json`, thread-locked read/write.
- **`CONTENT_SKIP_SIGNALS`**: omit slow sources (e.g. `trends`) without code changes.
- **YouTube quota tracking** (`apis/youtube_quota.py`, `youtube_quota.json`) to surface search quota usage.

### API integrations

- Central registry in **`apis/register_signals.py`** for signals including: youtube, reddit, trends, news, sports, live_scores, odds, rawg, steam, autocomplete, **tapology**, **ufc_context**.
- **YouTube search** signal with normalized errors and quota classification (`apis/youtube_api.py`).
- **Live scores** signal with ESPN-oriented game matching (`apis/live_scores_api.py`).
- **Draft-aware variants** (`apis/draft_policy.py`, `apis/entity_extractor.py`, `apis/topic_variants.py`).
- **OpenAI** content package with JSON mode, signal facts injection, anti-hallucination prompts (`core/content_engine.py`).
- **YouTube upload** (`youtube/upload.py`): OAuth, resumable `videos.insert`, `publishAt`, idempotent `publish_log`.
- **Job worker** (`jobs/worker.py`): processes upload/render jobs from DB/JSON queue.

### UI and developer experience

- **`core/ui.py`**: sectioned CLI, signal health legend, variant list, DB status line.
- **`core/logging.py`**: configurable quiet mode via `CONTENT_QUIET_LOGS` / `CONTENT_LOG_LEVEL`.
- **`config/settings.py`**: `.env` loader, centralized settings dataclass.
- **`.env.example`** expanded for DB, assets, channel, upload, and worker hints.
- **`requirements.txt`** pinned dependencies (OpenAI, Google API client, MoviePy, SQLAlchemy, PRAW, etc.).

### Documentation and housekeeping

- Added **`docs/`** package: `project_brief.md`, `architecture.md`, `roadmap.md`, `change_log.md`, `debugging.md`, `post_scheduling.md`.
- **`.gitignore`**: `data/` directory for local JSON fallbacks.

---

## Historical / pre-pipeline (inferred from structure)

The following components predate or sit beside the current pipeline and may reflect earlier experiments:

- **`draft_aggregator.py`**, **`prospect_scraper.py`**, **`video/background_selector.py`** — removed (unused).
- **`topic_strategist.py`** + **`apis/signal_synthesizer.py`** — alternate angle generation from title synthesis (not imported by pipeline).
- **`apis/api_registry.py`** + **`apis/signals_bootstrap.py`** — class-based registry now wired via `register_signals.build_registry()`.
- **`sports/`** package — standalone topic router for playoffs/player/standings (not wired to `core/pipeline.py`).
- Root **`channel_memory.json`** / **`performance_memory.json`** — legacy flat files still supported for default channel.

---

## Known issues / open items

- **Operator setup:** OAuth (`YOUTUBE_UPLOAD_ENABLED`, `py -m youtube.oauth_setup --channel tapin`) required before unattended publish.
- **Tapology scrape:** May return 403/blocked; use `ufc_context` + news; see **`docs/debugging.md`**.
- **OneDrive / signal cache:** Heavy parallel discovery can contend on `data/signal_cache.json`; cache failures are non-fatal but may disable caching for that run.
- **Alembic + FKs:** Use **`storage/migrate_schema.py`** today; full revisions should add FKs (`content_run_id` → `content_runs`) and formalize schema.
- **Metrics delay:** Run `py -m analytics.sync_metrics` after publish, not seconds after upload.
- **Dual JSON/Postgres** for default-channel memory: read prefers Postgres when `DATABASE_URL` is set.

See **`docs/debugging.md`** for symptom → fix tables.

---

## How to update this changelog

When shipping meaningful changes:

1. Add a dated section under `[Unreleased]` or a new version heading.
2. Reference modules and tables affected.
3. Note breaking changes to env vars, CLI flags, or DB schema.
4. Reconcile **`docs/roadmap.md`** checkboxes when a planned phase item is fully delivered.
5. Add symptom/fix notes to **`docs/debugging.md`** when operators hit new failure modes.
