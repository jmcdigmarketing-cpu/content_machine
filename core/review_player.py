"""Start the review-room player: setSource then play. Testable without decoding."""

from __future__ import annotations

import os
from typing import Any


def start_review_player(player: Any, path: str) -> bool:
    """True when the file exists and play() was invoked. Does not decode in CI."""
    if player is None or not path or not os.path.isfile(path):
        return False
    source: Any = os.path.abspath(path)
    try:
        from PySide6.QtCore import QUrl

        source = QUrl.fromLocalFile(source)
    except ImportError:
        pass
    setter = getattr(player, "setSource", None)
    if callable(setter):
        setter(source)
    play = getattr(player, "play", None)
    if callable(play):
        play()
        return True
    return False
