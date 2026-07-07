# Video Creation Stack — tools to add (2026-07)

**Directive (operator, 2026-07-07):** override [operating_plan.md](operating_plan.md)
§8's "keep generation boring, don't chase quality/volume." Generation quality is
now treated as a real competitive lever — 2026 SOTA AI video makes slideshow-style
faceless output look dated, and *"all's fair; competition is a copycat game."* This
doc lists **every tool/provider to add** for video creation, plus fresh brainstorm.

Recorded as [decisions.md](decisions.md) §17. Two things the override does **not**
change: (1) the moat still stands — grounding + the closed analytics loop stay;
the video layer is *additive*, not a replacement; (2) richer/realistic AI video
*increases* the need for the 2026 authenticity-disclosure layer
([core/authenticity.py](../core/authenticity.py)), it doesn't remove it.

## Architecture: pluggable provider slots (Content OS-native)

Don't bolt on a second pipeline. Add each capability as a **provider chain** in
the shape Content OS already uses (`assets/` provider chain: local → Pexels →
Pixabay; [core/llm_router.py](../core/llm_router.py) tier chains). Every slot:

- **free/local-first**, paid upgrade opt-in, **env-gated**, **priced in the cost
  meter** ([core/cost_meter.py](../core/cost_meter.py)) so the margin math stays honest;
- **fail-open** to the current behavior (an AI-video slot that errors falls back to
  stock/hybrid backgrounds — never breaks a render);
- optional **ComfyUI / fal.ai / Replicate** as aggregator backends so we add one
  HTTP client, not N SDKs, and swap models without code changes.

> **Licensing (practical, not preachy):** borrow *ideas/patterns* freely. For
> *code*, MoneyPrinterV2 is **AGPL-3.0** — pattern-only, don't lift source into
> this repo. For *model weights*, check each license before commercial use — some
> hot 2026 video models are research/non-commercial (e.g. some Hunyuan/Kling
> terms); Apache/OpenRAIL ones (Wan, LTX-Video, Mochi, MusicGen, Kokoro) are safe.

---

## The slots (all tools to add)

### 1. AI video generation — b-roll & full scenes  *(biggest gap; new `video/providers/`)*
Replaces/augments stock clips with generated, prompt-matched footage per scene
beat (feeds the existing [video/scene_plan.py](../video/scene_plan.py) beats).
- **Open / self-host (free):** **Wan 2.x** (Alibaba, Apache-2.0, strongest open in
  2026), **LTX-Video** (Lightricks — realtime-ish, cheap), **Hunyuan Video**
  (Tencent), **Mochi-1** (Genmo, Apache-2.0), **CogVideoX**, **Open-Sora**. Run via
  ComfyUI or diffusers on a GPU box.
- **API / paid:** **Google Veo 3.1** (native audio — big deal), **OpenAI Sora 2**,
  **Kling 3.0**, **Runway Gen-4**, **Luma Ray**, **Pika 2.x**, **MiniMax Hailuo**,
  **Higgsfield** (Seedance/Kling wrapper). Aggregate via **fal.ai** / **Replicate**.
- **Wire-in:** new `MediaProvider` behind `assets/composite.py` — `AI_VIDEO_PROVIDER=
  none|wan|ltx|veo|kling|runway|fal` , per-beat prompt from the scene plan, fail-open
  to stock. Cost-metered per clip-second.

### 2. Voice / TTS  *(dominant per-video cost — biggest cost lever left)*
Extend TTS beyond ElevenLabs with a provider chain + a voice-clone slot (Phase O
"voice variety").
- **Open / local (free):** **Kokoro-82M** (tiny, fast, great quality/size), **Chatterbox**
  (Resemble, emotion), **F5-TTS**, **Fish Speech**, **XTTS-v2** (Coqui, cloning),
  **Piper** (edge/CPU), **Orpheus**, **KittenTTS** (MoneyPrinterV2's pick).
- **API / paid:** **ElevenLabs v3** (current), **Cartesia Sonic** (low-latency),
  **Hume Octave** (emotional), **OpenAI TTS**, **PlayHT**, **Rime**.
- **Wire-in:** `TTS_PROVIDER=elevenlabs|kokoro|xtts|piper|cartesia|...` behind
  `core/tts.py`; word-level timing from providers that emit it, else Whisper (slot 3).
  Local TTS ⇒ ~$0 voice cost.

### 3. Captions / word-timing / alignment  *(Whisper local — already on roadmap)*
Content OS uses ElevenLabs timestamps today; add local alignment so *any* TTS (or
clip-from-source) gets accurate word timing.
- **Tools:** **faster-whisper** / **WhisperX** (word-level, local), **Montreal Forced
  Aligner** / **aeneas** (forced alignment fallback).
- **Brainstorm adds:** auto-**emoji** injection on keywords, **keyword-pop** b-roll
  triggers synced to caption highlights (extends the karaoke `CAPTION_STYLE`), and
  auto-**censor bleeps** for brand-safety.

### 4. Music & SFX  *(new `video/audio_bed.py`)*
Background music beds + stingers/whooshes on cuts — a large perceived-quality jump
for shorts.
- **Open / local (free):** **MusicGen** (Meta), **Stable Audio Open**, **AudioLDM2**.
- **API / paid:** **Suno**, **Udio**, **ElevenLabs SFX + Music**, **Cassette**.
- **Wire-in:** ducked under VO in the FFmpeg mix; mood from the research brief
  (`audience_sentiment`/angle). `MUSIC_PROVIDER=none|musicgen|suno|elevenlabs`.

### 5. Thumbnails / images  *(Flux already; text-in-image is the gap)*
- **Add:** **Ideogram v3** (best text rendering), **Recraft v3**, **Nano Banana**
  (Gemini image), **Seedream 4**, **GPT-image-1**, **Flux Kontext** (edit existing).
- **Wire-in:** extend `assets/flux_thumbnail.py` to a thumbnail-provider chain;
  the A/B `thumbnail_style` harness already exists to test them against engaged-rate.

### 6. Talking-head / avatar  *("faceless with a face" mode, optional)*
- **Open / local (free):** **LatentSync** (ByteDance), **Hallo2**, **MuseTalk**,
  **SadTalker**, **Wav2Lip** (lip-sync a still/portrait to the VO).
- **API / paid:** **Hedra Character-3**, **HeyGen**, **D-ID**, **Argil**.
- **Wire-in:** optional avatar track as an alternative to stock/AI b-roll;
  `AVATAR_PROVIDER=none|latentsync|hedra|heygen`. Note: real-person likeness ⇒ must
  trip the AI-disclosure layer.

### 7. Clip-from-source  *(Phase R — market hedge, pairs with idea-intake)*
Long video / VOD / podcast (file or YouTube URL — idea-intake already accepts links)
→ transcribe → LLM finds strong moments → vertical cuts with captions.
- **Self-host:** **faster-whisper** transcript → LLM moment scoring (reuse
  `core/hook_score.py` + grading) → **auto-reframe** (subject tracking via
  **Ultralytics YOLO** or face-center crop) → existing caption/render stack.
- **External refs:** OpusClip, Vizard, Klap (patterns, not deps).

### 8. Upscaling / interpolation / cleanup  *(polish AI b-roll)*
- **Tools:** **Real-ESRGAN** (upscale), **RIFE / FILM** (frame interpolation for
  smooth slow-mo), **CodeFormer** (face restore), **Topaz Video AI** (paid).
- **Wire-in:** optional post-render FFmpeg/ComfyUI pass; off by default (GPU cost).

### 9. Scene / storyboard planning  *(extend `video/scene_plan.py`)*
LLM shot-list: script beat → per-shot generation prompt (camera, subject, motion)
for the slot-1 video provider. Turns "one background" into a directed sequence.

### 10. Distribution / repurposing  *(from the tooling scan — reach, not creation)*
- **Dual-format render profiles** (one script → 9:16 + 16:9 + 1:1) over the render step.
- **n8n companion recipes** downstream of `core/events.py` webhooks (cross-post,
  clipper) — lucaswalter/n8n-ai-automations shapes.
- **AutoSocial-style local posting** as a Phase-M API-quota hedge (weigh ToS risk).

### 11. Knowledge ingestion  *(Pillar 4 extension — feeds grounding, keeps the moat)*
- **anything-to-notebooklm**-style multi-source importer → provenance-tagged vault
  notes ([core/obsidian_facts.py](../core/obsidian_facts.py)).
- **goose3** (maintained python-goose fork) to harden [core/link_facts.py](../core/link_facts.py).

### 12. Aggregator / infra backends
- **ComfyUI** (self-hosted node graph — one endpoint for image+video+upscale models),
  **fal.ai** / **Replicate** (hosted model marketplace), **Modal / RunPod** (GPU for
  the open models). One HTTP client, many swappable models.

---

## Fresh brainstorm (today-in-mind, beyond the slots)

- **Native-audio video (Veo 3.1 / Sora 2)** — generate ambient/diegetic audio *with*
  the clip, mixed under VO: a quality tier stock can't touch.
- **Motion presets / viral effects** — Higgsfield-style camera moves (push-in, orbit,
  crash-zoom) as named presets in the shot planner.
- **Auto-b-roll from the script** — NER on the script → fetch/generate a matching clip
  per named entity (extends scene-matched b-roll).
- **Sound-design pass** — auto whoosh/impact on every hard cut + a riser into the hook.
- **Face/logo brand overlay** — consistent channel bug + intro sting per channel profile.
- **Multi-lingual dub** — Whisper transcript → translate → local-clone TTS in the same
  voice → per-language uploads (real growth lever; pairs with slot 2 cloning).
- **Hook A/B at the video layer** — render 2 hook variants (different first-3s visual),
  attribute to engaged-rate via the existing experiment harness.
- **"Style memory"** — store winning visual/pacing params in the vault (Pillar 4) and
  bias the shot planner toward what engaged.
- **Vertical auto-reframe for any source** — subject-tracked 9:16 crop as a reusable
  primitive (clip-from-source + repurposing both need it).
- **On-device fast path** — Kokoro TTS + LTX-Video + local Whisper = a genuinely
  ~$0-marginal render for high-volume drafting.

---

## Suggested build order (quality-per-effort)

1. **TTS provider chain + Kokoro/XTTS local** — kills the dominant cost, unlocks voice
   variety. *(slot 2)*
2. **Whisper local alignment** — word timing for any TTS + enables clip-from-source. *(slot 3)*
3. **Music/SFX bed (MusicGen/ElevenLabs)** — big perceived-quality jump, low effort. *(slot 4)*
4. **AI-video provider slot (fal.ai → Veo/Kling, or local Wan/LTX)** — the headline
   upgrade; start behind a flag on one channel. *(slot 1)*
5. **Thumbnail text models (Ideogram)** + dual-format render. *(slots 5, 10)*
6. **Clip-from-source (Phase R)** + auto-reframe. *(slot 7)*
7. **Avatar mode, upscaling, storyboard shot-lists** — polish tiers. *(slots 6, 8, 9)*

Every step ships as a flagged, cost-metered, fail-open provider — generation gets
*better*, and the cost meter + grounding + learning loop keep it honest.
