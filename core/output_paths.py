"""Channel-scoped output directories for audio, video, and thumbnails."""

from __future__ import annotations

import os
from datetime import datetime

from config.channels import get_channel_profile, resolve_channel_id
from core.logging import get_logger

logger = get_logger("core.output_paths")

# Windows MAX_PATH is 260 including NUL. Leave headroom for .mp3/.mp4 and dirs.
_DEFAULT_MAX_PATH = 240


def max_path_limit() -> int:
    raw = os.getenv("WIN_MAX_PATH", str(_DEFAULT_MAX_PATH)).strip()
    try:
        return max(80, int(raw))
    except ValueError:
        return _DEFAULT_MAX_PATH


def long_paths_enabled() -> bool:
    return os.getenv("WIN_LONG_PATHS", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def windows_long_prefix(path: str) -> str:
    """Prefix \\\\?\\ so ffmpeg/upload can open paths past MAX_PATH when needed."""
    if os.name != "nt" or not path:
        return path
    ap = os.path.abspath(path)
    if ap.startswith("\\\\?\\"):
        return ap
    if len(ap) <= max_path_limit() or not long_paths_enabled():
        return ap
    if ap.startswith("\\\\"):
        return "\\\\?\\UNC\\" + ap.lstrip("\\")
    return "\\\\?\\" + ap


def _clip_filename(directory: str, base: str, ext: str) -> str:
    """Shorten `base` so abspath(directory/base+ext) stays under WIN_MAX_PATH."""
    filename = f"{base}{ext}"
    path = os.path.join(directory, filename)
    overflow = len(os.path.abspath(path)) - max_path_limit()
    if overflow <= 0:
        return filename
    keep = max(8, len(base) - overflow)
    clipped = f"{base[:keep]}{ext}"
    logger.warning(
        "Output name clipped for MAX_PATH (%s -> %s)",
        filename[:48],
        clipped,
    )
    return clipped


def channel_output_root(channel_id: str | None = None) -> str:
    """e.g. output/tapin or output/default"""
    cid = resolve_channel_id(channel_id)
    profile = get_channel_profile(cid)
    subdir = getattr(profile, "output_subdir", None) or cid
    return os.path.join("output", subdir)


def ensure_channel_output_dirs(channel_id: str | None = None) -> dict[str, str]:
    root = channel_output_root(channel_id)
    dirs = {
        "root": root,
        "audio": os.path.join(root, "audio"),
        "video": os.path.join(root, "video"),
        "thumbnails": os.path.join(root, "thumbnails"),
    }
    for path in dirs.values():
        os.makedirs(path, exist_ok=True)
    return dirs


def media_paths_for_topic(
    topic: str,
    *,
    channel_id: str | None = None,
    timestamp: str | None = None,
) -> tuple[str, str, str]:
    """
    Return (mp3_path, mp4_filename, mp4_path) for a render.
    """
    dirs = ensure_channel_output_dirs(channel_id)
    ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = (
        "".join(c for c in topic if c.isalnum() or c == " ").strip().replace(" ", "_").lower()
    )
    base = f"{safe_title}_{ts}"
    mp4_filename = _clip_filename(dirs["video"], base, ".mp4")
    stem = mp4_filename[: -len(".mp4")] if mp4_filename.lower().endswith(".mp4") else base
    mp3_name = _clip_filename(dirs["audio"], stem, ".mp3")
    mp3_path = os.path.join(dirs["audio"], mp3_name)
    mp4_path = os.path.join(dirs["video"], mp4_filename)
    return mp3_path, mp4_filename, mp4_path
