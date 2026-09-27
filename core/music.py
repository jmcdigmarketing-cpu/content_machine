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


def library_status_line(channel_id: str | None) -> str:
    """One line for preflight / `ops reliability`."""
    cfg = music_config(channel_id)
    if not cfg["enabled"]:
        return "Music bed: off for this channel"
    n = len(library_tracks(channel_id))
    if not n:
        return f"Music bed: none - drop royalty-free tracks in {cfg['folder']}"
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
