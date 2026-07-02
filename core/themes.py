"""Terminal UI themes — swappable skins for the CLI (roadmap "themeable skins").

A theme bundles every presentation constant that used to be hardcoded: ANSI
palette (16-color + richer 256-color where the terminal supports it), spinner
frames + themed loading copy, section glyphs, meter characters, a startup
tagline, an inline mascot panel, a celebration art key, and a high-score hype
line. Themes are **presentation-only lookups** — no pipeline logic reads them,
and everything degrades to plain text when colors/ASCII are disabled.

Resolution order (first match wins):
  1. ``CONTENT_UI_THEME`` env var
  2. the active channel's ``"ui_theme"`` in channels.json (set via
     :func:`set_channel_theme`, called once after channel selection)
  3. ``default``

Skins: ``default`` · ``plain`` · ``onepiece`` · ``zelda`` · ``pokemon`` ·
``dbz`` · ``jjba``. CI/logs stay clean: ``plain`` has no color, no art, ASCII
spinner — and ``CONTENT_UI_COLOR/ASCII=false`` still override everything.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field

_RESET = "\033[0m"

# Braille spinner (the classic) — reused by several themes.
_BRAILLE_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

_DEFAULT_GLYPHS = {
    "discovery": "◇",
    "content": "✎",
    "render": "▶",
    "upload": "↑",
    "queue": "☰",
    "channel": "◎",
}


@dataclass(frozen=True)
class Theme:
    name: str
    tagline: str = "── discovery → render → publish ──"
    # role -> (16-color ANSI, 256-color ANSI). Roles: primary, accent, success,
    # warn, error. 256 codes light up in Windows Terminal / COLORTERM shells.
    palette: dict[str, tuple[str, str]] = field(default_factory=dict)
    spinner_frames: tuple[str, ...] = _BRAILLE_FRAMES
    # phase-prefix -> themed loading copy shown by DiscoverySpinner.
    spinner_copy: dict[str, str] = field(default_factory=dict)
    section_glyphs: dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_GLYPHS))
    meter_chars: tuple[str, str] = ("▓", "░")
    celebration_key: str = ""  # bonus-art key fired on publish success ("" = random)
    score_hype: str = ""  # short tag appended to a >= 90 composite score
    # Small inline mascot panel for the startup screen (right column). Empty →
    # the file-based Luffy mascot is used when available (onepiece/default).
    mascot: tuple[str, ...] = ()
    use_luffy_mascot: bool = True


def _p(c16: str, c256: int) -> tuple[str, str]:
    return (c16, f"\033[38;5;{c256}m")


_DEFAULT_PALETTE = {
    "primary": _p("\033[36m", 45),  # cyan
    "accent": _p("\033[33m", 220),  # yellow
    "success": _p("\033[32m", 40),
    "warn": _p("\033[33m", 214),
    "error": _p("\033[31m", 196),
}


# ---------------------------------------------------------------------------
# Inline mascot panels (small, ASCII/Unicode-safe under main.py's UTF-8 stdout)
# ---------------------------------------------------------------------------

_ZELDA_MASCOT = (
    "        ▲        ",
    "       ▲ ▲       ",
    "      ▲▲▲▲▲      ",
    "     ▲   ▲ ▲     ",
    "    ▲ ▲ ▲ ▲ ▲    ",
    "   ▲▲▲▲▲▲▲▲▲▲    ",
    "  it's dangerous ",
    "  to go alone —  ",
    "  take signals.  ",
)

_POKEMON_MASCOT = (
    "      ,'''''.    ",
    "     /  ___  \\   ",
    "    |  /   \\  |  ",
    "    |==| ● |==|  ",
    "    |  \\___/  |  ",
    "     \\       /   ",
    "      `.....'    ",
    "  gotta post     ",
    "  'em all!       ",
)

_DBZ_MASCOT = (
    "     \\  |  /     ",
    "   ─ ((( ● ))) ─ ",
    "     /  |  \\     ",
    "    _/ ─┼─ \\_    ",
    "       / \\       ",
    "  ⚡ POWER UP ⚡  ",
    "  scouter: ON    ",
)

_JJBA_MASCOT = (
    "   ゴ      ゴ    ",
    "  ゴ  ▙▄▄▟   ゴ  ",
    "     ▐ ◉ ◉▌      ",
    "  ゴ ▐  ▼ ▌  ゴ  ",
    "     ▝▄▄▄▘       ",
    "   ゴ      ゴ    ",
    "  your next line ",
    "  is... a banger ",
)


THEMES: dict[str, Theme] = {
    "default": Theme(
        name="default",
        palette=dict(_DEFAULT_PALETTE),
    ),
    "plain": Theme(
        name="plain",
        tagline="-- discovery -> render -> publish --",
        palette={},  # no color roles — paint() falls through untouched
        spinner_frames=("|", "/", "-", "\\"),
        section_glyphs={},
        meter_chars=("#", "."),
        use_luffy_mascot=False,
    ),
    "onepiece": Theme(
        name="onepiece",
        tagline="── set sail: discovery → render → publish ──",
        palette={
            **_DEFAULT_PALETTE,
            "primary": _p("\033[31m", 196),  # straw-hat red
            "accent": _p("\033[33m", 220),  # gold
        },
        spinner_copy={
            "Fetching signals": "Charting the Grand Line",
            "Scoring variants": "Weighing the bounties",
            "Finishing up": "Raising the flag",
        },
        celebration_key="trophy",
        score_hype=" ☠ KING-OF-THE-HILL",
    ),
    "zelda": Theme(
        name="zelda",
        tagline="── it's dangerous to publish alone ──",
        palette={
            **_DEFAULT_PALETTE,
            "primary": _p("\033[32m", 40),  # kokiri green
            "accent": _p("\033[33m", 220),  # triforce gold
        },
        spinner_frames=("▲", "▴", "△", "▴"),
        spinner_copy={
            "Fetching signals": "Opening chests",
            "Scoring variants": "Reading the sheikah slate",
            "Finishing up": "Final dungeon",
        },
        section_glyphs={**_DEFAULT_GLYPHS, "discovery": "▲", "content": "✦", "queue": "❤"},
        meter_chars=("❤", "♡"),
        celebration_key="zelda_item",
        score_hype=" ✦ SECRET FOUND",
        mascot=_ZELDA_MASCOT,
        use_luffy_mascot=False,
    ),
    "pokemon": Theme(
        name="pokemon",
        tagline="── gotta post 'em all ──",
        palette={
            **_DEFAULT_PALETTE,
            "primary": _p("\033[31m", 196),  # pokeball red
            "accent": _p("\033[33m", 226),  # pikachu yellow
        },
        spinner_frames=("◓", "◑", "◒", "◐"),
        spinner_copy={
            "Fetching signals": "Searching tall grass",
            "Scoring variants": "Checking type advantage",
            "Finishing up": "Throwing the ball",
        },
        section_glyphs={**_DEFAULT_GLYPHS, "discovery": "◓", "render": "⚡"},
        celebration_key="pokemon_levelup",
        score_hype=" ⚡ SUPER EFFECTIVE",
        mascot=_POKEMON_MASCOT,
        use_luffy_mascot=False,
    ),
    "dbz": Theme(
        name="dbz",
        tagline="── power level: rising ──",
        palette={
            **_DEFAULT_PALETTE,
            "primary": _p("\033[33m", 208),  # saiyan orange
            "accent": _p("\033[36m", 45),  # ki blue
        },
        spinner_frames=("·", "•", "●", "◉", "●", "•"),
        spinner_copy={
            "Fetching signals": "Scouter scanning",
            "Scoring variants": "Reading power levels",
            "Finishing up": "Charging the spirit bomb",
        },
        section_glyphs={**_DEFAULT_GLYPHS, "discovery": "◉", "render": "⚡"},
        meter_chars=("█", "░"),
        celebration_key="dbz_over9000",
        score_hype=" ⚡ IT'S OVER 9000!",
        mascot=_DBZ_MASCOT,
        use_luffy_mascot=False,
    ),
    "jjba": Theme(
        name="jjba",
        tagline="── your next video is already rendering ──",
        palette={
            **_DEFAULT_PALETTE,
            "primary": _p("\033[35m", 165),  # stand purple
            "accent": _p("\033[33m", 220),  # menacing gold
        },
        spinner_frames=("ゴ", "ゴゴ", "ゴゴゴ", "ゴゴ"),
        spinner_copy={
            "Fetching signals": "Stand awakening",
            "Scoring variants": "ORA ORA scoring variants",
            "Finishing up": "Za Warudo — time resumes",
        },
        section_glyphs={**_DEFAULT_GLYPHS, "discovery": "✧", "content": "♦", "render": "➤"},
        meter_chars=("♦", "◇"),
        celebration_key="jjba_tbc",
        score_hype=" ✧ MUDA MUDA MUDA",
        mascot=_JJBA_MASCOT,
        use_luffy_mascot=False,
    ),
}


# ---------------------------------------------------------------------------
# Active-theme resolution
# ---------------------------------------------------------------------------

_channel_theme: str = ""  # set once after channel selection (main.py)


def set_channel_theme(channel_id: str | None) -> None:
    """Adopt the channel's channels.json "ui_theme" as the session default."""
    global _channel_theme
    try:
        from config.channels import get_channel_profile

        _channel_theme = (get_channel_profile(channel_id).ui_theme or "").strip().lower()
    except Exception:
        _channel_theme = ""


def theme_names() -> list[str]:
    return sorted(THEMES)


def active_theme() -> Theme:
    """Resolve the current theme: env override → channel default → "default"."""
    name = os.getenv("CONTENT_UI_THEME", "").strip().lower() or _channel_theme
    return THEMES.get(name, THEMES["default"])


# ---------------------------------------------------------------------------
# Color depth + role colors
# ---------------------------------------------------------------------------


def color_depth() -> int:
    """16 or 256. auto-detects Windows Terminal / COLORTERM; override via env."""
    raw = os.getenv("CONTENT_UI_COLOR_DEPTH", "auto").strip().lower()
    if raw in ("16", "256"):
        return int(raw)
    if os.getenv("WT_SESSION") or os.getenv("COLORTERM") or "256" in os.getenv("TERM", ""):
        return 256
    return 16


def role_color(role: str) -> str:
    """ANSI code for a palette role in the active theme ('' when unthemed)."""
    pair = active_theme().palette.get(role)
    if not pair:
        return ""
    return pair[1] if color_depth() == 256 else pair[0]


# ---------------------------------------------------------------------------
# Meters (quota / cadence visualisation)
# ---------------------------------------------------------------------------


def _unicode_ok() -> bool:
    """ops paths don't force UTF-8 stdout; fall back to ASCII meters there."""
    enc = (getattr(sys.stdout, "encoding", "") or "").lower()
    return "utf" in enc


def meter(used: float, cap: float, *, width: int = 10) -> str:
    """A themed block meter like `▓▓▓░░░░░░░ 3/10` (ASCII-safe on cp1252)."""
    try:
        used_f, cap_f = max(float(used), 0.0), max(float(cap), 0.0)
    except (TypeError, ValueError):
        return f"{used}/{cap}"
    if cap_f <= 0:
        return f"{used}/{cap}"
    # Small integer caps render one block per slot (5 hearts for a 5-video cap).
    if cap_f.is_integer() and 0 < int(cap_f) <= width:
        width = int(cap_f)
    filled_char, empty_char = active_theme().meter_chars
    if not _unicode_ok():
        filled_char, empty_char = "#", "."
    filled = min(width, int(round(width * min(used_f / cap_f, 1.0))))
    bar = filled_char * filled + empty_char * (width - filled)
    if float(used_f).is_integer() and float(cap_f).is_integer():
        return f"{bar} {int(used_f)}/{int(cap_f)}"
    return f"{bar} {used_f:.2f}/{cap_f:.2f}"


def themed_phase(phase: str) -> str:
    """Themed loading copy for a spinner phase (prefix match), else unchanged."""
    copy = active_theme().spinner_copy
    for prefix, themed in copy.items():
        if phase.startswith(prefix):
            return themed
    return phase
