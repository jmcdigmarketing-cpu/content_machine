"""WhisperX word-level alignment seam (Pillar 6) — OFF by default, fail-open.

Local word timing for *any* TTS (or clip-from-source), for when ElevenLabs timestamps
aren't available (e.g. a local TTS provider from `core/tts.py`). The real backend
(`whisperx` + torch) is an optional extra — install with `pip install -e ".[providers]"`.
Unselected or uninstalled ⇒ `ProviderResult.fail_open`, so callers keep the current
proportional/ElevenLabs caption path (`video/caption_timing.py`).

    CAPTION_ALIGN_BACKEND=whisperx     # default: none

Wire point (documented, not activated): in `video/caption_timing.py`, call
`transcribe_and_align(audio)` when `words_from_alignment(...)` yields nothing.
"""

from __future__ import annotations

from core.logging import get_logger
from core.providers import (
    STATUS_ERROR,
    STATUS_NOT_CONFIGURED,
    ProviderResult,
    selected_provider,
)

logger = get_logger("core.caption_align")

SLOT = "caption_align"


def transcribe_and_align(audio_path: str, *, device: str = "cpu") -> ProviderResult:
    """Return per-word `{start, end, word}` segments, or fail-open when unavailable."""
    backend = selected_provider("CAPTION_ALIGN_BACKEND", "none")
    if backend in ("", "none"):
        return ProviderResult.fail_open(
            SLOT, "CAPTION_ALIGN_BACKEND unset", status=STATUS_NOT_CONFIGURED
        )
    if backend != "whisperx":
        return ProviderResult.fail_open(
            SLOT, f"unknown backend {backend!r}", status=STATUS_NOT_CONFIGURED
        )
    try:
        import whisperx  # optional extra (torch) — never imported unless selected
    except Exception as exc:
        return ProviderResult.fail_open(
            SLOT, f"whisperx not installed: {exc}", status=STATUS_NOT_CONFIGURED
        )
    try:
        model = whisperx.load_model("small", device, compute_type="int8")
        result = model.transcribe(audio_path, batch_size=8)
        align_model, metadata = whisperx.load_align_model(
            language_code=result["language"], device=device
        )
        aligned = whisperx.align(result["segments"], align_model, metadata, audio_path, device)
        return ProviderResult.success(SLOT, "whisperx", data=aligned.get("word_segments", []))
    except Exception as exc:
        logger.warning("whisperx alignment failed for %s: %s", audio_path, exc)
        return ProviderResult.fail_open(SLOT, str(exc), status=STATUS_ERROR)
