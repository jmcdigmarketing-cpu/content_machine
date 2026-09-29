"""Emoji in burned captions (#504): switch to an emoji font for each emoji run.

libass draws a caption in its style's font (Arial, Impact ...), which has no emoji
glyphs, so an emoji the script carried vanished from the video. Operator's choice (wave
47): render them. `wrap_emoji` puts each emoji run between ASS font switches -
`{\\fn<emoji font>}...{\\fn<the style's font>}` - so libass draws it from an emoji font.

The default is Segoe UI Emoji, which ships with Windows 10/11 and whose monochrome
outlines libass can draw (colour emoji are beyond libass). `CAPTION_EMOJI_FONT` names
another installed font. Text with no emoji comes back unchanged, byte for byte.
"""

from __future__ import annotations

import os
import re
from typing import Any

DEFAULT_EMOJI_FONT = "Segoe UI Emoji"

# Pictographs, symbols and dingbats; arrows, (c) and (tm) stay text on purpose.
_CHAR = (
    "\U0001f000-\U0001faff"  # emoticons, pictographs, transport, symbols, flags parts
    "☀-➿"  # misc symbols + dingbats
    "⬀-⯿"  # stars and squares
    "⌀-⏿"  # watch, hourglass, media keys
)
_MOD = "️⃣"  # variation selector-16, keycap
EMOJI_RE = re.compile(rf"(?:[{_CHAR}][{_MOD}]?(?:‍[{_CHAR}][{_MOD}]?)*)+")


def emoji_font() -> str:
    name = (os.getenv("CAPTION_EMOJI_FONT") or "").replace(",", " ").strip()
    return name or DEFAULT_EMOJI_FONT


def wrap_emoji(text: str, base_font: str) -> str:
    """`text` with each emoji run drawn from the emoji font, then back to `base_font`."""
    if not text or not EMOJI_RE.search(text):
        return text
    font = emoji_font()
    return EMOJI_RE.sub(lambda m: f"{{\\fn{font}}}{m.group(0)}{{\\fn{base_font}}}", text)


def has_emoji(words: list[dict[str, Any]] | None) -> bool:
    return any(EMOJI_RE.search(str(w.get("word") or "")) for w in words or [])
