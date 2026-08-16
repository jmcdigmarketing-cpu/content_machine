# Free ($0) mode

`py main.py` asks you to pick a **cost mode** before a render:

```
  Cost mode
  1) Standard  - best quality (may use paid providers)
  2) Free ($0) - local voice + free models only, no paid calls
  Free ready:  voice=piper OK   llm=ollama OK (local $0)   web=duckduckgo   signals=free
```

**Free mode pins every cost center to its zero-cost backend for the whole run — local-first:**

| Cost center | Free-mode backend |
|---|---|
| Voice (TTS) | local **Piper** (or Kokoro/XTTS) — `$0` |
| LLM (script/facts) | local **Ollama** (unlimited, offline). OpenRouter `:free` is only a *rate-limited* cloud fallback |
| Web search | keyless **DuckDuckGo** (`ddgs`) |
| reddit + youtube_competitors | `SIGNAL_BACKEND=free` (Reddit OAuth + yt-dlp) |
| twitter / tiktok_trends | **skipped** (no free backend) |
| assets / thumbnails | already local / Pexels / Pixabay (free) |

**It is strict.** Free mode never falls back to a paid provider. If a required $0
backend is missing it **blocks** with setup guidance rather than quietly spending money —
e.g. no local voice ⇒ the render stops instead of calling paid ElevenLabs.

**Truly free = local.** A genuinely $0, unlimited run uses **local Ollama** for the LLM.
OpenRouter's `:free` tier is free but *rate-limited* (it throttles under load) — Free mode
uses it only when Ollama isn't running, and labels it `(free, throttled)`. The tradeoff of
going local: all inference runs on your machine, so a full run is **slower and
lower-quality** than paid models, and needs a capable box (~8GB+ RAM, GPU ideal).

Check what's ready any time:

```powershell
py -m scripts.ops free-doctor
```

Headless: `RUN_COST_MODE=free py main.py` selects Free without the prompt.

---

## One-time setup (so Free mode is genuinely $0)

All commands are Windows/PowerShell (see [startup-powershell.md](startup-powershell.md)).
Install the lightweight truly-free stack once: **`pip install -e ".[free]"`** (Piper +
ddgs — no heavy ML deps). Do *not* use `.[providers]` for Free mode: it pulls in Coqui
`TTS`, whose `gruut` dep pins `numpy<2.0` and conflicts with the project's numpy, aborting
the whole install.

### 1. Local LLM — Ollama (the truly-free engine)

Ollama runs models locally: **$0, unlimited, offline, no account or rate limits.**

```powershell
# install Ollama from https://ollama.com, then:
ollama pull llama3.1:8b      # good default; qwen2.5:7b is a solid alternative
# in .env
OLLAMA_MODEL=llama3.1:8b
# OLLAMA_BASE_URL=http://localhost:11434/v1   # only if Ollama runs elsewhere
```

Free mode pings the Ollama server and, when it's up, pins all three tiers to your local
model. If Ollama isn't running, it falls back to OpenRouter `:free` (rate-limited) when a
key is set, else it blocks (the LLM is required for discovery and the script).

> **Cloud fallback (not truly free):** OpenRouter `:free` needs no install but throttles.
> `OPENROUTER_API_KEY=sk-or-...` — pins `meta-llama/llama-3.3-70b-instruct:free`
> (override per tier with `OPENROUTER_MODEL_CHEAP/EXTRACT/PREMIUM`).

### 2. Local voice — Piper (required for $0 voiceover)

Piper is CPU/ONNX, no GPU or torch, MIT-licensed (already in the `providers` extra).
Download one voice (`.onnx` + `.onnx.json`) from the Piper releases — `en_US-lessac-medium`
is a good default — then point the env at the `.onnx`:

```powershell
# in .env
PIPER_VOICE=C:\voices\en_US-lessac-medium.onnx
```

Free mode sets `TTS_PROVIDER=piper` for you once `PIPER_VOICE` exists.

> No local voice yet? Free mode still runs discovery + scripting, but **blocks at render**
> with the install reminder. Standard mode is unaffected (uses ElevenLabs).

#### Captions are the catch — local TTS emits no word timings

ElevenLabs returns per-character alignment and `core/tts.py` writes an
`<audio>.words.json` sidecar, which is what makes captions land on the spoken word.
**Local TTS produces no sidecar**, so `video/subtitles.py` falls back to *proportional*
timing and captions drift out of sync. Turn the local aligner on alongside Piper:

```powershell
# in .env — pair these two, or $0 voice costs you caption accuracy
TTS_PROVIDER=piper
PIPER_VOICE=C:\voices\en_US-lessac-medium.onnx
CAPTION_ALIGN_BACKEND=faster_whisper    # CPU; model downloads on first use (~75MB)
```

Timing accuracy is good — **43–56 ms** median caption line-start error, 12–15× realtime
on CPU (measured, `py -m scripts.bench_caption_align`).

> **Not recommended yet.** The aligner transcribes the audio blind, so caption *text* is
> ASR output rather than your script: "Salkilld" comes back as "Salkal", "Mateusz Gamrot"
> as "Mattius Gamarat". On a channel about fighters and games, that is the wrong thing to
> burn into a video. Until the timings are re-labelled from the known script, the honest
> trade is: **ElevenLabs for anything you publish** (~$0.25/video, ~91% of run cost),
> local TTS for drafts and experiments where captions don't ship.

Piper also speaks ~20% slower than ElevenLabs for the same script (66.3s vs 55.2s
measured on run 65), which shifts video length and feeds the learned-length loop.

#### Where to get more free voices

- **Piper** — the full catalog is the **`rhasspy/piper-voices`** repo on HuggingFace
  (quality tiers `x_low`/`low`/`medium`/`high`; `medium` is the sweet spot). Every voice is
  **two files** — `<voice>.onnx` **and** `<voice>.onnx.json`. Download both into
  `video/voices/` (override with `PIPER_VOICES_DIR`).
- **Kokoro** — ships its own voices, no download. `KOKORO_VOICE` selects one
  (default `af_heart`); needs torch + espeak-ng, so it's the GPU-box option.
- **XTTS** — clones a voice from a 6s+ clean reference wav (`XTTS_SPEAKER_WAV`).
- **Qwen3-TTS** — local voice **cloning** on a GPU (`pip install -U qwen-tts`; needs torch +
  CUDA, fits a 12GB card). `QWEN_VOICE` is either a built-in speaker name **or** a path to a
  reference `.wav` to clone a **brand voice** for a channel (transcript from a sidecar
  `<ref>.txt` or `QWEN_REF_TEXT`). Add it to `config/voices.json` `local.qwen[]`. A unique,
  consistent, $0 voice per channel — the authenticity moat, without ElevenLabs characters.

Run **`py -m scripts.ops voices`** to see every voice this machine can use — local `.onnx`
files found on disk, plus the voices on your ElevenLabs account with their ids and labels —
and what each channel resolves to right now.

**Adding voices is config, not code.** Put them in [`config/voices.json`](../config/voices.json):
`local.piper[]` takes `.onnx` paths, `local.kokoro[]` takes voice names, and the
`elevenlabs` categories take voice ids — each with a `weight` (higher = picked more often).
A category whose name starts with `_` is **parked**: kept for reference, never used.
Per-channel rotation lives in `channels.json` (`tts.voice_pool` / `tts.local_voices`).

### 3. Free web search + signals

- **Web search** — keyless DuckDuckGo via `ddgs` (in the `providers` extra). Free mode sets
  `WEB_SEARCH_BACKEND=duckduckgo`; best-effort ($0, no key). Outside Free mode, set
  `WEB_SEARCH_BACKEND=auto` to use a keyed provider when present, else DuckDuckGo.
- **yt-dlp** (YouTube competitors) — a core dependency, keyless, always available.
- **Reddit** (optional) — a free "script app" (reddit.com/prefs/apps, ~2 min, 100 req/min):

```powershell
# in .env
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
```

`twitter` / `tiktok_trends` have no free backend, so Free mode skips them — discovery still
runs on YouTube, Reddit, Wikipedia, RSS, trends, and DuckDuckGo.

---

## How it works (for maintainers)

`core/run_mode.py` is the whole feature. `prompt_cost_mode()` (`core/ui.py`) picks the mode;
`apply_cost_mode("free")` mutates `os.environ` once at startup
(`main.py::_apply_cost_mode_interactive`). Every knob is read at call-time, so the env update
propagates to all subsystems — the one exception, `register_signals`, was made per-call
(`_skip_signals()`).

- `_free_llm()` is **local-first**: `_ollama_ready()` (OLLAMA_MODEL + a live `/api/tags` ping)
  → OpenRouter `:free` → none.
- `apply_cost_mode` sets `WEB_SEARCH_BACKEND=duckduckgo` and no longer skips `web_search`.

`FREE_MODE_STRICT=1` (set by `apply_cost_mode`) arms the never-pay guards at the paid seams:

- `core/tts.py::generate_audio` — raises instead of the ElevenLabs fallback.
- `core/llm_router.py::_resolve_chain` — filters the chain to `ollama` / OpenRouter `:free`
  only; when the sole free provider is rate-limited it retries briefly, then raises a
  catchable `LLMUnavailableError` (the flow degrades instead of crashing).
- `apis/apify_client.py::run_actor` — refuses a paid actor run (like the breaker).

Verify a run was actually $0 via the end-of-run line: `Est. run cost: $0.0000`
(`core/cost_meter.py`).
