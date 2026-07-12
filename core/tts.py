import base64
import json
import os
import random

from elevenlabs.client import ElevenLabs

from config.channels import get_channel_profile, resolve_channel_id
from core.logging import get_logger
from core.utils import clean_script_for_tts
from video.caption_timing import words_from_alignment

logger = get_logger("core.tts")

VOICE_REGISTRY = {
    "primary_male": {
        "nPczCjzI2devNBz1zQrb": 4,
        "XjLkpWUlnhS8i7gGz3lZ": 3,
        "JBFqnCBsd6RMkjVDRZzb": 2,
    },
    "secondary_male": {
        "VR6AewLTigWG4xSOukaG": 1,
    },
    "female": {
        "r1KmysJdVYZjJCm4mL3b": 3,
        "cgSgspJ2msm6clMCkdW9": 2,
        "hA4zGnmTwX2NQiTRMt7o": 1,
    },
}

DEFAULT_MODEL = "eleven_multilingual_v2"


def weighted_random_voice(pool: dict[str, int] | None = None) -> str:
    source = pool or {}
    if not source:
        for category in VOICE_REGISTRY.values():
            for voice_id, weight in category.items():
                source[voice_id] = source.get(voice_id, 0) + weight

    choices = []
    for voice_id, weight in source.items():
        choices.extend([voice_id] * max(1, int(weight)))
    return random.choice(choices)


def resolve_tts_config(channel_id: str | None = None) -> tuple[str, str]:
    """Return (voice_id, model_id) for channel."""
    profile = get_channel_profile(channel_id)
    model_id = profile.tts_model_id or DEFAULT_MODEL

    if profile.tts_voice_id:
        return profile.tts_voice_id, model_id

    if profile.tts_voice_pool:
        return weighted_random_voice(profile.tts_voice_pool), model_id

    return weighted_random_voice(), model_id


def generate_audio(script, output_path, channel_id: str | None = None):
    channel_id = resolve_channel_id(channel_id)
    script = clean_script_for_tts(script)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Provider seam (Pillar 6): a non-ElevenLabs TTS_PROVIDER (local Kokoro/XTTS) is
    # tried first; on any failure it falls back to the ElevenLabs default below.
    alt = _try_alt_tts_provider(script, output_path, channel_id)
    if alt:
        return alt

    # Free mode (strict): local $0 voice failed/absent and paid ElevenLabs is
    # disallowed — block with install guidance instead of silently paying.
    if _free_mode_strict():
        raise RuntimeError(
            "Free mode ($0, strict): no local TTS produced audio and paid ElevenLabs "
            "is disallowed. Install a local voice - pip install piper-tts, set "
            "PIPER_VOICE=<voice.onnx> and TTS_PROVIDER=piper. See docs/free_mode.md."
        )

    eleven_key = os.getenv("ELEVEN_API_KEY")
    if not eleven_key:
        raise Exception("ELEVEN_API_KEY not found.")
    voice_id, model_id = resolve_tts_config(channel_id)

    client = ElevenLabs(api_key=eleven_key)

    # Word-level timestamps (free from the same TTS call) power accurate / karaoke
    # captions (video/caption_timing). Best-effort — any failure falls back to the
    # plain stream, so captions just revert to the proportional estimate.
    if _word_timestamps_enabled() and _save_word_timestamps(
        client, voice_id, model_id, script, output_path
    ):
        print(f"[TTS] Channel: {channel_id} | Voice: {voice_id} | Model: {model_id} | +timestamps")
        return output_path

    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        model_id=model_id,
        text=script,
    )
    with open(output_path, "wb") as f:
        for chunk in audio:
            f.write(chunk)

    print(f"[TTS] Channel: {channel_id} | Voice: {voice_id} | Model: {model_id}")
    return output_path


def _resolve_tts_provider() -> str:
    return (os.getenv("TTS_PROVIDER", "elevenlabs") or "elevenlabs").strip().lower()


def _free_mode_strict() -> bool:
    """Free-mode never-pay guard (set by core.run_mode.apply_cost_mode)."""
    return os.getenv("FREE_MODE_STRICT", "").strip().lower() in ("1", "true", "yes")


_LOCAL_TTS_PROVIDERS = ("kokoro", "xtts", "piper")


def is_local_tts_provider() -> bool:
    """True when TTS_PROVIDER selects a local (zero-marginal-cost) voice backend."""
    return _resolve_tts_provider() in _LOCAL_TTS_PROVIDERS


def _transcode_to_mp3(src_path: str, output_path: str) -> str | None:
    """Transcode a local-synth wav to the mp3 path the render pipeline expects.

    The pipeline ignores generate_audio's return and reads `mp3_path` directly
    (core/pipeline.py → video/render_video.py: AudioFileClip, subtitles, ffmpeg mux),
    so a local provider MUST leave a real mp3 at `output_path`. Fail-open → None on
    any ffmpeg failure (caller falls back to ElevenLabs); removes the temp wav.
    """
    import subprocess

    cmd = ["ffmpeg", "-y", "-i", src_path, "-codec:a", "libmp3lame", "-qscale:a", "4", output_path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except Exception as exc:
        logger.warning("TTS transcode failed to launch ffmpeg: %s", exc)
        return None
    if proc.returncode != 0 or not os.path.isfile(output_path):
        logger.warning(
            "TTS transcode failed (rc=%s): %s", proc.returncode, (proc.stderr or "")[-300:]
        )
        return None
    try:
        os.remove(src_path)
    except OSError:
        pass
    return output_path


def _tmp_wav_path(output_path: str) -> str:
    return os.path.splitext(output_path)[0] + ".tmp.wav"


def _kokoro_synth(script: str, output_path: str, channel_id: str | None) -> str | None:
    """Local Kokoro-82M TTS (optional extra: kokoro, soundfile; needs espeak-ng)."""
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    pipeline = KPipeline(lang_code=os.getenv("KOKORO_LANG", "a"))
    voice = os.getenv("KOKORO_VOICE", "af_heart")
    chunks = [audio for _, _, audio in pipeline(script, voice=voice)]
    if not chunks:
        return None
    wav_path = _tmp_wav_path(output_path)
    sf.write(wav_path, np.concatenate(chunks), 24000)
    return _transcode_to_mp3(wav_path, output_path)


def _xtts_synth(script: str, output_path: str, channel_id: str | None) -> str | None:
    """Local XTTS-v2 voice clone (optional extra: TTS). Needs XTTS_SPEAKER_WAV set."""
    from TTS.api import TTS

    speaker = os.getenv("XTTS_SPEAKER_WAV")
    if not speaker:
        return None
    wav_path = _tmp_wav_path(output_path)
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    tts.tts_to_file(
        text=script, speaker_wav=speaker, language=os.getenv("XTTS_LANG", "en"), file_path=wav_path
    )
    return _transcode_to_mp3(wav_path, output_path)


def _piper_synth(script: str, output_path: str, channel_id: str | None) -> str | None:
    """Local Piper TTS (optional extra: piper-tts) — CPU/ONNX, no torch, MIT.

    The Windows-box path: needs only `pip install piper-tts` plus a voice model
    (PIPER_VOICE=<path/to/voice.onnx>, e.g. en_US-lessac-medium from the Piper
    releases). Synthesizes to wav via the python API, then transcodes to the mp3.
    """
    import wave

    model = os.getenv("PIPER_VOICE", "").strip()
    if not model or not os.path.isfile(model):
        logger.warning("TTS_PROVIDER=piper needs PIPER_VOICE=<path/to/voice.onnx>")
        return None

    from piper import PiperVoice

    voice = PiperVoice.load(model)
    wav_path = _tmp_wav_path(output_path)
    with wave.open(wav_path, "wb") as wav_file:
        voice.synthesize(script, wav_file)
    return _transcode_to_mp3(wav_path, output_path)


_ALT_TTS = {"kokoro": _kokoro_synth, "xtts": _xtts_synth, "piper": _piper_synth}


def _try_alt_tts_provider(script: str, output_path: str, channel_id: str | None) -> str | None:
    """Try a non-ElevenLabs TTS provider; return the mp3 path on success, else None.

    Providers synth to a temp wav and transcode to `output_path` (the mp3 the render
    pipeline reads), so callers that ignore the return keep working. No-op (None ⇒
    ElevenLabs fallback) unless `TTS_PROVIDER` selects a known local provider; any
    provider failure also falls back — local voice can never break a render.
    """
    provider = _resolve_tts_provider()
    if provider in ("", "elevenlabs"):
        return None
    synth = _ALT_TTS.get(provider)
    if not synth:
        logger.warning("Unknown TTS_PROVIDER=%s — using ElevenLabs", provider)
        return None
    try:
        path = synth(script, output_path, channel_id)
    except Exception as exc:
        logger.warning("TTS provider %s failed (%s) — falling back to ElevenLabs", provider, exc)
        return None
    if path:
        print(f"[TTS] Channel: {channel_id} | Provider: {provider} (local, $0)")
    return path


def word_timing_path(audio_path: str) -> str:
    return audio_path + ".words.json"


def _word_timestamps_enabled() -> bool:
    return os.getenv("TTS_WORD_TIMESTAMPS", "true").lower() in ("1", "true", "yes")


def _save_word_timestamps(client, voice_id, model_id, script, output_path) -> bool:
    """Convert with character alignment, write the MP3 + a word-timing sidecar.

    Returns True on success; False (no files written for this path) on any error so
    the caller falls back to the plain stream.
    """
    try:
        result = client.text_to_speech.convert_with_timestamps(
            voice_id=voice_id,
            model_id=model_id,
            text=script,
        )
        audio_b64 = getattr(result, "audio_base_64", None) or getattr(result, "audio_base64", None)
        alignment = getattr(result, "alignment", None) or getattr(
            result, "normalized_alignment", None
        )
        if not audio_b64 or alignment is None:
            return False
        chars = getattr(alignment, "characters", None)
        starts = getattr(alignment, "character_start_times_seconds", None)
        ends = getattr(alignment, "character_end_times_seconds", None)
        if not (chars and starts and ends):
            return False

        with open(output_path, "wb") as f:
            f.write(base64.b64decode(audio_b64))
        words = words_from_alignment(list(chars), list(starts), list(ends))
        if words:
            with open(word_timing_path(output_path), "w", encoding="utf-8") as f:
                json.dump(words, f)
        return True
    except Exception as exc:
        logger.debug("word-timestamp TTS unavailable, using plain stream: %s", exc)
        return False
