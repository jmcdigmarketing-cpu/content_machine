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
