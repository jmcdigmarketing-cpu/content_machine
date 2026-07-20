import base64
import datetime
import hashlib
import json
import os
import random
from typing import Any

from elevenlabs.client import ElevenLabs

from config.channels import get_channel_profile, resolve_channel_id
from config.paths import VOICES_FILE
from core.logging import get_logger
from core.utils import clean_script_for_tts
from video.caption_timing import words_from_alignment

logger = get_logger("core.tts")

# Fallback catalog, used only when config/voices.json is missing or unusable. The
# operator-facing catalog lives in that file so adding a voice never needs a code change
# (discover ids with `py -m scripts.ops voices`).
_BUILTIN_VOICE_REGISTRY: dict[str, dict[str, int]] = {
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

# (mtime, parsed) — voices.json is re-read only when it changes.
_voice_catalog_cache: tuple[float, dict[str, Any]] | None = None


def _load_voice_catalog() -> dict[str, Any]:
    """Parsed config/voices.json, mtime-cached. Returns {} when missing or unreadable."""
    global _voice_catalog_cache
    try:
        mtime = os.path.getmtime(VOICES_FILE)
    except OSError:
        _voice_catalog_cache = None
        return {}
    if _voice_catalog_cache is not None and _voice_catalog_cache[0] == mtime:
        return _voice_catalog_cache[1]
    try:
        with open(VOICES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError) as exc:
        logger.warning("voices.json unreadable (%s) - using the built-in voice registry", exc)
        data = {}
    _voice_catalog_cache = (mtime, data)
    return data


def _entries_to_pool(entries: Any) -> dict[str, int]:
    """`[{"id": ..., "weight": n}, ...]` (or bare id strings) -> `{id: weight}`.

    Blank ids are skipped and weights floor at 1, so a half-filled catalog can't produce
    an unusable pool.
    """
    pool: dict[str, int] = {}
    if not isinstance(entries, list):
        return pool
    for entry in entries:
        if isinstance(entry, str):
            voice_id, weight = entry.strip(), 1
        elif isinstance(entry, dict):
            voice_id = str(entry.get("id") or "").strip()
            try:
                weight = int(entry.get("weight", 1))
            except (TypeError, ValueError):
                weight = 1
        else:
            continue
        if voice_id:
            pool[voice_id] = max(1, weight)
    return pool


def load_voice_registry() -> dict[str, dict[str, int]]:
    """ElevenLabs voices as `{category: {voice_id: weight}}` — config first, built-in last.

    Reads the `elevenlabs` block of config/voices.json. Falls back to
    `_BUILTIN_VOICE_REGISTRY` when the file is absent, malformed, or defines no usable
    voice, so behavior is identical to before when no catalog exists. Categories are only
    a grouping aid: an unpooled channel draws from all of them.
    """
    block = _load_voice_catalog().get("elevenlabs")
    if isinstance(block, dict):
        registry = {
            str(category): pool
            for category, entries in block.items()
            # A leading underscore parks a category (kept for reference, never used) —
            # e.g. ids the API rejects until they're added to the account's library.
            if not str(category).startswith("_") and (pool := _entries_to_pool(entries))
        }
        if registry:
            return registry
    return {name: dict(pool) for name, pool in _BUILTIN_VOICE_REGISTRY.items()}


def load_local_voice_pool(provider: str) -> dict[str, int]:
    """Local (free) voices for a provider as `{voice: weight}` from voices.json.

    Piper entries are `.onnx` paths, Kokoro entries are built-in voice names. Empty when
    the catalog has none, which drops resolution through to the env forms.
    """
    block = _load_voice_catalog().get("local")
    if not isinstance(block, dict):
        return {}
    return _entries_to_pool(block.get((provider or "").strip().lower()))


# Voice ids this account rejected this session (400 voice_not_found). Skipped when
# picking, so one stale id in a pool can't keep breaking renders.
_dead_voices: set[str] = set()


def _is_unusable_voice(exc: Exception) -> bool:
    """True when an error says the voice id itself is unusable (not a transient fault)."""
    text = str(exc).lower()
    return "voice_not_found" in text or "voice with id" in text


def _mark_voice_dead(voice_id: str, reason: object) -> None:
    if voice_id in _dead_voices:
        return
    _dead_voices.add(voice_id)
    logger.warning(
        "ElevenLabs voice '%s' is not on this account (%s) - skipping it this session. "
        "Add it from the ElevenLabs Voice Library, or remove it from config/voices.json.",
        voice_id,
        str(reason)[:160],
    )


def reset_dead_voices() -> None:
    """Test/CLI helper — forget voices marked unusable this session."""
    _dead_voices.clear()


def weighted_random_voice(pool: dict[str, int] | None = None) -> str:
    source = dict(pool or {})
    if not source:
        for category in load_voice_registry().values():
            for voice_id, weight in category.items():
                source[voice_id] = source.get(voice_id, 0) + weight

    # Drop known-bad ids, but never leave the pool empty (if every id is dead we retry
    # them rather than crash with nothing to choose from).
    source = {v: w for v, w in source.items() if v not in _dead_voices} or source

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

    client = ElevenLabs(api_key=eleven_key)

    # A voice id this account can't use (400 voice_not_found — e.g. a Voice Library voice
    # that was never added to the library) must not kill a render at the TTS step, which
    # runs after the whole script + grounding pipeline. Mark it dead for the session and
    # retry once with a freshly resolved voice.
    last_voice = ""
    for attempt in (0, 1):
        voice_id, model_id = resolve_tts_config(channel_id)
        last_voice = voice_id
        try:
            # Word-level timestamps (free from the same TTS call) power accurate /
            # karaoke captions (video/caption_timing). Best-effort — any failure falls
            # back to the plain stream, so captions revert to the proportional estimate.
            if _word_timestamps_enabled() and _save_word_timestamps(
                client, voice_id, model_id, script, output_path
            ):
                print(
                    f"[TTS] Channel: {channel_id} | Voice: {voice_id} | "
                    f"Model: {model_id} | +timestamps"
                )
                return output_path

            audio = client.text_to_speech.convert(
                voice_id=voice_id,
                model_id=model_id,
                text=script,
            )
            with open(output_path, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
            break
        except Exception as exc:
            if attempt or not _is_unusable_voice(exc):
                raise
            _mark_voice_dead(voice_id, exc)

    print(f"[TTS] Channel: {channel_id} | Voice: {last_voice} | Model: {model_id}")
    return output_path


def _resolve_tts_provider() -> str:
    return (os.getenv("TTS_PROVIDER", "elevenlabs") or "elevenlabs").strip().lower()


def _free_mode_strict() -> bool:
    """Free-mode never-pay guard (set by core.run_mode.apply_cost_mode)."""
    return os.getenv("FREE_MODE_STRICT", "").strip().lower() in ("1", "true", "yes")


_LOCAL_TTS_PROVIDERS = ("kokoro", "xtts", "piper")

# Per-channel local voice → global env fallback. Value semantics depend on the provider:
# Piper → a .onnx path, Kokoro → a voice name (e.g. "af_heart"), XTTS → a speaker wav.
_LOCAL_VOICE_ENV = {"piper": "PIPER_VOICE", "kokoro": "KOKORO_VOICE", "xtts": "XTTS_SPEAKER_WAV"}
_LOCAL_VOICE_POOL_ENV = {
    "piper": "PIPER_VOICES",
    "kokoro": "KOKORO_VOICES",
    "xtts": "XTTS_SPEAKERS",
}

# Delivery-variation speed band (TTS_VOICE_VARIETY). Narrow enough to never hurt
# intelligibility; a factor > 1 speeds delivery up, < 1 slows it down.
_VARIETY_MIN, _VARIETY_MAX = 0.94, 1.06


def is_local_tts_provider() -> bool:
    """True when TTS_PROVIDER selects a local (zero-marginal-cost) voice backend."""
    return _resolve_tts_provider() in _LOCAL_TTS_PROVIDERS


def _env_pool(env_key: str) -> list[str]:
    return [v.strip() for v in (os.getenv(env_key, "") or "").split(",") if v.strip()]


def resolve_local_voice(provider: str, channel_id: str | None = None) -> str | None:
    """Resolve the local voice for a channel + provider, or None to use the synth default.

    Precedence mirrors the ElevenLabs per-channel/pool pattern in `resolve_tts_config`:
      1. per-channel config (`channels.json` `tts.local_voices` pool → rotates per run =
         delivery variation; or `tts.local_voice` single value);
      2. shared catalog — `config/voices.json` `local.<provider>` (weighted, rotates);
      3. global env pool — PIPER_VOICES / KOKORO_VOICES / XTTS_SPEAKERS (csv, rotates);
      4. global env single — PIPER_VOICE / KOKORO_VOICE / XTTS_SPEAKER_WAV.
    Step 4 means when nothing new is configured this returns exactly today's value, so
    the synths stay byte-identical. Fail-open: any profile-load error drops to the env
    forms; never raises.
    """
    provider = (provider or "").strip().lower()
    if provider not in _LOCAL_TTS_PROVIDERS:
        return None
    try:
        profile = get_channel_profile(channel_id)
    except Exception:
        profile = None
    if profile is not None:
        if profile.local_tts_voices:
            return random.choice(list(profile.local_tts_voices))
        if profile.local_tts_voice:
            return profile.local_tts_voice
    catalog = load_local_voice_pool(provider)
    if catalog:
        return weighted_random_voice(catalog)
    pool = _env_pool(_LOCAL_VOICE_POOL_ENV.get(provider, ""))
    if pool:
        return random.choice(pool)
    single = (os.getenv(_LOCAL_VOICE_ENV.get(provider, ""), "") or "").strip()
    return single or None


def _voice_variety_enabled() -> bool:
    return os.getenv("TTS_VOICE_VARIETY", "").strip().lower() in ("1", "true", "yes")


def _variety_speed_factor(channel_id: str | None = None, *, seed: str | None = None) -> float:
    """Stable speed factor in [_VARIETY_MIN, _VARIETY_MAX], or exactly 1.0 when off.

    Deterministic in `seed` (default: today + channel) so a re-render reproduces the same
    delivery while different videos / channels / days differ — variation without random
    intelligibility risk. Returns 1.0 (a no-op) unless TTS_VOICE_VARIETY is set.
    """
    if not _voice_variety_enabled():
        return 1.0
    key = seed or f"{datetime.date.today().isoformat()}:{channel_id or 'default'}"
    bucket = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16) % 1000
    return round(_VARIETY_MIN + (bucket / 999) * (_VARIETY_MAX - _VARIETY_MIN), 4)


def _piper_syn_config(factor: float):
    """A piper `SynthesisConfig` applying the variety speed factor, or None (plain synth).

    `length_scale` is the inverse of speed (> 1 slower). Returns None when variety is a
    no-op or the installed piper lacks `SynthesisConfig`, so the plain synth call is
    always the fallback.
    """
    if factor == 1.0:
        return None
    try:
        from piper import SynthesisConfig
    except Exception:
        return None
    try:
        return SynthesisConfig(length_scale=round(1.0 / factor, 4))
    except Exception:
        return None


def _piper_write_wav(voice: Any, script: str, wav_file, syn_config) -> None:
    """Write Piper audio into an open wave file across piper API generations.

    Current piper (>=1.3) exposes `synthesize_wav(text, wav_file, syn_config=...)` and its
    bare `synthesize` returns audio chunks (no wav_file); older piper wrote via
    `synthesize(text, wav_file)`. `syn_config` carries the optional delivery-jitter speed;
    a plain call is always the fallback so jitter can never break synthesis.
    """
    synth_wav = getattr(voice, "synthesize_wav", None)
    if callable(synth_wav):
        if syn_config is not None:
            synth_wav(script, wav_file, syn_config=syn_config)
        else:
            synth_wav(script, wav_file)
        return
    voice.synthesize(script, wav_file)  # legacy piper API (voice is Any → mypy-safe)


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
    voice = resolve_local_voice("kokoro", channel_id) or "af_heart"
    speed = _variety_speed_factor(channel_id, seed=output_path)
    try:
        if speed != 1.0:
            gen = pipeline(script, voice=voice, speed=speed)
        else:
            gen = pipeline(script, voice=voice)
    except TypeError:  # older kokoro without a speed kwarg — delivery jitter is best-effort
        gen = pipeline(script, voice=voice)
    chunks = [audio for _, _, audio in gen]
    if not chunks:
        return None
    wav_path = _tmp_wav_path(output_path)
    sf.write(wav_path, np.concatenate(chunks), 24000)
    return _transcode_to_mp3(wav_path, output_path)


def _xtts_synth(script: str, output_path: str, channel_id: str | None) -> str | None:
    """Local XTTS-v2 voice clone (optional extra: TTS). Needs XTTS_SPEAKER_WAV set."""
    from TTS.api import TTS

    speaker = resolve_local_voice("xtts", channel_id)
    if not speaker:
        return None
    wav_path = _tmp_wav_path(output_path)
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    kwargs = {
        "text": script,
        "speaker_wav": speaker,
        "language": os.getenv("XTTS_LANG", "en"),
        "file_path": wav_path,
    }
    speed = _variety_speed_factor(channel_id, seed=output_path)
    try:
        if speed != 1.0:
            tts.tts_to_file(**kwargs, speed=speed)
        else:
            tts.tts_to_file(**kwargs)
    except TypeError:  # model/version without a speed kwarg — jitter is best-effort
        tts.tts_to_file(**kwargs)
    return _transcode_to_mp3(wav_path, output_path)


def _piper_synth(script: str, output_path: str, channel_id: str | None) -> str | None:
    """Local Piper TTS (optional extra: piper-tts) — CPU/ONNX, no torch, MIT.

    The Windows-box path: needs only `pip install piper-tts` plus a voice model
    (PIPER_VOICE=<path/to/voice.onnx>, e.g. en_US-lessac-medium from the Piper
    releases). Synthesizes to wav via the python API, then transcodes to the mp3.
    """
    import wave

    model = (resolve_local_voice("piper", channel_id) or "").strip()
    if not model or not os.path.isfile(model):
        logger.warning("TTS_PROVIDER=piper needs PIPER_VOICE=<path/to/voice.onnx>")
        return None

    from piper import PiperVoice

    voice = PiperVoice.load(model)
    wav_path = _tmp_wav_path(output_path)
    syn_config = _piper_syn_config(_variety_speed_factor(channel_id, seed=output_path))
    with wave.open(wav_path, "wb") as wav_file:
        _piper_write_wav(voice, script, wav_file, syn_config)
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
