import os
import random

from elevenlabs.client import ElevenLabs

from config.channels import get_channel_profile, resolve_channel_id
from core.utils import clean_script_for_tts

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
    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        model_id=model_id,
        text=script,
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in audio:
            f.write(chunk)

    print(f"[TTS] Channel: {channel_id} | Voice: {voice_id} | Model: {model_id}")
    return output_path
