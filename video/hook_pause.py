"""#124 Pause-after-hook: 200–400ms of silence after spoken line 1.

Fail-open and byte-identical when word timings are missing (same honesty as
#24/#26). A `.hookpause` marker next to the audio prevents a second apply.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile

from core.logging import get_logger

logger = get_logger("video.hook_pause")

HOOK_PAUSE_SECONDS = 0.25
_MARKER_SUFFIX = ".hookpause"


def first_line_end_seconds(words: list[dict] | None, script: str) -> float | None:
    """End time of the last timed word in the first sentence, or None."""
    if not words:
        return None
    first = (script or "").replace("!", ".").replace("?", ".").split(".", 1)[0].strip()
    if not first:
        return None
    n = len(first.split())
    if n < 1 or n > len(words):
        return None
    try:
        end = float(words[n - 1].get("end"))
    except (TypeError, ValueError, KeyError):
        return None
    if end <= 0:
        return None
    return end


def _marker_path(audio_path: str) -> str:
    return audio_path + _MARKER_SUFFIX


def _shift_sidecar(audio_path: str, after: float, delta: float) -> None:
    sidecar = audio_path + ".words.json"
    if not os.path.isfile(sidecar):
        return
    try:
        with open(sidecar, encoding="utf-8") as fh:
            words = json.load(fh)
        if not isinstance(words, list):
            return
        for item in words:
            if not isinstance(item, dict):
                continue
            start = item.get("start")
            end = item.get("end")
            if start is not None and float(start) >= after:
                item["start"] = float(start) + delta
            if end is not None and float(end) >= after:
                item["end"] = float(end) + delta
        with open(sidecar, "w", encoding="utf-8") as fh:
            json.dump(words, fh)
    except Exception as exc:
        logger.debug("hook-pause sidecar shift skipped: %s", exc)


def maybe_insert_hook_pause(
    audio_path: str,
    *,
    words: list[dict] | None,
    script: str,
) -> bool:
    """Insert HOOK_PAUSE_SECONDS of silence after line 1. False = untouched bytes."""
    if not audio_path or not os.path.isfile(audio_path):
        return False
    if os.path.isfile(_marker_path(audio_path)):
        return False
    end = first_line_end_seconds(words, script)
    if end is None:
        logger.debug("hook pause skipped: no first-line timings")
        return False
    pause = HOOK_PAUSE_SECONDS
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
    os.close(tmp_fd)
    graph = (
        f"[0:a]atrim=0:{end:.3f},asetpts=PTS-STARTPTS[a];"
        f"anullsrc=r=24000:cl=mono,atrim=0:{pause:.3f},asetpts=PTS-STARTPTS[p];"
        f"[0:a]atrim=start={end:.3f},asetpts=PTS-STARTPTS[b];"
        f"[a][p][b]concat=n=3:v=0:a=1[out]"
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        audio_path,
        "-filter_complex",
        graph,
        "-map",
        "[out]",
        tmp_path,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
        if proc.returncode != 0:
            logger.debug("hook pause ffmpeg skipped: %s", (proc.stderr or "")[-300:])
            return False
        if os.path.isfile(tmp_path) and os.path.getsize(tmp_path) > 0:
            os.replace(tmp_path, audio_path)
        _shift_sidecar(audio_path, after=end, delta=pause)
        try:
            with open(_marker_path(audio_path), "w", encoding="utf-8") as fh:
                fh.write(f"{pause}\n")
        except Exception as exc:
            logger.debug("hook-pause marker skipped: %s", exc)
        return True
    except Exception as exc:
        logger.debug("hook pause skipped: %s", exc)
        return False
    finally:
        if os.path.isfile(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
