"""#672: prove TapIn grain actually changes pixel variance."""

from __future__ import annotations

import os
import subprocess

from video.render_video import look_filter_fragment


def measure_look_noise(work_dir: str, *, channel_id: str = "tapin") -> dict[str, float] | None:
    """Encode a flat frame with and without the look filter; return stddevs."""
    from PIL import Image

    fragment = look_filter_fragment(channel_id)
    if "noise=" not in fragment:
        return None
    plain = os.path.join(work_dir, "plain.png")
    looked = os.path.join(work_dir, "look.png")
    src = os.path.join(work_dir, "src.png")
    Image.new("RGB", (64, 64), (90, 90, 90)).save(src)
    if not _ffmpeg_filter(src, plain, "null"):
        return None
    filt = fragment.rstrip(",")
    if not _ffmpeg_filter(src, looked, filt):
        return None
    return {
        "plain": _stddev(plain),
        "with_look": _stddev(looked),
    }


def _ffmpeg_filter(src: str, dest: str, filt: str) -> bool:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        src,
        "-vf",
        filt,
        "-frames:v",
        "1",
        dest,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    except Exception:
        return False
    return proc.returncode == 0 and os.path.isfile(dest)


def _stddev(path: str) -> float:
    from PIL import Image, ImageStat

    stat = ImageStat.Stat(Image.open(path).convert("L"))
    return float(stat.stddev[0])
