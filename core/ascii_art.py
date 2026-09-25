"""ASCII banners for CLI (disable with CONTENT_UI_ASCII=false)."""

from __future__ import annotations

import logging
import os
import shutil
from datetime import date
from functools import lru_cache
from pathlib import Path

from config.paths import LUFFY_ASCII_FILE
from core.ui_theme import paint, ui_color_enabled

logger = logging.getLogger(__name__)

_C = "\033[36m" if ui_color_enabled() else ""
_M = "\033[35m" if ui_color_enabled() else ""
_Y = "\033[33m" if ui_color_enabled() else ""
_G = "\033[32m" if ui_color_enabled() else ""
_R = "\033[0m" if ui_color_enabled() else ""


def ascii_enabled() -> bool:
    return os.getenv("CONTENT_UI_ASCII", "true").lower() not in ("0", "false", "no")


def mascot_enabled() -> bool:
    if not ascii_enabled():
        return False
    mode = os.getenv("CONTENT_UI_MASCOT", "luffy").strip().lower()
    return mode not in ("0", "false", "no", "off", "none")


def mascot_forced() -> bool:
    return os.getenv("CONTENT_UI_ART", "").strip().lower() in ("1", "true", "yes", "on")


def mascot_stamp_path() -> Path:
    override = os.getenv("CONTENT_UI_MASCOT_STAMP", "").strip()
    if override:
        return Path(override)
    from config.paths import DATA_DIR

    return Path(DATA_DIR) / "mascot_shown_day.txt"


def mascot_collapsed_today() -> bool:
    """#482. After the first look of the day, skip the ~60-line panel."""
    if mascot_forced():
        return False
    try:
        return mascot_stamp_path().read_text(encoding="utf-8").strip() == date.today().isoformat()
    except OSError:
        return False


def mark_mascot_shown() -> None:
    if mascot_forced():
        return
    path = mascot_stamp_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(date.today().isoformat(), encoding="utf-8")
    except OSError as exc:
        logger.debug("mascot stamp skipped: %s", exc)


def luffy_ascii_path() -> Path:
    """Bundled mascot art (UTF-8, no BOM)."""
    return Path(LUFFY_ASCII_FILE)


def _visible_width(line: str) -> int:
    plain = line.replace(_C, "").replace(_M, "").replace(_Y, "").replace(_G, "").replace(_R, "")
    return len(plain)


_BRAILLE_BLANK = "\u2800"


def _normalize_mascot_line(line: str) -> str:
    """Map ASCII spaces to U+2800 so editors/Python strip() cannot collapse offsets."""
    if " " not in line:
        return line
    return line.replace(" ", _BRAILLE_BLANK)


@lru_cache(maxsize=1)
def luffy_mascot_lines() -> tuple[str, ...]:
    """
    Load mascot rows from core/data/luffy_ascii.txt.

    Trim newlines only — never strip/lstrip row content. Alignment depends on
    leading U+2800 Braille blanks.
    """
    path = luffy_ascii_path()
    if not path.is_file():
        return ()

    try:
        with open(path, encoding="utf-8") as f:
            rows = [line.rstrip("\n\r") for line in f]
    except OSError as exc:
        logger.debug("Luffy art unreadable at %s: %s", path, exc)
        return ()

    if rows and rows[0].startswith("\ufeff"):
        rows[0] = rows[0].removeprefix("\ufeff")

    if not rows:
        return ()

    return tuple(_normalize_mascot_line(row) for row in rows)


def startup_banner_lines(channel_id: str | None = None) -> list[str]:
    if not ascii_enabled():
        return []

    lines = [
        r"  ██████╗ ███╗   ███╗",
        r" ██╔════╝ ████╗ ████║",
        r" ██║      ██╔████╔██║   CONTENT MACHINE",
        r" ██║      ██║╚██╔╝██║",
        r" ╚██████╗ ██║ ╚═╝ ██║",
        r"  ╚═════╝ ╚═╝     ╚═╝",
    ]
    if channel_id == "tapin":
        lines.append("  ── TapIn Media · gaming & UFC shorts ──")
    else:
        try:
            from core.themes import active_theme

            lines.append(f"  {active_theme().tagline}")
        except Exception:
            lines.append("  ── discovery → render → publish ──")

    out: list[str] = []
    for i, line in enumerate(lines):
        if i < 6:
            out.append(paint(line, _C) if ui_color_enabled() else line)
        else:
            out.append(paint(line, _Y) if ui_color_enabled() else line)
    return out


def startup_banner(channel_id: str | None = None) -> str:
    return "\n".join(startup_banner_lines(channel_id))


def merge_columns(left: list[str], right: list[str], gap: int = 3) -> list[str]:
    if not right:
        return left
    if not left:
        return right

    left_w = max(_visible_width(line) for line in left)
    height = max(len(left), len(right))
    merged: list[str] = []
    for i in range(height):
        lft = left[i] if i < len(left) else ""
        rgt = right[i] if i < len(right) else ""
        pad = left_w - _visible_width(lft)
        merged.append(lft + (" " * pad) + (" " * gap) + rgt)
    return merged


def merge_columns_right(
    left: list[str],
    right: list[str],
    *,
    cols: int,
    gap: int = 3,
    margin: int = 1,
) -> list[str]:
    """Place the right column flush to the terminal's right edge (mascot panel)."""
    if not right:
        return left
    if not left:
        return right

    left_w = max((_visible_width(line) for line in left), default=0)
    right_w = max((_visible_width(line) for line in right), default=0)
    right_start = max(left_w + gap, cols - margin - right_w)
    height = max(len(left), len(right))
    merged: list[str] = []
    for i in range(height):
        lft = left[i] if i < len(left) else ""
        rgt = right[i] if i < len(right) else ""
        pad = max(0, right_start - _visible_width(lft))
        merged.append(lft + (" " * pad) + rgt)
    return merged


def _mascot_gap() -> int:
    try:
        return max(2, int(os.getenv("CONTENT_UI_MASCOT_GAP", "8")))
    except ValueError:
        return 8


def _mascot_indent() -> int:
    try:
        return max(0, int(os.getenv("CONTENT_UI_MASCOT_INDENT", "4")))
    except ValueError:
        return 4


def _mascot_layout(cols: int, left_w: int, mascot_w: int) -> tuple[int, int, bool]:
    """
    Return (gap, right_indent, fits_full_width).

    Mascot is right-aligned; we never truncate — if the full art does not fit,
    callers should fall back to the CM banner only.
    """
    margin = 2
    gap = _mascot_gap()
    right_indent = _mascot_indent()

    avail = cols - left_w - gap - right_indent - margin
    if avail < mascot_w:
        slack = mascot_w - avail
        shrink = min(right_indent, slack)
        right_indent -= shrink
        slack -= shrink
        shrink = min(max(0, gap - 2), slack)
        gap -= max(0, shrink)
        avail = cols - left_w - gap - right_indent - margin

    return gap, right_indent, avail >= mascot_w


def _theme_mascot_lines() -> tuple[str, ...]:
    """The active theme's mascot panel: inline art, or Luffy when the theme keeps it."""
    try:
        from core.themes import active_theme

        theme = active_theme()
    except Exception:
        return luffy_mascot_lines()
    if theme.mascot:
        return theme.mascot
    if theme.use_luffy_mascot:
        return luffy_mascot_lines()
    return ()


def startup_panel_lines(channel_id: str | None = None) -> list[str]:
    left = startup_banner_lines(channel_id)
    if not mascot_enabled() or mascot_collapsed_today():
        return left

    mascot = _theme_mascot_lines()
    if not mascot:
        return left

    logo = left[:6]
    tagline = left[6:]

    cols = shutil.get_terminal_size(fallback=(120, 24)).columns
    left_w = max((_visible_width(line) for line in logo), default=0)
    mascot_w = max(_visible_width(line) for line in mascot)
    gap, right_indent, fits = _mascot_layout(cols, left_w, mascot_w)
    if not fits:
        return left

    merged = merge_columns_right(
        logo,
        list(mascot),
        cols=cols - right_indent,
        gap=gap,
    )
    if tagline:
        return [*merged, "", *tagline]
    return merged


def print_startup_panel(channel_id: str | None = None) -> None:
    collapsed = mascot_collapsed_today()
    lines = startup_panel_lines(channel_id)
    if not lines:
        return
    for line in lines:
        print(line)
    print()
    if mascot_enabled() and not collapsed:
        mark_mascot_shown()


def section_glyph(name: str) -> str:
    if not ascii_enabled():
        return ""
    glyphs = {
        "discovery": "◇",
        "content": "✎",
        "render": "▶",
        "upload": "↑",
        "queue": "☰",
        "channel": "◎",
    }
    try:
        from core.themes import active_theme

        glyphs = active_theme().section_glyphs  # {} (plain theme) = no glyphs
    except Exception as exc:
        logger.debug("active_theme skipped: %s", exc)
    key = name.strip().lower().split()[0]
    g = glyphs.get(key, "•" if glyphs else "")
    if not g:
        return ""
    return paint(f"{g} ", _M) if ui_color_enabled() else f"{g} "
