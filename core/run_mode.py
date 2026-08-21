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

from core.logging import get_logger

logger = get_logger("core.run_mode")

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
# and (piper/xtts/qwen) a voice model configured — mirrors core/tts.py._ALT_TTS.
# Qwen is included only when qwen_tts + a voice are actually ready (not merely imported).
_LOCAL_TTS_ORDER = ("piper", "kokoro", "xtts", "qwen")


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


def _tts_provider_ready(provider: str) -> bool:
    """True when this local TTS backend can actually synth — no model load, no GPU probe.

    Reachable-is-not-usable (decisions §18): a module on sys.path is not enough for
    piper/xtts/qwen; they need a configured voice (file on disk for paths, name for
    speakers). Kokoro ships a default voice so the module is the bar.
    """
    provider = (provider or "").strip().lower()
    if provider == "piper":
        if not _module_available("piper"):
            return False
        voice = os.getenv("PIPER_VOICE", "").strip()
        return bool(voice and os.path.isfile(voice))
    if provider == "kokoro":
        return _module_available("kokoro")
    if provider == "xtts":
        return bool(_module_available("TTS") and os.getenv("XTTS_SPEAKER_WAV", "").strip())
    if provider == "qwen":
        if not _module_available("qwen_tts"):
            return False
        voice = os.getenv("QWEN_VOICE", "").strip()
        if not voice:
            pool = [v.strip() for v in os.getenv("QWEN_VOICES", "").split(",") if v.strip()]
            voice = pool[0] if pool else ""
        if not voice:
            return False
        if voice.lower().endswith((".wav", ".mp3", ".flac")):
            return os.path.isfile(voice)
        return True  # built-in speaker name — don't load the 1.7B model to check
    return False


def _local_tts_available() -> str | None:
    """First local TTS provider whose backend AND voice model are ready, else None."""
    for provider in _LOCAL_TTS_ORDER:
        if _tts_provider_ready(provider):
            return provider
    return None


def _ollama_model_pulled(model: str) -> bool:
    """True when `model` is among the tags the local Ollama daemon actually serves."""
    if not (model or "").strip():
        return False
    try:
        from core.llm_router import ollama_installed_models

        installed = ollama_installed_models()
    except Exception:
        return False
    wanted = model.strip()
    return any(m == wanted or m.split(":")[0] == wanted.split(":")[0] for m in installed)


def _ollama_ready() -> tuple[bool, str]:
    """(usable, model) — Ollama is truly free only if the configured model is PULLED.

    This used to return `status_code == 200` from `/api/tags`, i.e. "the daemon
    answered". On a box with Ollama running and nothing pulled that reported
    `llm=ollama OK (local $0)`, Free mode pinned the premium tier to it, and live run 70
    died 71 seconds later on `404 model 'llama3.1:8b' not found` — after a full
    discovery. Reachable is not usable (decisions §18).

    `core.llm_router` already had this right, so this delegates rather than keeping a
    second, weaker copy of the same probe: the router's list is the single source of
    truth for what Ollama can actually serve, and it caches the localhost call.
    """
    model = os.getenv("OLLAMA_MODEL", "").strip()
    if not model:
        return False, ""
    return _ollama_model_pulled(model), model


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
    if os.getenv("OLLAMA_MODEL", "").strip():
        # The model is configured but not pulled — say so, since "run Ollama" would be
        # wrong advice when the daemon is already up.
        return None, "", "ollama has no model pulled - run: ollama pull $OLLAMA_MODEL"
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


class CostModeBlocked(RuntimeError):
    """Free mode is missing a $0 backend — callers must not start discovery."""


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

    @property
    def blocked(self) -> bool:
        """True when Free mode was requested but cannot actually run."""
        return self.mode == COST_MODE_FREE and not self.can_render


def abort_if_blocked(result: ApplyResult) -> None:
    """Raise CostModeBlocked when Free mode cannot proceed. Standard is a no-op.

    Live run 70 already taught us not to *advertise* a dead Ollama. This stops the
    next step: do not spend discovery (or an overnight batch) after the operator
    picked Free and the $0 backends are missing.
    """
    if not result.blocked:
        return
    detail = "; ".join(result.blockers) or "Free mode backends not ready"
    raise CostModeBlocked(
        f"{detail}. Free mode can't continue until this is resolved (docs/free_mode.md)."
    )


def apply_and_guard(mode: str | None = None, *, readiness: Readiness | None = None) -> ApplyResult:
    """Apply a cost mode (default ``RUN_COST_MODE``) and abort if Free cannot proceed.

    After pinning env, also verifies the *first* LLM/TTS call would actually hit a
    usable backend (run 70: apply trusted a stale Readiness, then Ollama 404'd).
    """
    result = apply_cost_mode(mode or resolve_cost_mode(), readiness=readiness)
    abort_if_blocked(result)
    abort_if_first_call_unusable(result)
    return result


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


@dataclass
class FirstCallCheck:
    """What the first LLM/TTS call would actually hit, given current env.

    Distinct from Readiness (probe) and ApplyResult (env pins): this is the
    *completion* check — resolve_tier / TTS_PROVIDER after apply, including the
    forced-provider hole where ``_resolve_chain`` skips ``_provider_available``.
    """

    llm_by_tier: dict[str, tuple[str, str]] = field(default_factory=dict)
    tts_provider: str = ""
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def inspect_first_calls() -> FirstCallCheck:
    """Inspect the first LLM/TTS call without making a paid API request.

    Ollama is the cached localhost tags probe (same SoT as the router). Standard
    only warns for a pinned-but-unpulled Ollama or a local TTS env that isn't
    ready — it does not warn that OpenAI would be used when that's the normal
    chain. Free fail-closes when a first call would 404 or hit a paid seam.
    """
    check = FirstCallCheck()
    check.tts_provider = (os.getenv("TTS_PROVIDER") or "elevenlabs").strip().lower() or "elevenlabs"
    strict = free_mode_strict()

    if strict and check.tts_provider in ("", "elevenlabs"):
        # Apply failed to pin a local voice — first synth would pay ElevenLabs.
        check.blockers.append("tts: first call would hit paid ElevenLabs")
    elif (
        not strict
        and check.tts_provider not in ("", "elevenlabs")
        and not _tts_provider_ready(check.tts_provider)
    ):
        check.warnings.append(
            f"TTS_PROVIDER={check.tts_provider} is set but that backend is not ready"
        )

    try:
        from core.llm_router import _is_free_llm, _model_is_dead, resolve_tier
    except Exception as exc:
        msg = f"llm: router unavailable ({exc})"
        if strict:
            check.blockers.append(msg)
        return check

    for tier in ("cheap", "extract", "premium"):
        try:
            provider, model = resolve_tier(tier)
        except RuntimeError as exc:
            if strict:
                check.blockers.append(f"llm {tier}: {exc}")
            continue
        check.llm_by_tier[tier] = (provider, model)
        if provider == "ollama" and not _ollama_model_pulled(model):
            msg = (
                f"llm {tier}: first call would hit ollama {model!r} which is not pulled "
                f"(ollama pull {model})"
            )
            if strict:
                check.blockers.append(msg)
            else:
                check.warnings.append(msg)
        elif strict and not _is_free_llm(provider, model):
            check.blockers.append(f"llm {tier}: first call would hit paid {provider}/{model}")
        elif strict and provider == "openrouter" and _model_is_dead(provider, model):
            check.blockers.append(
                f"llm {tier}: openrouter model {model!r} is retired — "
                f"set OPENROUTER_MODEL_{tier.upper()}"
            )

    return check


def abort_if_first_call_unusable(result: ApplyResult | None = None) -> None:
    """Fail closed in Free when the first LLM/TTS call is not actually usable."""
    if result is not None and result.mode != COST_MODE_FREE and not free_mode_strict():
        return
    if result is None and not free_mode_strict():
        return
    check = inspect_first_calls()
    if not check.blockers:
        return
    detail = "; ".join(check.blockers)
    raise CostModeBlocked(
        f"{detail}. Free mode can't continue until this is resolved (docs/free_mode.md)."
    )


def guard_before_discovery() -> list[str]:
    """Choke point before discovery: Free fail-closed, Standard may warn.

    Only raises when ``FREE_MODE_STRICT`` is on (set by apply_cost_mode) so a
    leftover RUN_COST_MODE in the operator .env cannot abort unit tests.
    Returns Standard-mode warnings for the CLI to print.
    """
    check = inspect_first_calls()
    if free_mode_strict() and check.blockers:
        detail = "; ".join(check.blockers)
        raise CostModeBlocked(f"{detail}. Stopping before discovery (docs/free_mode.md).")
    for warning in check.warnings:
        logger.warning("%s", warning)
    return check.warnings


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
