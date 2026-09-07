"""#243. PNG wordmark for HTML/booth; ASCII banners stay the terminal path."""

from __future__ import annotations

import os
from pathlib import Path

from config.paths import ROOT_DIR

WORDMARK_REL = Path("assets") / "branding" / "wordmark.png"


def wordmark_enabled() -> bool:
    return os.getenv("CONTENT_UI_WORDMARK", "").strip().lower() in ("1", "true", "yes", "on")


def wordmark_path() -> Path:
    return Path(ROOT_DIR) / WORDMARK_REL


def wordmark_html() -> str:
    """Img tag when the flag is on and the PNG exists; otherwise empty."""
    if not wordmark_enabled():
        return ""
    path = wordmark_path()
    if not path.is_file():
        return ""
    src = path.as_posix()
    return f"<img class='wordmark' src='{src}' alt='Content OS'>"
