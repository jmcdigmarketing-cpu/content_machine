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
Install the local extras once: `pip install -e ".[providers]"` (Piper, ddgs, etc.).

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
