"""#403 voice-consistency: intro/outro TTS family vs body TTS_PROVIDER."""

from __future__ import annotations

import os

_LOCAL = frozenset({"piper", "kokoro", "qwen", "xtts"})


def _family(raw: str) -> str:
    name = (raw or "").strip().lower()
    if name in _LOCAL:
        return "local"
    if name in ("", "elevenlabs"):
        return "elevenlabs"
    return name


def voice_mix_warning() -> str | None:
    """Warn once when intro/outro TTS is a different family than the body.

    Unset INTRO_TTS_PROVIDER / OUTRO_TTS_PROVIDER means the intro is a file clip,
    not a second TTS — a healthy TapIn run stays silent.
    """
    extra = (os.getenv("INTRO_TTS_PROVIDER") or os.getenv("OUTRO_TTS_PROVIDER") or "").strip()
    if not extra:
        return None
    body = _family(os.getenv("TTS_PROVIDER", "elevenlabs"))
    other = _family(extra)
    if body == other:
        return None
    return f"Voice mix: body TTS is {body}, intro/outro TTS is {other}"
