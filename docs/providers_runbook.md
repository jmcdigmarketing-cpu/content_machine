# Providers runbook — Pillar 6 seams (code-tied)

The living, in-repo version of the operator's master tool-integration runbook: each tool
mapped to the **module that hosts it**, its **env gate**, a **proof command**, and its
**status**. Companion to [video_creation_stack.md](video_creation_stack.md) (slot design +
costs), [tooling_landscape.md](tooling_landscape.md) (borrow/threat verdicts), and
[groundwork_2026Q3.md](groundwork_2026Q3.md) (new-tools documentation + 3-month roadmap).

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
| WhisperX | [core/caption_align.py](../core/caption_align.py) | `CAPTION_ALIGN_BACKEND=whisperx` | `transcribe_and_align(audio)` returns word segments | seam |
| anything-to-notebooklm | [core/vault_ingest.py](../core/vault_ingest.py) | `INGEST_ENABLED` (auto only) | `python -c "from core.vault_ingest import ingest_url; print(ingest_url('https://www.bbc.com/news'))"` | seam (`ingest_url` real) |
| Expert Panel (ai-marketing-skills) | [core/grade.py](../core/grade.py) | `EXPERT_PANEL_ENABLED` | add persona to `prompts/expert_panel/`, `expert_panel_review(draft)` | seam |
| ComfyUI | [core/comfy_client.py](../core/comfy_client.py) | `COMFYUI_URL` | run ComfyUI, `generate(prompt, workflow=...)` | seam |
| LTX-Video | [workflows/](../workflows/README.md) + comfy_client | `AI_VIDEO_PROVIDER=comfyui` | export `workflows/ltx_broll.json`, submit via comfy_client | seam |
| AI video-gen slot | [assets/ai_video_provider.py](../assets/ai_video_provider.py) | `AI_VIDEO_PROVIDER` | register in `assets/manager._PROVIDERS`, add to `ASSET_PROVIDER_ORDER` | seam (not registered) |
| MusicGen | [core/music.py](../core/music.py) | `MUSIC_PROVIDER=musicgen` | `generate_bed('calm', 10)` returns a wav path | seam |
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
python -m unittest discover -s tests
```
