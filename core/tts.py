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
    eleven_key = os.getenv("ELEVEN_API_KEY")
    if not eleven_key:
        raise Exception("ELEVEN_API_KEY not found.")

    script = clean_script_for_tts(script)
    channel_id = resolve_channel_id(channel_id)
    voice_id, model_id = resolve_tts_config(channel_id)

    client = ElevenLabs(api_key=eleven_key)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

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
