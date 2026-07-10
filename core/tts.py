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


def _kokoro_synth(script: str, output_path: str, channel_id: str | None) -> str | None:
    """Local Kokoro-82M TTS (optional extra: kokoro, soundfile). Returns a .wav path."""
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    pipeline = KPipeline(lang_code=os.getenv("KOKORO_LANG", "a"))
    voice = os.getenv("KOKORO_VOICE", "af_heart")
    chunks = [audio for _, _, audio in pipeline(script, voice=voice)]
    if not chunks:
        return None
    wav_path = os.path.splitext(output_path)[0] + ".wav"
    sf.write(wav_path, np.concatenate(chunks), 24000)
    return wav_path


def _xtts_synth(script: str, output_path: str, channel_id: str | None) -> str | None:
    """Local XTTS-v2 voice clone (optional extra: TTS). Needs XTTS_SPEAKER_WAV set."""
    from TTS.api import TTS

    speaker = os.getenv("XTTS_SPEAKER_WAV")
    if not speaker:
        return None
    wav_path = os.path.splitext(output_path)[0] + ".wav"
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    tts.tts_to_file(
        text=script, speaker_wav=speaker, language=os.getenv("XTTS_LANG", "en"), file_path=wav_path
    )
    return wav_path


_ALT_TTS = {"kokoro": _kokoro_synth, "xtts": _xtts_synth}


def _try_alt_tts_provider(script: str, output_path: str, channel_id: str | None) -> str | None:
    """Try a non-ElevenLabs TTS provider; return a path on success, else None (fall back).

    Baseline seam: local providers write a `.wav` sidecar and return it — wiring the
    render to accept/transcode that path is the follow-up. No-op (returns None) unless
    `TTS_PROVIDER` selects a known local provider.
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
        print(f"[TTS] Channel: {channel_id} | Provider: {provider} (local)")
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
