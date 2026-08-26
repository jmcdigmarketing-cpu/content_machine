# Tool Integration Plan — the top 7 (2026-08-25)

How the seven highest-ranked tools from the
[tooling landscape addendum](tooling_landscape.md#addendum--14-operator-submitted-tools-2026-08-25)
would actually be integrated — what ships, what is blocked, and what turns out to be
built already.

> **This document's whole value is that its claims were checked against the code, not
> assumed.** Every module and line reference below was verified at the time of writing.
> If you touch one of these seams, update the reference or delete it — a stale pointer
> here is worse than no pointer.

---

## Executive summary

| # | Tool | Status | Effort |
|---|------|--------|--------|
| 1 | MoneyPrinterTurbo → **Coverr provider** | **Ship** — Wave A | `[S]` |
| 2 | awesome-gpt-image-2 → **thumbnail arms** | **Ship** — Wave A, own words only | `[S]` |
| 3 | mattpocock/skills → **`/tdd` skill** | **Ship** — Wave A, own words only | `[S]` |
| 4 | MoneyPrinterTurbo → **Edge TTS** | **Blocked** — legal read pending | `[M]` |
| 5 | public-apis | **Research** — Wave C, shortlist only | `[S]` |
| 6 | senior-prompt-engineer | **Already built** — no work | — |
| 7 | hister | **Already solved** — no work | — |
| — | OmniRoute | **Already built** — no work | — |

Of the seven, **three need no integration at all**, one is blocked on a licence
question, and three are small, well-seamed additions.

---

## Three are already built

Reading the code before planning is what produced this section. Each of these was
ranked as worth adopting; each turns out to exist here already, in some cases in a
better form than the tool being considered.

### senior-prompt-engineer → `core/prompt_evals.py`

The skill's central rule is *"never change a prompt without a baseline."* That is
already implemented, and more strictly than the skill proposes:

- **Frozen golden topics with frozen key facts** — `config/prompt_evals.json`.
- **A deterministic heuristic rubric** — hook score, authenticity, ungrounded-specific
  count against the frozen facts, word-count fit, filler count. **No LLM judge**, so a
  re-run on unchanged prompts is reproducible.
- **Results tagged by prompt version**, written to `data/prompt_evals/<timestamp>.json`.
- **`compare`** diffs the two most recent runs per metric.
- Exposed as **`py -m scripts.ops prompt-eval`**, and `ops skillopt` gates skill-directive
  changes on the same frozen evals.

**Correction to the addendum.** The ranking entry said `PROMPT_VERSION` "is bumped by
hand with no A/B behind it." Both halves are wrong and the entry should be read with
this note. `current_prompt_version()` calls `prompt_version_for_sources()`
([`core/content_engine.py:45`](../core/content_engine.py)), which SHA-256 hashes the
actual prompt source blob — versions are **derived from the prompt text**, so they
cannot drift from it, and no one has to remember to bump anything. And
`prompt_evals` *is* the A/B.

**Takeaway:** nothing to integrate. If anything is missing it is a *habit*, not a
module — run `ops prompt-eval compare` after prompt edits.

### hister → `LINK_READER_PROXY`

hister's appeal was that a browser has already rendered a JS-heavy page, so it can
index what a scraper cannot — aimed at run 71, where an MSN link came back headline-only.

That path already exists. `core/link_facts.py` detects the failure and retries:

- `_reader_proxy_enabled()` ([`core/link_facts.py:339`](../core/link_facts.py)) gates on
  `LINK_READER_PROXY`.
- `_reader_proxy_facts()` fetches the rendered text through a reader proxy.
- The retry fires exactly on the observed symptom — `if is_title_only(raw) and
  _reader_proxy_enabled()`.

It is **opt-in and off by default on purpose**: it sends the target URL to a third
party, which cuts against the self-hosted-first stance. That is a deliberate trade, not
an oversight.

**Takeaway:** nothing to integrate. hister would be a *self-hosted alternative* to that
proxy — a real option someday, but it is Go, AGPL, and a separate service to run, for a
problem that already has two answers (`paste` mode and the proxy). Not worth it now.

### OmniRoute → `core/llm_router.py`

Tier routing, provider failover, a session breaker, and cost-meter wiring are all
present. A gateway placed between us and the providers would **blind the breaker**,
which is the opposite of what it is for.

**Takeaway:** do not adopt. Mine its free-tier provider list for slugs to add to the
router we already have.

---

## Licence findings — the gate on what can be borrowed

The operator's call on Edge TTS was *get a legal read first*. That discipline was then
applied to every borrow rather than only the one that raised the question, and it
changed three of the four.

| Source | Licence | Consequence |
|---|---|---|
| **edge-tts** | **LGPL-3.0** (with `srt_composer.py` MIT) | **Parked.** Designed below; nothing added to the dependency tree until cleared. |
| **Coverr** | Free for commercial use **including monetised YouTube**; attribution not required | **Usable**, with the caveats below. |
| **awesome-gpt-image-2** | Repo is MIT, but it **explicitly disclaims third-party prompt/image rights** and says to get authorization from rights holders before commercial use | **Method only.** Never paste its prompts. |
| **mattpocock/skills** | **No LICENSE file** → all rights reserved by default | **Do not copy.** Write our own; an idea is not copyrightable, a file is. |

`pyproject.toml` declares this project `Proprietary`, and the landscape doc already
holds this line elsewhere — Ultralytics YOLO is flagged AGPL, and MoneyPrinterV2 is
"AGPL-3.0 blocks code reuse". These findings are consistent with that, not a new policy.

**Coverr caveats worth recording**, since footage goes into a monetised channel:

- Model releases exist but are **not provided to users** — compliance with privacy and
  publicity law is on us. Prefer footage without recognisable faces.
- **No AI-training or dataset use.** Coverr clips may be used *as footage*; they must
  not be fed to the Pillar 6 video-gen providers as training or conditioning input.
- No redistribution into a competing stock/editing service — irrelevant here, but it is
  why the licence is not simply CC0.

---

## Wave A — buildable now

### A1. Coverr as a third stock provider `[S]`

The seam is already a registry, so this is additive and low-risk.

- `_PROVIDERS` at [`assets/manager.py:16`](../assets/manager.py) maps a provider name
  to its class.
- Each channel's order lives in `channels.json` as `asset_provider_order`, currently
  `["local", "pexels", "pixabay"]` for both channels.

**Implementation:** one `CoverrAssetProvider` in `assets/coverr_provider.py`, modelled
line-for-line on [`assets/pexels_provider.py`](../assets/pexels_provider.py) — an
`is_configured()` reading the key from settings, and a `find_video()` returning
`AssetResult`, reusing the shared helpers (`find_cached`, `register`, `download_file`,
`safe_filename`, and `search_query` from `assets.category`). Then one line in
`_PROVIDERS` and `"coverr"` appended to each channel's order.

**Why it is worth doing:** a third source reduces repeated footage across uploads.
Visual sameness between videos is the *variation* half of what the 2026 authenticity
policy assesses — the same reason MoneyWise was just given its own voice.

**Verification:** it must fail open exactly like the others — no key configured means
the chain falls through to Pexels with no error. Test with a fake `requests` response
in the `make_signal`-style pattern used by the existing provider tests; no network.

### A2. Thumbnail composition arms, written from the method `[S]`

`_LEVERS` in [`core/experiment_levers.py`](../core/experiment_levers.py) already carries
`thumbnail_style` and `thumbnail_format` with `kind: "thumbnail"`, and the `kind` filter
stops visual directives leaking into script prompts. Arms feed
[`assets/flux_thumbnail.py`](../assets/flux_thumbnail.py), and `ops experiment` already
reports arms against realized engagement.

So a new arm is **a dict entry that gets measured for free** — the cheapest lever on
this list.

**What to borrow:** the *structural* idea behind awesome-gpt-image-2 — that a strong
image prompt is composed of named slots (subject scale, composition, lighting, negative
space for text) rather than written as prose. Express those slots in our own words,
matched to what this channel actually posts.

**What not to borrow:** its prompt text. The repo's own disclaimer is explicit that
third-party prompts carry third-party rights.

**Verification:** thumbnail CTR is not yet attributable — the roadmap notes CTR
optimisation needs impressions/CTR in the metrics sync before the experiment report can
attribute clicks rather than engagement. So new arms are worth adding *now* and worth
*judging* only once that lands. Say so rather than reading early engagement as a verdict.

### A3. A `/tdd` skill in our own words `[S]`

`.claude/` currently holds only `settings.local.json` — there is no skills directory.

Add `.claude/skills/tdd/SKILL.md` enforcing the loop this repo learned the hard way:
**write the test, watch it fail, then fix, then re-run.** That rule is already the first
one in [`.cursor/rules/content-machine.mdc`](../.cursor/rules/content-machine.mdc); the
skill makes it *invokable* rather than merely written down, and gives Claude Code a
slash command where Cursor has a rules file.

It has earned its place empirically. Every defect in the last three audits was green in
CI, and the escaping bug was only proved real because the test was run against the old
code first and produced `-22 Invalid argument` from ffmpeg.

**Write it from our own evidence.** mattpocock/skills has no licence file, so its
content is all rights reserved; the discipline is not his to license and ours is already
documented.

---

## Wave B — Edge TTS, designed and parked

Designed now because the design is what a legal read needs in order to assess anything,
and because this is the highest-value item on the list.

### The seam

[`core/tts.py:844`](../core/tts.py) holds `_ALT_TTS = {"kokoro": …, "xtts": …,
"piper": …, "qwen": …}`. Each synth has the signature `(script, output_path,
channel_id) -> str | None`, and `_try_alt_tts_provider` catches any failure and returns
`None`, which falls back to ElevenLabs. Adding `"edge"` is **one registry entry and one
function**.

### The prize is the timings, not the voice

This is the part that makes it worth the licence question.

- edge-tts emits **`WordBoundary` events** carrying offset, duration and text —
  the mechanism exists specifically for subtitle generation.
- **No local provider writes a `.words.json` sidecar today.** `word_timing_path()`
  ([`core/tts.py:877`](../core/tts.py)) defines the path; only the ElevenLabs path
  populates it. That absence is precisely why the $0 route depends on whisper
  alignment.
- An Edge provider that writes the sidecar would give Free mode **exact caption timings
  with no whisper at all** — and, through the `resolve_word_timings` seam
  (`video/subtitles.py`), hook motion and lower thirds would fire on the $0 path too.

It may also retire the pronunciation-lexicon item outright: that item exists because
Piper mispronounces the fighter and game names that are the channel's entire subject.

### Conditions the parked decision implies

If cleared, it enters under these constraints — recorded now so they are not
re-argued later:

- **Unmodified installed dependency** in the `[free]` extra. Never vendored, never
  patched — that is the boundary LGPL linking relies on.
- **Never the default provider.** `TTS_PROVIDER=edge` is opt-in, exactly like
  `piper` / `kokoro` / `xtts` / `qwen`.
- **Fail-open** through `_try_alt_tts_provider` to the existing chain, so an
  undocumented upstream endpoint disappearing can never break a render.
- **One real render compared against Piper** before anything depends on it — both for
  voice quality and to confirm the sidecar timings match the audio.
- The endpoint is undocumented and can change without notice. It is a **cost lever, not
  a foundation**.

---

## Wave C — public-apis as a research input

Not a dependency and not a code change. [`apis/free_backends.py`](../apis/free_backends.py)
already provides the `SIGNAL_BACKEND=apify|free|auto` seam and `fetch_youtube_free`, so
the question is never "how do we plug in a free backend" — it is "which free backends
are worth plugging in."

**Deliverable:** a shortlist appended to
[`agent_reach_evaluation.md`](agent_reach_evaluation.md), not a new document. For each
candidate: the signal in `apis/` it would serve, the paid call it displaces, whether it
needs a key, and whether it survives a rate limit under real discovery load. Anything
that cannot answer the last two is not a candidate.

This matters because the remaining paid Apify actors (`tiktok_trends`,
`youtube_competitors`) are still the main recurring cost.

---

## Sequencing

1. **Wave A** — three small, independent, licence-clear additions. Any order.
2. **Wave C** — research, can run alongside Wave A.
3. **Wave B** — only after the licence read returns.

Wave A items are deliberately small enough to land individually. None of them blocks
another, and none touches the render path that the 21–28 wave just changed.

## Out of scope

- **Anything from MoneyPrinterTurbo beyond Coverr and Edge TTS.** Its WebUI, publishing
  and orchestration overlap what exists here.
- **Adopting OmniRoute, hister, or a second prompt-eval harness** — see "already built".
- **Judging thumbnail arms on engagement** until impressions/CTR reach the metrics sync.

## Related

- [tooling_landscape.md](tooling_landscape.md) — the ranking these seven came from.
- [agent_reach_evaluation.md](agent_reach_evaluation.md) — free/keyless backend
  evaluation that Wave C feeds.
- [video_creation_stack.md](video_creation_stack.md) — where a TTS provider slot sits in
  Pillar 6.
- [decisions.md](decisions.md) §23 — captions are timed by the ASR and spelled by the
  script, which is the constraint Edge TTS's sidecar would relax.
