"""RAM/VRAM preflight before whisper / local TTS (candidate 95).

Opt-in floors so Free mode does not OOM mid-run. Empty/0/off = disabled so the
unit suite cannot abort on a small CI box. Nested try; ASCII `>=`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, ClassVar

from core.logging import get_logger

logger = get_logger("core.ram_preflight")


def _env_gb(name: str) -> float | None:
    raw = os.getenv(name, "").strip().lower()
    if raw in ("", "0", "off", "false", "no"):
        return None
    try:
        val = float(raw)
    except ValueError:
        return None
    return val if val > 0 else None


def min_ram_gb() -> float | None:
    return _env_gb("RAM_MIN_GB")


def min_vram_gb() -> float | None:
    return _env_gb("VRAM_MIN_GB")


def available_ram_gb() -> float | None:
    """Available physical RAM in GB, or None if the probe fails."""
    if os.name == "nt":
        try:
            import ctypes

            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_: ClassVar = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = _MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return None
            return float(stat.ullAvailPhys) / (1024**3)
        except Exception as exc:
            logger.debug("GlobalMemoryStatusEx skipped: %s", exc)
    try:
        page = os.sysconf("SC_PAGE_SIZE")
        avail = os.sysconf("SC_AVPHYS_PAGES")
        return float(page * avail) / (1024**3)
    except Exception as exc:
        logger.debug("sysconf RAM skipped: %s", exc)
        return None


def available_vram_gb() -> float | None:
    """Free GPU memory in GB via nvidia-smi. None when missing. Never loads CUDA."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return None
    try:
        creation = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            [
                smi,
                "--query-gpu=memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
            check=False,
            creationflags=creation,
        )
        line = (result.stdout or "").strip().splitlines()[0] if result.stdout else ""
        mb = float(line.split(",")[0].strip())
        return mb / 1024.0
    except Exception as exc:
        logger.debug("nvidia-smi VRAM skipped: %s", exc)
        return None


def snapshot() -> dict[str, Any]:
    ram = available_ram_gb()
    vram = available_vram_gb()
    return {
        "ram_gb": ram,
        "vram_gb": vram,
        "ram_min_gb": min_ram_gb(),
        "vram_min_gb": min_vram_gb(),
    }


def block_reason(*, kind: str = "whisper") -> str | None:
    """Why whisper/local TTS should not start, or None. Missing probe fail-opens."""
    need_ram = min_ram_gb()
    ram = available_ram_gb()
    if need_ram is not None and ram is not None and ram < need_ram:
        return (
            f"{kind} preflight: {ram:.2f} GB RAM free, need >= {need_ram:.2f} GB "
            "(refusing so Free mode does not OOM mid-run)"
        )
    need_vram = min_vram_gb()
    vram = available_vram_gb()
    if need_vram is not None and vram is not None and vram < need_vram:
        return (
            f"{kind} preflight: {vram:.2f} GB VRAM free, need >= {need_vram:.2f} GB "
            "(refusing so Free mode does not OOM mid-run)"
        )
    return None


def render(data: dict[str, Any] | None = None) -> str:
    data = data or snapshot()
    ram = data.get("ram_gb")
    vram = data.get("vram_gb")
    ram_s = f"{ram:.2f} GB" if isinstance(ram, int | float) else "n/a"
    vram_s = f"{vram:.2f} GB" if isinstance(vram, int | float) else "n/a"
    return f"RAM {ram_s} free; VRAM {vram_s} free"
