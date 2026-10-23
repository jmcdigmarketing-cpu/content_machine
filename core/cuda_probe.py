"""CUDA / GPU readiness (candidate 70).

Windows-safe diagnostic only: never installs CUDA, never pip-installs torch,
never downloads weights. Nested try so an optional torch import cannot wipe
caller state (reliability / doctor).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

from core.logging import get_logger

logger = get_logger("core.cuda_probe")


def ffmpeg_has_nvenc() -> bool:
    """True when `ffmpeg -encoders` lists h264_nvenc. Never encodes. Fail-open."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    try:
        creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
            creationflags=creation,
        )
        blob = (result.stdout or "") + (result.stderr or "")
        return "h264_nvenc" in blob
    except Exception as exc:
        logger.debug("ffmpeg NVENC probe skipped: %s", exc)
        return False


# #1470 (S17): the driver FFmpeg's NVENC (SDK 12.2, FFmpeg 7's Windows builds) needs. A native
# crash in a render is the S17 class; the driver it ran on is the first thing to know.
_NVENC_MIN_DRIVER = "551.76"


def gpu_driver() -> tuple[str, str] | None:
    """(GPU name, driver version) from nvidia-smi, or None without one. No window, 5 s."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return None
    try:
        creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            [smi, "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            check=False,
            creationflags=creation,
        )
        first = (result.stdout or "").strip().splitlines()[0]
        name, _sep, version = first.rpartition(",")
    except Exception as exc:
        logger.debug("nvidia-smi driver query skipped: %s", exc)
        return None
    return (name.strip(), version.strip()) if name.strip() and version.strip() else None


def _version(text: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in str(text).strip().split("."))
    except ValueError:
        return ()


def driver_check(data: dict[str, Any]) -> tuple[bool, str]:
    """(ok, line) for `ops doctor`'s gpu row: the GPU and its driver, failing under the NVENC
    floor (`NVENC_MIN_DRIVER`). No NVIDIA driver passes - the render encodes on the CPU."""
    name, version = data.get("gpu_name"), data.get("driver_version")
    if not name or not version:
        return True, "no NVIDIA driver found (the render encodes on the CPU)"
    floor = (os.getenv("NVENC_MIN_DRIVER") or _NVENC_MIN_DRIVER).strip()
    have, need = _version(str(version)), _version(floor)
    if have and need and have < need:
        return False, (
            f"{name}, driver {version} - update the NVIDIA driver: FFmpeg's NVENC needs {floor} "
            "or later"
        )
    return True, f"{name}, driver {version}"


def probe() -> dict[str, Any]:
    """Read-only snapshot of torch/CUDA/nvidia-smi/NVENC. Fail-open, no GPU work."""
    out: dict[str, Any] = {
        "torch_version": None,
        "cuda_available": False,
        "cuda_built": False,
        "nvidia_smi": False,
        "nvenc_capable": False,
        "nvenc_hint": "",
    }
    try:
        import torch  # type: ignore[import-not-found]

        out["torch_version"] = str(getattr(torch, "__version__", "") or "?")
        try:
            out["cuda_built"] = bool(getattr(torch.version, "cuda", None))
        except Exception as exc:
            logger.debug("torch.version.cuda skipped: %s", exc)
        try:
            out["cuda_available"] = bool(torch.cuda.is_available())
        except Exception as exc:
            logger.debug("torch.cuda.is_available skipped: %s", exc)
            out["cuda_available"] = False
    except Exception as exc:
        logger.debug("torch import skipped: %s", exc)
        out["torch_error"] = type(exc).__name__

    smi = shutil.which("nvidia-smi")
    out["nvidia_smi"] = bool(smi)
    driver = gpu_driver() if smi else None
    if driver:
        out["gpu_name"], out["driver_version"] = driver  # #1470
    out["nvenc_capable"] = ffmpeg_has_nvenc()
    if out["nvenc_capable"]:
        out["nvenc_hint"] = "h264_nvenc listed by ffmpeg (capability only; encode is candidate 38)"
    elif smi:
        out["nvenc_hint"] = "nvidia-smi present; ffmpeg has no h264_nvenc (driver/ffmpeg build)"
    elif out["cuda_available"]:
        out["nvenc_hint"] = "torch CUDA yes, nvidia-smi missing from PATH"
    else:
        out["nvenc_hint"] = "no CUDA torch / no nvidia-smi — CPU libx264 is the current gate"

    # Electricity line stays $0 until CUDA torch is actually on (candidate 70).
    out["gpu_hour_usd"] = 0.0
    try:
        raw = os.getenv("COST_GPU_HOUR_USD", "").strip()
        if raw and raw.lower() not in ("0", "off", "false", "no"):
            out["gpu_hour_usd"] = max(0.0, float(raw))
    except (TypeError, ValueError):
        out["gpu_hour_usd"] = 0.0
    return out


def render(data: dict[str, Any] | None = None) -> str:
    data = data or probe()
    tv = data.get("torch_version") or "not installed"
    cuda = "yes" if data.get("cuda_available") else "no"
    built = "yes" if data.get("cuda_built") else "no"
    smi = "yes" if data.get("nvidia_smi") else "no"
    nvenc = "yes" if data.get("nvenc_capable") else "no"
    lines = [
        "CUDA / GPU readiness (no install, no download)",
        f"  torch     : {tv}",
        f"  cuda built: {built}",
        f"  cuda avail: {cuda}",
        f"  nvidia-smi: {smi}",
        f"  driver    : {data.get('gpu_name') or '-'} {data.get('driver_version') or ''}".rstrip(),
        f"  nvenc     : {nvenc}",
        f"  note      : {data.get('nvenc_hint') or ''}",
    ]
    if data.get("torch_error"):
        lines.append(f"  import    : {data['torch_error']} (CPU torch remains the gate)")
    return "\n".join(lines)
