"""CUDA / GPU readiness (candidate 70).

Windows-safe diagnostic only: never installs CUDA, never pip-installs torch,
never downloads weights. Nested try so an optional torch import cannot wipe
caller state (reliability / doctor).
"""

from __future__ import annotations

import os
import shutil
from typing import Any

from core.logging import get_logger

logger = get_logger("core.cuda_probe")


def probe() -> dict[str, Any]:
    """Read-only snapshot of torch/CUDA/nvidia-smi. Fail-open, no GPU work."""
    out: dict[str, Any] = {
        "torch_version": None,
        "cuda_available": False,
        "cuda_built": False,
        "nvidia_smi": False,
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
    if smi:
        out["nvenc_hint"] = "nvidia-smi present; NVENC encode is candidate 38 (not this probe)"
    elif out["cuda_available"]:
        out["nvenc_hint"] = "torch CUDA yes, nvidia-smi missing from PATH"
    else:
        out["nvenc_hint"] = "no CUDA torch / no nvidia-smi — CPU torch is the current gate"

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
    lines = [
        "CUDA / GPU readiness (no install, no download)",
        f"  torch     : {tv}",
        f"  cuda built: {built}",
        f"  cuda avail: {cuda}",
        f"  nvidia-smi: {smi}",
        f"  note      : {data.get('nvenc_hint') or ''}",
    ]
    if data.get("torch_error"):
        lines.append(f"  import    : {data['torch_error']} (CPU torch remains the gate)")
    return "\n".join(lines)
