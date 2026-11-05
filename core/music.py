"""Music / SFX bed seam (Pillar 6) — OFF by default, fail-open.

Generates a background music bed for a render. The real backend (MusicGen via
`audiocraft` + torch) is an optional extra — `pip install -e ".[providers]"`. Unselected
or uninstalled ⇒ `ProviderResult.fail_open`, so the render proceeds with no bed exactly
as it does today.

    MUSIC_PROVIDER=musicgen     # default: none

Wire point (documented, not activated): duck the returned file under the VO in the
FFmpeg mix (`video/render_video.py`); pick `mood` from the research brief
(`audience_sentiment` / angle).
"""

from __future__ import annotations

import os
import uuid

from core.logging import get_logger
from core.providers import (
    STATUS_ERROR,
    STATUS_NOT_CONFIGURED,
    ProviderResult,
    selected_provider,
)

logger = get_logger("core.music")

SLOT = "music"

# #411: the operator's own tracks. `*.mp3` is gitignored, so they never reach the repo.
AUDIO_SUFFIXES = (".mp3", ".m4a", ".wav", ".ogg", ".flac")
DEFAULT_VOLUME = 0.18


def _state_file():
    from config.paths import DATA_DIR

    return os.path.join(DATA_DIR, "music_last.json")


MUSIC_STATE_FILE = _state_file()


def music_config(channel_id: str | None) -> dict:
    """The channel's `music` block: enabled, folder (default assets/music/<channel>), volume."""
    try:
        from config.channels import get_channel_profile

        profile = get_channel_profile(channel_id)
        raw = dict(getattr(profile, "music", None) or {})
        cid = profile.id
    except Exception as exc:
        logger.debug("music config unavailable: %s", exc)
        return {"enabled": False, "folder": "", "volume": DEFAULT_VOLUME}
    try:
        volume = float(raw.get("volume", DEFAULT_VOLUME))
    except (TypeError, ValueError):
        volume = DEFAULT_VOLUME
    folder = str(raw.get("folder") or os.path.join("assets", "music", cid))
    return {"enabled": bool(raw.get("enabled", False)), "folder": folder, "volume": volume}


def library_tracks(channel_id: str | None) -> list:
    """Audio files in the channel's music folder, by name. [] when none or unreadable."""
    from pathlib import Path

    folder = Path(music_config(channel_id)["folder"])
    try:
        return sorted(
            (p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_SUFFIXES),
            key=lambda p: p.name.lower(),
        )
    except OSError:
        return []


def _load_last() -> dict:
    import json

    try:
        with open(MUSIC_STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def pick_track(channel_id: str | None):
    """A track for this render - never the one the channel's previous render used."""
    import json
    import random

    tracks = library_tracks(channel_id)
    if not tracks:
        return None
    key = str(channel_id or "default")
    last = _load_last()
    choices = [t for t in tracks if t.name != last.get(key)] or tracks
    track = random.choice(choices)
    last[key] = track.name
    try:
        os.makedirs(os.path.dirname(MUSIC_STATE_FILE) or ".", exist_ok=True)
        with open(MUSIC_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(last, f)
    except OSError as exc:
        logger.debug("music pick not remembered: %s", exc)
    return track


# ---- #1995 (wave 150b, the operator: "Generate one with ffmpeg") ------------------------------
# No track had ever been in assets/music/tapin, so no render had a bed; MusicGen meant a
# multi-gigabyte download under a non-commercial licence. A long video's bed is made here from
# sines - nobody else's music, $0: two four-chord progressions, 8 s a chord, each chord eased into
# the next by raised-cosine windows that sum to one, warmed by a soft octave, filtered to a pad,
# given a little room and width. Every frequency is rounded to whole cycles in the 64 s loop, so
# the render's `-stream_loop` joins it without a seam. Generated once per variant into
# data/music_beds/ as FLAC - lossless, no AAC priming at the loop (about 15 s each) and taken in turn, never the one the last long video used.
LONG_BED_SECONDS = 180.0  # a render longer than this is a long video (tts.is_long_length's rule)
SYNTH_SLOT = 8.0
# The pad comes out of the expression at -24.1 LUFS. The first cut took it to -20; the operator
# heard it under a voice (11-05): "much much quieter" - 12 dB down, -32 LUFS alone, so at the
# channel's 0.18 it sits about 23 dB under the voice before the ducking.
SYNTH_GAIN_DB = -8.0
_A3 = 220.0
# Semitones from A3 (low root first) in A minor - Am, F, C, G, Em, Dm.
_AM, _F, _C, _G = (-12, 0, 3, 7), (-16, -4, 0, 3), (-21, -9, -5, -2), (-14, -2, 2, 5)
_EM, _DM = (-17, -5, -2, 2), (-19, -7, -4, 0)
SYNTH_PROGRESSIONS: tuple[tuple[tuple[int, ...], ...], ...] = (
    (_AM, _F, _C, _G, _AM, _EM, _F, _G),  # i VI III VII, i v VI VII
    (_AM, _DM, _F, _EM, _AM, _F, _C, _G),  # i iv VI v, i VI III VII
    (_F, _G, _AM, _AM, _DM, _F, _G, _EM),  # VI VII i i, iv VI VII v
)
SYNTH_KEYS = (0, -2)  # A minor, G minor


def synth_variants() -> int:
    return len(SYNTH_PROGRESSIONS) * len(SYNTH_KEYS)


def synth_expr(chords: tuple[tuple[int, ...], ...], *, transpose: int = 0) -> str:
    """The pad as an `aevalsrc` expression, periodic over len(chords) * `SYNTH_SLOT` seconds."""
    slot = SYNTH_SLOT
    cycle = slot * len(chords)
    terms = []
    for k, chord in enumerate(chords):
        centre = k * slot + slot / 2
        d = f"(mod(t-{centre:g}+{cycle / 2:g},{cycle:g})-{cycle / 2:g})"
        window = f"if(lt(abs({d}),{slot:g}),pow(cos(PI*{d}/{2 * slot:g}),2),0)"
        notes = []
        for i, semis in enumerate(chord):
            freq = round(_A3 * 2 ** ((semis + transpose) / 12) * cycle) / cycle  # whole cycles
            notes.append(
                f"{0.5 if i == 0 else 1.0:g}*(sin(2*PI*{freq:.6f}*t)+0.25*sin(4*PI*{freq:.6f}*t))"
            )
        terms.append(f"{window}*({'+'.join(notes)})")
    tremolo = f"(0.88+0.12*sin(2*PI*{8 / cycle:.6f}*t))"
    return f"0.11*{tremolo}*(" + "+".join(terms) + ")"


def synth_bed_argv(dest: str, variant: int) -> list[str]:
    """ffmpeg for one bed variant: two cycles rendered, the second kept (its echo already
    warm), so the loop's end runs into its start."""
    chords = SYNTH_PROGRESSIONS[variant % len(SYNTH_PROGRESSIONS)]
    transpose = SYNTH_KEYS[(variant // len(SYNTH_PROGRESSIONS)) % len(SYNTH_KEYS)]
    cycle = SYNTH_SLOT * len(chords)
    graph = (
        f"aevalsrc='{synth_expr(chords, transpose=transpose)}':s=22050:d={2 * cycle:g},"
        "lowpass=f=1400,highpass=f=60,aecho=0.8:0.55:90|170:0.22|0.14,"
        "pan=stereo|c0=c0|c1=c0,adelay=0|12,"  # 22,050 Hz: aresample broke the loop's period
        f"atrim=start={cycle:g}:end={2 * cycle:g},asetpts=PTS-STARTPTS,"
        f"volume={SYNTH_GAIN_DB:g}dB"
    )
    return ["ffmpeg", "-nostdin", "-y", "-filter_complex", graph,
            "-c:a", "flac", dest]  # fmt: skip


def synth_enabled() -> bool:
    return os.getenv("MUSIC_SYNTH_LONG", "true").strip().lower() not in ("0", "false", "no", "off")


def synth_bed(channel_id: str | None, *, variant: int | None = None) -> str:
    """#1995: a long video's generated bed - the next variant after the one the channel's last
    long video had, made once into data/music_beds/. "" when ffmpeg could not make it."""
    import json
    import subprocess

    from config.paths import DATA_DIR

    key = f"{channel_id or 'default'}:synth"
    last = _load_last()
    if variant is None:
        try:
            variant = (int(last.get(key, -1)) + 1) % synth_variants()
        except (TypeError, ValueError):
            variant = 0
    folder = os.path.join(DATA_DIR, "music_beds")
    # the level is in the name: a pad made at another gain is made again, never reused
    dest = os.path.join(folder, f"pad{variant}_{SYNTH_GAIN_DB:+g}dB.flac")
    if not os.path.isfile(dest):
        os.makedirs(folder, exist_ok=True)
        try:
            subprocess.run(synth_bed_argv(dest, variant), capture_output=True,
                           stdin=subprocess.DEVNULL, timeout=300, check=False)  # fmt: skip
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("generated music bed not made: %s", exc)
            return ""
        if not os.path.isfile(dest):
            logger.warning("generated music bed not made (ffmpeg wrote nothing)")
            return ""
    last[key] = variant
    try:
        os.makedirs(os.path.dirname(MUSIC_STATE_FILE) or ".", exist_ok=True)
        with open(MUSIC_STATE_FILE, "w", encoding="utf-8") as handle:
            json.dump(last, handle)
    except OSError as exc:
        logger.debug("bed variant not remembered: %s", exc)
    return dest


def library_status_line(channel_id: str | None) -> str:
    """One line for preflight / `ops reliability`."""
    cfg = music_config(channel_id)
    if not cfg["enabled"]:
        return "Music bed: off for this channel"
    n = len(library_tracks(channel_id))
    if not n:  # #1995: a long video still gets the generated pad
        pad = " (long videos: the generated pad)" if synth_enabled() else ""
        return f"Music bed: none - drop royalty-free tracks in {cfg['folder']}{pad}"
    return f"Music bed: {n} track{'s' if n != 1 else ''} in {cfg['folder']}"


def _out_path(explicit: str | None) -> str:
    if explicit:
        return explicit
    from config.paths import DATA_DIR, ensure_data_dir

    ensure_data_dir()
    tmp = os.path.join(DATA_DIR, "tmp", "music")
    os.makedirs(tmp, exist_ok=True)
    return os.path.join(tmp, f"bed_{uuid.uuid4().hex[:12]}")


def generate_bed(mood: str, duration: float, *, out_path: str | None = None) -> ProviderResult:
    """Return a `ProviderResult` whose `data` is a path to a music-bed file, or fail-open."""
    provider = selected_provider("MUSIC_PROVIDER", "none")
    if provider in ("", "none"):
        return ProviderResult.fail_open(SLOT, "MUSIC_PROVIDER unset", status=STATUS_NOT_CONFIGURED)
    if provider != "musicgen":
        return ProviderResult.fail_open(
            SLOT, f"unknown provider {provider!r}", status=STATUS_NOT_CONFIGURED
        )
    try:
        from audiocraft.data.audio import audio_write  # optional extra
        from audiocraft.models import MusicGen
    except Exception as exc:
        return ProviderResult.fail_open(
            SLOT, f"audiocraft not installed: {exc}", status=STATUS_NOT_CONFIGURED
        )
    try:
        model = MusicGen.get_pretrained(os.getenv("MUSICGEN_MODEL", "facebook/musicgen-small"))
        model.set_generation_params(duration=max(1.0, float(duration)))
        wav = model.generate([f"{mood} background music, instrumental, loopable"])
        base = _out_path(out_path)
        audio_write(base, wav[0].cpu(), model.sample_rate, strategy="loudness")
        return ProviderResult.success(SLOT, "musicgen", data=f"{base}.wav")
    except Exception as exc:
        logger.warning("musicgen bed failed (mood=%s): %s", mood, exc)
        return ProviderResult.fail_open(SLOT, str(exc), status=STATUS_ERROR)
