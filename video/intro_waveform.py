"""#188. Show sting duration vs the 2.15s TapIn offset without re-deriving it."""

from __future__ import annotations

import math
import struct
import wave
from dataclasses import dataclass
from pathlib import Path

from core.logging import get_logger
from video.channel_intro import DEFAULT_INTRO_DURATION

logger = get_logger("video.intro_waveform")


@dataclass(frozen=True)
class IntroWaveform:
    ok: bool
    line: str
    duration_seconds: float = 0.0
    offset_seconds: float = 0.0
    path: str = ""


def describe_intro_waveform(
    audio_path: str,
    *,
    dest_path: str = "",
    channel_id: str | None = None,
) -> IntroWaveform:
    del channel_id  # reserved for a per-channel offset
    path = Path(audio_path)
    if not path.is_file():
        logger.debug("intro waveform skipped; file not found: %s", audio_path)
        return IntroWaveform(ok=False, line=f"intro file not found: {audio_path}")
    try:
        duration, samples = _read_mono_samples(path)
    except (OSError, wave.Error, struct.error, ValueError) as exc:
        logger.debug("intro waveform unreadable %s: %s", audio_path, exc)
        return IntroWaveform(ok=False, line=f"intro file not found: {audio_path}")
    offset = float(DEFAULT_INTRO_DURATION)
    dest = Path(dest_path) if dest_path else path.with_suffix(".waveform.png")
    _draw_waveform(samples, dest)
    line = f"sting {duration:.1f}s (offset {offset:.2f}s) -> {dest}"
    return IntroWaveform(
        ok=True,
        line=line,
        duration_seconds=duration,
        offset_seconds=offset,
        path=str(dest),
    )


def _read_mono_samples(path: Path) -> tuple[float, list[float]]:
    with wave.open(str(path), "rb") as fh:
        channels = fh.getnchannels()
        width = fh.getsampwidth()
        rate = fh.getframerate()
        nframes = fh.getnframes()
        raw = fh.readframes(nframes)
    if rate <= 0 or nframes <= 0 or width not in (1, 2):
        raise ValueError("unsupported wav")
    duration = nframes / float(rate)
    samples: list[float] = []
    if width == 2:
        count = len(raw) // 2
        fmt = "<" + "h" * count
        values = struct.unpack(fmt, raw[: count * 2])
        step = max(1, channels)
        samples = [v / 32768.0 for v in values[::step]]
    else:
        step = max(1, channels)
        samples = [(b - 128) / 128.0 for b in raw[::step]]
    return duration, samples


def _draw_waveform(samples: list[float], dest: Path) -> None:
    from PIL import Image, ImageDraw

    width, height = 640, 160
    image = Image.new("RGB", (width, height), (11, 15, 20))
    draw = ImageDraw.Draw(image)
    mid = height // 2
    draw.line((0, mid, width, mid), fill=(42, 47, 58))
    if samples:
        bucket = max(1, len(samples) // width)
        for x in range(width):
            chunk = samples[x * bucket : (x + 1) * bucket]
            if not chunk:
                continue
            amp = min(1.0, math.sqrt(sum(v * v for v in chunk) / len(chunk)) * 2.5)
            y = int(amp * (height * 0.45))
            draw.line((x, mid - y, x, mid + y), fill=(247, 231, 169))
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest)
