"""Run-level cost mode — pick Standard (paid providers allowed) or Free ($0) at start.

Free mode pins every cost center to its zero-cost backend for the whole run and,
in *strict* mode, guarantees no paid provider is ever called. The guards live at
the paid seams (core/tts.py, core/llm_router.py, apis/apify_client.py): if a
required $0 backend is missing, Free mode BLOCKS (raises a clear error at the seam)
rather than silently falling back to paid ElevenLabs / DeepSeek / OpenAI / Apify.
See docs/free_mode.md for the one-time local-backend setup.

Every knob here is a plain env var read at call-time by its subsystem, so applying
a mode is just a coordinated ``os.environ`` update done once at startup:

    TTS_PROVIDER=<local>            -> $0 voice (core/tts.py)
    LLM_{CHEAP,EXTRACT,PREMIUM}_*  -> free LLM tier (core/llm_router.py)
    SIGNAL_BACKEND=free             -> free reddit + youtube_competitors
    CONTENT_SKIP_SIGNALS+=…         -> skip the paid signals with no free backend
    FREE_MODE_STRICT=1              -> arms the never-pay guards at each seam
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field

COST_MODE_STANDARD = "standard"
COST_MODE_FREE = "free"

# Paid signals with no free backend — skipped entirely in Free mode. (web_search
# now has a keyless DuckDuckGo backend, so it is NOT skipped.)
_PAID_NO_FREE_BACKEND = ("twitter", "tiktok_trends")

# OpenRouter free (`:free`) model — the CLOUD fallback used only when local Ollama
# isn't running. Free but rate-limited; override with OPENROUTER_MODEL_<TIER>.
_OPENROUTER_FREE_MODEL = "meta-llama/llama-3.3-70b-instruct:free"

# Truly-free (keyless) web-search backend wired in Free mode — see apis/web_search_api.
_FREE_WEB_SEARCH_BACKEND = "duckduckgo"

# Local (zero-cost) TTS providers, best first. Each needs its backend installed
# and (piper/xtts) a voice model configured — mirrors core/tts.py._ALT_TTS.
_LOCAL_TTS_ORDER = ("piper", "kokoro", "xtts")


def resolve_cost_mode() -> str:
    """Non-interactive default from RUN_COST_MODE (standard unless =free)."""
    return (
        COST_MODE_FREE
        if os.getenv("RUN_COST_MODE", "").strip().lower() == "free"
        else COST_MODE_STANDARD
    )


def free_mode_strict() -> bool:
    """True when the never-pay guards are armed (set by Free mode)."""
    return os.getenv("FREE_MODE_STRICT", "").strip().lower() in ("1", "true", "yes")


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def _local_tts_available() -> str | None:
    """First local TTS provider whose backend AND voice model are ready, else None."""
    for provider in _LOCAL_TTS_ORDER:
        if provider == "piper" and _module_available("piper"):
            voice = os.getenv("PIPER_VOICE", "").strip()
            if voice and os.path.isfile(voice):
                return "piper"
        elif provider == "kokoro" and _module_available("kokoro"):
            return "kokoro"  # ships a default voice (KOKORO_VOICE optional)
        elif (
            provider == "xtts"
            and _module_available("TTS")
            and os.getenv("XTTS_SPEAKER_WAV", "").strip()
        ):
            return "xtts"
    return None


def _ollama_ready() -> tuple[bool, str]:
    """(reachable, model) — local Ollama is truly free only if a model is set AND the
    server answers. A quick /api/tags ping keeps readiness honest (don't route to a
    down server, then crash). Never raises."""
    model = os.getenv("OLLAMA_MODEL", "").strip()
    if not model:
        return False, ""
    base = os.getenv("OLLAMA_BASE_URL", "").strip() or "http://localhost:11434/v1"
    root = base.rsplit("/v1", 1)[0].rstrip("/")
    try:
        import requests  # type: ignore[import-untyped]

        resp = requests.get(f"{root}/api/tags", timeout=2)
        return resp.status_code == 200, model
    except Exception:
        return False, model


def _openrouter_free_model() -> str:
    """The cheap-tier OpenRouter model the router would actually use.

    Single source of truth: reads the router's default (which already honors
    OPENROUTER_MODEL_CHEAP) rather than keeping a second copy of the slug here — a stale
    duplicate is exactly how readiness ends up advertising a retired model.
    """
    try:
        from core.llm_router import _default_model

        return _default_model("openrouter", "cheap") or _OPENROUTER_FREE_MODEL
    except Exception:
        return _OPENROUTER_FREE_MODEL


def _model_known_dead(provider: str, model: str) -> bool:
    """True when this session already saw the provider reject that model (404)."""
    try:
        from core.llm_router import _model_is_dead

        return _model_is_dead(provider, model)
    except Exception:
        return False


def _free_llm() -> tuple[str | None, str, str]:
    """Truly-free LLM (provider, model, blocked_reason), LOCAL-FIRST: local Ollama
    (unlimited, offline, $0) > OpenRouter `:free` (cloud, rate-limited) > none. A truly-
    free run should use the unlimited local model, not the throttled cloud one.

    A key being present is NOT proof the free model works — if the router already hit
    404 on that slug this session we report it blocked instead of claiming OK.
    """
    ready, model = _ollama_ready()
    if ready:
        return "ollama", model, ""
    if os.getenv("OPENROUTER_API_KEY", "").strip():
        free_model = _openrouter_free_model()
        if _model_known_dead("openrouter", free_model):
            return None, "", "openrouter free model retired - set OPENROUTER_MODEL_CHEAP"
        return "openrouter", free_model, ""
    return None, "", "run Ollama or set OPENROUTER_API_KEY"


@dataclass
class Readiness:
    """What free ($0) backends are actually available on this machine right now."""

    tts_provider: str | None  # local $0 TTS provider ready, else None
    llm_provider: str | None  # free LLM provider ready, else None
    llm_model: str = ""
    llm_local: bool = False  # True when the LLM is a local (truly-free, unlimited) backend
    llm_note: str = ""  # why no free LLM is available (shown instead of a bare "X")
    reddit_free: bool = False
    youtube_free: bool = False

    @property
    def voice_ok(self) -> bool:
        return self.tts_provider is not None

    @property
    def llm_ok(self) -> bool:
        return self.llm_provider is not None


def free_backend_readiness() -> Readiness:
    """Probe (never mutates env) which $0 backends are ready for Free mode."""
    from apis.free_backends import reddit_available, youtube_available

    llm_provider, llm_model, llm_note = _free_llm()
    return Readiness(
        tts_provider=_local_tts_available(),
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_local=(llm_provider == "ollama"),
        llm_note=llm_note,
        reddit_free=reddit_available(),
        youtube_free=youtube_available(),
    )


@dataclass
class ApplyResult:
    """Outcome of apply_cost_mode: env keys set + any missing $0 backends (blockers)."""

    mode: str
    applied: dict[str, str] = field(default_factory=dict)
    blockers: list[str] = field(default_factory=list)

    @property
    def can_render(self) -> bool:
        """A render needs $0 voice AND a free LLM; signals degrade gracefully."""
        return not any(b.startswith(("voice:", "llm:")) for b in self.blockers)


def _merge_skip(existing: str) -> str:
    have = [s.strip() for s in existing.split(",") if s.strip()]
    for name in _PAID_NO_FREE_BACKEND:
        if name not in have:
            have.append(name)
    return ",".join(have)


def apply_cost_mode(mode: str, *, readiness: Readiness | None = None) -> ApplyResult:
    """Apply a cost mode to os.environ. Standard is a no-op; Free pins every cost
    center to $0 and arms the strict never-pay guards. Missing $0 backends are
    recorded as blockers (and are NOT papered over with a paid provider)."""
    mode = (mode or "").strip().lower()
    if mode != COST_MODE_FREE:
        return ApplyResult(mode=COST_MODE_STANDARD)

    r = readiness or free_backend_readiness()
    result = ApplyResult(mode=COST_MODE_FREE)

    def _set(key: str, value: str) -> None:
        os.environ[key] = value
        result.applied[key] = value

    # Arm the never-pay guards first, so even a partial apply can't hit a paid seam.
    _set("FREE_MODE_STRICT", "1")

    # TTS — local $0 voice, or block (never set a paid provider).
    if r.tts_provider:
        _set("TTS_PROVIDER", r.tts_provider)
    else:
        result.blockers.append(
            "voice: no local TTS ready - install Piper + set PIPER_VOICE (docs/free_mode.md)"
        )

    # LLM — pin all tiers to the free provider/model, or block.
    if r.llm_provider:
        for tier in ("CHEAP", "EXTRACT", "PREMIUM"):
            _set(f"LLM_{tier}_PROVIDER", r.llm_provider)
            if r.llm_model:
                _set(f"LLM_{tier}_MODEL", r.llm_model)
    else:
        result.blockers.append(
            "llm: no free model ready - run Ollama (OLLAMA_MODEL) or set OPENROUTER_API_KEY "
            "(docs/free_mode.md)"
        )

    # Signals — free backends for reddit + youtube_competitors, keyless DuckDuckGo for
    # web search; skip only the paid signals that have no free backend.
    _set("SIGNAL_BACKEND", "free")
    _set("WEB_SEARCH_BACKEND", _FREE_WEB_SEARCH_BACKEND)
    _set("CONTENT_SKIP_SIGNALS", _merge_skip(os.getenv("CONTENT_SKIP_SIGNALS", "")))

    return result


def format_readiness_line(r: Readiness | None = None) -> str:
    """One cp1252-safe line summarizing Free-mode readiness for the startup prompt."""
    r = r or free_backend_readiness()
    voice = f"voice={r.tts_provider} OK" if r.voice_ok else "voice=X (install Piper)"
    if not r.llm_ok:
        llm = f"llm=X ({r.llm_note or 'run Ollama or set OPENROUTER_API_KEY'})"
    elif r.llm_local:
        llm = f"llm={r.llm_provider} OK (local $0)"
    else:
        llm = f"llm={r.llm_provider} OK (free, throttled)"
    # Report what was actually probed — reddit_free/youtube_free are real checks, so
    # don't print a blanket "signals=free" that outlives the thing it claims.
    free_signals = [
        name for name, ok in (("reddit", r.reddit_free), ("youtube", r.youtube_free)) if ok
    ]
    signals = f"signals={'+'.join(free_signals)}" if free_signals else "signals=X (none free)"
    return f"Free ready:  {voice}   {llm}   web={_FREE_WEB_SEARCH_BACKEND}   {signals}"
