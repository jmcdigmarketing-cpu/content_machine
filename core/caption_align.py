"""Local word-level caption alignment (Pillar 6, U1) — OFF by default, fail-open.

Word timing for audio that has no ElevenLabs `.words.json` sidecar — i.e. a local TTS
provider (`core/tts.py`) or imported audio. Without it `video/subtitles.py` falls back
to *proportional* timing, which drifts out of sync with the speech; that is what has
made the $0 local-TTS path unusable, and TTS is ~88% of a rendered run's cost.

    CAPTION_ALIGN_BACKEND=faster_whisper   # CPU-friendly (default choice)
    CAPTION_ALIGN_BACKEND=whisperx         # adds a wav2vec2 alignment pass
    CAPTION_ALIGN_MODEL=tiny               # tiny | base | small | medium | large-v3
    CAPTION_ALIGN_DEVICE=auto              # auto -> cuda when available, else cpu
    CAPTION_ALIGN_COMPUTE=int8             # int8 on CPU, float16 on GPU

**Backend choice.** `faster_whisper` returns word timestamps directly from Whisper's
decoder, so it needs no second alignment model; it is CTranslate2-based and built for
CPU inference. `whisperx` adds a wav2vec2 forced-alignment pass, which is more accurate
in principle but roughly doubles the model footprint and is slow without a GPU. Both are
offered; faster_whisper is the one to reach for on a CPU box.

Models download on first use (~75MB tiny, ~145MB base, ~480MB small) and are cached by
the backend thereafter.

**This returns ASR text — treat it as timing, not as caption copy.** Transcribing blind
misspells exactly the words this channel is about: run 65 came back with "Salkal" for
"Salkilld" and "Mattius Gamarat" for "Mateusz Gamrot". The timings are good (~45ms); the
words are not. `video/caption_retext.py` closes that gap by keeping these timings and
taking the text from the known script, so captions are spelled by the script and timed
by whisper. Anything consuming this module directly (a bench, Phase R clip-from-source)
must do the same, or accept mangled proper nouns.

Wired: `video/subtitles.py::generate_subtitle_file` calls this via
`video/caption_timing.words_from_caption_align` when no ElevenLabs sidecar exists for
the audio, then retexts the result against the script. Unselected, uninstalled or
failing ⇒ `ProviderResult.fail_open`, so callers keep the proportional caption path.
Never raises.
"""

from __future__ import annotations

import os
from typing import Any

from core.logging import get_logger
from core.providers import (
    STATUS_ERROR,
    STATUS_NOT_CONFIGURED,
    ProviderResult,
    selected_provider,
)

logger = get_logger("core.caption_align")

SLOT = "caption_align"

_BACKENDS = ("faster_whisper", "whisperx")
# #771 (operator, 2026-09-17): on by default. After #775 one Short in six is piper, and piper
# leaves no word timings - those captions drifted on the proportional estimate. The model
# stays `tiny` (align_model's measured default). CAPTION_ALIGN_BACKEND=none switches it off.
DEFAULT_BACKEND = "faster_whisper"


def align_backend() -> str:
    """The configured alignment backend; `none` means off."""
    return selected_provider("CAPTION_ALIGN_BACKEND", DEFAULT_BACKEND)


def align_model() -> str:
    """Whisper model size.

    `tiny` by default, chosen from measurement rather than instinct. Benchmarked against
    ElevenLabs' own word timings on three real 55-58s channel shorts
    (`scripts/bench_caption_align.py`), `tiny` beat `base` on typical caption-line start
    error (**43-56ms** median vs 73-85ms) at 12-15x realtime on CPU, while being half
    the download. The audio here is clean synthetic speech — the easiest case for ASR —
    so the larger models buy nothing and mostly re-segment differently.

    Raise this for noisy or accented source audio (e.g. Phase R clip-from-source), where
    the picture will look very different.
    """
    return (os.getenv("CAPTION_ALIGN_MODEL", "tiny") or "tiny").strip()


def align_device() -> str:
    """`cuda` when a GPU is actually present, else `cpu`. Explicit env wins."""
    configured = (os.getenv("CAPTION_ALIGN_DEVICE", "auto") or "auto").strip().lower()
    if configured and configured != "auto":
        return configured
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def align_compute_type(device: str | None = None) -> str:
    """int8 on CPU (the only sane choice), float16 on GPU. Explicit env wins."""
    configured = (os.getenv("CAPTION_ALIGN_COMPUTE", "") or "").strip()
    if configured:
        return configured
    return "float16" if (device or align_device()) == "cuda" else "int8"


def _words_from_faster_whisper(audio_path: str, device: str) -> list[dict[str, Any]]:
    from faster_whisper import WhisperModel

    model = WhisperModel(
        align_model(),
        device=device,
        compute_type=align_compute_type(device),
    )
    segments, _info = model.transcribe(audio_path, word_timestamps=True, vad_filter=True)
    words: list[dict[str, Any]] = []
    for segment in segments:  # generator — consuming it is what runs the transcription
        for word in getattr(segment, "words", None) or []:
            text = str(getattr(word, "word", "") or "").strip()
            if not text:
                continue
            words.append(
                {
                    "word": text,
                    "start": getattr(word, "start", None),
                    "end": getattr(word, "end", None),
                }
            )
    return words


def _words_from_whisperx(audio_path: str, device: str) -> list[dict[str, Any]]:
    import whisperx

    model = whisperx.load_model(align_model(), device, compute_type=align_compute_type(device))
    result = model.transcribe(audio_path, batch_size=8)
    align_model_obj, metadata = whisperx.load_align_model(
        language_code=result["language"], device=device
    )
    aligned = whisperx.align(result["segments"], align_model_obj, metadata, audio_path, device)
    return list(aligned.get("word_segments") or [])


def transcribe_and_align(audio_path: str, *, device: str | None = None) -> ProviderResult:
    """Return per-word `{start, end, word}` segments, or fail-open when unavailable."""
    backend = align_backend()
    if backend in ("", "none"):
        return ProviderResult.fail_open(
            SLOT, "CAPTION_ALIGN_BACKEND unset", status=STATUS_NOT_CONFIGURED
        )
    if backend not in _BACKENDS:
        return ProviderResult.fail_open(
            SLOT,
            f"unknown backend {backend!r} (expected one of {', '.join(_BACKENDS)})",
            status=STATUS_NOT_CONFIGURED,
        )
    if not audio_path or not os.path.exists(audio_path):
        return ProviderResult.fail_open(
            SLOT, f"audio not found: {audio_path!r}", status=STATUS_NOT_CONFIGURED
        )

    try:
        from core.ram_preflight import block_reason as ram_block

        why = ram_block(kind="whisper")
    except Exception as exc:
        logger.debug("ram preflight skipped: %s", exc)
        why = None
    if why:
        return ProviderResult.fail_open(SLOT, why, status=STATUS_NOT_CONFIGURED)

    resolved_device = device or align_device()
    runner = _words_from_faster_whisper if backend == "faster_whisper" else _words_from_whisperx
    try:
        words = runner(audio_path, resolved_device)
    except ImportError as exc:
        # Optional extra: `pip install -e ".[providers]"`.
        return ProviderResult.fail_open(
            SLOT, f"{backend} not installed: {exc}", status=STATUS_NOT_CONFIGURED
        )
    except Exception as exc:
        logger.warning("%s alignment failed for %s: %s", backend, audio_path, exc)
        return ProviderResult.fail_open(SLOT, str(exc), status=STATUS_ERROR)

    if not words:
        return ProviderResult.fail_open(SLOT, "no words returned", status=STATUS_ERROR)
    return ProviderResult.success(SLOT, backend, data=words)
