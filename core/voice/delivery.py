"""#1039. The hook is a touch faster. Asterisks are emphasis. An ellipsis is a wait.

ElevenLabs multilingual v2 does not honor a break tag, so the ellipsis is taken
out of the request and the next word is held by the join.
"""

from __future__ import annotations

import os
import re
from typing import Any

_EMPHASIS = re.compile(r"\*([^*]+)\*")
_ELLIPSIS = re.compile(r"(?:\.{3}|…)")
HOOK_BUMP = 0.05
EMPHASIS_STYLE = 0.35
ELLIPSIS_PAUSE = 0.3
_SPEED_MIN, _SPEED_MAX = 0.7, 1.2
_PAUSE_SUFFIX = ".delivery_pause"


def delivery_for(text: str, *, hook: bool, speed: float) -> dict[str, Any]:
    """Spoken text, pace, emphasis style, and the seconds to hold after it."""
    spoken = text or ""
    style: float | None = None
    if _EMPHASIS.search(spoken):
        style = EMPHASIS_STYLE
        spoken = _EMPHASIS.sub(r"\1", spoken)
    pause = 0.0
    if _ELLIPSIS.search(spoken):
        spoken = _ELLIPSIS.sub(" ", spoken)
        pause = ELLIPSIS_PAUSE
    spoken = re.sub(r"\s+", " ", spoken).strip()
    pace = float(speed)
    if hook:
        pace = min(_SPEED_MAX, max(_SPEED_MIN, round(pace + HOOK_BUMP, 3)))
    return {"text": spoken, "speed": pace, "style": style, "pause_after": pause}


def write_silence(path: str, seconds: float) -> bool:
    """Write `seconds` of silence. False leaves no file and logs nothing above debug."""
    import subprocess
    import tempfile

    if not path or seconds <= 0:
        return False
    fd, tmp = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"anullsrc=r=24000:cl=mono,atrim=0:{float(seconds):.3f}",
        "-c:a",
        "libmp3lame",
        "-qscale:a",
        "4",
        tmp,
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
        )
        if proc.returncode != 0 or not os.path.isfile(tmp) or os.path.getsize(tmp) <= 0:
            return False
        os.replace(tmp, path)
        return True
    except OSError:
        return False
    finally:
        if os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def note_pause(path: str, seconds: float) -> None:
    """Remember a hold after this segment. The join shifts the next word by it."""
    if not path or seconds <= 0:
        return
    with open(path + _PAUSE_SUFFIX, "w", encoding="utf-8") as handle:
        handle.write(str(seconds))


def pause_after(path: str) -> float:
    marker = path + _PAUSE_SUFFIX
    if not os.path.isfile(marker):
        return 0.0
    try:
        with open(marker, encoding="utf-8") as handle:
            return float(handle.read().strip())
    except (OSError, ValueError):
        return 0.0
