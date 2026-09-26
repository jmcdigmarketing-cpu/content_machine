# Providers runbook — Pillar 6 seams (code-tied)

> **Class:** runbook · **Status:** living · **Reviewed:** 2026-09-26

The living, in-repo version of the operator's master tool-integration runbook: each tool
mapped to the **module that hosts it**, its **env gate**, a **proof command**, and its
**status**. Companion to [video_creation_stack.md](video_creation_stack.md) (slot design +
costs), [tooling_landscape.md](tooling_landscape.md) (borrow/threat verdicts), and
[master_plan.md](master_plan.md) (the current forward plan; the archived
[groundwork_q3_2026.md](groundwork_q3_2026.md) holds the original tool notes).

## The contract ([core/providers.py](../core/providers.py))

Every seam generalizes the two provider patterns already in the repo —
[apis/signal_contract.py](../apis/signal_contract.py) (`make_signal`, never-raise) and
[assets/base.py](../assets/base.py) `AssetProvider` + the fail-open chain in
[assets/manager.py](../assets/manager.py). Rules every seam keeps:

- **Env-gated OFF by default** — `resolve_order` / `selected_provider` / `flag_enabled`.
- **Lazy-imports** its heavy backend — torch / whisperx / audiocraft never import at load,
  so CI is green with none of the `[providers]` extras installed.
- **Fails open** — returns `ProviderResult.fail_open(...)` (or `None` for the asset/TTS
  path), never raises; the caller keeps its current behavior.
- **Cost-aware** — `ProviderResult.cost_usd` carries the metered spend for a real call.

Install the heavy backends on demand: `pip install -e ".[providers]"`.

## Status map

`implemented` = wired + runs today · `seam` = baseline stub, fail-open until a backend +
gate are supplied · `excluded` = deliberately not integrated this pass.

| Tool | Module | Env gate | Proof / test | Status |
|---|---|---|---|---|
| **goose3** | [core/link_facts.py](../core/link_facts.py) `_goose3_body_lines` | (always on; falls back) | `python -m unittest tests.test_link_facts_goose3` | **implemented** |
| Kokoro-82M / XTTS-v2 / **Piper** | [core/tts.py](../core/tts.py) `_try_alt_tts_provider` | `TTS_PROVIDER=piper\|kokoro\|xtts` (+ `PIPER_VOICE=…onnx`) | `python -m unittest tests.test_tts_local`; live: set gate, render → real mp3 + `tts $0.0000` | **implemented** |
| **Voice variety** (per-channel + jitter) | [core/tts.py](../core/tts.py) `resolve_local_voice` | `channels.json` `tts.local_voice(s)` / `PIPER_VOICES` (csv) + `TTS_VOICE_VARIETY` (off) | `python -m unittest tests.test_tts_voice_variety`; live: two channels → distinct `[TTS]` voice | **implemented** |
| **faster-whisper** / WhisperX | [core/caption_align.py](../core/caption_align.py) | `CAPTION_ALIGN_BACKEND=faster_whisper\|whisperx` (+ `CAPTION_ALIGN_MODEL`, default `tiny`) | `python -m unittest tests.test_caption_align`; accuracy: `py -m scripts.bench_caption_align` | **implemented on CPU** (U1) — see note below |
| anything-to-notebooklm | [core/vault_ingest.py](../core/vault_ingest.py) | `INGEST_ENABLED` (auto only) | `python -c "from core.vault_ingest import ingest; print(ingest('https://www.bbc.com/news'))"` | **implemented** (URL/PDF/YouTube → vault note, `ops ingest`) |
| Expert Panel (ai-marketing-skills) | [core/grade.py](../core/grade.py) | `EXPERT_PANEL_ENABLED` | add persona to `prompts/expert_panel/`, `expert_panel_review(draft)` | seam |
| ComfyUI | [core/comfy_client.py](../core/comfy_client.py) | `COMFYUI_URL` | run ComfyUI, `generate(prompt, workflow=...)` | seam |
| LTX-Video | [workflows/](../workflows/README.md) + comfy_client | `AI_VIDEO_PROVIDER=comfyui` | export `workflows/ltx_broll.json`, submit via comfy_client | seam |
| AI video-gen slot | [assets/ai_video_provider.py](../assets/ai_video_provider.py) | `AI_VIDEO_PROVIDER` | registered in the asset chain, routes via `core/comfy_client` | **wired** (U4; ComfyUI/Wan/LTX backend parked — GPU) |
| MusicGen | [core/music.py](../core/music.py) | `MUSIC_PROVIDER=musicgen` | `generate_bed('calm', 10)` returns a wav path | **wired** (U3: ducked under VO in render; backend parked — GPU) |
| system_prompts_leaks | [core/run_eval_corpus.py](../core/run_eval_corpus.py) | (`EVAL_CORPUS_LLM` for scoring) | drop cases in `prompts/eval_corpus/`, `py -m core.run_eval_corpus` | seam |
| LatentSync (avatar) | [core/avatar.py](../core/avatar.py) | `AVATAR_PROVIDER` | — (real-likeness ⇒ must trip AI disclosure) | seam |
| Ultralytics YOLO (auto-reframe) | [core/reframe.py](../core/reframe.py) | `REFRAME_ENABLED` | — (**AGPL** — license check before shipping) | seam |
| n8n / lucaswalter / Marvomatic | [core/events.py](../core/events.py) (already shipped) | `EVENT_WEBHOOK_URL` | point an n8n Webhook node at the URL; fire a run | wired (webhook) |

### Excluded this pass
- **Higgsfield** — paid API; opt-in later only if local generation quality misses the bar.
- **`[search github]` repos** — Real-ESRGAN/RIFE nodes, youtube-automation-agent,
  gemini-youtube-automation, AutoSocial (each needs a GitHub search to locate the current
  repo; revisit deliberately).
- **DO NOT INSTALL** — ShortGPT, **MoneyPrinterV2** (AGPL — don't clone near the repo),
  ComplianceAsCode (category mismatch).

The four cloned tool checkouts (`ComfyUI/`, `ai-marketing-skills/`,
`qiaomu-anything-to-notebooklm/`, `system_prompts_leaks/`) are gitignored — local
reference/runtime, never embedded into this repo.

### U1 caption alignment — CPU works; "needs a GPU box" was wrong (2026-08-15)

`faster_whisper` runs the alignment slot on **CPU**, measured against ElevenLabs'
own `.words.json` sidecars over three real 55–58s shorts
(`py -m scripts.bench_caption_align`):

| model | caption line-start error (p50) | p90 | speed |
|---|---|---|---|
| **tiny** (default) | **43–56 ms** | 111–176 ms | 12–15× realtime |
| base | 73–85 ms | 142–159 ms | 4–15× realtime |

`tiny` wins on typical error *and* speed *and* download size — the audio is clean
synthetic speech, the easiest case for ASR, so bigger models mostly re-segment
differently. Raise `CAPTION_ALIGN_MODEL` for noisy source audio (Phase R).

**Caption text now comes from the script (2026-08-16).** Whisper transcribes blind, so
its words were wrong exactly where it mattered ("Salkal" for "Salkilld").
[video/caption_retext.py](../video/caption_retext.py) keeps whisper's timings and takes
the text from the script by `difflib` alignment, which is what made this slot
caption-ready and unblocked the $0 TTS switch ([free_mode.md](free_mode.md)).

Measured on run 66 (243 words, `py -m scripts.bench_caption_align`), retexting is
effectively free:

| | words covered | word p50 | line p50 | line p90 |
|---|---|---|---|---|
| raw ASR | 243 of 251 heard, **12 misheard** | 42 ms | 47 ms | 117 ms |
| **+retext** | **243/243, 0 misheard** | 43 ms | 50 ms | 117 ms |

Below `CAPTION_RETEXT_MIN_MATCH` (0.35) it **declines** and the caller falls back to the
proportional estimate — a transcript that doesn't match the script has timings for
different audio. Real audio scores **0.87**, unrelated audio ~0.0.

### The other "parked — needs a GPU" slots are blocked by an install, not hardware

This box has an **RTX 4070 Ti (12 GB, driver 591.86)**, but `torch` is installed as
**`2.8.0+cpu`**, so `torch.cuda.is_available()` is `False`. Every slot below marked
*parked — GPU* (WhisperX's wav2vec2 pass, MusicGen, ComfyUI/Wan/LTX, YOLO reframe,
avatar, Real-ESRGAN/RIFE, XTTS/Kokoro voice cloning) is waiting on a CUDA torch build,
not on new hardware. Verify with `nvidia-smi` and
`python -c "import torch; print(torch.__version__, torch.cuda.is_available())"` before
believing any "parked" status here.

## Adding a provider

1. Read the seam module's docstring — it names the entry point + the eventual wire point.
2. Implement the backend behind the lazy import; return `ProviderResult.success(...)` with
   `cost_usd` set, or fail open on any error.
3. Flip the env gate (and add the backend to the `providers` extra in
   [pyproject.toml](../pyproject.toml) if it's a new dependency).
4. Add a test that asserts fail-open when the gate is off / backend absent (see
   [tests/test_providers.py](../tests/test_providers.py)).
5. Only then wire it into the live path (render / asset chain / grading) — keep that step
   separate so a half-built provider can't break a render.

## Verify (mirrors CI)

```powershell
ruff check .
ruff format --check .
python -m unittest discover -s tests -t .
```
