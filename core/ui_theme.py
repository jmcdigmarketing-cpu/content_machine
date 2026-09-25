"""ANSI colors for CLI (Windows Terminal / PowerShell 5.1+ with VT enabled).

Colors are theme-aware: role colors (primary/accent/success/warn/error) come
from the active skin in core/themes.py (CONTENT_UI_THEME / channel "ui_theme"),
falling back to the classic cyan/yellow scheme. CONTENT_UI_COLOR=false still
disables everything.
"""

from __future__ import annotations

import os
import shutil
import sys

from core.logging import get_logger

logger = get_logger("core.ui_theme")


def ui_color_enabled() -> bool:
    if os.getenv("NO_COLOR", "").strip():
        return False
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
        except Exception as exc:
            logger.debug("GetStdHandle skipped: %s", exc)
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


def _role(role: str, fallback: str) -> str:
    """Theme role color, or the classic fallback when the theme has no palette."""
    try:
        from core.themes import role_color

        return role_color(role) or fallback
    except Exception:
        return fallback


def paint(text: str, *styles: str) -> str:
    if not ui_color_enabled():
        return text
    return "".join(styles) + text + _C.RESET


def terminal_width(*, minimum: int = 56, maximum: int = 100) -> int:
    """Usable banner width — fills the terminal without going novel-length."""
    cols = shutil.get_terminal_size(fallback=(minimum, 24)).columns
    return max(minimum, min(cols - 2, maximum))


def banner_line(char: str = "=", width: int | None = None) -> str:
    line = char * (width if width is not None else terminal_width())
    return paint(line, _role("primary", _C.CYAN)) if ui_color_enabled() else line


def title(text: str) -> str:
    return paint(f"  {text}", _C.BOLD, _C.WHITE, _C.BG_MAGENTA)


def subsection_label(text: str) -> str:
    return paint(f"-- {text} --", _C.BOLD, _role("primary", _C.CYAN))


def ok(text: str) -> str:
    return paint(text, _role("success", _C.GREEN))


def warn(text: str) -> str:
    return paint(text, _role("warn", _C.YELLOW))


def err(text: str) -> str:
    return paint(text, _role("error", _C.RED))


def accent(text: str) -> str:
    return paint(text, _role("accent", _C.YELLOW))


def score_badge(score: float) -> str:
    hype = ""
    if score >= 90:
        try:
            from core.themes import active_theme

            hype = active_theme().score_hype
        except Exception:
            hype = ""
    if score >= 70:
        return paint(f"[{score}]", _C.BOLD, _role("success", _C.GREEN)) + (
            accent(hype) if hype else ""
        )
    if score >= 45:
        return paint(f"[{score}]", _role("warn", _C.YELLOW))
    return paint(f"[{score}]", _C.DIM)


def health_status(name: str, line: str) -> str:
    if "QUOTA" in line or "AUTH FAILED" in line or "OFF" in line:
        return f"  {paint(name + ':', _C.BOLD)} {err(line)}"
    if "not active" in line.lower() or "inactive" in line.lower():
        return f"  {paint(name + ':', _C.BOLD)} {paint(line, _C.DIM)}"
    if line.startswith("ON"):
        return f"  {paint(name + ':', _C.BOLD)} {ok(line)}"
    return f"  {paint(name + ':', _C.BOLD)} {line}"
