"""Post-encode audiovisual acceptance checks (#414, #420, #498).

This is technical quality control, not an editorial grade.  It uses the
installed FFmpeg/ffprobe binaries and reports unavailable checks explicitly;
absence of a finding is never converted into a pass.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Any

_BLACK_RE = re.compile(r"\bblack_start\s*:\s*([0-9.]+)", re.I)
_FREEZE_RE = re.compile(r"\bfreeze_start(?:\s*:|\s*=)\s*([0-9.]+)", re.I)
_LOUDNESS_JSON_RE = re.compile(r'\{\s*"input_i".*?\}', re.S)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def loudness_targets() -> dict[str, float]:
    """One source for render targets and post-encode acceptance tolerances."""
    return {
        "integrated": _env_float("LUFS_TARGET_I", -14.0),
        "true_peak": _env_float("LUFS_TARGET_TP", -1.5),
        "range_target": _env_float("LUFS_TARGET_LRA", 11.0),
        "integrated_tolerance": _env_float("LUFS_TOLERANCE", 2.0),
        "range_min": _env_float("LUFS_RANGE_MIN", 1.0),
        "av_tolerance": _env_float("AV_DURATION_TOLERANCE_SECONDS", 0.25),
    }


@dataclass(frozen=True)
class TechnicalQC:
    status: str
    passed: bool
    path: str
    has_video: bool = False
    has_audio: bool = False
    width: int | None = None
    height: int | None = None
    video_duration: float | None = None
    audio_duration: float | None = None
    integrated_lufs: float | None = None
    true_peak_dbfs: float | None = None
    loudness_range_lu: float | None = None
    black_intervals: int = 0
    freeze_intervals: int = 0
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _duration(stream: dict[str, Any], fallback: float | None) -> float | None:
    return _number(stream.get("duration")) or fallback


def _run(command: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _loudness_values(ffmpeg: str, path: str, targets: dict[str, float]):
    proc = _run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            path,
            "-af",
            (
                f"loudnorm=I={targets['integrated']}:TP={targets['true_peak']}:"
                f"LRA={targets['range_target']}:print_format=json"
            ),
            "-f",
            "null",
            "-",
        ],
        timeout=45,
    )
    matches = _LOUDNESS_JSON_RE.findall(proc.stderr or "")
    if proc.returncode != 0 or not matches:
        return None, None, None
    try:
        payload = json.loads(matches[-1])
    except (TypeError, ValueError, json.JSONDecodeError):
        return None, None, None
    return (
        _number(payload.get("input_i")),
        _number(payload.get("input_tp")),
        _number(payload.get("input_lra")),
    )


def inspect_technical_qc(
    path: str,
    *,
    expected_size: tuple[int, int] | None = None,
) -> TechnicalQC:
    """Inspect a finished video. Never raises; unavailable is not a pass."""
    source = str(path or "")
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        return TechnicalQC(
            status="unavailable",
            passed=False,
            path=source,
            issues=["ffmpeg/ffprobe unavailable; technical QC did not run"],
        )
    if not os.path.isfile(source):
        return TechnicalQC(
            status="unavailable",
            passed=False,
            path=source,
            issues=["render file missing; technical QC did not run"],
        )

    try:
        probe = _run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,width,height,duration",
                "-of",
                "json",
                source,
            ]
        )
        if probe.returncode != 0:
            return TechnicalQC(
                status="unavailable",
                passed=False,
                path=source,
                issues=["ffprobe could not read the render; technical QC did not run"],
            )
        payload = json.loads(probe.stdout or "{}")
        streams = payload.get("streams") if isinstance(payload, dict) else []
        streams = streams if isinstance(streams, list) else []
        video = next(
            (row for row in streams if isinstance(row, dict) and row.get("codec_type") == "video"),
            {},
        )
        audio = next(
            (row for row in streams if isinstance(row, dict) and row.get("codec_type") == "audio"),
            {},
        )
        format_duration = _number((payload.get("format") or {}).get("duration"))
        video_duration = _duration(video, format_duration) if video else None
        audio_duration = _duration(audio, format_duration) if audio else None
        raw_width = video.get("width")
        raw_height = video.get("height")
        width = int(raw_width) if raw_width is not None else None
        height = int(raw_height) if raw_height is not None else None
    except Exception as exc:
        return TechnicalQC(
            status="unavailable",
            passed=False,
            path=source,
            issues=[f"technical probe failed: {type(exc).__name__}"],
        )

    issues: list[str] = []
    has_video = bool(video)
    has_audio = bool(audio)
    if not has_video:
        issues.append("missing video stream")
    if not has_audio:
        issues.append("missing audio stream")
    if expected_size and (width, height) != expected_size:
        issues.append(
            f"resolution {width or '?'}x{height or '?'}; expected "
            f"{expected_size[0]}x{expected_size[1]}"
        )

    targets = loudness_targets()
    if (
        video_duration is not None
        and audio_duration is not None
        and abs(video_duration - audio_duration) > targets["av_tolerance"]
    ):
        issues.append(f"audio/video duration mismatch {abs(video_duration - audio_duration):.2f}s")

    analysis_status = "evaluated"
    black_count = 0
    freeze_count = 0
    if has_video:
        frame_probe = _run(
            [
                ffmpeg,
                "-hide_banner",
                "-nostats",
                "-i",
                source,
                "-vf",
                "blackdetect=d=0.25:pix_th=0.10,freezedetect=n=-60dB:d=1.0",
                "-an",
                "-f",
                "null",
                "-",
            ],
            timeout=45,
        )
        if frame_probe.returncode != 0:
            analysis_status = "partial"
            issues.append("black/freeze analysis unavailable")
        else:
            stderr = frame_probe.stderr or ""
            black_count = len(_BLACK_RE.findall(stderr))
            freeze_count = len(_FREEZE_RE.findall(stderr))
            if black_count:
                issues.append(f"{black_count} black interval(s) detected")
            if freeze_count:
                issues.append(f"{freeze_count} frozen interval(s) detected")

    integrated = peak = loudness_range = None
    if has_audio:
        integrated, peak, loudness_range = _loudness_values(ffmpeg, source, targets)
        if integrated is None or peak is None or loudness_range is None:
            analysis_status = "partial"
            issues.append("audio loudness analysis unavailable or silent")
        else:
            if (
                os.getenv("LUFS_NORMALIZE", "").strip().lower()
                in (
                    "1",
                    "true",
                    "yes",
                    "on",
                )
                and abs(integrated - targets["integrated"]) > targets["integrated_tolerance"]
            ):
                issues.append(
                    f"integrated loudness {integrated:.1f} LUFS misses "
                    f"{targets['integrated']:.1f} LUFS target"
                )
            if peak > targets["true_peak"]:
                issues.append(f"true peak {peak:.1f} dBFS exceeds {targets['true_peak']:.1f} dBFS")
            if loudness_range < targets["range_min"]:
                issues.append(
                    f"loudness range {loudness_range:.1f} LU is below "
                    f"{targets['range_min']:.1f} LU"
                )

    return TechnicalQC(
        status=analysis_status,
        passed=analysis_status == "evaluated" and not issues,
        path=source,
        has_video=has_video,
        has_audio=has_audio,
        width=width,
        height=height,
        video_duration=video_duration,
        audio_duration=audio_duration,
        integrated_lufs=integrated,
        true_peak_dbfs=peak,
        loudness_range_lu=loudness_range,
        black_intervals=black_count,
        freeze_intervals=freeze_count,
        issues=issues,
    )


def render_technical_qc(result: TechnicalQC) -> str:
    if result.status == "unavailable":
        return f"Technical QC UNAVAILABLE: {'; '.join(result.issues)}"
    status = "PASS" if result.passed else "ADVISORY"
    measured = []
    if result.integrated_lufs is not None:
        measured.append(f"{result.integrated_lufs:.1f} LUFS")
    if result.true_peak_dbfs is not None:
        measured.append(f"peak {result.true_peak_dbfs:.1f} dBFS")
    if result.loudness_range_lu is not None:
        measured.append(f"LRA {result.loudness_range_lu:.1f} LU")
    suffix = f" ({', '.join(measured)})" if measured else ""
    detail = "; ".join(result.issues) if result.issues else "streams and sampled frames OK"
    return f"Technical QC {status}: {detail}{suffix}"
