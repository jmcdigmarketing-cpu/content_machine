"""#270: waveform under the player from existing audio. No new TTS spend."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from video.intro_waveform import describe_intro_waveform

_WAV = {".wav"}


def under_player_waveform(audio_path: str, dest_path: str) -> str:
    source = Path(audio_path)
    wav_path = source
    tmp: str | None = None
    if source.suffix.lower() not in _WAV:
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", str(source), "-ac", "1", tmp],
            capture_output=True,
            check=False,
            timeout=20,
        )
        if proc.returncode != 0:
            Path(tmp).unlink(missing_ok=True)
            raise OSError(proc.stderr[-200:] if proc.stderr else f"ffmpeg failed for {audio_path}")
        wav_path = Path(tmp)
    result = describe_intro_waveform(str(wav_path), dest_path=dest_path)
    if tmp:
        Path(tmp).unlink(missing_ok=True)
    if not result.ok or not result.path:
        raise OSError(result.line or f"waveform failed for {audio_path}")
    return result.path
