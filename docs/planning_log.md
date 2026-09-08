# Planning log

A durable record of planning/brainstorming sessions so ideas aren't lost when the
ephemeral plan files (`~/.claude/plans/*.md`) are cleared. **Newest first.** Each entry
captures the prompt, the brainstorm/decisions, and what actually shipped — the tactical
backlog itself lives in [roadmap.md](roadmap.md).

> Convention: when a planning session happens (plan mode, or a substantial "what should we
> build" discussion), append a dated section here with the options considered, the
> decision, and — once built — the outcome. See [../CLAUDE.md](../CLAUDE.md).

---

## 2026-09-07 (Cursor) — Stage 2 look + 20

**Prompt:** complete Stage 2 of the desktop programme AND the next 20
backlog/roadmap tasks, then update docs and the mailbox, then commit.

**Fail-then-fix:** unmodified HEAD `7e4284c` raised `ModuleNotFoundError:
core.chrome` / `core.contact_sheet` / `core.negative_facts` / `core.script_craft`
/ `core.font_cache` / `tests.isolation` / `tests.signature_audit`. Widget test
failed `assertTrue(qss.strip())` (empty stylesheet). Persona lint returned `''`
for "delve". 32 errors + 2 fails observed before the fix.

**Shipped — Stage 2 (#150 #172 #173):**
- `core/chrome.py` — `build_qss` / `themed_css` from shipped `design_tokens.json`
  only. TapIn `#E53935` vs MoneyWise `#81C995`. Type body 16px, spacing page 20px.
  Dark from `end_card_bg`. Empty/error copy. DPR 1.0 without a screen.
- `desktop/window.py` applies QSS, SVG icon, facts meter, drag-drop, geometry.
- Missing PySide6: refuse, exit 2, no WARNING. CLI without `--gui` unchanged.
  `GRADE_VERSION` stayed **v3**.

**Shipped — 20 additional:**
1. **#295** `ops contact-sheet --path` — live: 4 thumbs; empty: "no thumbnail files"
2. **#296** print CSS on the contact-sheet HTML
3. **#625** `audit_known_doubles()`; dated two undated `tags: [facts]` notes
4. **#333** negative-fact store + `ops negative-fact`
5. **#602** end-card Y in `[0.12h, 0.80h]`, not `y=(h-text_h)/2`
6. **#527** high-contrast / reduced-motion QSS flags
7. **#258** facts meter vs live `operator_key_fact_char_budget()`
8. **#525** `facts_from_drop` txt + URL
9. **#523** per-channel window state JSON
10. **#515** ScriptedBackend and AskBridge agree on `y`/`3`
11. **#247** CSS grain/vignette preview (env, default off)
12. **#541** delve / in today's video via `llm_tells.json`
13. **#550** `first ever` ungrounded; `not only` skipped
14. **#635** HTML redacts vault path and username
15. **#612** `load_font` identity cache
16. **#540** uniform sentence length flag
17. **#542** strip pre-CTA recap; both paragraph counts persisted
18. **#318** persist `screen` name (physical second monitor = #673)
19. **#512** `noise=` / `vignette=` from tokens when `channel_id` set
20. **#455** `IsolatedQuotaStore`; GovernorCase uses it

**Proof:** `ops contact-sheet` without `--path` -> `contact-sheet requires --path <dest.png>`.
With path: 4 thumbs. `ops negative-fact` without claim -> require line.
`ops command-ref` regenerated `docs/ops_commands.md`.

**Filed:** #672 grain argv-only · #673 second physical monitor · #674 traces not
redacted. Held: #670 no CI Qt · #671 1-5 line · #416.

**Not done:** Stage 3 panels. No `cached-strolling-popcorn.md`.

**Audit:** ruff + format clean; suite **2,685 -> 2,718**; mypy **144** held;
`git status --short data/` empty. `ops roadmap-index`: **404** open / **506**
done, highest **#674**.

**The new five** (`roadmap.md`): Stage 3 review room · **#671** · **#607** ·
**#335** · **#416** (still blocked).

## 2026-09-07 (Cursor) — Stage 1 run window

**Prompt:** complete Stage 1 (the Qt run window from [desktop_app.md](desktop_app.md)).

**Fail-then-fix:** `tests/test_stage1_run_window.py` on unmodified HEAD `3a338e8`
raised `ModuleNotFoundError: core.ask_bridge`. Widget test later failed with
`_set_ask_enabled() got an unexpected keyword argument` until the kwargs-only
signature matched the call.

**Shipped:**
- `core/ask_bridge.py` — queue + `classify_prompt` for the five live gate
  strings, Proceed, fact loop, Choose 1-5 / Select 1-4. Paste box drains
  fact lines then auto-returns `""` so PowerShell one-line intake is skipped.
  `cancel()` raises `KeyboardInterrupt`.
- `desktop/` — `RunWindow` (channel combo from shipped `list_channel_ids`,
  topic, facts box min height 160, output pane, gate buttons). Worker runs
  `main._run_new_video_flow`. Stdout tee so `print(script)` still shows.
- Launch: `py -m desktop` · `py main.py --gui` · `ops run-window`. Missing
  PySide6 prints `run-window requires PySide6 - pip install -e ".[app]"` and
  exits 2 — zero WARNING.
- Extra `[app]` is optional. CI still installs `.[shell]` only (#670).
  `GRADE_VERSION` stayed **v3**. CLI without `--gui` is unchanged.

**Found on the way:** an emdash in the refuse line garbled in conhost (ASCII
hyphen now). Duplicate `AskBridge` methods from a bad merge (rewrote the
file). Accidental delete of `ops intro-waveform` register (restored).

**Filed:** #670 no CI Qt; #671 angle variants are still a 1-5 line, not a
visual list.

**Not done:** Stage 2 QSS; #295/#296; #333; #416. A live topic-to-mp4 still
needs keys/network — not a CI proof.

**Proof:** widget test offscreen (PySide6 6.11.2 present locally). Bridge
round-trip: worker `ask_confirm(AUTH_PROMPT)` blocks until `submit("y")`.
Fact feeder: two lines then `""`. Run 73 topic `"GTA 6 looks amazing!!!"` is
reaction.

**Audit:** ruff + format clean; suite **2,673 -> 2,685** (CI skips the widget
test without `[app]`); mypy **144** held (`BridgeBackend` subclasses `Backend`;
`main.py` stdout `reconfigure` via getattr so following `import main` does not
add an error); `git status --short data/` empty. Backlog **424** open /
**483** done (`roadmap-index`), highest open **#671**.

**The new five** (`roadmap.md`): Stage 2 look · **#295** contact sheet ·
**#625** test-double signatures · **#333** negative-fact store · **#602**
end-screen vs caption safe area.

## 2026-08-28 (Piper mix / secrets) — 1/8 Piper, drop Brave/BFL, ElevenLabs + Ollama

**Prompt:** how to add parked ElevenLabs voices; rotate Piper in ~1/8 of the time;
why Ollama doctor FAILs after installing the app; stop secrets-doctor nagging Brave/BFL.

**Answers (no code):**
- ElevenLabs Voice Library is [elevenlabs.io](https://elevenlabs.io) on the same
  account as `ELEVEN_API_KEY`. Explore → Add to my voices → `ops voices` shows
  `* <id>`. Then move the id out of `_parked_voice_not_found`. Ids are 20
  characters; `3TPKV1kjDlVtZbl4Ksh` (19) cannot be added. TapIn is pinned to
  Brian, so catalog mix is separate from Piper mix.
- Ollama app ≠ pulled model. Doctor FAILs until `OLLAMA_MODEL` is in `GET /api/tags`.
  Optional: `ollama pull llama3.1:8b`. Leave the FAIL if you do not want a local LLM.

**Tests failed first** (unmodified code): remaining optionals present + Brave/BFL
blank still listed those two names; `_should_piper_mix` / `last_tts_was_piper_mix`
AttributeError; `generate_audio` still constructed ElevenLabs on mix.

**Shipped (measured):**
- **secrets-doctor** optional list is OpenAI / Anthropic / News only. Brave and
  BFL APIs unchanged (`BRAVE_API_KEY` / `BFL_API_KEY`); doctor does not list them.
- **Piper mix:** `TTS_PIPER_MIX_EVERY=8` (0 = off). One `randrange` per
  `generate_audio` when provider resolves to elevenlabs, Piper `.onnx` ready, not
  Free-strict. Does **not** write `TTS_PROVIDER=piper`. Synth fail → ElevenLabs.
  Lexicon on the Piper path. `[TTS] … Provider: piper (mix 1/8)`.
  `last_tts_was_piper_mix()` zeros the TTS cost line the same way a cache hit
  does. Suite pins `TTS_PIPER_MIX_EVERY=0` so ElevenLabs tests do not flake.

**Do not commit** unless asked. Do not unpark ElevenLabs ids. Do not `ollama pull`.

## 2026-08-28 (doctor greens) — secrets, Sherdog, Piper pool, ElevenLabs intake, fact paste

**Prompt:** doctor FAILs that are ours (not Ollama), random Piper not Patrick,
intake seven ElevenLabs ids, keep fact intake accepting long paragraphs and URLs.

**Tests failed first** (unmodified code): doctor secrets `ok=False` with only
optional keys blank (`5 present / 5 missing`); `required_missing` KeyError;
`sherdog.com/rss/news.xml` still in shipped JSON; `PIPER_VOICE=README.md` counted
ready; dir `.onnx` did not; empty `local.piper[]`; seven ids absent;
`read_multiline_paste` ImportError. Long paragraph (~600 chars) and fetched-article
lint already passed — locked, not claimed as a fix.

**Shipped (measured):**
- **Secrets required vs optional.** Missing Anthropic/OpenAI/Brave/BFL/News is a
  detail line, not `ok=False`. Missing DeepSeek/OpenRouter/Eleven/Apify/YouTube
  still FAILs. Never mocked `secrets_doctor.gather` when asserting doctor.
- **Sherdog RSS removed** from `config/data_sources.json` + `config/seo/tapin.json`.
  MMA Fighting / Bloody Elbow / MMA Weekly / UFC.com stay. Ratchet: no
  `sherdog.com` URL in those files. `cached_warnings` drops URLs that are no
  longer configured so a 7-day-old cache cannot FAIL doctor after the removal.
- **Piper pool:** four release pairs (bobby/carl/eminem/patrick) downloaded into
  `video/voices/` (gitignored). `voices.json` `local.piper[]` equal weight 1.
  Doctor ready iff a path **ends with `.onnx`** and exists — README is not a voice.
  Rotation is existing `resolve_local_voice`. `PIPER_VOICES_DIR=video/voices` in
  `.env.example`; operator `.env` fallback is bobby `.onnx`.
- **ElevenLabs intake:** all seven ids listed; `ops voices` showed **none** on the
  account (19-char `3TPKV1kjDlVtZbl4Ksh` likely truncated). Moved to
  `_parked_voice_not_found`. No invented names.
- **Fact paste:** `read_multiline_paste` stops on `.` / `END` / two consecutive
  blanks; a single blank is a paragraph break. URL fetch + lint unchanged (URL-only
  only when the line *is* a URL).

**Left FAIL on purpose:** Ollama — still free/local; nothing pulled. Open roadmap
checkbox; shipped router item stays ticked.

**Do not commit** unless asked. Do not commit `.onnx` weights.

## 2026-08-28 (parked-four wave) — Edge TTS, ingest-clips, #389, #433


**Prompt:** implement the evening order (Edge TTS → `ops ingest-clips` → #389 →
#433), then explain the CUDA torch wheel — do not install it. Stay on the current
branch. Do not commit unless asked.

**Parked unchanged:** Phase M, #141–#146, CUDA torch wheel, #333/#349 (narrowed,
not this wave), #451 LAN booth, #416 scene-beat cuts.

**Tests failed first** (unmodified code): `TTS_PROVIDER=edge` not in `_ALT_TTS`
(warning + None); live `STATUS_UNAVAILABLE` + 10h cache was not served; 50h was
not the issue yet because *no* stale path existed; `from core.cross_channel_dup`
was `ModuleNotFoundError`; `ops next` blockers had only the render-gate until
the collision line was appended.

**Shipped (measured):**
- **Edge TTS** (`TTS_PROVIDER=edge`): `_ALT_TTS` entry, `[free]` extra
  `edge-tts` unmodified (LGPL-3.0 linking; decisions §28). Prints `(cloud, $0)`
  not `(local, $0)`. `is_local_tts_provider()` False; `estimate_run_cost` tts==0.
  Lexicon as SSML `<sub>`/`<phoneme>` only when a substitution matches. WordBoundary
  sidecar `{word, start, end}`. Stream failure → None (ElevenLabs). Never default;
  Piper stays `_LOCAL_TTS_ORDER` floor. `_tts_provider_ready("edge")` is importable.
- **`ops ingest-clips`**: dry-run default; `--apply` muted H.264 remux. Filename →
  library folder (GTA V alias). Unmatched listed, not dumped into `gaming/`.
  `clip_index.json` ffprobe fields; HUD `null` (documented gap). `command-ref`
  regenerated (#458).
- **#389**: live failure ≤48h serves expired cache, flagged STALE, not a hit,
  score 0; >48h refuses; honest `inactive` does not resurrect; eligible stale not
  clobbered. `STALE_CACHE_MAX_AGE_HOURS=0` restores today.
- **#433**: same `extract_anchors` franchise (else `normalize_title` on the topic)
  **and** same real `infer_domain` lens. TapIn + MoneyWise GTA *review* blocks;
  Take-Two *stock* allows. Pipeline before `generate_content_package`; publish
  next to `title_collision`; `ops next` via `publish_blockers`. Suite
  `CROSS_CHANNEL_DUP=off`.

**CUDA (explained, not installed):** `nvidia-smi` reports **CUDA 13.1** on the
4070 Ti; runtime torch is `2.8.0+cpu` / `cuda.is_available() False`. Uninstall
the CPU wheel first, install the CUDA wheel pytorch.org lists for that driver,
prove `+cu…` and `True`, then `ops doctor`. NVENC already ships via ffmpeg (#38).

**Not done:** live Edge synth (needs Microsoft; CI mocks `Communicate.stream`);
`--apply` ingest against the Xbox folder (dry-run only unless the listing looks
right); HUD detector; #416; CUDA wheel.

**Audit:** ruff clean; suite **2339** (`python -m unittest discover -s tests -t .`);
previous wave was 2315. `git status --short data/` empty. `ops ingest-clips`
dry-run: 16 Xbox captures, 15 matched, 1 unmatched (GTA Online — no dump into
`gaming/`). `ops free-doctor` Voice line is still Piper, not Edge.

---

## 2026-08-27 - Next 10 from 331–480 (green-and-inert holes)

**Prompt:** view roadmap 331–480, complete the next 10 mixed items (mostly [S], couple
[M], green-and-inert first), then a fail-visible audit. Stay on
`consolidate/2026-08-27`. Do not commit unless asked.

**Parked:** Phase M, #141–#147, NVENC, CUDA torch, Edge TTS, `SCENE_MATCHED_BROLL` on
TapIn, Coverr as a quality lever, #389 stale-cache, #433 cross-channel dup,
#416/#417 owned footage.

**Shipped (measured):**
- **#332** disputed flag: operator vs Warriors source → `disputed=True`, losing line
  dropped from the corpus, report card prints DISPUTED.
- **#347** `ops vault-decay` wraps `expired_notes`. Empty vault: honest line, no WARNING.
- **#331** `stamp_as_of` on packed vault facts (`load_facts` + interactive
  `vault_accepted`). 20-day UFC fact labeled; just-pasted operator facts are not.
  Script is not regex-rewritten.
- **#346** rumor pass after odds. Bare GTA delay on a leak topic is softened;
  Tapology result left; "reports to EA" skipped. Known gap: outlet not inferred
  from the corpus.
- **#372** Apify cache hits × `COST_APIFY_PER_RUN` on `ops reliability`. `$` only
  when hits > 0.
- **#371** TTS forecast before synth; actual + delta on features. Fail-open.
- **#381** `PAID_CALLS=off` → Free via `resolve_cost_mode`. Doctor fails if
  `FREE_MODE_STRICT` is not armed.
- **#369** `PROJECTED_COST_MAX_USD` unset=off. When set, blocks `run_pipeline`
  before `run_discovery` using `estimate_run_cost`, not post-run actuals.
- **#405** both script texts on rewritten runs; omitted on clean (same shape as #322).
- **#394** three Tapology-class empty-200s session-disable; Wikipedia no-page and
  "Not an MMA topic" do not. Not persisted to `quota_state.json`.
- **#442** thin `ops next` over cost / decay / `blocking_publish_sentence`.

**Audit:** ruff clean; suite **2254** (`python -m unittest discover -s tests -t .`);
last-wave vault `n` / `relevance_corpus` / `channel_id` / Fortnite folder / xfade
duration still green; `git status --short data/` empty. Bugbot: INACTIVE-as-healthy
and as-of missing from interactive packing — both fixed in this wave.

**Not done:** #389, #433, #416/#417, FastAPI #147, Phase M.

---

## 2026-08-27 - Vault relevance engine finished (P2–P4)

**Prompt:** finish the vault relevance engine (public-corpus crash, two-stage web skip,
measured P3 flip, conditional P4). Do not restart P2; do not mix Fortnite clip-picker
work; do not demote `_GAME_ANCHORS` from topic-graph.

**Measured (`ops vault-eval --no-save`):** holdout from live runs 66 and 70, both labels,
scored precision **1.0** and recall **1.0** vs P1 baseline **0.667**. Overall on the
14-case set: 4 uncertain / 3 confident / 7 reject. The encoded P3 gate passed, so
`config/vault_relevance.json` `default_mode` flipped to `scored`.

**Shipped:**
- Public `Sources:` accept `relevance_corpus`; headless loads with `relevance_policy=public`;
  already-chosen URLs skip a corpus-less vault reload (`generate_content_package` no longer
  TypeErrors).
- Two-stage discovery: fetch non-web, score vault, then `_fetch_one("web_search")` or
  `STATUS_SKIPPED`. Scorer failure fails open to web and logs a warning. Legacy keeps the
  pre-fetch density skip. No second cache inside the signal.
- Operator pick indexes match the printed `1. …` numbers; near-threshold rejects are
  inspect-only and never auto-attached.
- P4 extract-tier JSON tiebreak (`VAULT_RELEVANCE_TIEBREAK`, default off) for
  operator-facing uncertain rows only. Cache key = topic + bullet + corpus hash + scorer
  version. Pre- and post-tiebreak bands persist on `FactRecord` and the run audit (§25).
  Never called from public Sources: or web-search skip.

**Not done:** P4 is not turned on. 4/14 uncertain is a real residual band, which is why
the code shipped; an extra extract-tier call on every operator vault scan is still an
operator opt-in.

---

## 2026-08-27 - Next 5 shipped; the POA for subject relevance

**Prompt:** "review cursor, edit as needed, and roadmap next 5", then: "what about
changing the scoring matrix itself? its not perfect isnt good enough ... brainstorm a
way to do so even if its the long route".

**Shipped:** 326 (install the declared deps, and 12.3.0 not 11.3.0), 327/328
(spoken-number ranges + the IndexError), 329 P0+P1 (surface anchor-less notes, and the
eval harness), 330 (the crossfade duration bug). 2160 tests green.

### Reviewing Cursor

Rule 6 worked end to end: it closed the run-71 vault gap **and** inverted the documented
gap test exactly as that test's docstring instructed. Marvel Rivals and SEGA genuinely
no longer attach to a GTA topic, and still do not.

The fix over-corrected. Requiring a shared *franchise anchor* also dropped notes about
the people and companies in the story - "Rockstar Games confirms the leak investigation
is ongoing" vanished from a GTA topic that names Rockstar, silently, on the interactive
vault prompt. `_GAME_ANCHORS` is a hand-kept list of **games**, so companies are invisible
to it.

### The POA: change the scoring matrix, not the filters

The operator's framing was right and it is the architectural answer.
`load_fact_records` is a **chain of boolean gates** - token overlap `and` distinctive
tokens `and` anchor family. A chain of ANDs can only get stricter, so every fix trades a
false positive for a false negative, and strong evidence on one axis can never
compensate for weak evidence on another. "Rockstar Games confirms..." has high corpus
similarity and zero anchor family; the chain kills it on the anchor gate and never sees
the similarity.

**This repo already solves this class of problem correctly elsewhere** -
`apis/topic_scorer.composite_score` is a weighted evidence model with
`core/opportunity.signal_breakdown` explaining the result. The vault path is the odd one
out. Make it match.

**Measured on run 71's real five bullets, against run 71's real corpus:**

| Axis | GOOD Rockstar | GOOD subpoena | BAD Wolverine | BAD Marvel | BAD SEGA |
|---|---|---|---|---|---|
| Entity-in-corpus (bullet) | **1/1** | 0/0 | **0/1** | **0/3** | 0/0 |
| Entity-in-corpus (note) | - | **1/2** | **0/0** | - | - |
| Corpus cosine (bullet) | **0.309** | 0.000 | 0.143 | 0.063 | 0.000 |
| Corpus cosine (note) | - | **0.296** | **0.000** | - | - |

No single axis separates all five; together they do. Entity-less bullets are decided at
the **note** level. And decisively: against the **topic** the bad Wolverine bullet
*beats* the good one (0.286 > 0.154) because the topic itself says "Wolverine"; against
the **corpus** the ordering is right at 2.2x. **The corpus is the disambiguator, not the
angle.**

Every input already exists - `fact_grounding.specific_entities` / `mentions`,
`authenticity._content_tokens` / `_cosine`, `fact_store.TIER_WEIGHTS`. No new dependency,
no model, **no hand list**. `_GAME_ANCHORS` becomes one weighted feature among six, so it
can shrink or retire without a cliff, and `topic_graph.py`'s second hand list stops being
load-bearing.

**Getting past "not perfect isn't good enough": make it a number.** P1 shipped
`core/vault_evals.py` (`ops vault-eval`), frozen labelled cases, deterministic rubric,
no LLM judge - **baseline precision 0.667, recall 0.667**. P2 has to beat that, measured.

**Phases:** P0 stop the silent drop (done) - P1 harness + baseline (done) - P2 scorer
behind a flag - P3 flip on a measured win, demote `_GAME_ANCHORS` - P4 optional
extract-tier tiebreak for whatever band remains. Never silent: the score and its
breakdown surface in the fact prompt.

**Limits recorded:** ALL-CAPS acronyms are not extracted as entities, so SEGA scores 0/0
on that axis; a short corpus weakens every axis; six fixtures is indicative, not
conclusive - grow the set from real runs before trusting a tuning decision.

### Worth not relearning

- **A manifest edit is not an applied upgrade.** The whole dependency wave was declared
  and never installed; the pin test now asserts installed-vs-declared.
- **11.3.0 was not the safe choice.** It still carried 25 advisories - all fixed only in
  12.x, and all in font/PDF/JPEG2000/TGA parsers, i.e. the untrusted-bytes surface.
- **A filter graph ffmpeg accepts can still be wrong.** The crossfade ran clean and
  shortened every background by the fade; only a real render with `ffprobe` showed it.

---

## 2026-08-26 - Next 20 (1L / 4M / 15S) implemented

**Prompt (step 2):** implement the mixed wave on `main` after PR #37. Same
exclusions (Phase M, #141–#147 FastAPI/tray/XL, Edge TTS, NVENC, CUDA torch,
`SCENE_MATCHED_BROLL` on TapIn, Coverr-as-quality, do not flip
`background_mode` to `local`).

**Shipped in order:**

1. **#47 topic graph `[L]`** — JSON sidecar; `get_best_bets` continues week-1 →
   week-2; graveyarded follow-up excluded; empty graph fail-open.
2. **§26 hybrid xfade `[M]`** — TapIn `hybrid_local_ratio` 0.70 (still hybrid,
   not local); `xfade` at the local→stock join. MoneyWise ratio unchanged.
3. **#46 seasonal calendar `[M]`** — `config/seasonal_calendar.json`; frozen
   `now=`; no HTTP.
4. **#123 spoken numbers `[M]`** — TTS path expands `29-1` / UFC 317 / `$50k`;
   captions keep digits.
5. **#42 franchise batch cache `[M]`** — same `build_key`/`_fetch_one` cache,
   franchise key inside `run_batch` only.
6–20. DATABASE_URL suite blanking; real PDF fixture; wolverine-only vault gap
   closed; Extended chapters; demonetization detector; policy runbook ops verb;
   n8n weekly-report cron; Dataview dossier keys; wiki-links; quota-increase
   playbook; booth favicon; 1.25× playback; Send-to facts.txt; tray git
   describe; TapIn swatch strip.

**Honesty:** Edge TTS Wave B still parked (LGPL-3.0). `background_mode` is still
`hybrid`. `origin/claude/docs-optimization-review-a4l104` stays unmerged.

---

## 2026-08-26 - Stock-footage preference + MoneyPrinter hyper-compare (docs)

**Prompt (step 3 of the four-step session):** note that the operator does not
like taking that much unnecessary stock footage — it is often unrelated, and a
cut from gaming to live-action reality with no transition is disorienting. Also:
what does MoneyPrinter actually do for video clips, and which project is better.

**Two different MoneyPrinters.** Do not conflate them.

- **MoneyPrinterV2** (`FujiwaraChoki`) — AGPL-3.0, ~30k★, velocity/cost play
  (gpt4free, KittenTTS). Pattern-borrow only; never clone near this repo.
- **MoneyPrinterTurbo** (`harry0703`) — MIT, the Aug-25 Wave A source. Same
  commodity generator shape as ShortGPT: topic → LLM script → stock clips →
  TTS → MoviePy/FFmpeg. **No fact engine, no claim verifier, no YouTube
  learning loop.**

**What Turbo does for clips** (read from `app/services/material.py`, not from
marketing):

1. After the script, an LLM emits a list of search terms (default **5**).
2. For each term it searches **one** configured source: Pexels, Pixabay,
   Coverr, or `local` (a folder). Exclusive — not a hybrid mix.
3. It downloads until summed `min(max_clip_duration, clip.duration)` covers
   VO length. Default **max clip = 5s**. Concat mode **random** (shuffle) or
   **sequential**. Optional transitions: none / fade / slide / shuffle.
4. `match_script_order` can keep term order; otherwise random shuffle is the
   default. Coverr: `GET https://api.coverr.co/videos` Bearer + `urls=true`.
5. Separate path: **WaveSpeed** on-demand AI clips (paid, stop when duration
   is filled) — closest analogue to our parked ComfyUI/LTX slot, not to Pexels.

**What we do:** TapIn ships `background_mode: hybrid` at `hybrid_local_ratio:
0.45`. `get_background_asset` takes one local gameplay clip and one stock
clip (Pexels → Pixabay → Coverr). `build_hybrid_concat_command` hard-concats
local then stock with **no fade**. Keyword rewrite + abstract-tag skip exist;
they do not make live-action "GTA" footage. `SCENE_MATCHED_BROLL` (opt-in) is
one stock clip per beat — more of the same problem.

**Verdict:** Content OS is the better *media OS* for TapIn/MoneyWise
(grounding, loop, compliance, cost meter, YouTube ops). Turbo is the better
*stock-b-roll concatenator* (transitions, 5-term LLM search, clip duration).
For the operator's actual complaint, **Turbo would make it worse** — more
live-action cuts per Short. The useful borrow is a crossfade at our hybrid
join, not Coverr-as-quality and not enabling scene-matched stock. Owned
gameplay (`background_mode: local` or a higher local ratio) is the fix; that
config was not flipped this session.

**Recorded as:** [decisions.md](decisions.md) §26,
[moneyprinter_vs_content_os.md](moneyprinter_vs_content_os.md). No production
render change.

---

## 2026-08-26 - Next-20 mixed S/M wave (implemented, not committed)

**Prompt:** user said "next 20" — implement the approved 20-item wave
(`new_repos_next_20_3a743bff.plan.md`) as Step 2 of a four-step session. No
commit. No Step 3 audit. No Step 4 commit.

**Shipped (in order 1→20):**

1. Original `/tdd` skill at `.claude/skills/tdd/SKILL.md` + Cursor copy (fail-then-fix; never mock the function under test; not a third-party copy).
2. Coverr stock provider (`GET https://api.coverr.co/videos`, Bearer, `urls=true`); registered; both channels + settings default; no-key fail-open, no healthy-run warning; prefer no-face tags.
3. Thumbnail composition arms `subject_scale` / `text_negative_space` / `hard_light` in our own words; kind stays `thumbnail`.
4. Wave C public-apis shortlist in `docs/agent_reach_evaluation.md` — no keyless candidate displaces `tiktok_trends`; `youtube_competitors` already has a free backend.
5. In-repo eval-corpus fixture `prompts/eval_corpus/invented_release_date.md` (gitignore exception); runner lists it with EVAL_CORPUS_LLM off.
6. Overnight `--facts-file` through existing `run_batch(..., key_facts=)`; `--file` remains topics.
7. Pillow==11.3.0, requests==2.32.4, drop moviepy; duration from `_probe_video_duration`.
8. #101 `captions.insert` on the publish path; fail-open if no track.
9. #124 250ms pause after line 1; skip is byte-identical.
10. #36 `ops topic-clone --run-id` calls `generate_draft` for real.
11. Vault competing-franchise gate (run-71 Marvel Rivals/SEGA vs GTA); remaining gap is a wolverine-only bullet with no franchise string.
12. #86 frozen golden scripts per channel on heuristic `score_script` (no LLM judge).
13. #89 `redact_for_public` + unpublished dossier withhold + SKU; pre/post line counts (§25).
14. #81 MoneyWise TapIn length/slot shape prior; never topics or `domain_slots`.
15. #28 learned intro duration; keep 2.15s until drop-off samples exist.
16. Expert Panel second original persona `shorts_pacing`; persist on the run; ops grade/booth when enabled; default off.
17. #105 opt-in channel comment (Data API has no pin); profanity first.
18. #106 Studio-deleted detection cancels `publish_log`; `ops studio-deleted` + daily_sync.
19. #133 `.ics` beside HTML dumps; `ops publish-ics`.
20. Tests that actually call `enabled_publish_platforms` / `publishers_for_channel` / `is_upload_configured`.

**Honest remaining gaps:** YouTube Data API cannot pin a comment; Coverr face filter is tag-based not vision; intro learning needs RETENTION_MIN_VIDEOS curves; wolverine-only vault bullets still attach; pins upgraded in files, local venv not reinstalled in this step.

**Parked:** Phase M, #141–#145, #146 tray daemon, #147 FastAPI, clip-from-source/avatar, volume-gated backtest, auto-flip TTS_PROVIDER, Benable #79, Edge TTS Wave B, CUDA torch, NVENC (#38).

---

## 2026-08-25 - Ten small tasks, production-complete wave (shipped)

**Prompt:** implement the documented MoneyWise persona plus #53, #298, #299,
#271, #262, #22, #21, #39, and #31 end-to-end on the current branch.

**Decisions and boundaries:**

- The persona is the exact finance-safe text documented in the 2026-08-23
  planning entry, including the schedule-backed Week Ahead recurring segment.
- Prompt versions are `content_engine_v7-<12 hex>` from SHA-256 over every
  content-engine function that constructs or repairs an LLM prompt. This catches
  silent source edits without hashing run-specific facts, dates, or topics; the
  source-unavailable fallback hashes stable code fields, never object addresses.
- Review metadata comes from the persisted content-run row, not a display
  fixture. Spoken duration comes from ffprobe on the persisted MP3 (not the
  intro-bearing final MP4); estimate uses persisted word count and the measured
  3.3 words/second constant.
- The burned-caption path now preserves a sibling SRT even for karaoke output.
  The booth converts that SRT to WebVTT because HTML5 `<track>` does not
  reliably consume SRT directly.
- #22 is deliberately a conservative Pillow visual-density check over the
  bottom 20%. It catches risky high-contrast composition but does not claim
  face or OCR detection, and reports QUIET/REVIEW rather than SAFE.
- `ops render-preview` writes `_preview.mp4` at 480x854 / ultrafast / CRF 30,
  uses a separate `_preview.mp3`, skips intro, extra formats, thumbnails,
  media-row updates, and asset records. The publisher blocks `_preview.mp4`.
  Default publish rendering remains 1080x1920 / fast / CRF 23.
- `ops artifact-retention` is a report, not a job yet. It lists old drafts,
  traces, and vault `_runs` clones, ignores `--apply`, and has no delete call.
  The older `ops artifacts --apply` output-cap command remains a separate,
  explicitly destructive pre-existing surface.

**Behavioral proof:** the initial red run recorded 11 tests (3 failures, 8
errors); the completed first pass had 13 wave tests. The audit added 3 more
behavior tests and observed 7 failures/errors before the fixes. The 16-test
module now exercises shipped config/persona, deterministic source-hash drift,
stored booth metadata and spoken-audio duration, escaped SRT-to-WebVTT,
thumbnail risk detection through the production caller, caption skin in the
real render caller, isolated preview output plus upload rejection, and
report-only retention.

**Operator proof:** shipped MoneyWise validation reached the real config path
(persona warning gone; the expected missing local OAuth-token warning remains);
`ops artifact-retention` printed `DRY RUN ONLY` against a temp root and selected
zero files; `ops booth --channel moneywise` wrote `booth.html` under a temp
HTML directory; `ops render-preview --run-id 999999` returned the explicit
`No content run` guard without writing media.

**Still out:** no dependency upgrades, no real paid TTS/ffmpeg preview render,
no OCR/face model, and no retention deletion mode. Those are materially larger
or require operator media/cost approval.

**Final verification:** `ruff check .` and `ruff format --check .` passed;
the full isolated suite ran **1,985 tests OK** (up from 1,969), and
`git status --short data/` was empty.

---

## 2026-08-25 - Post-wave-4 operator pickup (shipped)

**Prompt:** take the next five roadmap pickups, plan them, then implement them
without committing. The five work units were #313, #282, #308-310 together,
#232, and #122.

**Two roadmap assumptions were false when traced through production:**

1. #313 said the tray action would use an "existing opt-in gate file". No
   overnight pause file or check existed. The wave added one
   (`core/overnight_pause.py`) and checks it at the start of `run_overnight`,
   before topic collection or batch generation.
2. #232 described a Desktop link to the booth URL. `serve_booth` binds an
   ephemeral port and the server dies with its process, so a literal URL would
   be a dead shortcut. `booth_os.pyw` starts the server, opens the browser, and
   keeps the process alive; `ops booth-shortcut` installs that launcher.

**Shipped:**

- **#313:** tray pause/resume button and CLI flags. The paused batch returns an
  explicit result and performs no topic collection.
- **#282:** deterministic `Human: just now / Nm / Nh / Nd ago`, plus honest
  `heartbeat off` and `never` states on the real tray chip.
- **#308-310:** the successful primary ffmpeg argv is captured at render time;
  a music-bed failure replaces it with the VO-only retry argv. The separate
  intro-concat argv is captured too. Both persist in the existing redacted run
  trace. The booth renders native collapsible trace/command sections and copies
  a PowerShell-safe command. Nothing is reconstructed from incomplete paths.
- **#232:** persistent Desktop booth shortcut via `pythonw`, reusing the proven
  WScript.Shell installer rather than adding a second shortcut mechanism.
- **#122:** root `video/backgrounds/license.yaml` records owned/commercial use.
  A nearer folder sidecar overrides it; `LocalAssetProvider` carries the
  resolved metadata into `AssetResult.attribution`, and the existing asset
  recorder persists it.

**Behavioral proof:** `tests/test_next_five_pickups.py` failed against the
unmodified implementation with 2 failures + 6 errors (missing pause module,
formatter, callback/persistence, booth kwargs, shortcut, and attribution).
After wiring, the full isolated suite ran **1,969 tests OK**. `ruff check .`
passed; formatting was applied to the two files identified by
`ruff format --check`.

**Operator proof:**

- Pause -> `ops overnight --count 1` printed `Overnight paused by operator
  flag` and drafted nothing; resume removed the temp override flag.
- `ops booth --channel tapin` wrote the real last-run booth, whose HTML contains
  the redacted raw trace section. That historical run predates command capture,
  so ffmpeg details will first appear after the next render.
- `ops booth-shortcut` installed
  `C:\Users\jonma\Desktop\Content OS Review Booth.lnk`.

**Still out:** MoneyWise persona config, the Pillow/requests/MoviePy dependency
wave (needs a real thumbnail/render), FastAPI #147, tray daemon #146, Phase M,
and the operator's Piper voice judgment.

---

## 2026-08-23 - MoneyWise persona + the Pillow decision (docs only)

**Prompt:** "give moneywise a persona, then how would we deal with pillow?
different software or cut entirely, update? document and answer only, no loc"

---

### 1. MoneyWise persona

**Why it was missing:** candidate 33's `channels.json` ratchet found it on its first
run. Every prior test built its own dict, so the *shipped* config was never validated
and the gap sat there unseen. `moneywise` is the higher-RPM channel and it was
publishing with no human-context block at all.

**What consumes it:** `core/channel_persona.py` reads `perspective`, `tone`,
`audience`, `recurring_segment`, `signoff` (in that order, extras appended) and folds
them into an advisory prompt block. `core/channel_go_live.py:81` requires **`tone` +
`audience`** at minimum to report the channel ready.

**The constraint that shapes it:** finance content cannot sound like advice. The
description already carries "Not financial advice. For informational purposes only."
(#125), and the script prompt forbids personalised recommendations. A persona that
reads as a stock picker would fight both. So the point of view is deliberately
*explanatory* - the person who reads the filing and translates it - not predictive.
That is also the honest differentiator against the "5 stocks to buy now" tier the
2026 authenticity policy is aimed at.

**Ready to paste into `config/channels.json` under `moneywise`:**

```json
"persona": {
  "perspective": "someone who reads the filing, the print, or the fine print before having an opinion - and says plainly what it means for a normal paycheck",
  "tone": "calm, plain-spoken, mildly sceptical of hype - explains, never sells",
  "audience": "working adults who want to understand the money story behind the headline, not be told what to buy",
  "recurring_segment": "Week ahead: the two or three numbers that actually move things, and why",
  "signoff": "Numbers first. Opinions after."
}
```

Notes on the choices:

- **`recurring_segment`** maps to the schedule that already exists in the config -
  Sunday 18:00 ET is the "week ahead" slot, alongside weekday 08:30 pre-market and
  Saturday 10:00 evergreen. A recurring segment the schedule cannot support would be
  invented continuity, which is the thing the persona is meant to prevent.
- **Deliberately ASCII.** The persona text flows into prompts, logs and cp1252
  PowerShell output; `tapin`'s em dash is fine in the file but there is no reason to
  add more (candidate 250's ASCII-safe rule).
- **Tone contrasts with TapIn on purpose** ("high-energy, confident, a little
  irreverent"). Two channels sharing one voice is exactly the templated-at-scale
  pattern the policy penalises.
- Not written into `channels.json` this pass - the prompt was document-and-answer.
  Dropping it in is a config edit, after which `py -m config.validate_channels
  --channel moneywise` should report 0 warnings (it currently warns on the gap).

---

### 2. Pillow: update. The blocker was not real.

**Answer to "different software or cut entirely, update?" - update, and it is
unblocked today.** Pillow is 26 of the 75 known vulnerabilities that candidate 98's
pip-audit baseline found, the worst single package by a wide margin.

**Correcting the record:** this was previously written up as "pinned for moviepy 1.0.3
compat", which is wrong and had been the reason to defer. Measured:

```
moviepy 1.0.3 requires: decorator, imageio, imageio_ffmpeg, tqdm, numpy,
                        requests, proglog          <- no Pillow at all
imageio    2.37.3  ->  pillow>=8.3.2               <- floor
goose3     3.1.21  ->  Pillow                      <- unbounded
torchvision        ->  pillow!=8.3.*,>=5.3.0       <- no ceiling ([providers] only)
matplotlib         ->  pillow>=9                    <- floor ([providers] only)
```

**Nothing in the tree caps Pillow.** `pyproject.toml:26` is a bare `Pillow==9.5.0`
with no rationale comment. The constraint was folklore.

**The API surface is four calls**, none removed in Pillow 10, 11 or 12:

| Call | File | Status |
|---|---|---|
| `Image.new("RGB", ...)`, `ImageDraw.Draw`, `ImageFont` | `assets/flux_thumbnail.py:425` | stable |
| `Image.open`, `ImageStat` | `assets/thumbnail_scorer.py:63` | stable |

No `Image.ANTIALIAS`, no `draw.textsize`, no `font.getsize` - the three removals that
break most Pillow 10 upgrades. Verified by grep across `assets/`, `video/`, `core/`.

**Recommendation:** bump to **Pillow 11.3.0**, not 12.x. 11.x clears all 26 CVEs and
is the conservative choice while 12 is new; the four calls above are identical in
both, so 12 is a later no-op bump if wanted. Verify with one real render (thumbnail
generation is the only consumer) plus `py -m scripts.ops all-checks`.

**"Cut entirely" is the wrong question for Pillow, and the right one for moviepy.**
`moviepy` appears in exactly one line of production code:

```python
video/render_video.py:4    from moviepy.editor import AudioFileClip
video/render_video.py:220  audio_clip = AudioFileClip(mp3_path); duration = audio_clip.duration
```

One import, to read a duration. **The same file already has an ffprobe duration
helper** - `_probe_video_duration` at `video/render_video.py:63`, which uses
`format=duration` and works on audio containers too. So moviepy (and its decorator /
tqdm / proglog / imageio chain) is carried for a call the file can already make.
Cutting it is a genuine simplification independent of the security question - and
ffmpeg is already a hard requirement, so it adds no new dependency.

**Also worth noting:** the remaining 49 vulnerabilities are concentrated in the
optional `[providers]` extra - `torch` (8), `transformers` (5) - plus `setuptools`
(7), which is build tooling, not runtime. Only Pillow, `requests` (a trivial
2.32.3 -> 2.32.4 bump) and `cryptography` are in the core runtime path. That reframes
"75 vulns" considerably: the core install is a much smaller problem than the number
suggests.

**Suggested wave order:**

1. `Pillow==9.5.0` -> `11.3.0` + `requests` 2.32.3 -> 2.32.4. Verify with a real
   render and a Pillow-fallback thumbnail.
2. Drop `moviepy` from `pyproject.toml`; swap the one `AudioFileClip` call for
   `_probe_video_duration`. Verify the rendered mp4 duration matches.
3. Leave `[providers]` alone until a provider is actually in use; pin `setuptools`
   only if CI starts flagging it.

Both items need a **real render** to verify, which is why they stay their own wave
rather than riding along with a correctness pass.

---

## 2026-08-22 — Honesty + leave-the-terminal wave 4 (shipped)

**Prompt:** "back to work roadmap back to work" — resume the roadmap. Implement a
coherent wave of leftover `[S]` then `[M]`. Do not commit or push. Prefer
honesty / leave-the-terminal / operator-safety. Skip #147 FastAPI, #146 tray
daemon, caption skin (#21), thumbnail safe-area (#22), Phase M, volume-gated
backtest.

**Swap vs numerical next:** did **not** pick 21 caption skin, 22 thumbnail
safe-area, 31 artifact retention, 101 caption track, 146 tray daemon, 147
FastAPI, or 172 HTML design system. Ranked leftover `[S]` that (1) keep the
next *public* honest (playbook lint, vault sources in the description,
ungrounded numeric chips, authenticity semantic bar, grade breakdown,
overnight-render / RPM / yesterday-unsynced copy), (2) surface TTS 91% /
quota on the booth (cache-hit $0, Pillow vs Flux, signal dots, feed-stale,
sticky cost + quota, 16px type), (3) leave PowerShell (copy unlisted URL,
Obsidian dossier URI, postmortem markdown, quiet-hours toast DND, tray last
domain). **#147 still skipped.** No #141/#142/#143/#144/#145, no Phase M, no
volume-gated backtest, no auto-flip Piper.

**Shipped (20):** 37 playbook lint, 103 description sources, 252 copy unlisted
URL, 255 Obsidian dossier URI, 275 numeric chips, 276 semantic-arm bar, 277
grade breakdown, 280 TTS cache-hit $0, 281 Pillow vs Flux badge, 283
overnight-render plain English, 284 RPM deferred reason, 285 yesterday
unsynced copy, 289 signal-health dots, 290 feed-stale strip, 292 mute toasts
in quiet hours, 305 16px min type, 306 sticky cost bar, 307 sticky quota bar,
311 postmortem markdown, 316 tray last domain.

**Knobs:** `DESCRIPTION_SOURCES`, `CONTENT_TOAST_DND`, `CONTENT_TRAY_DOMAIN`.
Suite forces `CONTENT_TRAY_DOMAIN=false`. Playbook lint and yesterday-unsynced
copy have no kill switch (read-only / informational).

**Out:** Phase M, volume-gated backtest, $0 TTS voice judgment, FastAPI host,
`.env` / secrets / `data/` / `output/`. Leftover next: 313 pause-overnight,
282 human-presence last-seen, 308–310 collapsible/copy ffmpeg, 232 booth
`.lnk`, 122 `license.yaml`. Live-run 71 docs (already dirty) left as
documentation-only.

---

## 2026-08-21 — Honesty + leave-the-terminal wave 3 (shipped)

**Prompt:** implement **20 more** roadmap items on top of unpushed `7c243b0`,
commit, do not push / amend / PR. Advising allowed. Prefer `[S]` then `[M]`.

**Swap vs numerical next:** did **not** pick 21 caption skin, 22 thumbnail
safe-area, 31 artifact retention, 101 caption track, 146 tray daemon, 147
FastAPI, or 172 HTML design system. Ranked leftover `[S]` that (1) keep the
next *public* honest (UFC PPV window, quiet hours, SEO first line, UFC
stock-query rewrite, odds "favored" not "will", gambling-safe CTAs, FTC
copy), (2) surface TTS 91% / quota on the booth (escaped-LLM pill,
Standard-would-have-billed, allocated vs marginal, uploads + ElevenLabs
header, Apify pills, thin-facts banner), (3) leave PowerShell (click-toast
opens the mp4, high-contrast CSS, skip-link, copy-as-markdown, tray doctor
HTML + last grade). **#147 still skipped.** No #141/#142/#143/#144/#145, no
Phase M, no volume-gated backtest, no auto-flip Piper.

**Shipped (20):** 115 UFC PPV blackout, 116 quiet hours, 118 description
SEO first line, 121 UFC stock-query rewrite, 126 odds market voice, 127
gambling-safe CTAs, 128 FTC affiliate line, 229 click-toast opens mp4, 234
high-contrast CSS, 251 copy-as-markdown, 261 skip-link, 273 escaped-LLM
pill, 274 thin-facts banner, 278 Standard-would-have-billed, 279 allocated
vs marginal one-liner, 286 uploads-left booth header, 287 ElevenLabs chars
header, 288 Apify remaining pills, 314 tray doctor HTML, 315 tray last
grade.

**Knobs:** `UFC_PPV_BLACKOUT`, `QUIET_HOURS`, `DESCRIPTION_SEO_FIRST_LINE`,
`FTC_DISCLOSURE`, `ODDS_MARKET_VOICE`, `GAMBLING_SAFE`,
`STOCK_QUERY_UFC_REWRITE`, `CONTENT_TOAST_OPEN_MP4`, `CONTENT_TRAY_GRADE`.
Suite forces PPV/quiet/odds/gambling/SEO/tray-grade off.

**Out:** Phase M, volume-gated backtest, $0 TTS voice judgment, FastAPI
host, `.env` / secrets / `data/` / `output/`.

---

## 2026-08-21 — Honesty + leave-the-terminal wave 2 (shipped)

**Prompt:** implement **20 more** roadmap items on top of unpushed `48a062f`,
commit, do not push / amend / PR. Advising allowed. Prefer `[S]` then `[M]`.

**Swap vs numerical next:** did **not** pick 21 caption skin, 22 thumbnail
safe-area, 23 end-card, 146 tray daemon, 147 FastAPI, or 172 HTML design
system. Ranked leftover `[S]` that (1) keep the next publish honest
(category / kids / language / unique titles / UFC lint / MoneyWise
disclaimer), (2) stop doomed Free-mode sessions (RAM/VRAM, NVENC *probe*
not encode, secrets-doctor, OneDrive), (3) surface TTS 91% and quota
outside PowerShell (booth subtitle, economics CSV, scheduled/overnight/
uploads-left toasts, tray folder + Free/Standard). **#147 still skipped.**
No #141/#142/#143/#144/#145, no Phase M, no volume-gated backtest, no
auto-flip Piper.

**Shipped (20):** 94 NVENC capability probe, 95 RAM/VRAM preflight, 96
secrets-doctor, 100 OneDrive/.git hazard, 102 YouTube category from
`infer_domain`, 107 madeForKids audit, 108 default language, 117 title
uniqueness, 125 MoneyWise finance disclaimer, 129 UFC title lint, 135
economics `--csv`, 225 scheduled-upload toast, 227 overnight-drafts toast,
228 uploads-left balloon, 242 `ops grade --html`, 250 ASCII-safe HTML, 256
reveal trace, 272 booth TTS 91% subtitle, 312 tray open-output folder, 317
tray Free vs Standard.

**Knobs:** `RAM_MIN_GB`, `VRAM_MIN_GB`, `YOUTUBE_DEFAULT_LANGUAGE`,
`TITLE_UNIQUENESS`, `UFC_TITLE_LINT`, `FINANCE_DISCLAIMER`. Suite forces
`RAM_MIN_GB=0`, `VRAM_MIN_GB=0`, `TITLE_UNIQUENESS=off`.

**Out:** Phase M, volume-gated backtest, $0 TTS voice judgment, FastAPI
host, `.env` / secrets / `data/` / `output/`.

---

## 2026-08-21 — Leave-the-terminal wave (shipped)

**Prompt:** implement the **Recommended next 20 (2026-08-20 night)**, commit,
do not push. Advising allowed: prefer 20 *working* operator-visible pieces
over a half-done FastAPI shell.

**Swap:** skip **#147** FastAPI operator shell (`[L]` — would swallow the
wave; booth uses stdlib `http.server` via `ops booth --serve` instead). Slot
20 is **#240** `ops status --html`. **#254** reveal-thumb ships on the same
`ops reveal` helper as #253 (the two `[S]` leftovers named in the prompt).
Did **not** start Content OS Desktop #141, Shorts Visual Studio #142, or
Phase M.

**Shipped (20 + bundled 254):** 223 reliability `--html`, 222 tray quota
chip, 291 AppUserModelID, 226 breaker toast, 221 ffmpeg toast, 224 lightbox,
253 reveal mp4, 241 economics `--html`, 92 MAX_PATH, 93 FFmpeg lock retry,
109 unlisted-before-public, 319 blocking-publish sentence, 43 script trim,
97 trace redaction, 231 pyw Start Menu shortcut, 171 last-run booth, 200
thin-facts abort screen, 198 doctor `--html`, 78 intelligence-report SKU,
240 status `--html`. 254 bundled.

**Knobs:** `CONTENT_TOAST`, `CONTENT_HTML_OPEN`, `YOUTUBE_UNLISTED_REVIEW`,
`SCRIPT_TRIM`, `WIN_MAX_PATH`, `WIN_LONG_PATHS`, `FFMPEG_LOCK_RETRIES`.
Suite forces toast/HTML-open/unlisted-review off.

**Out:** Phase M, volume-gated backtest, $0 TTS voice judgment, FastAPI
host, `.env` / secrets / `data/` / `output/`.

---

## 2026-08-20 (night) — Recommended next 20 pickup order

**Prompt:** produce the **next 20** roadmap items in pickup/importance order
after PR #35 (live-run wave) and PR #36 (candidates 141–320). Ranking + docs
only — no features, no commit, no push, no `.env` / secrets / `data/` /
`output/`. Rank by the cycle’s three axes (**future viability**, **short-term
success**, **real-world cost**) plus the operator’s last theme (**get out of
the terminal / UI / aesthetics / app**) without unparking Phase M. Do not
re-list shipped 20 Aug waves or F1/F2/F3. Brainstorm next-5 (221, 222, 223,
224, 171) is a hint, not a cage. Prefer `[S]` then `[M]`; at most one `[XL]`
as item 20 with a warning — none used. PARKED items out unless labeled, never
as #1.

**Ranking rationale**

1. **The cost/honesty CLI wave is largely shipped.** Remaining pickup is not
   another ASCII dashboard; it is *surfacing* what already exists (reliability,
   economics, quota, gates) outside PowerShell — then the leftover Windows /
   leak / policy `[S]` that can still kill the next publish.
2. **Brainstorm next-5 does not survive as 1–5.** All five stay *in* the 20;
   the order changes. A ffmpeg-finished toast is operator minutes; a **breaker
   toast** and a **browser reliability dump** prevent doomed sessions and
   silent disablement (the cycle’s actual failure shape). **AppUserModelID
   (#291)** sits before the toasts so they group as Content OS, not
   `python.exe`. The **review booth (#171)** stays `[M]` at #16 — after HTML
   dumps, Explorer reveal, and unlisted-before-public — not as the first
   “app.”
3. **Leftover 1–140 still beats decorative CSS.** `#92` MAX_PATH and `#93`
   Defender file-lock can waste a render after you left the terminal. `#43`
   script trim still moves TTS (~91% of a rendered run). `#97` trace redaction
   and `#109` unlisted-before-public are honesty/policy, not chrome. Phone
   bezels, grain toggles, and magazine layouts stayed out.
4. **Viability still gets a slot.** `#78` intelligence-report SKU (no video,
   no TTS) is #19 so the UI theme cannot erase operating_plan §6.2.
5. **No `[XL]` in the 20.** `#147` FastAPI shell is item 20 with an `[L]`
   warning — thinnest host for the booth, not Content OS Desktop (#141).
   Phase M, volume-gated backtest, and the $0 TTS *voice judgment* stay out
   (not even as labeled PARKED pickups).

**The 20** (id · title · size) — detail + surfaces in
[roadmap.md](roadmap.md) **Recommended next 20 (2026-08-20 night)**:

1. **223** `ops reliability --html` `[S]`
2. **222** System-tray quota chip `[S]`
3. **291** Windows AppUserModelID `[S]`
4. **226** Toast when a breaker trips `[S]`
5. **221** Toast when ffmpeg finishes `[S]`
6. **224** Thumbnail lightbox (last Pillow thumb) `[S]`
7. **253** Reveal mp4 in Explorer `[S]`
8. **241** `ops economics --html` `[S]`
9. **92** Windows MAX_PATH / long output paths `[S]`
10. **93** FFmpeg file-lock retry `[S]`
11. **109** Unlisted review before public `[S]`
12. **319** “What’s blocking publish” one-sentence `[S]`
13. **43** Script trim pass `[S]`
14. **97** Redact API bodies from traces `[S]`
15. **231** Start-menu shortcut via pyw `[S]`
16. **171** Last-run review booth `[M]`
17. **200** Thin-facts abort screen `[M]`
18. **198** Doctor HTML page `[M]`
19. **78** Intelligence-report SKU `[M]`
20. **147** Localhost FastAPI operator shell `[L]` — warning: not the next hour; not #141.

**What stayed out**

- Shipped evening next-5 (pre-run gate, oauth tests + coverage extra,
  pronunciation lexicon, allocated vs marginal, numeric/record grounding) and
  the 20 Aug follow-on waves / F1–F3.
- PARKED: Phase M, volume-gated recommender backtest, $0 TTS voice judgment
  (including #144 / #166 / #167). Not in this 20.
- Massive **141–145** (Desktop, Visual Studio, Portfolio Web OS, Distribution
  Sidecar, Moat Suite). Item 20 is `#147` `[L]`, not an `[XL]`.
- Clip-from-source, avatar, storyboard, `instagram_figures`, MoneyWise *depth
  signals* (a board is #159 `[L]`, not this wave).
- Decorative CSS / aesthetics-only hours (phone bezel, grain, magazine
  layout, 2×2 contact sheets) until HTML dumps exist.
- Full review room **#168**, tray *daemon* **#146**, HTML design system **#172**
  (themed `--html` is enough until several dumps exist), file-count retention
  **#31** (`ops artifacts` already caps GB).

**Rejected this session:** implementing any of the 20; restoring Phase M;
auto-flipping Piper; rewriting July docs; overwriting the 141–320 candidate
lists; touching `.env` / secrets / `data/` / `output/`. No commit.

**Canvas:** `roadmap-next20-night.canvas.tsx` in the Cursor canvases folder
(grouped UI/app vs cost vs honesty vs ops).

---

## 2026-08-20 (late-night brainstorm) — 180 ideas (UI / app / aesthetics / sibling software)

**Prompt:** brainstorm **180 unique** ideas after the 20 Aug waves on `main`
(operator: PR #35), persist them, and leave a readable ranking. Counts must
hit exactly: **5 massive / 25 larger / 50 moderate / 100 small.** Cover
future viability, short-term success, and real-world cost (the house ranking
used all cycle) **and** more aesthetics/UI, application development / getting
out of the terminal, and expansion of this project **or different software**
beside it. Honest about YouTube-only and Phase M parked. Planning only — no
features, no commit, no push, no `.env` / secrets / `data/` / `output/`.

**Constraints honored:** skip anything already `[x]`; do not restate shipped
items (pre-run gate through F3 keyhash clear, including the 20 Aug night /
evening / follow-on waves); skip Next-up duplicates and candidates **1–140**
unless reframed as a *new product* with a new number; Phase M, the
volume-gated recommender backtest, and the $0 TTS *voice judgment* may appear
only as massive/larger labeled **PARKED**. TTS remains ~91% of a rendered
run; YouTube upload ≈ 1,600/10k units; remaining paid Apify is
`tiktok_trends` + `youtube_competitors`; Windows/PowerShell; unittest; no
second signal cache; breakers via `quota_governor` only.

**How ranked**

1. **Did not overwrite** the 2026-08-20 evening **Recommended next 5** — those
   five are already marked **shipped** (night wave). A new **Brainstorm next-5
   (UI/app)** sits beside them so the house ranking stays the historical
   record.
2. **House axes still bind:** future viability, short-term success, real-world
   cost. This pass *covers* them; it does not pretend the CLI cost/honesty
   work is unfinished.
3. **Operator themes this prompt asked to cover** (not 100% one theme):
   aesthetics/UI, leaving the terminal (desktop, web, tray, canvas, operator
   console), expansion **or sibling software**. Massive ideas are new product
   surfaces / years of work; small ideas are hours / a PR.
4. **Short-term UI/app pickup** is five *small/moderate* items that help the
   next publish (see the toast, leave a doomed run unstarted, review without
   scrolling `main.py`) **without** restarting Phase M.
5. PARKED items are labeled in-title. Sibling apps are called out as *not
   this CLI*.

**Lists:** [roadmap.md](roadmap.md) **Candidates 141–320 (2026-08-20 late-night
brainstorm)** — Massive 141–145 `[XL]`, Larger 146–170 `[L]`, Moderate
171–220 `[M]`, Small 221–320 `[S]`. **Brainstorm next-5 (UI/app)** is under
Next up, below the shipped evening five.

**Brainstorm next-5 (UI/app)** — small/moderate, short-term, no Phase M:

1. **221** Windows toast when ffmpeg finishes `[S]`
2. **222** System-tray quota chip (uploads-left + ElevenLabs chars + Apify
   breaker) `[S]`
3. **223** `ops reliability --html` themed snapshot `[S]`
4. **224** Thumbnail lightbox for the last Pillow thumb `[S]`
5. **171** Last-run review booth (localhost play / grade / approve) `[M]`

**The 5 massive (full)**

1. **141 — Content OS Desktop (local-first operator console)** `[XL]`
   The operator's bottleneck is no longer a missing governor; it is living in
   PowerShell. A Tauri or WinUI shell over existing `core/` (discovery,
   review, job queue, publish, reliability, economics) is years of UX, a11y,
   packaging, and Windows integration. Python stays the engine: same
   `make_signal()` shape, same `quota_governor` façade, no second signal
   cache. This is different software that *hosts* Content Machine, not a
   prettier `main.py`.

2. **142 — Shorts Visual Studio (aesthetics as a product)** `[XL]`
   Look today is a stock loop, Pillow/Flux thumbs, burned captions, and ANSI
   `ui_theme` skins. A sibling design app — type, motion, brand kits,
   thumbnail composition, caption choreography, shared design tokens with
   any future GUI — is a years-long product sitting *beside* the CLI.
   Distinct from candidates 21–28 (JSON skins, PIL checkers, one Ken Burns
   beat): those are flags; this is a studio.

3. **143 — Portfolio Intelligence Web OS** `[XL]`
   Vision v3 ("operate media businesses"): multi-channel margin, opportunity
   scanner, channel launch, holdouts, YPP. Honest: operating_plan still says
   **don't go SaaS** until the YouTube-only data moat is real (~10 measured
   vs a 15-sample recommender gate). This is the 12-month architecture as a
   product surface, not a CLI dashboard restyle, and it stays YouTube-only
   until Phase M is unparked.

4. **144 — PARKED — Distribution Sidecar (TikTok / Reels)** `[XL]`
   Phase M as *different software* that consumes an already-rendered 9:16 —
   never as Content Machine feature flags, never as the next pickup. Live
   constraint remains YouTube Data API (upload ≈ 1,600 of 10k/day). Parked
   by operator choice; listed so the idea isn't lost and so it cannot
   masquerade as a small YouTube tweak.

5. **145 — Moat Suite: Vault Companion + Clip Librarian + Cost Tower** `[XL]`
   The dataset *is* the company (operating_plan §7). Three sibling apps —
   facts/playbooks/dossiers with tier/expiry UX; licensed clip memory with
   anti-repeat and performance; spend control for TTS (~91% of a rendered
   run), the two remaining paid Apify actors, and YouTube units — that
   outlive any one renderer. Not this CLI; they read traces, vault, and
   `quota_governor.snapshot()` only.

**Rejected this session:** implementing any of the 180; restoring Phase M as
a near-term YouTube checkbox; auto-flipping Piper; treating clip-from-source /
avatar / Instagram figures as "next"; rewriting July docs; merging
`docs-optimization` branches; touching `.env` / secrets / `data/` / `output/`.
No commit.

**Canvas:** `brainstorm-141-320-ui-app.canvas.tsx` in the Cursor canvases
folder for this workspace.

---

## 2026-08-20 (follow-on 4) — Next 20 after night + evening + wave 3

**Prompt:** complete the next 20 roadmap candidates in pickup/importance order on
top of the three uncommitted waves, then audit.

**Pickup:** no new "Next 20" list after wave 3. Ranked previously skipped-but-eligible
items (C9, 68 fixture, 70 diagnostic, 67 report-only) then remaining evening `[S]`,
morning leftover `[S]`, and afternoon `[S]` for operator safety / suite hygiene.
Parked: Phase M, volume-gated backtest, $0 TTS *voice judgment* (no auto-flip Piper).

**Skipped:** none of the 20. **67** shipped report-only (no auto-assign). **70**
shipped as a CUDA readiness probe (no pip install / no kWh meter until CUDA torch
is actually on). **68** used a synthetic fixture in `tests/fixtures/` (no real
invoice, no network).

**Shipped:**

1. C9 Google HTTPS leak (99) — skip YouTube warmup in tests; `static_discovery=True`.
2. Apify monthly true-up (68) — synthetic invoice vs $0.02/run; `ops apify-trueup`.
3. CUDA / GPU diagnostic (70) — `core/cuda_probe.py`; no install; `ops doctor`.
4. TTS provider Bayesian report (67) — `ops tts-arms`; never writes experiments.json.
5. Cap `output/` by GB (77) — `ops artifacts`; dry-run default; `--apply` deletes oldest.
6. Inauthentic-content hash canary (80) — snapshot-only on reliability; no HTTP.
7. RPM x cost by domain (84) — `ops economics` domain lines.
8. Weekly moat backup (85) — dry-run plan; secrets excluded; pg_dump listed not run.
9. YPP checklist (87) — `ops ypp`; fail-open without metrics.
10. Per-stage LLM cost — `complete(..., stage=)`; script/brief/title tagged.
11. Docs metric lint in CI — `tests/test_docs_lint.py` + CI step; relative links.
12. Stable vault dossier paths — `{run_id}_{slug}.md`; date-prefix clones unlinked.
13. Audio LUFS — `LUFS_NORMALIZE` opt-in; default ffmpeg command unchanged.
14. Background clip anti-repeat — in-process deque; `CLIP_MEMORY` file opt-in.
15. `ops postmortem --run-id` (29) — traces already on disk.
16. `ops doctor` (30) — free stack + cached feeds + oauth file + quota + CUDA.
17. Cap discovery workers (41) — `DISCOVERY_MAX_WORKERS` default 8; 0 = unlimited.
18. Overnight quota-aware (45) — `OVERNIGHT_QUOTA_GATE` opt-in; skip/shrink count.
19. Disk-space preflight (91) — `DISK_MIN_FREE_GB` opt-in; ASCII `>=`.
20. Fact-expiry watchdog (55) — vault leftovers; `load_facts` already drops them.

**Audit (same pass):** warmup/live YouTube client forbidden in the suite. Overnight
quota / disk / LUFS / clip-file / policy fetch stay opt-in so leftover env cannot
abort tests or write `data/`. Policy canary and fact-expiry do not HTTP from
`reliability.gather()`. Artifact retention never deletes without `--apply` and
never walks `data/`. Moat backup never copies `.env` / `config/secrets/` /
`quota_state.json`. TTS arm report cannot start a lever. Nested tries on doctor
optional imports. Residual C9 leak: Analytics `HttpError` for `abc123` when
operator `.env` had `YOUTUBE_ANALYTICS_SYNC` on — `get_youtube_*_service` now
returns None under `CONTENT_FORBID_LIVE_YOUTUBE` before `load_credentials`,
OAuth refresh is skipped, competitor-sync API-key `build()` is gated, and the
suite forces `YOUTUBE_ANALYTICS_SYNC=false`.

**Deferred:** afternoon leftovers (31 file-count retention as a separate job,
caption skin, schema ratchet, …); remaining `[M]`/`[L]` in 78–89 and 91–140
except 91/99.

---

## 2026-08-20 (follow-on 3) — Next 10 after night + evening waves

**Prompt:** complete the next 10 roadmap candidates in pickup/importance order on
top of the two uncommitted waves, then audit.

**Pickup:** no new "Next 10" list after the evening ship. Ranked remaining
evening leftovers (now including skipped `[M]`s) plus morning/late `[S]` that
the evening wave deferred. Parked: Phase M, volume-gated backtest, $0 TTS voice
judgment.

**Skipped:** **67** TTS provider Bayesian arm (would auto-assign Piper; same
shape as the parked voice judgment). **70** CUDA/electricity (no GPU torch
install). **68** Apify invoice true-up (no invoice fixture in-repo).

**Shipped:**

1. Operator minutes-per-run (65) — `core/operator_timer.py`. Wall vs `input()`
   wait; summary line; in-memory only.
2. Human-presence unattended render (90) — `HUMAN_PRESENCE_HOURS` opt-in;
   overnight/daily-sync/worker do not stamp; drafts unchanged.
3. Competitor-sync YouTube-unit cap (88) — RSS free; API fallback capped + one
   upload reserved. Suite sets both knobs to 0.
4. Paid-signal outcome attribution (57) — `ops paid-signals`; engaged-rate then
   composite. Catalog untouched.
5. Justify remaining Apify (73) — same report; `disable` at n>=5/arm is a
   recommendation only.
6. RPM < cost skip slot (63) — `RPM_COST_GATE` opt-in; last 7 monetized uploads;
   worker defers without consuming a retry.
7. Channel-go-live trailer/handle/banner (139) — MoneyWise banner passes;
   handle/trailer still FAIL.
8. Integration incident ledger — rank count/(1+days); persist on `ops
   reliability` / `ops incidents`, not inside the signal pool.
9. `signal_facts` earnings ratchet — symbol/date/days/EPS, not JSON dump.
10. Competitor-channel health — RSS probe in ops; snapshot-only on reliability;
    McAfee UC flagged unverified, not auto-replaced.

**Audit (same pass):** heartbeat is a no-op on the default path unless
`HUMAN_PRESENCE_HOURS` is on (a first-pass `ops.main()` in the suite had written
`data/operator_heartbeat.json` — deleted, gate-off skip added). Competitor
health does not HTTP from `reliability.gather()`. Paid-signal report never
writes `apify_sources.json`. RPM / human-presence stay opt-in. ASCII in gate
strings. C9 Google HTTPS `ResourceWarning` still present (not this wave).

**Deferred:** 67/70/68 as above; C9 HTTPS ResourceWarning; remaining afternoon
21–55 `[S]`.

---

## 2026-08-20 (late-night follow-on) — Evening remaining [S] after the night wave

**Prompt:** complete the next 10 roadmap candidates in pickup/importance order on top of
the uncommitted night wave, then audit.

**Pickup:** no new "Next 10" list was written after the night ship, so remaining evening
`[S]` items (short-term / cost / honesty / operator safety). Skipped `[M]` 57/63/67/73,
CUDA 70, operator-parked Phase M / volume-gated backtest / $0 TTS voice judgment.
Skipped **65** (operator minutes) and **68** (Apify invoice true-up) — lower leverage
than the TTS/thumbnail cost gates.

**Shipped:**

1. Overnight/unattended render-queue gate (58) — `core/render_gate.py`. Auto-generate +
   render worker; interactive `main.py` unchanged. Missing grade fail-closes.
2. YouTube "N uploads left this reset" (59) — `youtube_quota.uploads_remaining`; reliability
   + startup. Check point stays `apis/youtube_quota.py`.
3. `ops channel-go-live` (60) — OAuth/SEO/feeds/brand kit/persona. MoneyWise still FAIL on
   persona. Never reads token contents except via existing oauth helpers.
4. Metrics-before-next gate (62) — `METRICS_BEFORE_NEXT` opt-in; no yesterday upload = pass.
5. Free-mode Standard billed dry-run (64) — counterfactual ElevenLabs+thumb; does not
   mutate persisted cost.
6. Hard character cap before TTS (75) — refuse, do not clip; default 5000; 0/off disables.
7. TTS cache by script hash (71) — spoken+provider+voice; sidecar copied; cache hit meters
   $0. `TTS_CACHE` opt-in (discover does not load `tests/__init__.py`).
8. Pillow-first thumbnail until ≥ B (74) — missing letter fail-opens; C/D/F skip paid APIs.
9. Subscription utilization dashboard (69) — reliability Utilization section; Brave has no
   usage counter yet.
10. Skip web-search on vault density (72) — distinctive vault facts only (no extra RSS HTTP
    / cache-stat probes); skip in `register_signals` orchestration.

**Audit fixes in the same pass:** cache-hit TTS line is $0 (no double-bill); nested tries
on optional reliability imports; no second cache inside `web_search`; governors/gates that
can abort stay opt-in (`METRICS_BEFORE_NEXT`, `TTS_CACHE`) so leftover `RUN_COST_MODE=free`
/ `FREE_MODE_STRICT` cannot abort the unit suite, and unittest discover cannot write
`data/tts_cache`. Render-gate messages stay ASCII (`>=`) so a cp1252 console cannot
swallow a block and then render anyway.

**Deferred:** 65 operator minutes; 68 Apify invoice true-up; morning leftovers (incident
ledger, `signal_facts` ratchet, competitor-channel health); 57 paid-signal attribution.

---

## 2026-08-20 (night) — Shipped recommended next 5 + cost/honesty 56/61/66/76 + Qwen3 + oauth coverage


**Prompt:** implement the top 10 roadmap candidates in importance order, then audit for optimization, efficiency, and debug quality.

**Shipped:**

1. Pre-run completion gate — `inspect_first_calls` / `guard_before_discovery` / `apply_and_guard`. Free fail-closed (stale Readiness cannot start discovery); Standard warns. `FREE_MODE_STRICT` is the raise switch so a leftover `RUN_COST_MODE=free` cannot abort unit tests.
2. `youtube/oauth.py` tests + `coverage` extra — temp token files only; `run_interactive_oauth` skipped. `coverage>=7.6.0` in `[dev]`; command recorded under the coverage wave; not a CI % gate.
3. Pronunciation lexicon — `config/pronunciations.json` on the local TTS path only. Captions/retext keep the caller script. ElevenLabs unchanged.
4. Allocated vs marginal unit economics — `ops economics` shows both. `COST_TTS_PLAN_USD` / `COST_TTS_PLAN_CHARS`. `cost_meter` marginal rates unchanged.
5. Numeric/record grounding — `find_ungrounded_numeric` (records/ranks/dates in sports context; purses always). Warn/fail-open; does not change `GROUNDING_GATE`. Round scores like 10-9 are not records (would have fired a premium regen). Run-66 "If Netflix" intact.
6. Thin-facts abort before TTS — default on, 3 lines + 50% support; missing verifier fail-opens. Interactive prompt / `--force`. Drafts stay saved.
7. ElevenLabs character-quota governor — `ELEVENLABS_MONTHLY_CHAR_BUDGET` opt-in (empty = off, same shape as Apify). Persist via `quota_governor` only. Trip to Piper or block before ElevenLabs. Tests isolate the store.
8. Qwen3 in Free TTS readiness — `qwen` in `_LOCAL_TTS_ORDER` when `qwen_tts` + `QWEN_VOICE` are ready; does not load the 1.7B model. Piper still preferred.
9. Meter Flux / Ideogram / Recraft — `COST_THUMBNAIL_PER_IMAGE` default $0.045. Pillow / no image = $0. TTS-only re-merge leaves a stored thumbnail line alone.
10. Escaped free-first LLM — usage record + cost line + reliability. Pinned provider never flags. First-hit DeepSeek premium is not an escape.

**Audit fixes in the same pass:** restored `reliability.gather()` (had been swallowed into `_elevenlabs_section`); nested the escaped-flag read so a cost_meter import failure cannot wipe LLM breaker state; tightened fighter-record regex so 10-9/29-28 judging cards do not trigger `GROUNDING_REGEN`; ElevenLabs governor stays opt-in so tests cannot poison `data/quota_state.json`.

**Deferred:** none of 1–10. Phase M, volume-gated backtest, and the $0 TTS voice judgment stay out. Did not pull integration incident ledger, `signal_facts` formatter ratchet, or competitor-channel health.

---

## 2026-08-20 (late) — Next 5 unchanged + 50 any-way candidates (91–140)

**Prompt:** the next 5 roadmap items, plus a final 50 ideas regarding this
project in any way.

**Not built.** Pickup order is still the evening recommended next 5. Phase M
stays parked (operator choice). Volume-gated backtest and the $0 TTS voice
judgment stay out. None of 91–140 restates Next-up, the morning 20, or
candidates 21–90.

**Recommended next 5** (unchanged):

1. Pre-run completion gate `[S]`
2. `youtube/oauth.py` tests + `coverage` extra `[S]`
3. Pronunciation lexicon for local TTS `[M]`
4. Allocated vs marginal unit economics `[S]`
5. Numeric/record grounding `[M]`

**50 new candidates (91–140)** grouped on [roadmap.md](roadmap.md):

| Group | Items | Through-line |
|---|---|---|
| Machine / Windows | 91–100 | Preflights, secrets, traces, supply chain, the C9 HTTPS leak |
| YouTube surface | 101–112 | Caption tracks, category, playlists, unlisted review — still YouTube-only |
| Content / learning | 113–124 | Prediction ledger, mailbag, PPV blackout, stock watermarks, SSML numbers |
| Legal / policy | 125–132 | Disclaimers, trademark, right-of-publicity, demonetization, incident runbook |
| Operator product | 133–140 | `.ics`, CSV economics, vault wiki-links, long-form preset, quota-increase playbook |

**Rejected this session:** implementing the five; restoring Phase M; treating
clip-from-source / avatar / Instagram as "next".

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

---

## 2026-08-25 — Roadmap #23–27 render + thumbnail wave

**Sequence:** implemented #23, #24, #25, #26, then #27 on top of the current
uncommitted ten-task wave. No Cursor plan file, commit, push, live network call, or
real `data/` store was intentionally touched.

**Decisions and boundaries:**
- End cards are generated from validated channel config rather than requiring a
  hand-authored asset. The in-place concat uses the intro's restoration discipline:
  the body has to be restored after subprocess launch errors, non-zero exits, and
  empty outputs. Draft previews never get intro/outro.
- Lower thirds reuse `fact_grounding.specific_entities`, then require the complete
  label phrase in one supplied fact line; only capped display labels persist. Raw fact
  lines do not. Overlay ASS is emitted only when a
  label can be located in a real word-timing sidecar; proportional timing is not
  presented as measured timing.
- Color "LUT" scope is the smallest production-complete parametric equivalent:
  validated FFmpeg `eq` saturation/contrast/brightness. This avoids claiming a LUT
  file exists and propagates through every command-building path.
- Hook motion uses `zoompan` only through the first measured cue and returns exactly
  to 1.0 afterward. A missing timing sidecar leaves argv unchanged.
- `thumbnail_format` is a dual-generation experiment, unlike the existing
  single-image `thumbnail_style`. Dual mode runs only for that active experiment or
  explicit `THUMBNAIL_DUAL=true`. Text-on prefers a configured text-capable provider;
  face-forward prefers Flux; each arm has an independent, visibly distinct Pillow
  fallback. Failed paid-attempt billing is persisted as `unknown`, not silently
  priced at zero.
- Generation does not assign an experiment arm. The validated operator pick writes
  `thumbnail_pick`, creates the selected thumbnail asset, then records assignment.
  Dual-unpicked runs cannot enqueue. Resolution is run-linked only; newest-mtime
  fallback was removed.

**Initial proof:** 15 new behavioral tests were run before production edits and failed
(13 errors + 2 failures); the real FFmpeg failure added one focused font-binding
regression. The later safety audit brought focused integration to 112 tests and the
full isolated suite to 2,010 tests (up from 1,985). `ruff check .` and
`ruff format --check .` are clean. `py -m config.validate_channels` returned OK for
all three profiles with the same three pre-existing operational warnings. Operator
registry lists `pick-thumbnail`; its missing-run path returned `No content run
#999999` without mutation.

**Real temp proof:** the first FFmpeg end-card encode failed because the installed
Windows FFmpeg has no Fontconfig default. The failure restored the original body as
designed. Binding `drawtext` to installed Arial (DejaVu fallback on Linux) made the
same proof pass: a 0.6s synthetic body became a 2.133s body+card and the callback
captured the outro argv. The later audit split that callback into explicit
`outro_attempt` and `outro_success` events.

**Remaining visual proof:** no paid thumbnail call was made in this offline/no-network
wave. Run one full publish render with a temp/output override and inspect the first
cue, lower thirds, grade, and final card, then activate `thumbnail_format` for a
disposable run and pick in `ops booth --serve`.

## 2026-08-25 — Roadmap #23–27 behavior/safety audit

The audit added nine behavioral regressions; eight were observed failing before their
fixes. Confirmed defects and fixes:

- FFmpeg callbacks had only an unqualified command emitted before execution, so a
  failed intro/outro looked successful in the trace. Callbacks now emit
  `*_attempt`/`*_success`; traces retain every attempt and expose a successful command
  only after a usable output exists.
- Public lower thirds inherited the internal token-anywhere grounding rule, allowing
  two unrelated fact fragments to "ground" one display name. Public labels now require
  the exact ordered phrase in one supplied fact line.
- An explicit identity grade inserted an `eq` filter despite being the documented
  default. Identity values now produce byte-equivalent argv to an absent grade.
- Hook motion stopped at an empty/malformed sidecar row instead of finding the first
  real cue. It now skips invalid rows and uses the first finite, positive timed cue.
- Booth POST trusted a submitted run id, and the served booth used `file://` URLs that
  Chrome blocks on an HTTP page. POST bodies are bounded/strict, tied to the displayed
  run and known arms, and candidate images use fixed booth-local HTTP routes.
- Dual fallback evidence named pre/post providers but omitted their cost values.
  Candidate evidence now reports both pre- and post-fallback rates while preserving
  failed paid-attempt billing as `unknown`.
- The standalone and interactive requeue paths did not explicitly carry the picked
  thumbnail. Both now block unpicked dual runs and enqueue the validated selected path.

Proof: roadmap regressions 25/25; focused render/thumbnail/pipeline suite 112/112; full
isolated suite 2,010/2,010. Shipped config: 3 profiles valid with the same three
operational warnings. Safe operator checks: command registry listed `pick-thumbnail`;
missing `--run-id` returned 2 without mutation. No `data/` changes.

## 2026-08-28 — the 23-item wave (three parked enablements + 20 from 331–480)

Picked up mid-flight: the modules and their production wiring already existed,
the suite did not pass. Six failures/errors in 2,296 tests, `ruff` red on 3
errors and 6 files, nothing ticked, and #373 never started. Finished green at
**2,308 tests**, `data/` untouched.

**Shipped.** #38 NVENC encode behind one `video/encoder.py` helper used by all
four ffmpeg call sites; #147 as a localhost GET-only FastAPI shell (not #141);
CUDA as a fail-visible doctor line with no wheel install; and 20 candidates
(#340 #348 #353 #355 #360 #366 #370 #373 #379 #382 #395 #403 #406 #419 #426
#432 #439 #443 #444 #458).

**What the audit found that green tests did not.**

- **#419 was inert on the path that actually ships.** The rebalance lived only
  in `split_script_into_lines`, which feeds the *estimated-timing* fallback.
  decisions §23 means a normal run is timed by the ASR and cues come from
  `caption_timing.group_into_lines`, which had no rebalance — so on every real
  render the item did nothing while its tests were green. Fixed on both paths;
  the word moves with its own start/end.
- **#419's first cut also broke an older contract.** Rebalancing the running
  list let a one-word sentence steal the previous sentence's last word, merging
  two sentences into one cue —`test_sentence_boundaries_not_crossed` has
  forbidden that since long before 419. The rebalance is now per sentence, and
  the pre-existing `test_proportional_timing` passes **unmodified**; it was not
  a stale test, it was the contract.
- **NVENC broke #309.** The persisted "success" argv was the command *passed
  in*, so a run that fell back to libx264 would hand the operator an
  `h264_nvenc` command that had failed. `executed_cmd` now reports what ran.
- **#369 (previous wave) could never fire.** `projected_cost_block_reason`
  estimated from `script=""`, putting TTS — ~91% of a rendered run — at $0 and
  the total at $0.0075. A realistic `PROJECTED_COST_MAX_USD=0.50` was therefore
  unreachable; only a sub-cent cap tripped it, which is what its own test used.
  Its assertion `script == ""` had pinned the bug. Now estimates against the
  longest length preset: a $0.50 cap correctly refuses a ~$2.28 worst case, and
  unset is still off.

**Review pass on the uncommitted diff — six findings, four fixed.**

- **Fixed, and it would have hit a GTA 6 batch.** #394's empty-200 quarantine used
  a *denylist* (wikipedia only), but `rawg` (`apis/rawg_api.py:166`), `odds`
  (`odds_api.py:61`) and `sports` (`sports_data_api.py:76`) all return
  `connected=True, STATUS_INACTIVE` and **no** `status_detail` when a topic is
  outside their domain — the exact shape it counted as a dead scraper. Three
  off-domain topics in one `batch-drafts` session session-disabled RAWG, so a GTA
  topic later in the same batch silently got no game data. Now an **allowlist**
  (`tapology`): the safe default is never to quarantine.
- **Fixed.** #432's dry run hand-built `status` as `{privacyStatus}` while the real
  insert sends `build_video_status()` — so the "exact payload" omitted
  `selfDeclaredMadeForKids` (#107) and the #115/#116 `publishAt` bump, the two
  fields you open a dry run to check. It now calls the real builder.
- **Fixed.** #382's growth line was appended before the `... +N more` continuation,
  interleaving a summary into the file list at >20 candidates.
- **Fixed (during the wave).** #369's estimate; see above.
- **Not fixed — reported instead.** #355 computes `predicted_engaged_rate` at
  *sync* time, so the residual is recomputed and overwritten on every
  `sync-metrics` and is contaminated by videos published after it. The honest fix
  is to record the prediction at publish time; that is a schema change, not a
  patch.
- **Not fixed — deliberate.** #340's sidecar is written at `pipeline.py:308` with
  `quality={}` because `build_quality` runs at 348, so `ungrounded_count` is always
  null. claims/sources/disputed do populate. Reordering the finalize sequence is
  riskier than the gap.
- **Investigated and rejected.** #353's `n > 0` exemption looked like an inverted
  guard (n=0 skips the refusal). It is deliberate: experiments *generate* the
  samples, so a new channel must be able to bootstrap one, and forcing the refusal
  broke 14 existing tests that encode exactly that. Reverted; the caveat that
  `_measured_n`'s except branch also returns 0 is now documented in the code.

**NVENC proof, not probe.** `ffmpeg -encoders` listing `h264_nvenc` is a
capability claim. The real render argv was run against real inputs on this
machine: 1080x1920 h264 + aac, exact 3.000s, rc=0, ~1.5x faster than libx264.
NVENC's `cq 23` produces a larger file than x264's `crf 23` — different scales,
not a quality regression, and YouTube re-encodes anyway. Default stays on.

**Skipped, needs the operator:** #333 negative-fact store, #349 OCR intake,
#412 pronunciation append, #450 voice-note intake, #451 phone booth, #389
stale-cache serve, #433 cross-channel dup guard, #416/#417 owned footage, and
the CUDA torch wheel. #141–#146 and Phase M untouched.

Proof: full isolated suite 2,315/2,315; `ruff check` + `ruff format --check`
clean; `git status --short data/` empty; `ops doctor` / `next` / `command-ref` /
`vault-decay` / `artifact-retention` / `publish-dry-run` / `diff-runs` run for
real, and the shell's five routes answered 200 with `POST /` at 405.

## 2026-08-28 (evening) — operator decisions on the nine parked items

Answers from the operator, plus two items that **shrank** because the premise was
challenged. Decisions only; nothing implemented yet.

**Settled.**

- **#389 stale-cache serve — yes, 48h ceiling.** Past 48h the run refuses rather
  than serving. Stale must always present as worse than fresh, never silently
  equal (decisions §24).
- **#433 cross-channel dup — guard on the LENS, not the topic.** MoneyWise
  covering GTA 6's market impact is a finance angle and is allowed; MoneyWise
  reviewing GTA 6 is TapIn's job and is not. Block when two channels would treat
  a topic through the same domain lens; allow when the lenses genuinely differ.
  Apply generally, not as a GTA special case. Operator: "script writing and clips
  leaking over is not what I want."
- **#451 phone booth — bind to the LAN.** `review_booth.py:1112` and
  `operator_shell.BIND_HOST` are `127.0.0.1` today. Operator chose LAN over a
  Tailscale tunnel. Must be an explicit opt-in flag, not a silent default.
- **#412 pronunciation — REPLACED by wiring Edge TTS.** The append mechanism was
  rejected on the right grounds: a pronunciation dictionary is a workaround for a
  voice that cannot be told how to say a word. `core/tts.py:862` `_ALT_TTS` is a
  provider registry, so `"edge"` is one entry plus a synth function and inherits
  the cache, the fall-back-to-ElevenLabs path at `tts.py:888`, free-mode strict,
  and the voice catalog. Buys neural quality near ElevenLabs and **SSML
  `<phoneme>`**, which Piper cannot do. Caveats to carry: it is free but NOT
  local (Microsoft endpoint, needs network), the `(local, $0)` print is wrong for
  it, and the endpoint is unofficial — Piper stays the true-offline floor. Likely
  closes the $0 TTS item that has been blocked "on ears".
- **#416/#417 — skip hand-tagging.** All clips are the operator's own capture, so
  the license ledger is one line. Folder routing already works
  (`_keyword_choose_folder("GTA 6 leak...")` -> `gaming/open world/GTA V`).
  Auto-derived metadata (duration, resolution, HUD, motion) plus usage history
  only. **16 unfiled clips** sit in `C:\Users\jonma\OneDrive\Videos\Xbox Game DVR`
  (plus an NVIDIA capture path) whose filenames already match the library's
  naming, so `ops ingest-clips` is mechanical.
- **#450 voice-note intake — dropped.** Solves a problem the operator does not
  have; they start runs at the keyboard.

**Shrank under challenge — the operator was right both times.**

- **#349 OCR — fold into the research phase, drop the screenshot path.** Operator:
  "can't this be done by the AI during research? I'm not manually doing all that."
  Correct: if a number is on a page, research should fetch and extract it; OCR is
  only needed when the number exists ONLY as an image (an X screenshot, a
  broadcast graphic). That residue is rare and not worth building. The item
  becomes "strengthen numeric extraction in research", not an OCR intake.
- **#333 negative facts — narrowed to a backstop, not a parallel truth source.**
  Operator: "if we pull fresh articles every run, shouldn't that supersede
  previous facts, or work in tandem?" Mostly yes, and fresh research stays
  primary. Three gaps keep a small store worth having: (1) the corpus is not
  ranked by recency, so a stale claim and its denial can sit in the same block
  with equal weight — which is why #331 as-of stamps and #332 disputed exist;
  (2) retractions are quieter than the claims they retract, so search/RSS may
  surface five copies of the false claim and none of the denial; (3) absence is
  not refutation — research can only supersede what it actually retrieves. So the
  store is a memory of corrections already paid for, once per claim, able to VETO
  (operator wants a hard block, not a warning). Marking a claim retracted rides on
  #341's retraction watch asking once; everything after is automatic.

**Next session order:** edge-tts provider, then `ops ingest-clips`, then #389 and
#433 now that the rules are fixed.

**Outcome (same evening, parked-four wave):** all four implemented. Edge is opt-in
cloud $0 with SSML lexicon + WordBoundary sidecar (never default). `ops ingest-clips`
is dry-run/apply with hud=null. #389 serves ≤48h stale on live failure only. #433
blocks same-lens, allows different lens. CUDA wheel still not installed.

## 2026-08-28 (later) — edge-tts audit: three defects the tests could not see

Reviewing the Edge TTS provider after it was wired. All three were invisible to a
green suite because the test double recorded the call instead of performing it.

1. **Declared but not installed** (#326 all over again). `edge-tts>=7.0.0` was in
   the `[free]` extra; the environment had nothing. `TTS_PROVIDER=edge` would have
   logged a warning and silently billed ElevenLabs. Installed **7.2.8** and
   verified by importing it, not by reading `pyproject.toml`.

2. **The voice read the XML out loud.** `edge_tts.Communicate` **escapes** its
   input — it is not an SSML endpoint — so the `edge_ssml()` wrapper meant the
   synth spoke `"speak version equals one point zero xmlns equals http colon..."`.
   Measured against the live endpoint: **23.76s of audio for a 3.94s sentence.**
   Pronunciation now rides `apply_pronunciation_lexicon`, the same plain respelling
   the local providers already use; `edge_ssml` and its two helpers are deleted so
   nothing can reach for them again. After the fix the same line is **6.744s**.
   The old test asserted `<sub` and `<speak` were in the payload — it pinned the
   defect. Rewritten to assert no markup ever reaches the endpoint.

3. **No word timings at all.** edge-tts 7.x defaults `boundary="SentenceBoundary"`,
   so the `WordBoundary` branch never fired and `.words.json` was never written —
   captions on the $0 path would silently fall back to estimated timing, which is
   what decisions §23 exists to prevent. `Communicate(..., boundary="WordBoundary")`
   now yields **11 real word timings** on the probe sentence. The test fake only
   accepted `(text, voice)`, so it mirrored the caller's omission rather than the
   library's real signature; it now mirrors 7.x.

**End-to-end proof of the whole design:** voice says `toh-POO-ree-ah`, timings
carry that token, and `retext_words_from_script` restores **Topuria** for the
burned captions. Timed by the synth, spelled by the script — decisions §23 holds
on the $0 path.

**#433 lens fix.** The shipped guard keyed on `infer_domain`, which reads by
SUBJECT and checks gaming words before finance ones — so "GTA 6 economic impact on
the games market" classified as `gaming`. With `CROSS_CHANNEL_DUP` defaulting to
**block** and the guard wired at `pipeline.py:506` (before script) and in the
publisher, that refused the one MoneyWise angle the operator explicitly permitted.
Added `_lens_for`: finance TREATMENT cues override the subject. `infer_domain`
itself is untouched — it also drives the YouTube category (#102), per-domain signal
weights, and scoring. The operator's four canonical sentences now classify
correctly, and "GTA 6 review" is still blocked.

**Note on concurrency:** another agent was editing this tree during the audit
(`config/data_sources.json`, `core/secrets_doctor.py`, `core/ui.py`,
`core/voice_catalog.py`, `docs/roadmap.md`). Three suite failures and one F401 at
the time of writing belong to that in-flight work, not to anything above; the 164
tests covering the modules changed here pass in isolation.

## 2026-08-28 (run 73) — four defects from a real GTA 6 reaction run

Three runs on the same topic. The operator typed reaction-shaped topics every
time — "GTA 6 Extended look reactions, looks great!", "GTA 6 looks amazing!!!" —
and got critique angles, ending in "GTA 6 Community Predicts Toxic Meta Before
Launch — Why They're Wrong". Three of the four defects share the shape this repo
keeps hitting: **a check measuring the wrong thing, then reporting clean.**

- **Angles ignored the operator.** `generate_variants` chose `angle_types` from
  `profile.domain` and `repeat_count` only — the topic string never reached the
  decision. GTA 6 is established, so the gaming branch handed over
  `whats_broken_needs_fixing` / `community_wishlist` / `is_it_still_worth_playing`,
  and `generate_ai_angles` additionally instructed the model to "focus on
  ANALYSIS, PREDICTION, COMMUNITY debate, or CRITIQUE". A reaction video was
  structurally impossible to ask for. `core/angle_intent.py` now reads intent from
  the topic, selects a reaction angle set, drops the contradictory critique
  instruction, and prints the mode so it can be overridden. Measured on the live
  model: "predicts toxic meta" became "proves the hype is real".
- **Web search taught itself to stop.** Run 1 called Tavily and saved its findings
  to the vault; that cleared `WEB_SEARCH_SKIP_MIN_FACTS` (6), so runs 2 and 3
  printed `SKIPPED (vault coverage)`. Each run made the next less fresh, and a
  reveal hours old was grounded on notes the system had just written about itself.
  The bar counted density with no recency term. An event-shaped topic now never
  skips, and backing facts must carry a `verified_at` inside
  `WEB_SEARCH_SKIP_MAX_AGE_DAYS` (21). Evergreen topics still skip.
- **yt-dlp shouted through the spinner.** `quiet`/`no_warnings` do not stop
  extractor errors — only a `logger` does, and none was supplied. One shared
  `_YtdlpLogger` across the search and every extract; age-gated videos are counted
  at debug rather than printed. `YTDLP_COOKIES_FROM_BROWSER` is opt-in, unset by
  default, because reading the operator's cookie jar is their choice.
- **The "18-fact cap" does not exist** — 18 was the run's count and nothing was
  dropped. But the real limits (24 lines / 4500 chars) could not hold one article,
  since `link_facts` emits ~400-char lines and a BBC read is ~20 of them. Now
  60/12000, the default and the clamp agree (they disagreed: default 4500, clamp
  12000), and the prompt shows both halves. `facts_for_prompt` dropped facts with a
  bare `break` — `ui.py` compared counts afterwards but `title_generator`,
  `auto_generate` and `content_engine` got a silently shortened set of the
  highest-priority ground truth in the system (§4). Now logged and reported.

Two test doubles mirrored the caller instead of the real thing again, the same
shape as the edge-tts fake: `test_free_backends`'s `_full_one` accepted only
`(url)`, and `test_web_search_two_stage`'s fixture note carried no `verified_at`
though every note the machine writes is dated. Both corrected.

Proof: suite 2,387 → 2,408 green; ruff clean; `data/` untouched; angles, yt-dlp
and the article budget each verified against the live path, not a mock.

**Not done, still the operator's call:** the terminal. Assessment recorded — the
blocker is `main.py`'s 15 blocking `input()` calls, not HTML; the cheapest exit is
the booth (which already POSTs) gaining a start-a-run form over the already-headless
`generate_draft`, not #141 Desktop.

## 2026-08-28 (evening) — the roadmap split, and a decision on every XL and L

The operator asked for a full plan for a real Windows 11 desktop application, with
the same depth applied to cutting every remaining XL and L. Everything stays
**private, local, single-operator, never published** — a constraint that retires
work rather than deferring it.

**Why the roadmap had to move first.** 1,981 lines, of which "Next up — all open
items" was 1,282: 291 open items in one flat list with August's shipped-wave
narratives above the actual next work. The header was already wrong ("318 open"
vs a real 317). Split by job into roadmap.md (111) / desktop_app.md (229) /
backlog.md (778) / roadmap_archive.md (1,224). Counts reconcile exactly — 291
open, 424 shipped, nothing lost. The 30 open items stranded inside historical
phase and pillar sections moved to the backlog so the archive holds no open work.

**The reframing that makes the app tractable.** #141 was never one item. It is the
container for twenty-one others — #148 queue, #149 analytics, #152 canvas, #156
vault, #158 cost tower, #161 calendar, #163 script desk, #168 review room and the
rest are each a *panel inside it*. Read as one XL it is unapproachable; read as a
shell plus panels, each already backed by data `core/` computes today, it is
sixteen to nineteen ordinary waves.

**The "years of UX/packaging" estimate was true for what #141 specified and false
for what will be built.** #141 said Tauri/WinUI — a JavaScript front end in a
separate process, which reintroduces the request/response boundary the terminal
does not have. A PySide6 window is one process with memory, exactly like the
terminal, so `main.py`'s 15 blocking `input()` calls become an `ask()` seam with a
pluggable backend, not a resumable state machine. Stage 0 is one wave.

**Toolkit: PySide6 over WebView2**, reversing my own first recommendation. I had
argued WebView2 partly because it reuses the booth HTML — then measured it: ~113
tags and ~182 CSS rules, and most of review_booth.py's 1,124 lines is Python
building strings. What carries over is the design, not the markup, so the reuse
was worth about a week, not a head start. Against that: three L items are drag
canvases (#152 layers, #153 timeline keyframes, #148 reorder) and two need real
video playback (#168, #209) — `QGraphicsView` and `QMediaPlayer` versus bespoke
JavaScript each time. The canvas gap never closes; the polish gap does. Qt is also
one language, which matters because the operator wants to run this machine without
an agent.

**Every XL decided:** 141 becomes the programme · 142 absorbed into Stage 4 · 143
retired (a SaaS framing for something never published; its useful content is #169
and #476) · 144 stays parked with Phase M · 145 dissolved into #156/#157/#158 ·
468 retired (nothing is published, so a standalone fact-engine surface has no
consumer). Six open XL become zero.

**Every L decided:** 21 absorbed into app stages · 5 stay on the engine track
(#48 #50 #54 #416 + multimodal review) · 3 standalone (#79 affiliate spike with a
kill criterion, #155 MCP API, #478 channel kit) · 3 retired (#120 CLIP b-roll,
settled by §26 in favour of owned gameplay; #467 second operator seat, single
operator; #143's remains) · 2 stay parked (#166, #167).

**Guards, because the old header rotted quietly for months:** the archive must
hold no open checkbox, roadmap.md must stay under 200 lines, no numbered item may
be open in two files, and `ops roadmap-index` reads the counts from the files. It
immediately found 49 open items carrying no size tag — the next tidy.

Proof: suite 2,408 → 2,415 green; ruff clean; `data/` untouched; counts verified
against the 1,981-line original.

## 2026-08-28 (late) — the craft reframe, 164 candidates, and five inert features

**The reframe.** The operator asked to finish terminal aesthetics now so they are
not stranded half-done when the desktop app lands. Inventorying all 44 open
aesthetics items moved the target: **only two are terminal-only** (#243 wordmark,
#244 Windows Terminal profile). About twenty are booth chrome, which Stage 3's Qt
panels replace — so that dies too. And about twenty are **video craft, which no
toolkit change ever touches.**

The instinct was right and the bucket was wrong. What is genuinely at risk of
being wasted is the *booth* work; what has the highest lifetime value is video
craft, because it is burned into every video for the life of the channel. The
Craft wave therefore orders by what survives: video first, terminal second (it is
the daily driver for the 16–19 waves the app takes), config-only loopholes third,
and only the cheapest booth items at all.

Stage 0 keeps its place in front because the Craft wave reads its design tokens
(#170). Polishing before tokens exist invents the palette twice and throws the
second away — the exact drift #170 was written to prevent.

**Five loopholes, found by reading rather than running.** All are the repo's
signature defect: shipped, green, doing nothing.

1. **Six ANSI themes are unreachable.** `core/themes.py` ships `onepiece`,
   `zelda`, `pokemon`, `dbz`, `jjba`, `plain`. `ui_theme` is `None` on all three
   channels, so `set_channel_theme()` resolves to `""` and everything renders
   `default`. "UI/experience — themeable skins **shipped 2026-07-02**" has never
   once rendered in production. One config line per channel.
2. **`tts_voice_pool` unset on both channels** — voice variety has no pool.
3. **`local_tts_voice` / `local_tts_voices` unset on both** — the per-channel
   local-TTS seam is inert, which matters more now Edge TTS is wired.
4. **`SPORTSDATA_API_KEY` and `STEAM_API_KEY`** are declared in `.env.example` and
   appear nowhere in the code. An operator can set them and nothing happens. (A
   first pass flagged 27 orphans; 25 were false positives read through helper
   functions. Only these two are real — worth stating, because the cheap version
   of this check would have produced a list that was 93% noise.)
5. **Startup is 1.89s before the menu**, ~1s of it imports a session may never
   use: `elevenlabs.client` 0.51s (module-level in `core/tts.py`), `sports.espn`
   0.45s, `googleapiclient.discovery` 0.23s. The env surface is **392 vars read
   against 273 documented**.

Filed as #641–#644 rather than fixed silently, so they carry their evidence. #644
is the config-coverage test that would have caught 1–3 and will catch the next.

**164 new candidates, #481–#644**, in thirteen groups, weighted to what the
desktop programme does not cover. Measurements are real ones from this machine,
not estimates. Two observed signal failures became items: `trendingnow.games`
fails DNS on every run and a YouTube RSS id 404s — both decisions §19 candidates
for retirement rather than repair.

Backlog 291 → 455 open; highest #644; untagged unchanged at 49; suite 2,415 green.


## 2026-08-29 — Run 74: why fact intake had character limits at all

Started as "fix the crash", became a design decision about what the fact budget
is *for*.

**The abort chain was structural, not carelessness.** Run 74 produced no video
because `Proceed?` received the word `by` — Engadget's byline label, left in the
Windows console buffer by a paste at the **Fact** prompt. Three separate design
choices had to line up: the fact loop treats a blank line as "done" (a paragraph
break is indistinguishable from Enter), nothing drains buffered stdin between
prompts, and `Proceed?` treated anything unrecognised as "stop". Candidate 325
had already fixed the third for *prose*; `by` is two characters and one word, so
it sailed through. The lesson worth keeping: a gate that guesses intent from the
shape of the input will keep finding inputs it guesses wrong about. Only an
explicit decline stops now.

**The question that changed the scope.** Asked whether to keep the per-line
400-char cap and split at sentences, the operator asked back: *"why do we even
have char limits on facts?"* — then, when the total budget was defended on
per-call cost: *"we don't have to call every fact available every call… score
them against each other for what would be the best, with recency having a heavy
bias."*

That is the right answer, and the evidence was in the run itself. Of 54 packed
facts, roughly fifteen were article furniture — *"Below, you'll find everything
shown off…"*, *"Check out the five biggest takeaways below."*, *"Note: All of
these details are compiled from various previews…"* — while six wanted stars, the
Slim Jim carjacking minigame, the 80-hour playthrough and the November 19 release
date sat in the tail that never fit. **Raising the ceiling would have packed more
furniture.** Intake needs no limit; the prompt needs a ranking.

**Two limits, two different justifications.** Worth separating explicitly, because
they were treated as one thing:

- The **per-line cap** had no quality rationale at all. It was a runaway-blob
  guard against a scraped `<p>` holding a transcript, implemented as `line[:400]`.
  As a *splitter* it does its actual job better than as a truncator.
- The **total budget** is real: operator facts ride in every script and expansion
  call at ~1 token per 4 chars. That is worth spending well, not worth removing.

**The measurement that redirected the scorer.** The obvious move was to reuse
`score_vault_fact` for relevance. Measured on run 74's own facts, it scored the
Slim Jim mechanic — the single most useful detail in the article — at **0.03**,
because it measures how much a line *echoes the existing signal corpus*. That is
the right question for a vault note ("is this even about the topic?") and exactly
the wrong one for a pasted article, whose entire purpose is to add what the
signals lack. Hence `novelty` (share of a fact's named entities the corpus does
not already have) as a first-class term, and relevance demoted to the smallest
weight — a floor against off-subject lines rather than a ranking.

**Three rules that keep ground truth safe**, and should survive any future tuning:
operator-typed facts are pinned and never ranked out (decisions §4); scaffolding
is penalised rather than blacklisted, so a furniture-shaped line carrying a hard
number still competes; and every exclusion carries a printed reason, because a
silent drop of ground truth is the worst failure this module can have.

**Deliberately not done:** the report card still does not weight length, even
though run 74 shipped 277 words against a 300-word floor and graded A. Adding a
component changes the meaning of every historical grade — filed as #645 rather
than slipped in. The weights themselves were calibrated on one run's 54 facts and
need trace-level validation (#647).

Backlog 455 → 460 open; highest #650; suite 2,415 → 2,515 green.


## 2026-08-30 — why the ideas are bad: the framing is an accretion, not the charter

**Prompt:** *"is there any particular reason as to why the video ideas have been so
terrible recently? it seems like its struggling trying to fit the 'enter your own' ideas
into the initial markup of the project being about and for hot takes … and what are the
ways that this project can take the next level, within realism."*

Full trace: [idea_quality_diagnosis.md](idea_quality_diagnosis.md). Direction:
[strategy_next_level.md](strategy_next_level.md). Docs only this session — no code.

**The premise needed one correction, and it changes the fix.** There is no hot-take
charter to fight. `vision.md`, `positioning.md`, `project_brief.md`, `strategy_2026H2.md`
and `decisions.md` never frame the project that way, and `channels.json` actively
contradicts it — MoneyWise's persona is *"calm, plain-spoken, mildly sceptical of hype —
explains, never sells."* The framing is an **accretion of six layers**, each added for a
defensible local reason: the angle tables (`controversy` is in every one of them), the
22-phrase reaction lexicon that leaves every other intent as "default", the script
prompt's five unconditional take orders, `research_brief`'s `short_debate` default, the
vault playbook, and a report card that pays for the result.

**Option 5 was never a separate path.** `main.py:266` calls the same
`_run_new_video_flow` option 1 uses; the entire divergence is `main.py:317-319` (skip
best-bet). The operator's idea is a **search seed**, and `core/pipeline.py:493-501`
replaces it with the winning variant. A one-line typed idea carries *zero* creative
direction — `is_rich=False` leaves `creative_brief` empty — and on the YouTube-link
branch the operator is asked for "your angle for OUR take" and that answer is
concatenated into the search string, never reaching the writer.

**The bigger finding, which the question did not ask about: the selection step is not
selecting.** Live-run 71 recorded all five angles at exactly 100.0; run 72's report shows
all five at exactly 92.14. `_score_variant` scores the *topic's* signals, not the
*angle's*, so five framings of one subject return one number and `Enter = best` is
arbitrary. Candidate 323 made the tie honest (`ui.py:587-611` prints "this is a tie, not
a ranking") without resolving it. This explains "the idea it gave me was terrible" more
directly than any prompt wording, and it is unfixed.

**The evidence contradicted the own-vs-discovered half of the question, and that is
worth recording rather than smoothing.** Across 25 graded runs the report-card means are
≈78.6 (operator-typed) vs ≈78.2 (discovered) — no gap; the best grade on record (run 75,
A 94) is operator-typed and the worst (run 69, D 52) is discovered. The operator is not
wrong; **the report card is blind.** It graded A 91 on run 71's factually wrong title
(nothing reads the title `generate_title` returns), A 87 on run 74's 277 words with a
hook of 61, and authenticity 100/100 on a phrase `persona_lint` flagged four log lines
earlier. `data/traces/*.json` does not record which menu option produced a run, so that
comparison had to be inferred from typos and exclamation marks — worth instrumenting.

**The single most surgical finding.** `core/obsidian_facts.py:559` caps the vault
playbook at `limit=8` in **file order, not relevance**. `tapin/playbook.md` opens with
two "Narratives that work" sections, so the eight that reach every tapin script prompt
are 8/8 hot-take rules — and 100% of that same file's "Hook rules" and "Hard rules
(anti-hallucination)" are truncated away. The file is dated 2026-06-17 and says of
itself: *"These are human-authored beliefs; the Analytics Intelligence Agent will
eventually confirm/refine them with real performance data — update when it does."* It
never did. The strongest framing input in the system is eight unvalidated guesses, and
the outcome data available (hit rate 40%, composite uncorrelated with engagement, priors
at n=1) does not confirm them.

**A third instance of the run-74 gate-disagreement bug.** `test_gate_agreement.py` was
written to stop one gate rewarding what another bans. It checks `_INSIGHT_MARKERS`
against `_FILLER_PHRASES` and one prompt line only. Meanwhile `hook_score._CURIOSITY`
pays +15 for `"nobody's talking"` — a banned headline template in `topic_variants.py:291`
and a `_SLOP_PATTERN` in `title_generator.py:20` — and `authenticity` pays 35 for the
literal string `"hot take"`, which `title_generator.py:83` bans by name. 56% of the
report card is decided by two substring lists rewarding vocabulary the rest of the system
forbids.

**Operator's calls this session:** fix scope = **intent as a first-class dimension**
(#533, expanded from "more angle tables" to one intent steering angles, brief, prompt and
gates); deliverables = the two docs, code deferred; measurement = **build the eval
extension as part of the work**; horizon = **open to revisiting** the
private/local/single-operator constraint.

**Three doc contradictions found while mapping, all cheap to settle:** decisions §17
("generation quality *is* the lever") vs `strategy_2026H2.md` §9 ("don't add more
generation features") — §17 is newer and wins; `positioning.md` and `vision.md` were
retired in substance by the 2026-08-29 private/local constraint but carry no supersession
header; and §25's hedging loophole is documented and still open — runs 58, 73 and 75 all
show the claim rewriter buying support with weasel words. Also stale: `vision.md:156`
lists the prompt eval set as missing; it shipped as `core/prompt_evals.py`.

**The one constraint break worth re-pricing:** Phase M multi-platform. It is the only
lever that multiplies outcome samples without multiplying scripts, cost, or compliance
exposure — the asset is already rendered vertical. It does not make the tool public; it
un-parks a publishing target. Sequence it *after* the quality work, because it also
triples the blast radius of a bad script.

## 2026-08-30 (wave) — the idea-quality wave, and why it replaced the recommended five

Pickup from the diagnosis entry above. Operator asked to re-familiarize and take the
next five. Refamiliarization changed which five.

**Two of the recommended five were parked elsewhere.** `HANDOFF_SYNOPSIS.md` lists
#333 and #416 as "Still parked" in four consecutive wave entries, and `:141` records
#333 as *"Skipped at the time — needs the operator"* — while `roadmap.md` had them at
picks 1 and 5. #333's own roadmap line concedes *"The operator's call"*, and its stated
trigger #341 **does not exist in code**. #416 is `[L]` and blocked on data, not code:
`ops ingest-clips --apply` has never run, so `data/clip_index.json` is absent and the
scene planner has nothing to cut to. Both stay open; both left the next-five.

**#323's diagnosis was wrong, and that is the wave's most useful finding.** It
attributed the five-way tie to the 0-100 clamp. The real cause is that
`_VARIANT_REUSE_DEFAULT` pins **every** signal during variant scoring, so all five
variants are scored against the base topic's signals, and the variant string reaches
`composite_score_raw` only through `infer_domain` (identical across five framings) and
`get_historical_boost` (an exact-string lookup — 0.0 for an angle generated seconds
ago). The inputs are equal, so the outputs are equal, clamp or no clamp. Run 72 tied at
**92.14**, below the ceiling, *after* #323 shipped. The comment at
`apis/register_signals.py:322-324` claiming "composite_score still re-scores each
variant's text against the pinned data, so per-variant differentiation survives" is
**false** — no such re-scoring exists.

**The fix had to be a new component, and the honest constraint shaped it.** Re-fetching
signals per variant is what `reuse_signals` exists to prevent (150-185s and 5x web
spend per run) and would not work anyway — five angles on one subject return
near-identical trend data by construction. So `core/angle_ranker.py` scores the angle
*text*: distinctness (the angle prompt already asks for this in words — *"if two angles
could share the same thumbnail, rewrite one"* — and nothing measured it), seed fidelity
(run 48 turned an NBA seed into a Marvel Rivals script and no number noticed), and
specificity (reusing `fact_selection._specificity`).

**Deliberately not folded into the composite.** The measured record is that the
composite does not predict engagement (hit rate 40%; the lowest-scored topic beat two
100.0s). Averaging one unvalidated number into another would launder both. It rides as
a third dict on `DiscoveryResult` and a third key in `best_variant_index`, and the menu
prints it in brackets and says which number did the ranking.

**Three consumers were bypassing the ranking rule entirely** — `intelligence_report`
and `batch_generation` `max`-ed on the displayed score alone, and `auto_generate` used
`evaluated[0]`. A tie-break only the interactive menu benefits from is not a fix.

**The playbook fix used the operator's own structure rather than a keyword guess.**
`load_playbook` took the first 8 bullets in file order; `playbook.md` opens with two
"Narratives that work" sections, so the prompt got 8/8 hot-take heuristics and none of
that same file's anti-hallucination rules. Per-bullet `##` section context is now
carried on `NoteEntry` (additive) and selection goes round-robin across sections. The
alternative — classifying bullets by keyword — would have been another hand-built list,
which is exactly the criticism standing against `_SCAFFOLDING_MARKERS` (#648).

**A test double had drifted, and that was worth fixing rather than working around.**
`test_batch_generation` and `test_experiments` faked `DiscoveryResult` with a
`SimpleNamespace` lacking `raw_scores`, so they could not have caught a caller reading
it. Replaced with the real dataclass (#625's rule) instead of defensively `getattr`-ing
in production.

**Three grade components moved in one wave, and that has a cost.** Removing
`"hot take"` from `_INSIGHT_MARKERS` (35 of 100 authenticity), removing two `_CURIOSITY`
terms and adding a banned-template guard to `score_hook` (28% of the card) mean
**historical grades are no longer comparable to new ones.** That is the same migration
problem #645 was deferred for — so #645 is now pulled into the next five, because the
debt is owed either way.

**Left undone on purpose: #533.** It is `[L]` — six modules and ~15 prompt lines, each
written to command a take, and the honest work is authoring angle tables and prompt
blocks per intent, not plumbing. Its gate half moves the report card a *fourth* time;
stacking that on the same uncommitted wave would make any regression impossible to
attribute. It is now pick 1, to be shipped detector-and-tables first.

Suite 2,515 → **2,546** green; ruff clean; mypy 148 (unchanged). Backlog 460 → 463 open,
highest **#656**. Tree left uncommitted — the operator has not asked for a commit.

## 2026-09-05 — the next-five wave, and the four-step session written down

**Prompt:** *"next 5 tasks completed please, audit then commit afterwards.
brainstorm a new 5. is there any way to save this as a task, this process of
next 5, audit, commit, brainstorm?"*

**Pickup:** the five from `roadmap.md` as rewritten on 2026-08-30 — #533, #402,
#383, #645, #654 — plus the 2026-08-30 idea-quality wave, which had been sitting
uncommitted in the working tree for six days against rule 14. Operator's calls
this session: **one commit at the end** covering both waves (I argued for two and
was overruled — noted, not re-litigated), and **#533 as its minimum slice**.

**Shipped (order: cheapest and safest first, so the risky one could not strand
the rest):**

1. **#654** — `_ranked_on_note` names the shrunk figure `_domain_priority`
   actually sorted on. The raw mean stays the headline deliberately: #351's
   interval is computed over that raw vector, so swapping the point estimate
   without the interval would trade one quiet disagreement for another. Three
   sites existed, not one; the third (`_emit_hist`) was left alone because it
   prints a single run's own rate and a domain-shrunk figure is a different
   quantity. Measured: `nba averages 11.0% ... (ranked on 12.6% shrunk)`.
2. **#645** — the deferral was "it needs a migration story", and the mechanism
   for one **did not exist**: `GRADE_VERSION` was a string nothing read, wrote or
   compared. Stamped it onto `VideoGrade`, bumped to **v2** covering the length
   component *and* the three components that moved on 2026-08-30, and
   `QUALITY_VERSION` to **v3**. `_length_score` derives from the same floor
   comparison `format_length_report` already shows the operator, so it cannot
   disagree with what the operator reads (#653's lesson). Measured on run 74's
   real components: **A 86.8 -> B 82.8**; a row with no length keys is unchanged.
3. **#383** — `core/signal_canary.py` + `ops signal-canary`. It calls signal
   functions directly rather than through `_fetch_one`, which cannot answer from
   cache and cannot trip the persisted breaker.
4. **#533, detector + tables** — five new intents, each with a table where no
   frame asks what is broken. The mode now prints on the **main generation
   flow**; it only ever printed on the intelligence report, so the module's
   promise that the operator can see and override it was half true.
5. **#657**, found while scoping #402 — see below.

**#402 was not shipped, and confirming that was the useful part.** The split is
easy (`split_spoken_sentences` already exists). The blocker is that
`generate_audio` is ~147 lines with four provider branches, each with its own
`tts_cache_store`, plus quota checks, the Piper mix and a voice-fallback retry
loop. Rewriting the most cost-critical function in the repo late in a long
session, where a subtle error silently changes what the operator is billed or
breaks caption timing, is the shape of failure this repo has hit three times.
Filed the seam it needs as **#658** and left #402 open rather than half-shipping
a cache.

**Scoping it did surface a real defect.** `record_tts_actual` ran *before*
`tts_cache_lookup`, so a cached render stamped a full script's worth of "actual
synth chars" for characters nothing synthesized — and `core/pipeline.py`
persists that as `tts_actual_chars` into the run ledger. Shipped as **#657**.
Writing its test also exposed that `_last_cache_hit` is a module global no test
reset, so an existing "no cache hit yet" assertion was really asserting
alphabetical test order; added a `setUp`.

**The canary's first cut was backwards, and the correction is the point.** It
reported **15 of 33 signals dead**. Most were healthy: the probe topic is a UFC
string, so `coingecko`, `igdb` and `tmdb` *should* answer empty. That is decision
§18 turned inward — a canary that cries wolf nightly gets ignored, which is worse
than not having one. Reclassified onto the signal-contract vocabulary
(`STATUS_INACTIVE` is a source answering; `_FAILED` is the set worth waking for).
Measured after: **27 answered, none broken**. Also corrected the module's own
claim: zero *dollars* is true, zero *quota* is not — a probe run spends ~101
YouTube units of the 10k/day allowance.

**Audit (same pass).** Definition of done, checked not asserted: ruff and format
clean; suite **2,546 -> 2,573** green; every new test observed failing first with
the named reason (run 74's `87.3 not less than 87.3` and the canary's
`'12.6%' not found` are the two worth quoting); `git status --short data/` empty;
every new symbol traced to a production caller. **Two findings the checklist
caught that a green suite did not:** mypy had gone **148 -> 149** (a new
`str`/`Path` error in `signal_canary.save_results`, fixed by declaring
`SIGNAL_CANARY_FILE` in `config/paths.py` the way `FEED_HEALTH_FILE` already is),
and ruff flagged an import left unused by moving `record_tts_actual`. Both new
`logger.warning` calls fire only on the fail-open path, so a healthy run emits
none.

**The new five** (`roadmap.md`): **#662** calibration mixes rubric versions —
caused by these two waves and only now visible, because four grade components
have moved while `grade_calibration` re-grades all history with today's code;
**#658** the synthesis seam under #402; **#659** intent into the research brief;
**#647** fact-selection weights against real traces; **#661** the two intent
classifiers that disagree. Plus **#663**: nothing actually runs the canary yet,
and it must not go in `all-checks` (CI has no network and would fail every build).

**The ritual is now a skill.** `.claude/skills/next-five/SKILL.md`, mirrored
byte-identically to `.cursor/skills/` exactly as `tdd` is carried. It encodes the
recorded failures rather than generic advice: verify the next-five against the
synopsis before trusting it, a `[x]` is not proof (#323), counts come from
`roadmap-index`, write the slot last *then* re-run the suite, read `git status
--porcelain | grep '^??'` before `git add -A`, and do not move a grade component
without stamping the version.

Suite 2,546 -> **2,573** green; ruff clean; mypy **148** (unchanged from
baseline). Backlog 463 -> **465** open (done 429 -> 434), highest **#663**.

---

## 2026-09-06 — next 15 (no Stage 0)

**Prompt:** implement the attached next-15 plan; do not edit the plan file;
don't stop until all todos are done; commit only if asked.

**Picked vs the then-roadmap five.** The recommended five (#662, #658, #659,
#647, #661) plus overnight holes (#655, #663) plus finishing #533 (#660, #656)
plus idea-authority (#664, #665) plus cost (#402 after the seam) plus headless
facts (#646) plus #484 and #641-#644. Stage 0 / #333 / #416 stayed out.

**Shipped 1..15 (fail-then-fix; each new test observed red first):**

1. **#655** `confidence_note` `⚠` -> ASCII `!`. `encode("cp1252")` was
   `UnicodeEncodeError`.
2. **#663** overnight `_probe_signals`; not `all-checks`.
3. **#662** mixed rubric versions refuse one correlation bucket.
4. **#661** `"GTA 6 looks amazing!!!"` `classify_angle` was `general`, now
   `reaction`. `FEATURE_VERSION` v2.
5. **#659** explainer brief format + cache key `::{intent}`.
6. **#660** explainer prompt has no `TAKE A SIDE`; insight inject no-op on
   calm intents. `GRADE_VERSION` v3.
7. **#656** banned-template hook **-20**. Slop 93 -> below a 78 neutral.
8. **#664** option 5 always `creative_brief`; candidate 0; `variant_index=-1`
   must not fall through to `best_variant_index`.
9. **#665** `menu_path` / `angle_intent` on traces only when given.
10. **#658** `synthesize_to_path` seam; cache hit does not call it.
11. **#402** sentence loop + fractional `tts_cached`. 90% hit bills 10%.
12. **#646** `select_headless_facts` on auto_generate / overnight.
13. **#647** weights **held** on two fixtures (GTA + UFC), not retuned.
14. **#484** Ctrl+C at topic prompt returns without `SystemExit`.
15. **#644** + **#641-#643** real `channels.json`; ratchet failed on three
    blank fields first.

**Found on the way:** wiring `local_tts_voices` made
`test_piper_without_voice_model_returns_none` see a real tapin `.onnx` and
return a path. The test now clears the profile. That is #643 working.

**Not done:** Stage 0; #333; #416; commit (operator did not ask). Do not add
`cached-strolling-popcorn.md`.

**Audit:** ruff + format clean; suite **2,573 -> 2,606** green; `git status --short data/` empty.
Operator: `ops calibration` collecting (3/5); `ops recommend-time` no `⚠`.
Backlog **449** open / **452** done (`roadmap-index`), highest open **#650**.


## 2026-09-06 (review) — Claude reviewing Cursor's wave

**Prompt:** *"review the changes cursor made and do your end."*

**Cursor's headline claims all verified before anything else:** suite **2,606**
green, ruff and format clean, mypy **148** (baseline), `data/` untouched, 45
files uncommitted. `GRADE_VERSION` correctly bumped to **v3** with the reason
recorded — it used the versioning mechanism rather than working around it, which
is the thing #662 existed to make possible.

**Three defects found, all fixed here, all fail-first.**

**1. The sentence-TTS path was not gated on the cache it exists to serve.**
`TTS_CACHE` is opt-in and default OFF, but `generate_audio` split every
multi-sentence script regardless. With the cache off every lookup misses and
every store is a no-op, so splitting bought nothing and still cost N synth calls,
an ffmpeg re-encode, and an encoder boundary at every sentence break — in every
video, for renders that never asked for the cache. This was invisible because
every test in `TestSentenceCache` sets `TTS_CACHE=true`. Now gated; with the
cache off, behaviour is byte-identical to before. Measured: a three-sentence
script called the synth seam three times, now once.

**2. A concat failure erased the spend it had already incurred.** Cursor flagged
the double-bill in its own slot ("watch it"), and the money half is genuinely
hard to avoid once the segments are synthesized. The *ledger* half was not: the
fallback recorded `len(spoken_for_alt)` only, so the segment characters already
billed vanished from `tts_actual_chars`. That is the #657 defect exactly, one
level down. The failure path now carries `spent_chars` out and the fallback adds
it, and the warning names the double-spend instead of saying "cache failed".
Measured: the ledger recorded **23 chars where 45 were billed**; it now records
both. Preventing the spend needs a preflight — filed as **#666**.

**3. #662 blessed the history it was filed to catch.** The guard refuses to
correlate when it sees more than one `grade_version`. But every run graded before
the stamp existed carries no version at all, so they all read `"unversioned"` —
one value, `mixed_versions` False, correlation computed. Those are precisely the
rows the item is about: four components moved across v1/v2/v3 while nothing was
stamped. With `MIN_MEASURED = 5` and ~10 measured runs this was reachable today,
not hypothetically — measured, it produced a **0.99998** correlation over eight
unlabelled rows, a spuriously perfect number that reads as strong evidence.
`"unversioned"` is now treated as untrustworthy rather than as a version. Two
existing tests moved with it: `summary_line` now reports "still collecting"
*before* the version refusal (below the threshold the version question has not
bitten yet), and `_measured_runs` now stamps a version, because a real run does —
`run_quality.build_quality` writes `grade_version` on every payload.

**Verified working, not just green:** #664 prints the operator's typed idea as
candidate `0.` and `chosen_variant(d, -1)` returns it with the base signals;
#660 suppresses `TAKE A SIDE` and `NO both-sidesing` on a calm intent, and every
remaining occurrence of "hot take" on that path is a negation, not an order.

**Left as Cursor set it:** the next five (#485, #185, #505, #350, #648) is a
reasonable list and its call to make. **#647 held** — the operator's
`data/traces` is empty, so retuning the weights on fixtures would have been
calibration theatre.

Suite 2,606 -> **2,609** green; ruff and format clean; mypy **148** unchanged;
`data/` untouched.

## 2026-09-06 — next 15 craft / terminal / cost (no Stage 0)

**Prompt:** implement the attached next-15 plan (craft, terminal, cost); do not
edit the plan file; don't stop until all todos are done; commit only if asked.

**Picked vs the then-roadmap five.** The recommended five (#485 #185 #505 #350
#648) plus cheapest-first S-cluster (#666 #488 #487 #482 #490 #513 #502) plus
#297 with #185, #649, #182 last. Stage 0 / #333 / #416 / Ollama stayed out.
#491 already used `active_theme().spinner_frames`; ticked, not re-implemented.

**Shipped 1..15 (fail-then-fix; each new test observed red first):**

1. **#666** concat preflight. Unmodified: 3 sentence synths when ffmpeg missing.
   Now one whole-script seam call; billed chars = one script.
2. **#488** `fact_display_width()`. Patch width 140: 120-char fact prints fuller
   than 90.
3. **#487** TTY + `NO_COLOR=1`: `paint()` still emitted `\x1b[31m`; now plaintext.
4. **#482** second `print_startup_panel` same day returns no mascot lines; next
   calendar day shows it. `--art` forces. Stamp isolated off operator `data/`.
5. **#505** eight words / max 5 greedy `5+3`; now `4+4`. Both splitters. `#419`
   orphan retargeted to a 3-line sentence; `test_sentence_boundaries_not_crossed`
   unmodified.
6. **#490** fixtures 20/40/60 hinted 20 (most-recent); now median ≈ 40.
7. **#513** black/frozen Pillow check on the finished mp4 (intro-aware). Advisory;
   does not skip upload.
8. **#502** draft argv contains `drawbox`; publish argv from the same helper does
   not.
9–10. **#185+#297** WCAG ratio + pass/fail vs shipped tapin `#FFFFFF`. Busy vs
   quiet synthetic bands. **No `GRADE_VERSION` bump.** Not persisted on
   quality_json.
11. **#485** second `run_discovery` called `generate_variants` twice; now once.
    tapin/moneywise isolated; TTL expiry refetches. Empty `evaluated` not stored.
12. **#350** 20 frozen cases via `ops grounding-corpus` / `find_ungrounded_entities`.
    Not folded into `run_eval_corpus` (`test_eval_corpus_lists_without_llm` requires
    every row `scored=False`). Frozen `expect_ungrounded` matches current finder
    (lebron-grounded still flags `Lakers`; run71 hyphen `Take-Two`).
13. **#648** wrap-up furniture with no list marker scored penalty 0.0; now 0.5 and
    loses to a detail line. **#647 weights not retuned.**
14. **#649** lock: verifier prompt includes a negation tail past the old 400-char
    slice. Run-74 drones/K9/hurricane strings are **not in the repo**; known-gap
    test asserts that.
15. **#182** `ops caption-still`: PNG contains `Salkilld` after overlay.

**Found on the way:** #505 broke `test_three_word_leftover_stays_three` (8 words
is now a two-line wrap). Retargeted to 13 words / max 5 so #419 still holds.
`ops command-ref` drifted when `caption-still` / `grounding-corpus` landed.
mypy 148→149 from `render_check` name collisions in `run_media_only`; aliased.

**Not done:** Stage 0; #333; #416; commit (operator did not ask). Do not add
`cached-strolling-popcorn.md`.

**Proof:** `ops grounding-corpus` → `20 cases, 0 fail(s)`. `ops caption-still`
(no args) → `caption-still requires --path <image> and --file <script.txt>`.

**Audit:** ruff + format clean; suite **2,609 -> 2,637** green; mypy **148 -> 145**
(narrowed `_tts_forecast_features` + spinner lambda in files this wave already
edited); `git status --short data/` empty. Backlog **434** open / **468** done
(`roadmap-index`), highest open **#650**.

**The new five** (`roadmap.md`): Stage 0 seams · **#481** pinned status · **#184**
motion presets · **#190** MoneyWise disclaimer (pair **#191** if room) · **#338**
quote-attribution.



## 2026-09-06 (review 2) — Claude reviewing Cursor's craft wave

**Prompt:** *"review the changes cursor made and do your end."*

**Every claim verified before touching anything:** suite **2,637** green, ruff and
format clean, `data/` empty, and mypy **148 -> 145**. The mypy drop is genuine —
`git diff | grep 'type: ignore'` returns nothing added, and none of the four new
modules carries a suppression. That is a real improvement, not a silenced one.

**#666 was implemented the way it was filed.** `ffmpeg_concat_ready()` gates the
`if` *before* `_generate_by_sentences`, so no segment is synthesized when concat
cannot work, and it checks the `libmp3lame` encoder rather than just the binary
being on PATH. The double-bill I filed it for is now prevented rather than
merely reported.

**A near-miss on my side, worth recording.** `_discovery_ttl_seconds` looked like
a dead env knob — read `DISCOVERY_CACHE_TTL_SECONDS` into `raw`, then
`return DISCOVERY_CACHE_TTL`. That was my grep filter dropping the two lines in
between; the function honours the override. Read the function, not the diff
fragment.

**One defect fixed: the discovery cache said *that* it reused, never *how old*.**
#485 caches discovery for **90 minutes** and prints
`Reused discovery from cache (topic)`. An 89-minute-old discovery and a
two-minute-old one were the same line to the operator, and freshness decay is the
documented run-73 failure — *"each run made the next less fresh"*. Added
`apis.cache_manager.cache_age_seconds`, mirroring `get_expired`'s contract in
reverse (reports on a live entry, records no cache access), and the notice now
reads `Reused discovery from cache (topic) - 40m old`. Same convention
`feed_health` ("check is Nd old") and the competitor snapshot age already use.

**One robustness gap closed: the frozen corpus recorded no rationale.** #350's 20
cases are a genuine regression guard — they call the real
`find_ungrounded_entities` and a loosened gate fails CI. But behaviour and
*desired* behaviour are not the same thing, and three verdicts look wrong at a
glance: `Lakers` flagged when the facts say "Los Angeles", `Take-Two` flagged
when the facts say "the parent company of Rockstar Games", and generic title-case
deliberately unflagged. All three are correct under decisions §3, and Cursor's
slot said so — in prose that scrolls away. They now carry `note` fields stating
why, pinned by a test, so nobody reading a failing case later mistakes a genuine
fix for a regression and re-freezes the bug.

**Checked and found safe, not just green:** the new first-frame and caption
contrast checks are advisory on both the render and publish paths (warn, never
block) and fail open; `tests/__init__.py` gained a suite-store redirect for the
new mascot stamp, which strengthens isolation rather than weakening it; the
caption changes are additive (`two_line_split_index`) and do not move the
word-timing contract decisions §23 rests on.

**My own error, recorded:** proving the age notice, I ran `run_discovery` ad hoc
outside the suite and wrote one real key into `data/signal_cache.json`. Removed
it (8,137 -> 8,136 keys). tests/CLAUDE.md's isolation rule is about tests; the
lesson is that driving production code by hand needs the same care.

**Left as Cursor set it:** the next five (Stage 0 · #481 · #184 · #190 · #338),
**#647 held again** on structural deixis being a penalty rather than a weight
retune, and **#649** honestly scoped as a prompt lock rather than a run-74 replay
because the named strings are not in the repo — its known-gap test says so.

Suite 2,637 -> **2,639** green; ruff and format clean; mypy **145** (Cursor's
improved baseline, held); `data/` untouched.


## 2026-09-07 (Cursor) — Next 15: Stage 0 plus leftover craft

**Prompt:** implement the attached plan "Next 15: Stage 0 plus leftover craft".

**Pick vs the then-recommendation:** the recommended five were Stage 0 · #481 ·
#184 · #190 · #338. This wave took those plus the leftover craft that survives
the app (#191 #183 #187 #188 #243 #244 #239 #303 #304 #486). Held: #296
(blocked on #295), #512/#527 (need Qt or #247), #333/#416, Phase M, Ollama.
`GRADE_VERSION` stayed **v3**. Sitting 2026-09-06 craft wave was already
`f6869ea`, not dirty.

**Fail-then-fix:** every new test was run against unmodified code first
(import miss or assertion), then the helper landed.

**Shipped 1..15:**
1. **Stage 0 tokens #170** — `config/design_tokens.json`; `themes.role_color`
   and `caption_fill_hex` agree on shipped tapin `#FFFFFF` / moneywise `#F7E7A9`.
2. **`ask()` / `emit()`** — 15 `main.py` sites plus `core/ui.py` expand prompt.
   Fifth blocking gate is metrics at `main.py:346`, not cadence. `display_*`
   defaults `print_fn=emit` (`core/ui.py:496`).
3. **#481** — `format_pinned_status` calls real `format_uploads_left`;
   `emit()` (`core/emit.py:18`) invokes `refresh_pin`. CSI off when not TTY /
   `NO_COLOR`.
4. **#184** — `named_motion_filter` punch-in vs snap-zoom; disabled still `""`.
   `video/render_video.py:451`.
5. **#190 / #191** — `build_policy_overlays_ass` with shipped channel config;
   MoneyWise "Not financial advice" on-screen; TapIn not; `AI_DISCLOSURE_ENABLED=false`
   omits "Made with AI".
6. **#338** — `check_quote_attribution` from `core/content_engine.py:1130`.
   Invented quote flags; speaker in facts passes; `"GTA 6"` skipped. Nested
   quotes `known_gap`. Pre-rewrite count persisted if the script changes (§25).
7. **#183** — ASS `Style: Title` then Body (`video/caption_timing.py:214`).
8. **#187 / #188** — `ops end-card-preview` / `ops intro-waveform`.
9. **#243 / #244 / #239** — wordmark HTML flag; WT JSON fragment; `@media print`
   at `core/html_report.py:95`.
10. **#303 / #304 / #486** — MoneyWise header token not `#c62828`;
    `CONTENT_UI_REDUCED_CHROMA`; colorblind roles 33 vs 208; `plain` stays empty.

**Found on the way:** `print_fn=print` replace_all also matches `print_fn=print_fn`
(caught before commit). A broken indent in `ask_confirm` made `y` return `None`
(the scripted-gate test failed; restored `return raw in ("y", "yes")`). Filed
#667 (pin CSI untested on a real WT), #668 (WT snippet not auto-imported),
#669 (waveform offset is `DEFAULT_INTRO_DURATION`, not a probe).

**Not done:** #296; #333; #416; Stage 1 window; no PySide6. Do not add
`cached-strolling-popcorn.md`.

**Proof:** `ops end-card-preview` (no args) -> `end-card-preview requires --path <dest.png>`.
`ops intro-waveform` (no args) -> `intro-waveform requires --path <audio.wav|mp3>`.
Scripted `ask_confirm` of the metrics prompt with `""` -> `False`.

**Audit:** ruff + format clean; suite **2,639 -> 2,673** green; mypy **145 -> 144**;
`git status --short data/` empty. Backlog **422** open / **483** done
(`roadmap-index`), highest open **#669**.

**The new five** (`roadmap.md`): Stage 1 run window · **#295** contact sheet ·
**#607** defer elevenlabs import · **#625** test-double signatures · **#602**
end-screen vs caption safe area.

