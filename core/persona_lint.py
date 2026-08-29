"""#406 per-persona style linter — warn only, never rewrite (MoneyWise ranges)."""

from __future__ import annotations

import re

from core.logging import get_logger

logger = get_logger("core.persona_lint")

_FILLER_PHRASES = (
    "but here's the thing",
    "let's dive in",
    "without further ado",
    "at the end of the day",
    "buckle up",
    "game-changer",
)

# Spoken-number ranges that #327 already protects. Do not treat them as filler.
_RANGE_RE = re.compile(r"\b\d+\s*-\s*\d+\s*(%|years?|months?)\b", re.I)


def lint_persona_script(script: str, *, channel_id: str = "tapin") -> list[str]:
    """Return banned-filler hits. Empty list on a clean script (no WARNING)."""
    text = script or ""
    if not text.strip():
        return []
    # Pattern-catch: a MoneyWise range is not a style defect.
    if channel_id == "moneywise" and _RANGE_RE.search(text) and not _has_filler(text):
        return []
    hits = _has_filler(text)
    if hits:
        logger.debug("persona lint %s: %s", channel_id, hits)
    return hits


def _has_filler(text: str) -> list[str]:
    lowered = text.lower()
    return [p for p in _FILLER_PHRASES if p in lowered]
