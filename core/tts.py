import base64
import datetime
import hashlib
import json
import os
import random
import re
import shutil
from contextlib import contextmanager
from typing import Any

from config.channels import get_channel_profile, resolve_channel_id
from config.paths import PRONUNCIATIONS_FILE, VOICES_FILE
from core.logging import get_logger
from core.utils import clean_script_for_tts
from video.caption_timing import words_from_alignment

logger = get_logger("core.tts")

# Set by generate_audio so merge_render_cost can zero the TTS line on a cache hit
# (re-synth skipped — do not double-bill the ledger) or an occasional Piper mix.
_last_cache_hit = False
_last_piper_mix = False
_last_cache_fraction = 0.0
_last_paid_fallback = False
_last_paid_fallback_from = ""

# Tests patch this name. Production fills it on first paid synth so import stays cheap (#607).
ElevenLabs: Any = None


def last_tts_was_cache_hit() -> bool:
    return _last_cache_hit


def last_tts_was_piper_mix() -> bool:
    return _last_piper_mix


def last_tts_cache_fraction() -> float:
    """0..1 share of synthesized characters served from the TTS cache (#402)."""
    return _last_cache_fraction


def last_tts_fell_back_to_paid() -> bool:
    return _last_paid_fallback


def last_tts_fallback_from() -> str:
    return _last_paid_fallback_from


def mark_tts_paid_fallback(provider: str, reason: str = "") -> None:
    global _last_paid_fallback, _last_paid_fallback_from
    del reason
    _last_paid_fallback = True
    _last_paid_fallback_from = str(provider or "")


def _elevenlabs_client(api_key: str):
    """Paid SDK is imported only when a render actually bills ElevenLabs (#607)."""
    cls = ElevenLabs
    if cls is None:
        from elevenlabs.client import ElevenLabs as cls
    return cls(api_key=api_key)


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


# (mtime, parsed) — pronunciations.json is re-read only when it changes.
_lexicon_cache: tuple[float, dict[str, Any]] | None = None


def _load_pronunciation_lexicon() -> dict[str, Any]:
    """Parsed config/pronunciations.json, mtime-cached. Fail-open to {}."""
    global _lexicon_cache
    try:
        mtime = os.path.getmtime(PRONUNCIATIONS_FILE)
    except OSError:
        _lexicon_cache = None
        return {}
    if _lexicon_cache is not None and _lexicon_cache[0] == mtime:
        return _lexicon_cache[1]
    try:
        with open(PRONUNCIATIONS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError) as exc:
        logger.warning("pronunciations.json unreadable (%s) - lexicon disabled", exc)
        data = {}
    _lexicon_cache = (mtime, data)
    return data


def _lexicon_for_channel(channel_id: str | None) -> dict[str, str]:
    """Default replacements, overlaid by an optional per-channel map."""
    data = _load_pronunciation_lexicon()
    table: dict[str, str] = {}
    default = data.get("default")
    if isinstance(default, dict):
        table.update({str(k): str(v) for k, v in default.items() if k and v})
    channels = data.get("channels")
    if isinstance(channels, dict) and channel_id:
        overlay = channels.get(channel_id)
        if isinstance(overlay, dict):
            table.update({str(k): str(v) for k, v in overlay.items() if k and v})
    return table


def apply_pronunciation_lexicon(text: str, channel_id: str | None = None) -> str:
    """Return a spoken copy of `text` with lexicon substitutions. Does not mutate `text`.

    Longest key first so "Ilia Topuria" wins over "Topuria". Empty lexicon is a no-op
    (returns the original string object). Local TTS only — callers must not apply this
    to the caption/retext script.
    """
    if not text:
        return text
    table = _lexicon_for_channel(channel_id)
    if not table:
        return text
    keys = sorted(table, key=len, reverse=True)
    lower_map = {k.lower(): v for k, v in table.items()}
    pattern = re.compile("|".join(re.escape(k) for k in keys), re.IGNORECASE)

    def _repl(match: re.Match[str]) -> str:
        return lower_map.get(match.group(0).lower(), match.group(0))

    return pattern.sub(_repl, text)


def _edge_voice() -> str:
    return (os.getenv("EDGE_VOICE") or "en-US-JennyNeural").strip() or "en-US-JennyNeural"


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


def tts_cache_enabled() -> bool:
    """Re-synth skip for identical scripts. Opt-in (empty/0/off = disabled).

    Default off so a bare ``unittest discover -s tests`` (no ``-t .``, which
    does not import ``tests/__init__.py``) cannot write ``data/tts_cache``.
    Production: set ``TTS_CACHE=true``.
    """
    return os.getenv("TTS_CACHE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def tts_cache_dir() -> str:
    override = os.getenv("TTS_CACHE_DIR", "").strip()
    if override:
        return override
    from config.paths import DATA_DIR

    return os.path.join(DATA_DIR, "tts_cache")


def tts_cache_key(text: str, provider: str, voice: str = "") -> str:
    payload = f"{provider}\n{voice}\n{text}".encode()
    return hashlib.sha256(payload).hexdigest()


def _tts_cache_paths(key: str) -> tuple[str, str]:
    root = tts_cache_dir()
    mp3 = os.path.join(root, f"{key}.mp3")
    return mp3, mp3 + ".words.json"


def tts_cache_lookup(key: str, dest_path: str) -> bool:
    if not tts_cache_enabled() or not key:
        return False
    src, src_words = _tts_cache_paths(key)
    if not os.path.isfile(src) or os.path.getsize(src) <= 0:
        return False
    try:
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        shutil.copy2(src, dest_path)
        if os.path.isfile(src_words):
            shutil.copy2(src_words, dest_path + ".words.json")
        return True
    except Exception as exc:
        logger.debug("TTS cache lookup skipped: %s", exc)
        return False


def tts_cache_store(key: str, src_path: str) -> None:
    if not tts_cache_enabled() or not key or not src_path or not os.path.isfile(src_path):
        return
    try:
        os.makedirs(tts_cache_dir(), exist_ok=True)
        dest, dest_words = _tts_cache_paths(key)
        shutil.copy2(src_path, dest)
        words = src_path + ".words.json"
        if os.path.isfile(words):
            shutil.copy2(words, dest_words)
    except Exception as exc:
        logger.debug("TTS cache store skipped: %s", exc)


def _tts_cache_voice(channel_id: str | None) -> str:
    provider = _resolve_tts_provider()
    if provider == "edge":
        return _edge_voice()
    if is_local_tts_provider():
        return resolve_local_voice(provider, channel_id) or os.getenv(
            _LOCAL_VOICE_ENV.get(provider, ""), ""
        )
    try:
        voice_id, _ = resolve_tts_config(channel_id)
        return voice_id or ""
    except Exception as exc:
        logger.debug("TTS cache voice resolve skipped: %s", exc)
        return ""


def generate_audio(script, output_path, channel_id: str | None = None, length_choice: str = ""):
    """Synthesize `script`. `length_choice` selects the long-form voice policy (#758)."""
    with length_context(length_choice):
        return _generate_audio(script, output_path, channel_id=channel_id)


def _generate_audio(script, output_path, channel_id: str | None = None):
    global _last_cache_hit, _last_piper_mix, _last_cache_fraction
    global _last_paid_fallback, _last_paid_fallback_from
    _last_cache_hit = False
    _last_piper_mix = False
    _last_cache_fraction = 0.0
    _last_paid_fallback = False
    _last_paid_fallback_from = ""
    channel_id = resolve_channel_id(channel_id)
    spoken = clean_script_for_tts(script)
    try:
        from core.tts_char_cap import forecast_tts

        forecast_tts(script)
    except Exception as exc:
        logger.debug("tts forecast skipped: %s", exc)
    try:
        from core.spoken_numbers import expand_spoken_numbers

        spoken = expand_spoken_numbers(spoken)
    except Exception as exc:
        logger.debug("spoken-number expand skipped: %s", exc)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Lexicon is for EARS (local TTS) only. Captions/retext keep `script` from the
    # caller; ElevenLabs already handles names, so it gets the cleaned original.
    local_spoken = spoken
    if is_local_tts_provider():
        local_spoken = apply_pronunciation_lexicon(spoken, channel_id)

    spoken_for_alt = local_spoken if is_local_tts_provider() else spoken

    def _record_actual(chars: int) -> None:
        """Stamp what was *actually* synthesized.

        This used to run before the cache lookup, so a cache hit recorded a full
        script's worth of synth chars for characters nothing synthesized -- and
        `core/pipeline.py` persists that as `tts_actual_chars` into the run
        ledger, which is the number the operator and the analytics layer read.
        """
        try:
            from core.tts_char_cap import record_tts_actual

            record_tts_actual(chars)
        except Exception as exc:
            logger.debug("tts actual skipped: %s", exc)

    cache_key = tts_cache_key(spoken_for_alt, _resolve_tts_provider(), _tts_cache_voice(channel_id))
    if tts_cache_lookup(cache_key, output_path):
        _last_cache_hit = True
        _last_cache_fraction = 1.0
        _record_actual(0)
        print(f"[TTS] Channel: {channel_id} | cache hit")
        return output_path

    from core.script_length import split_spoken_sentences

    # Gated on the cache it exists to serve. With TTS_CACHE off (the default)
    # every lookup misses and every store is a no-op, so splitting buys nothing
    # and still costs N synth calls, an ffmpeg re-encode, and an encoder boundary
    # at every sentence break in every video.
    sents = split_spoken_sentences(spoken) if tts_cache_enabled() else []
    alts = split_spoken_sentences(spoken_for_alt) if tts_cache_enabled() else []
    if len(sents) == len(alts) and len(sents) > 1 and ffmpeg_concat_ready():
        try:
            return _generate_by_sentences(
                sents,
                alts,
                output_path,
                channel_id,
                cache_key,
                _record_actual,
            )
        except Exception as exc:
            # The segments were already synthesized and billed. Falling back
            # re-synthesizes the whole script, so the provider is charged roughly
            # twice -- and recording only the second pass would erase the first
            # from `tts_actual_chars`, which is the #657 defect again.
            spent = int(getattr(exc, "spent_chars", 0) or 0)
            if spent:
                logger.warning(
                    "sentence TTS concat failed after billing %d char(s); "
                    "the whole script is being re-synthesized, so this render is "
                    "billed twice: %s",
                    spent,
                    exc,
                )
            else:
                logger.warning("sentence TTS cache failed - synthesizing whole script: %s", exc)
            _record_actual(spent + len(spoken_for_alt))
            return synthesize_to_path(spoken, spoken_for_alt, output_path, channel_id, cache_key)

    _record_actual(len(spoken_for_alt))
    return synthesize_to_path(spoken, spoken_for_alt, output_path, channel_id, cache_key)


def offset_word_timings(words: list[dict[str, Any]], offset: float) -> list[dict[str, Any]]:
    """Shift word sidecar timestamps by `offset` seconds (#402 concat)."""
    shifted: list[dict[str, Any]] = []
    for item in words or []:
        row = dict(item)
        start = row.get("start")
        end = row.get("end")
        try:
            if start is not None:
                row["start"] = float(start) + offset
            if end is not None:
                row["end"] = float(end) + offset
        except (TypeError, ValueError):
            pass
        shifted.append(row)
    return shifted


def segment_audio_duration(path: str) -> float:
    """Prefer the sidecar's last end time; ffprobe if the sidecar is missing."""
    sidecar = path + ".words.json"
    if os.path.isfile(sidecar):
        try:
            with open(sidecar, encoding="utf-8") as f:
                words = json.load(f)
            ends: list[float] = []
            if isinstance(words, list):
                for word in words:
                    if not isinstance(word, dict) or word.get("end") is None:
                        continue
                    ends.append(float(word["end"]))
            if ends:
                return max(ends)
        except (OSError, TypeError, ValueError):
            pass
    import subprocess

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "csv=p=0",
        path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return float((proc.stdout or "0").strip() or 0)
    except (OSError, TypeError, ValueError) as exc:
        logger.debug("segment duration skipped: %s", exc)
        return 0.0


_lame_ok: dict[str, bool] = {}


def ffmpeg_concat_ready() -> bool:
    """True when ffmpeg is on PATH and can encode libmp3lame.

    #666: the sentence loop synthesizes N segments *then* concats. A missing
    or undersized ffmpeg fails after the spend, and the fallback synthesizes
    the whole script again. This is knowable for free.
    """
    exe = shutil.which("ffmpeg")
    if not exe:
        return False
    cached = _lame_ok.get(exe)
    if cached is not None:
        return cached
    try:
        import subprocess

        proc = subprocess.run(
            [exe, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        ok = "libmp3lame" in (proc.stdout or "")
    except Exception as exc:
        logger.debug("ffmpeg concat preflight skipped: %s", exc)
        ok = False
    _lame_ok[exe] = ok
    return ok


def concat_audio_segments(paths: list[str], dest: str) -> str:
    """Re-encode concatenated MP3s. Copy-concat across providers is unsafe."""
    import subprocess

    if not paths:
        raise RuntimeError("no TTS segments to concat")
    list_file = dest + ".concat.txt"
    try:
        with open(list_file, "w", encoding="utf-8") as f:
            for path in paths:
                safe = path.replace("\\", "/").replace("'", r"'\''")
                f.write(f"file '{safe}'\n")
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_file,
            "-c:a",
            "libmp3lame",
            "-qscale:a",
            "4",
            dest,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0 or not os.path.isfile(dest) or os.path.getsize(dest) <= 0:
            err = (proc.stderr or "")[-300:]
            raise RuntimeError(f"ffmpeg concat failed (rc={proc.returncode}): {err}")
        return dest
    finally:
        try:
            os.remove(list_file)
        except OSError:
            pass


def _write_concat_word_sidecar(paths: list[str], dest: str) -> None:
    merged: list[dict[str, Any]] = []
    offset = 0.0
    for path in paths:
        sidecar = path + ".words.json"
        chunk: list[dict[str, Any]] = []
        if os.path.isfile(sidecar):
            try:
                with open(sidecar, encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, list):
                    chunk = [w for w in loaded if isinstance(w, dict)]
            except (OSError, ValueError):
                chunk = []
        merged.extend(offset_word_timings(chunk, offset))
        offset += segment_audio_duration(path)
    try:
        with open(dest + ".words.json", "w", encoding="utf-8") as f:
            json.dump(merged, f)
    except OSError as exc:
        logger.debug("concat word sidecar skipped: %s", exc)


def _generate_by_sentences(
    sents: list[str],
    alts: list[str],
    output_path: str,
    channel_id: str | None,
    whole_cache_key: str,
    record_actual,
) -> str:
    global _last_cache_hit, _last_cache_fraction
    provider = _resolve_tts_provider()
    voice = _tts_cache_voice(channel_id)
    paths: list[str] = []
    cached_chars = 0
    synth_chars = 0
    tmp_paths: list[str] = []
    try:
        for i, (sent, alt) in enumerate(zip(sents, alts, strict=True)):
            seg = f"{output_path}.seg{i}.mp3"
            tmp_paths.append(seg)
            key = tts_cache_key(alt, provider, voice)
            if tts_cache_lookup(key, seg):
                cached_chars += len(alt)
            else:
                synthesize_to_path(sent, alt, seg, channel_id, key, allow_piper_mix=False)
                synth_chars += len(alt)
            paths.append(seg)
        try:
            concat_audio_segments(paths, output_path)
            _write_concat_word_sidecar(paths, output_path)
        except Exception as exc:
            # Tell the caller what was already paid for, so the fallback can add
            # it rather than report only its own synthesis.
            exc.spent_chars = synth_chars  # type: ignore[attr-defined]
            raise
        tts_cache_store(whole_cache_key, output_path)
        total = cached_chars + synth_chars
        _last_cache_fraction = (cached_chars / total) if total else 0.0
        _last_cache_hit = _last_cache_fraction >= 1.0
        record_actual(synth_chars)
        if _last_cache_hit:
            print(f"[TTS] Channel: {channel_id} | cache hit (sentences)")
        else:
            pct = f"{_last_cache_fraction:.0%}"
            print(f"[TTS] Channel: {channel_id} | sentence cache {pct}")
        return output_path
    finally:
        for path in tmp_paths:
            for extra in (path, path + ".words.json"):
                try:
                    os.remove(extra)
                except OSError:
                    pass


def synthesize_to_path(
    spoken: str,
    spoken_for_alt: str,
    output_path: str,
    channel_id: str | None,
    cache_key: str,
    *,
    allow_piper_mix: bool = True,
) -> str:
    """Write synthesized audio for one text blob. Callers own cache lookup + actuals.

    #658: generate_audio (and later per-sentence cache) go through this seam so
    provider branches are not duplicated. Piper mix still skips cache store —
    that path is an occasional stand-in, not a billed identity for the script.
    """
    global _last_piper_mix

    if is_local_tts_provider():
        try:
            from core.ram_preflight import block_reason as ram_block

            why = ram_block(kind="tts")
        except Exception as exc:
            logger.debug("ram preflight skipped: %s", exc)
            why = None
        if why:
            logger.warning("%s", why)
            if _free_mode_strict():
                raise RuntimeError(why)

    # Provider seam (Pillar 6): a non-ElevenLabs TTS_PROVIDER (local Kokoro/XTTS) is
    # tried first; on any failure it falls back to the ElevenLabs default below.
    alt = _try_alt_tts_provider(spoken_for_alt, output_path, channel_id)
    if alt:
        tts_cache_store(cache_key, alt)
        return alt

    if allow_piper_mix and _should_piper_mix():
        mixed_spoken = apply_pronunciation_lexicon(spoken, channel_id)
        try:
            mixed = _piper_synth(mixed_spoken, output_path, channel_id)
        except Exception as exc:
            logger.warning("Piper mix failed — using ElevenLabs: %s", exc)
            mixed = None
        if mixed:
            _last_piper_mix = True
            every = _piper_mix_every()
            print(f"[TTS] Channel: {channel_id} | Provider: piper (mix 1/{every})")
            return mixed

    # Free mode (strict): local $0 voice failed/absent and paid ElevenLabs is
    # disallowed — block with install guidance instead of silently paying.
    if _free_mode_strict():
        raise RuntimeError(
            "Free mode ($0, strict): no local TTS produced audio and paid ElevenLabs "
            "is disallowed. Install a local voice - pip install piper-tts, set "
            "PIPER_VOICE=<voice.onnx> and TTS_PROVIDER=piper. See docs/free_mode.md."
        )

    if _elevenlabs_quota_would_exceed(len(spoken)):
        try:
            from core.win_notify import notify_breaker

            notify_breaker("ElevenLabs", _elevenlabs_budget_display())
        except Exception as exc:
            logger.debug("breaker toast skipped: %s", exc)
        piped = _synth_piper_for_quota(spoken, output_path, channel_id)
        if piped:
            tts_cache_store(cache_key, piped)
            return piped
        raise RuntimeError(
            "ElevenLabs monthly character budget exhausted "
            f"({_elevenlabs_budget_display()}). Set ELEVENLABS_MONTHLY_CHAR_BUDGET "
            "or install Piper (PIPER_VOICE) to keep rendering."
        )

    eleven_key = os.getenv("ELEVEN_API_KEY")
    if not eleven_key:
        raise Exception("ELEVEN_API_KEY not found.")

    client = _elevenlabs_client(eleven_key)

    # A voice id this account can't use (400 voice_not_found — e.g. a Voice Library voice
    # that was never added to the library) must not kill a render at the TTS step, which
    # runs after the whole script + grounding pipeline. Mark it dead for the session and
    # retry once with a freshly resolved voice.
    last_voice = ""
    model_id = ""
    for attempt in (0, 1):
        voice_id, model_id = resolve_tts_config(channel_id)
        last_voice = voice_id
        try:
            # Word-level timestamps (free from the same TTS call) power accurate /
            # karaoke captions (video/caption_timing). Best-effort — any failure falls
            # back to the plain stream, so captions revert to the proportional estimate.
            if _word_timestamps_enabled() and _save_word_timestamps(
                client, voice_id, model_id, spoken, output_path
            ):
                print(
                    f"[TTS] Channel: {channel_id} | Voice: {voice_id} | "
                    f"Model: {model_id} | +timestamps"
                )
                _elevenlabs_record_chars(len(spoken))
                tts_cache_store(cache_key, output_path)
                return output_path

            audio = client.text_to_speech.convert(
                voice_id=voice_id,
                model_id=model_id,
                text=spoken,
            )
            with open(output_path, "wb") as f:
                for chunk in audio:
                    f.write(chunk)
            break
        except Exception as exc:
            if attempt or not _is_unusable_voice(exc):
                raise
            _mark_voice_dead(voice_id, exc)

    _elevenlabs_record_chars(len(spoken))
    print(f"[TTS] Channel: {channel_id} | Voice: {last_voice} | Model: {model_id}")
    tts_cache_store(cache_key, output_path)
    return output_path


# #775: no default long-form override any more - the operator opts in with TTS_PROVIDER_LONG.
_LONG_FORM_PROVIDER_DEFAULT = ""
_length_choice_context = ""


@contextmanager
def length_context(length_choice: str):
    """The render's length preset, for the duration of one `generate_audio` call."""
    global _length_choice_context
    previous = _length_choice_context
    _length_choice_context = str(length_choice or "")
    try:
        yield
    finally:
        _length_choice_context = previous


def long_form_provider(provider: str, length_choice: str) -> str:
    """Voice backend for this length (#758, reversed by #775).

    #758 sent Long/Extended to piper because TTS was 91% of spend. The operator listened to
    the first piper Extended render (run 79, 2026-09-17) and called it clearly worse, so
    long-form is paid again: this returns the configured provider unless the operator sets
    `TTS_PROVIDER_LONG` themselves. Piper survives as the 1-in-6 Shorts mix. A long video is
    1-2 a month, so the bill is mostly Shorts either way.
    """
    if os.getenv("TTS_PROVIDER", "").strip():
        return provider
    try:
        from core.script_length import WORDS_PER_SECOND, get_length_preset

        seconds = get_length_preset(str(length_choice or "")).max_words / max(WORDS_PER_SECOND, 0.1)
    except Exception as exc:
        logger.debug("long-form voice policy skipped: %s", exc)
        return provider
    if seconds <= 180:
        return provider
    return (
        os.getenv("TTS_PROVIDER_LONG", "").strip() or _LONG_FORM_PROVIDER_DEFAULT
    ).lower() or provider


def voice_stage_label(length_choice: str = "") -> str:
    """The render progress line, named for the voice this length will use (#772)."""
    provider = (os.getenv("TTS_PROVIDER", "elevenlabs") or "elevenlabs").strip().lower()
    return f"Voice ({long_form_provider(provider, length_choice)})..."


def _resolve_tts_provider() -> str:
    provider = (os.getenv("TTS_PROVIDER", "elevenlabs") or "elevenlabs").strip().lower()
    return long_form_provider(provider, _length_choice_context)


def _piper_mix_every() -> int:
    """1-in-N Standard ElevenLabs renders use Piper. Unset = 6 (#775); 0/off = never."""
    raw = (os.getenv("TTS_PIPER_MIX_EVERY", "6") or "6").strip().lower()
    if raw in ("0", "off", "false", "no"):
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 6


def _should_piper_mix() -> bool:
    """True for this generate_audio call when Piper should stand in for ElevenLabs."""
    if _free_mode_strict():
        return False
    if _resolve_tts_provider() != "elevenlabs":
        return False
    every = _piper_mix_every()
    if every <= 0:
        return False
    try:
        from core.run_mode import _tts_provider_ready

        if not _tts_provider_ready("piper"):
            return False
    except Exception as exc:
        logger.debug("piper mix readiness skipped: %s", exc)
        return False
    return random.randrange(every) == 0


def _free_mode_strict() -> bool:
    """Free-mode never-pay guard (set by core.run_mode.apply_cost_mode)."""
    return os.getenv("FREE_MODE_STRICT", "").strip().lower() in ("1", "true", "yes")


_LOCAL_TTS_PROVIDERS = ("kokoro", "xtts", "piper", "qwen")

# Per-channel local voice → global env fallback. Value semantics depend on the provider:
# Piper → a .onnx path, Kokoro → a voice name (e.g. "af_heart"), XTTS → a speaker wav,
# Qwen → a built-in speaker name OR a reference .wav path (voice cloning).
_LOCAL_VOICE_ENV = {
    "piper": "PIPER_VOICE",
    "kokoro": "KOKORO_VOICE",
    "xtts": "XTTS_SPEAKER_WAV",
    "qwen": "QWEN_VOICE",
}
_LOCAL_VOICE_POOL_ENV = {
    "piper": "PIPER_VOICES",
    "kokoro": "KOKORO_VOICES",
    "xtts": "XTTS_SPEAKERS",
    "qwen": "QWEN_VOICES",
}

# Delivery-variation speed band (TTS_VOICE_VARIETY). Narrow enough to never hurt
# intelligibility; a factor > 1 speeds delivery up, < 1 slows it down.
_VARIETY_MIN, _VARIETY_MAX = 0.94, 1.06


def is_local_tts_provider() -> bool:
    """True when TTS_PROVIDER selects a local (zero-marginal-cost) voice backend."""
    return _resolve_tts_provider() in _LOCAL_TTS_PROVIDERS


def _elevenlabs_budget() -> int | None:
    """Creator-plan character ceiling. Unset/0/off = governor disabled (Apify-shaped)."""
    raw = os.getenv("ELEVENLABS_MONTHLY_CHAR_BUDGET", "").strip()
    if raw.lower() in ("", "0", "off", "false", "no"):
        return None
    try:
        val = int(raw)
    except ValueError:
        return None
    return val if val > 0 else None


def _elevenlabs_budget_display() -> str:
    budget = _elevenlabs_budget()
    if budget is None:
        return "no budget"
    try:
        from core.quota_governor import elevenlabs_chars_reading

        used = elevenlabs_chars_reading()
    except Exception:
        used = None
    if used is None:  # #724: an unreadable ledger is not "0 used"
        return f"unknown/{budget:,} chars"
    return f"{used:,}/{budget:,} chars"


def _elevenlabs_quota_would_exceed(chars: int) -> bool:
    budget = _elevenlabs_budget()
    if budget is None or chars <= 0:
        return False
    try:
        from core.quota_governor import elevenlabs_would_exceed

        return elevenlabs_would_exceed(chars, budget)
    except Exception as exc:
        logger.debug("ElevenLabs quota check skipped: %s", exc)
        return False  # fail-open: never block a render because the store is unreadable


def _elevenlabs_record_chars(chars: int) -> None:
    if chars <= 0 or _elevenlabs_budget() is None:
        return
    try:
        from core.quota_governor import elevenlabs_add_chars

        elevenlabs_add_chars(chars)
    except Exception as exc:
        logger.warning(
            "ElevenLabs char count of %s not persisted (quota guard blind): %s",
            chars,
            exc,
        )


def _piper_voice_ready() -> bool:
    from core.voice_catalog import any_piper_onnx_ready

    try:
        import importlib.util

        if importlib.util.find_spec("piper") is None:
            return False
    except (ImportError, ValueError, ModuleNotFoundError):
        return False
    return any_piper_onnx_ready()


def _synth_piper_for_quota(script: str, output_path: str, channel_id: str | None) -> str | None:
    """Trip ElevenLabs → Piper when the monthly character budget would exhaust."""
    if not _piper_voice_ready():
        return None
    try:
        path = _piper_synth(script, output_path, channel_id)
    except Exception as exc:
        logger.warning("Piper fallback after ElevenLabs quota failed: %s", exc)
        return None
    if not path:
        return None
    os.environ["TTS_PROVIDER"] = "piper"  # so merge_render_cost meters tts at $0
    logger.warning(
        "ElevenLabs character budget would exceed (%s) — using Piper for this render",
        _elevenlabs_budget_display(),
    )
    print(f"[TTS] Channel: {channel_id} | Provider: piper (ElevenLabs quota trip)")
    return path


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
    (core/pipeline.py → video/render_video.py: ffprobe duration, subtitles, ffmpeg mux),
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


# Loaded Qwen3-TTS model(s), cached per process/model-id — loading a 1.7B model is heavy
# and a render only needs it once, but multi-render sessions (e.g. reruns) reuse it.
_qwen_model_cache: dict[str, Any] = {}


def _load_qwen_model(model_id: str):
    """Load + cache the Qwen3-TTS model (optional extra: qwen-tts, torch; needs a GPU)."""
    cached = _qwen_model_cache.get(model_id)
    if cached is not None:
        return cached
    import torch
    from qwen_tts import Qwen3TTSModel

    device = os.getenv("QWEN_TTS_DEVICE", "cuda:0")
    dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
    kwargs: dict[str, Any] = {"device_map": device, "dtype": dtype}
    attn = os.getenv("QWEN_TTS_ATTN", "").strip()  # optional, e.g. flash_attention_2
    if attn:
        kwargs["attn_implementation"] = attn
    model = Qwen3TTSModel.from_pretrained(model_id, **kwargs)
    _qwen_model_cache[model_id] = model
    return model


def _qwen_ref_text(ref_audio: str) -> str:
    """Transcript for a clone reference: sidecar `<ref>.txt`, else the QWEN_REF_TEXT env."""
    sidecar = os.path.splitext(ref_audio)[0] + ".txt"
    try:
        if os.path.isfile(sidecar):
            with open(sidecar, encoding="utf-8") as f:
                return f.read().strip()
    except OSError:
        pass
    return (os.getenv("QWEN_REF_TEXT", "") or "").strip()


def _qwen_synth(script: str, output_path: str, channel_id: str | None) -> str | None:
    """Local Qwen3-TTS (optional extra: qwen-tts + torch; needs a CUDA GPU).

    The resolved voice is either a built-in speaker name (e.g. "Vivian") or a path to a
    reference `.wav` for **voice cloning** (transcript from a sidecar `<ref>.txt` or
    QWEN_REF_TEXT). Any failure falls back to ElevenLabs — a local voice can't break a
    render. Voice resolution happens before heavy imports so the "not configured" path
    returns None without needing torch/qwen-tts installed.
    """
    voice = (resolve_local_voice("qwen", channel_id) or "").strip()
    if not voice:
        logger.warning("TTS_PROVIDER=qwen needs a QWEN_VOICE (speaker name or reference .wav)")
        return None

    import soundfile as sf

    model = _load_qwen_model(os.getenv("QWEN_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"))
    kwargs: dict[str, Any] = {"text": script, "language": os.getenv("QWEN_TTS_LANG", "English")}
    if voice.lower().endswith(".wav") and os.path.isfile(voice):
        kwargs["ref_audio"] = voice
        ref_text = _qwen_ref_text(voice)
        if ref_text:
            kwargs["ref_text"] = ref_text
    else:
        kwargs["speaker"] = voice

    wavs, sr = model.generate_custom_voice(**kwargs)
    wav = wavs[0] if isinstance(wavs, list | tuple) else wavs
    wav_path = _tmp_wav_path(output_path)
    sf.write(wav_path, wav, int(sr))
    return _transcode_to_mp3(wav_path, output_path)


_EDGE_TICKS_PER_SECOND = 10_000_000


def _edge_word_events(chunk: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize a WordBoundary chunk to {word, start, end} seconds, or None."""
    word = str(chunk.get("text") or chunk.get("Text") or "").strip()
    if not word:
        return None
    try:
        offset = float(chunk.get("offset") if "offset" in chunk else chunk.get("Offset") or 0)
        duration = float(
            chunk.get("duration") if "duration" in chunk else chunk.get("Duration") or 0
        )
    except (TypeError, ValueError):
        return None
    start = offset / _EDGE_TICKS_PER_SECOND
    return {"word": word, "start": start, "end": start + (duration / _EDGE_TICKS_PER_SECOND)}


def _edge_synth(script: str, output_path: str, channel_id: str | None) -> str | None:
    """Microsoft Edge neural TTS (unofficial endpoint). Cloud, $0, needs network.

    Writes mp3 + optional .words.json from WordBoundary events. Any failure returns
    None so the alt-provider chain can fall back. Never the default provider.
    """
    try:
        import asyncio

        import edge_tts
    except ImportError:
        logger.warning('TTS_PROVIDER=edge needs edge-tts (pip install -e ".[free]")')
        return None

    # NOT SSML: edge_tts.Communicate escapes its input, so markup is spoken aloud
    # (measured: 23.76s of "speak version equals one point zero" for a 3.94s line).
    # Pronunciation rides the same plain respelling the local providers use.
    spoken = apply_pronunciation_lexicon(script, channel_id)
    voice = _edge_voice()

    async def _run() -> str | None:
        # edge_tts 7.x defaults boundary to "SentenceBoundary"; ask for words or
        # the .words.json branch below never fires and captions lose their timing.
        communicate = edge_tts.Communicate(spoken, voice, boundary="WordBoundary")
        audio = bytearray()
        words: list[dict[str, Any]] = []
        async for chunk in communicate.stream():
            kind = str((chunk or {}).get("type") or "")
            if kind == "audio":
                audio.extend(chunk.get("data") or b"")
            elif kind == "WordBoundary":
                event = _edge_word_events(chunk)
                if event:
                    words.append(event)
        if not audio:
            return None
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "wb") as fh:
            fh.write(audio)
        if words and _word_timestamps_enabled():
            with open(word_timing_path(output_path), "w", encoding="utf-8") as fh:
                json.dump(words, fh)
        return output_path

    return asyncio.run(_run())


_ALT_TTS = {
    "kokoro": _kokoro_synth,
    "xtts": _xtts_synth,
    "piper": _piper_synth,
    "qwen": _qwen_synth,
    "edge": _edge_synth,
}


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
        mark_tts_paid_fallback(provider, str(exc))
        logger.warning("TTS provider %s failed (%s) — falling back to ElevenLabs", provider, exc)
        return None
    if path:
        kind = "cloud, $0" if provider == "edge" else "local, $0"
        print(f"[TTS] Channel: {channel_id} | Provider: {provider} ({kind})")
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
