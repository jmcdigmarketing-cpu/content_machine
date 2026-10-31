"""A cover from the video's own footage, never one another video used (decision 85; look_and_feel.md
L1 + L2 + L8, wave 135).

The covers were AI images from one prompt per genre, so every GTA cover looked alike, and two GTA 6
Shorts opened on one dark car. A cover is now a frame of the video's own shots - taken before the
captions are burned in, so it is clean, with no words - scored for sharpness, brightness and
something in the middle of the frame. A frame whose 64-bit difference hash is within
`NEAR_BITS` of a cover already used is refused and the next taken (`data/covers.json`). The fast
cut then opens on the shot the cover came from (L8), so the feed, the tile and the cover agree.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from core.logging import get_logger

logger = get_logger("assets.cover_frames")

NEAR_BITS = 10  # of 64: closer than this is the same picture
MIN_BRIGHT = 45.0  # the fast cut's own dark-shot floor (_MIN_LUMA)
MIN_SHARP = 60.0  # edge variance under this is motion blur or a flat screen
SUFFIX = "_frame_cover.jpg"  # the upload's "frames" mode sends only these


@dataclass
class Cover:
    index: int  # the shot it came from
    path: str
    hash: int
    score: float


def _file() -> str:
    from config import paths

    return paths.COVERS_FILE


def frame_at(video: str, at: float, dest: str) -> str:
    """One frame of `video` at `at` seconds as a JPEG, "" when it could not be read."""
    try:
        subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{max(0.0, at):.2f}", "-i", video,
             "-frames:v", "1", "-q:v", "2", dest],
            capture_output=True, stdin=subprocess.DEVNULL, timeout=60, check=False,
        )  # fmt: skip
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("cover frame unread (%s): %s", video, exc)
        return ""
    return dest if os.path.isfile(dest) else ""


def frame_score(image: Any) -> dict[str, float]:
    """{bright, sharp, centre, score}: mean luma, edge variance, the share of edges in the middle
    half (something in frame, not a blank sky), and their product - 0 when dark or blurred."""
    from PIL import ImageFilter, ImageStat

    gray = image.convert("L").resize((180, 320))
    bright = float(ImageStat.Stat(gray).mean[0])
    edges = gray.filter(ImageFilter.FIND_EDGES)
    sharp = float(ImageStat.Stat(edges).var[0])
    total = float(ImageStat.Stat(edges).sum[0]) or 1.0
    middle = edges.crop((45, 80, 135, 240))
    centre = float(ImageStat.Stat(middle).sum[0]) / total
    ok = bright >= MIN_BRIGHT and sharp >= MIN_SHARP
    score = (min(sharp, 2000.0) / 2000.0) * (0.5 + centre) * min(bright, 160.0) / 160.0 if ok else 0.0
    return {"bright": round(bright, 1), "sharp": round(sharp, 1), "centre": round(centre, 3),
            "score": round(score, 4)}  # fmt: skip


def dhash(image: Any) -> int:
    """A 64-bit difference hash - near-identical pictures differ in a few bits."""
    gray = image.convert("L").resize((9, 8))
    px = list(gray.getdata())
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (1 if px[row * 9 + col] > px[row * 9 + col + 1] else 0)
    return bits


def near(a: int, b: int, *, bits: int = NEAR_BITS) -> bool:
    return bin(a ^ b).count("1") < bits


def used_covers() -> list[dict[str, Any]]:
    try:
        with open(_file(), encoding="utf-8") as handle:
            rows = (json.load(handle) or {}).get("covers") or []
    except (OSError, ValueError, AttributeError):
        return []
    return [r for r in rows if isinstance(r, dict) and r.get("hash")]


def record_cover(cover_hash: int, path: str, *, when: datetime | None = None) -> None:
    """L2: this picture is taken. Fail-open."""
    try:
        rows = used_covers()
        rows.append({"hash": f"{cover_hash:016x}", "path": path,
                     "at": (when or datetime.now(timezone.utc)).isoformat()})  # fmt: skip
        target = _file()
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        tmp = f"{target}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump({"covers": rows[-500:]}, handle)
        os.replace(tmp, target)
    except Exception as exc:
        logger.debug("cover not recorded: %s", exc)


def choose_cover(shots: list[str], lengths: list[float], dest_stem: str) -> Cover | None:
    """L1 + L2: the best-scored frame of the shots, 40% into each, whose picture no earlier cover
    (nor an earlier candidate here) shares. None when no shot gives a usable frame."""
    from PIL import Image

    taken = [int(str(r["hash"]), 16) for r in used_covers()]
    best: Cover | None = None
    for index, (shot, length) in enumerate(zip(shots, lengths, strict=False)):
        path = frame_at(shot, 0.4 * float(length), f"{dest_stem}_cand{index:02d}.jpg")
        if not path:
            continue
        with Image.open(path) as image:
            scored = frame_score(image)
            picture = dhash(image)
        if scored["score"] <= 0 or any(near(picture, h) for h in taken):
            continue
        taken.append(picture)
        if best is None or scored["score"] > best.score:
            best = Cover(index=index, path=path, hash=picture, score=scored["score"])
    return best


def finish(cover: Cover, dest_stem: str) -> str:
    """Keep the chosen frame as the video's cover file and record it; the candidates go."""
    final = f"{dest_stem}{SUFFIX}"
    try:
        os.replace(cover.path, final)
    except OSError:
        return ""
    for name in os.listdir(os.path.dirname(final) or "."):
        if name.startswith(os.path.basename(dest_stem) + "_cand"):
            try:
                os.remove(os.path.join(os.path.dirname(final) or ".", name))
            except OSError:
                pass
    record_cover(cover.hash, final)
    return final


def strip_lines(new_path: str, *, last: int = 10) -> list[str]:
    """L10: the new cover beside the last ten - each one's distance in bits, a repeat flagged."""
    from PIL import Image

    try:
        with Image.open(new_path) as image:
            mine = dhash(image)
    except OSError:
        return [f"Cover: {new_path} (unreadable)"]
    rows = [r for r in used_covers() if r.get("path") != new_path][-last:]
    lines = [f"Cover: {new_path}"]
    for row in reversed(rows):
        bits = bin(mine ^ int(str(row["hash"]), 16)).count("1")
        flag = "  <- the same picture" if bits < NEAR_BITS else ""
        lines.append(f"  {bits:>2} bits from {os.path.basename(str(row.get('path')))}{flag}")
    return lines
