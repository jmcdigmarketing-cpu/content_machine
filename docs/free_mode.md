# Free ($0) mode

`py main.py` asks you to pick a **cost mode** before a render:

```
  Cost mode
  1) Standard  - best quality (may use paid providers)
  2) Free ($0) - local voice + free models only, no paid calls
  Free ready:  voice=piper OK   llm=openrouter OK   signals=free OK
```

**Free mode pins every cost center to its zero-cost backend for the whole run:**

| Cost center | Free-mode backend |
|---|---|
| Voice (TTS) | local **Piper** (or Kokoro/XTTS) — `$0` |
| LLM (script/facts) | **OpenRouter `:free`** models, or local **Ollama** |
| reddit + youtube_competitors | `SIGNAL_BACKEND=free` (Reddit OAuth + yt-dlp) |
| twitter / tiktok_trends / web_search | **skipped** (no free backend) |
| assets / thumbnails | already local / Pexels / Pixabay (free) |

**It is strict.** Free mode never falls back to a paid provider. If a required $0
backend is missing it **blocks** with setup guidance rather than quietly spending
money — e.g. no local voice ⇒ the render stops instead of calling paid ElevenLabs.
The `Free ready:` line tells you up front which backends are installed.

Headless: `RUN_COST_MODE=free py main.py` selects Free without the prompt.

---

## One-time setup (so Free mode is genuinely $0, including voice)

All commands are Windows/PowerShell (see [startup-powershell.md](startup-powershell.md)).

### 1. Local voice — Piper (required for $0 voiceover)

Piper is CPU/ONNX, no GPU or torch, MIT-licensed. It's already in the `providers`
optional extra.

```powershell
pip install -e ".[providers]"      # or: pip install piper-tts soundfile
```

Download one voice model (an `.onnx` + its `.onnx.json`) from the Piper releases —
`en_US-lessac-medium` is a good default — then point the env at the `.onnx` file:

```powershell
# in .env
PIPER_VOICE=C:\voices\en_US-lessac-medium.onnx
```

Free mode sets `TTS_PROVIDER=piper` for you once `PIPER_VOICE` exists. Verify:

```powershell
py -c "import os; os.environ['TTS_PROVIDER']='piper'; from core.tts import is_local_tts_provider; print(is_local_tts_provider())"   # True
```

> No local voice yet? Free mode still runs discovery + scripting, but **blocks at
> render** with the install reminder. Standard mode is unaffected (uses ElevenLabs).

### 2. Free LLM — OpenRouter (easiest) or Ollama

**OpenRouter** (free `:free` models, hosted): create a key at openrouter.ai, then:

```powershell
# in .env
OPENROUTER_API_KEY=sk-or-...
```

Free mode pins all three tiers to `meta-llama/llama-3.3-70b-instruct:free`
(override per tier with `OPENROUTER_MODEL_CHEAP/EXTRACT/PREMIUM`). Free `:free`
models are rate-limited — fine for this volume.

**Ollama** (fully local): install Ollama, pull a model, then set `OLLAMA_MODEL`:

```powershell
ollama pull llama3.1
# in .env
OLLAMA_MODEL=llama3.1
```

Readiness prefers OpenRouter when both are present. If neither is configured, Free
mode blocks (the LLM is required for both discovery and the script).

### 3. Free signals (optional — improves discovery quality)

- **yt-dlp** (YouTube competitors) is a core dependency — already available, keyless.
- **Reddit** free backend needs a free "script app" (create at
  reddit.com/prefs/apps, ~2 min, 100 req/min):

```powershell
# in .env
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
```

The paid-only signals (`twitter`, `tiktok_trends`, `web_search`) have no free
backend, so Free mode skips them — discovery still runs on the free signals.

---

## How it works (for maintainers)

`core/run_mode.py` is the whole feature. `prompt_cost_mode()` (in `core/ui.py`)
picks the mode; `apply_cost_mode("free")` mutates `os.environ` once at startup
(`main.py::_apply_cost_mode_interactive`). Because every knob is read at call-time,
that env update propagates to all subsystems — the one exception,
`register_signals`, was made per-call (`_skip_signals()`).

`FREE_MODE_STRICT=1` (set by `apply_cost_mode`) arms the never-pay guards at the
three paid seams:

- `core/tts.py::generate_audio` — raises instead of the ElevenLabs fallback.
- `core/llm_router.py::_resolve_chain` — filters the chain to `ollama` / OpenRouter
  `:free` only; raises if none remain (no OpenAI fallback).
- `apis/apify_client.py::run_actor` — refuses a paid actor run (like the breaker).

Verify a run was actually $0 via the end-of-run line: `Est. run cost: $0.0000`
(`core/cost_meter.py`).
