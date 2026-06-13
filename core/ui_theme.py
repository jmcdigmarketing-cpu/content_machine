"""ANSI colors for CLI (Windows Terminal / PowerShell 5.1+ with VT enabled)."""

from __future__ import annotations

import os
import sys


def ui_color_enabled() -> bool:
    if os.getenv("CONTENT_UI_COLOR", "true").lower() in ("0", "false", "no"):
        return False
    if not sys.stdout.isatty():
        return False
    if os.name == "nt":
        try:
            import ctypes

            kernel = ctypes.windll.kernel32
            handle = kernel.GetStdHandle(-11)
            mode = ctypes.c_uint32()
            if kernel.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel.SetConsoleMode(handle, mode.value | 0x0004)
        except Exception:
            pass
    return True


class _C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    BLUE = "\033[34m"
    RED = "\033[31m"
    WHITE = "\033[97m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"


def paint(text: str, *styles: str) -> str:
    if not ui_color_enabled():
        return text
    return "".join(styles) + text + _C.RESET


def banner_line(char: str = "=", width: int = 56) -> str:
    line = char * width
    return paint(line, _C.CYAN) if ui_color_enabled() else line


def title(text: str) -> str:
    return paint(f"  {text}", _C.BOLD, _C.WHITE, _C.BG_MAGENTA)


def subsection_label(text: str) -> str:
    return paint(f"-- {text} --", _C.BOLD, _C.CYAN)


def ok(text: str) -> str:
    return paint(text, _C.GREEN)


def warn(text: str) -> str:
    return paint(text, _C.YELLOW)


def err(text: str) -> str:
    return paint(text, _C.RED)


def score_badge(score: float) -> str:
    if score >= 70:
        return paint(f"[{score}]", _C.BOLD, _C.GREEN)
    if score >= 45:
        return paint(f"[{score}]", _C.YELLOW)
    return paint(f"[{score}]", _C.DIM)


def health_status(name: str, line: str) -> str:
    if "QUOTA" in line or "AUTH FAILED" in line or "OFF" in line:
        return f"  {paint(name + ':', _C.BOLD)} {err(line)}"
    if "not active" in line.lower() or "inactive" in line.lower():
        return f"  {paint(name + ':', _C.BOLD)} {paint(line, _C.DIM)}"
    if line.startswith("ON"):
        return f"  {paint(name + ':', _C.BOLD)} {ok(line)}"
    return f"  {paint(name + ':', _C.BOLD)} {line}"
