"""#439 Shorts-eligibility before upload. Missing file is fail-open."""

from __future__ import annotations

import os

from core.logging import get_logger

logger = get_logger("core.shorts_eligibility")

_TITLE_MAX = 100


def shorts_refuse_reason(
    *,
    duration_s: float | None = None,
    width: int | None = None,
    height: int | None = None,
    title: str = "",
    file_path: str | None = None,
) -> str | None:
    """Return a one-line refuse reason, or None if eligible / unknown.

    A missing file is fail-open (publish already has invalid_file). Probe
    failures leave duration/size None and do not refuse.
    """
    if file_path and not os.path.isfile(file_path):
        return None
    if duration_s is not None and float(duration_s) > 60.0:
        return f"Not a Short: duration {float(duration_s):.1f}s exceeds 60s"
    if width and height and int(height) <= int(width):
        return f"Not a Short: need 9:16 (got {int(width)}x{int(height)})"
    if title and len(title) > _TITLE_MAX:
        return f"Not a Short: title length {len(title)} exceeds {_TITLE_MAX}"
    return None
