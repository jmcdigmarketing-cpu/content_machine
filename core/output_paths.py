"""Channel-scoped output directories for audio, video, and thumbnails."""

from __future__ import annotations

import os
from datetime import datetime

from config.channels import get_channel_profile, resolve_channel_id


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
    mp4_filename = f"{base}.mp4"
    mp3_path = os.path.join(dirs["audio"], f"{base}.mp3")
    mp4_path = os.path.join(dirs["video"], mp4_filename)
    return mp3_path, mp4_filename, mp4_path
