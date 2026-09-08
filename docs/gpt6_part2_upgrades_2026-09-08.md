# GPT-6 Part 2 — Content Machine: the next 10 upgrades

**Source:** GPT-6 playground, 2026-09-08. Companion to
[gpt6_second_review_2026-09-08.md](gpt6_second_review_2026-09-08.md).

**Provenance:** External opinion, not a recorded operator decision. It does
not override [roadmap.md](roadmap.md) or [docs/decisions.md](decisions.md) by
existing. Do not enable `SCENE_MATCHED_BROLL` from item 6. Item 10 (paid
deliverable) is a commercial idea, not a shipped product decision.

A genuine installed-version audit would still need the lockfiles, redacted
provider config, FFmpeg build, and exact TTS repository/model versions.

---

## The next 10 upgrades

### 1. Replace paid public-metadata collection with the official YouTube API where equivalent

For known competitor channels, use channel upload playlists and batched video
metadata retrieval for fields the YouTube Data API actually exposes.

This could replace part of Apify’s YouTube work—not all discovery, and
certainly not unavailable competitor retention or revenue data.

Route it through the existing signal/cache boundary.

**Value:** Lower recurring discovery expenditure and a clearer integration
contract.

### 2. Add domain-specific primary-source adapters

Add narrowly scoped sources that supply **facts** rather than trend signals:

- **Moneywise:** SEC EDGAR for US filings; FRED for appropriate economic series.
- **Gaming:** Official patch notes, developer announcements, and supported game-news feeds.
- **UFC:** Official announcements and commission documents where accessible and permitted.

Normalize units, reporting periods, and source identifiers.

**Value:** More authoritative scripts and less manual searching. FRED is not a
replacement for real-time stock or crypto pricing.

### 3. Add a channel pronunciation dictionary

Maintain separate fields for:

- Canonical written name.
- Spoken alias.
- Provider/model-specific pronunciation instructions.

Use it for fighter names, game terminology, financial acronyms, and tickers.
Captions should retain the correct written form rather than phonetic spelling.

Where supported, use ElevenLabs pronunciation dictionaries rather than
repeatedly rewriting narration text.

**Value:** Fewer paid narration retries and a more professional voice.

### 4. Add a technical audiovisual acceptance pass

Use existing FFmpeg/ffprobe capabilities to detect:

- Unexpected silence.
- Audio clipping or excessive peaks.
- Audio/video duration mismatch.
- Unintended black frames.
- Missing audio streams.
- Encoding or resolution mismatches.

Use configurable loudness targets rather than assuming one universal platform
specification.

Present this as a technical QC result, separate from the existing editorial
grade.

**Value:** Catches defects viewers notice immediately, without another AI call.

### 5. Deliver real caption tracks, not only burned-in text

Export clean SRT/WebVTT from existing timings, with:

- Correct names and punctuation.
- Sensible phrase breaks.
- Declared language.
- Properly formatted numbers.

Where supported and authorized, upload a caption track through the YouTube API
in addition to burned-in captions.

**Value:** Accessibility, reusable deliverables, and better downstream
portability. This does not require caption choreography or another paid
transcription provider.

### 6. Add an owned-footage preparation station

Prepare frequently reused footage once:

- Technical metadata.
- Operator-approved vertical crops.
- Usable ranges.
- Lightweight preview files.
- Render-friendly proxies.
- Excluded regions or segments.

Key derived assets to the original file and processing settings so changed
footage does not reuse stale derivatives.

**Value:** Less repeated decoding, faster browsing, and less need to reach for
stock footage. This can use the existing owned-footage path **without enabling
scene-matched b-roll**.

### 7. Make the job queue resource-aware

Teach the existing queue about resource requirements:

- GPU-heavy render or transcription.
- CPU-heavy processing.
- TTS provider concurrency.
- Lightweight network work.

Reserve capacity for foreground work and prevent overnight jobs from starting
competing heavyweight stages when the operator is actively producing.

**Value:** A more responsive desktop, fewer avoidable rate-limit collisions,
and better use of the same machine—without adding another queue system.

### 8. Establish a reproducible Windows runtime

Lock and record the working combination of:

- Python dependencies.
- FFmpeg build.
- Qt plugins.
- CTranslate2/GPU dependencies, where used.
- Local model and voice assets.

Use the existing dependency-locking tool; consider `uv` if none exists. Add
vulnerability assessment with `pip-audit`, but do not automatically upgrade
every flagged dependency without compatibility review.

**Value:** Faster recovery from environment breakage and fewer “worked
yesterday” failures.

### 9. Build a license-and-credit compiler

For each included asset, retain the applicable permission or license receipt:

- Music and sound effects.
- Stock footage.
- Sources.
- Voice service/model.
- Game-footage usage policy where relevant.

Generate the required credit fragment and a deliverable-side license summary.

Distinguish permission to publish on your channel from permission to hand
assets or finished work to a paying client.

**Value:** Makes monetized and commissioned outputs materially more
professional.

### 10. Pilot a fixed-scope paid content deliverable

Offer a bounded package using the existing pipeline:

- One finished short.
- Caption file.
- Thumbnail.
- Source/credit sheet.
- Clearly limited revisions.

This sells the **output**, not the software, and does not require your own
channel to generate advertising revenue first.

Build delivery automation only after a real buyer requests the package.
Commercial voice and asset rights must cover the engagement.

**Value:** A potential direct revenue route independent of reaching YouTube
monetization thresholds. Customer acquisition and revision management remain
real work.

---

## API / software / repository audit priorities

| Component | What merits greater use—or a careful check |
|---|---|
| **YouTube Data API** | Greater use for equivalent public metadata and authorized caption delivery. Check current quota costs and data-retention requirements for the exact endpoints. |
| **Apify** | Retain tasks that provide genuinely unavailable discovery data. Replace equivalent public-metadata tasks selectively, not indiscriminately. |
| **SEC EDGAR / FRED** | Strong candidates for specific finance facts. Observe SEC access requirements and the licensing restrictions of individual FRED series. |
| **ElevenLabs** | Pronunciation support is a concrete efficiency opportunity. Confirm that the selected model supports the intended dictionary features and that the plan covers commercial outputs. |
| **FFmpeg / faster-whisper** | Exploit technical QC, proxy generation, and existing word timings. Benchmark hardware encoding on the actual machine; GPU encoding is not automatically the best quality/cost choice. |
| **Edge TTS** | If this means the common `edge-tts` package, distinguish it from an Azure AI Speech commercial API agreement. Check service permissions and reliability before relying on it for paid client delivery. |
| **Piper** | Inspect the exact installed repository and voice licenses. The original project and successor lineage should not be assumed interchangeable in maintenance, compatibility, or licensing. |
| **PySide6 / Qt** | Check the particular modules and eventual distribution obligations. Private local use alone does not establish a need to purchase a commercial Qt license. |

Useful inspection references—not live-verified assessments:

- YouTube Data API documentation
- SEC API documentation
- FRED API documentation
- `edge-tts`
- Piper successor repository candidate
- faster-whisper

For Piper especially, distinguish software-license obligations from
voice-model permissions; the software’s license does not automatically
determine the license of generated audio.

---

## What may be missing from the content catalog

Audit for these four inventories:

1. **Pronunciation inventory:** canonical names, acronyms, spoken aliases, provider compatibility.
2. **Production-ready footage inventory:** approved crops, usable ranges, proxy locations, technical characteristics.
3. **Rights inventory:** receipts, attribution text, commercial-use scope, client-delivery permissions.
4. **Primary-source inventory:** domain-specific endpoints, document types, units, and parsing conventions.

These are production assets that become more useful with reuse—not simply
additional topic ideas.

---

## Best course forward

Start with official metadata substitution, pronunciation control, and
technical audiovisual QC. Those offer concrete savings or output improvements
using much of the existing stack.

Then make the runtime and asset permissions dependable enough for professional
delivery. Explore one bounded paid-production pilot, rather than assuming that
increasing publishing volume or purchasing stronger AI models is the only
route to revenue.

For both projects, a genuine installed-version audit would require the
dependency manifests/lockfiles and redacted provider configuration; for
Content Machine, also the FFmpeg build information and exact TTS
repository/model versions.
