"""#406 per-persona style linter — warn only, never rewrite (MoneyWise ranges)."""

from __future__ import annotations

import json
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
    "in today's video",
    "delve",
)

# Spoken-number ranges that #327 already protects. Do not treat them as filler.
_RANGE_RE = re.compile(r"\b\d+\s*-\s*\d+\s*(%|years?|months?)\b", re.I)


def _channel_tells(channel_id: str) -> tuple[str, ...]:
    phrases = list(_FILLER_PHRASES)
    try:
        from pathlib import Path

        from config.paths import ROOT_DIR

        path = Path(ROOT_DIR) / "config" / "llm_tells.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        phrases.extend(str(p) for p in (data.get("shared") or []) if p)
        extra = data.get((channel_id or "").strip().lower()) or []
        phrases.extend(str(p) for p in extra if p)
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        pass
    seen: set[str] = set()
    out: list[str] = []
    for phrase in phrases:
        key = phrase.lower()
        if key not in seen:
            seen.add(key)
            out.append(phrase)
    return tuple(out)


def lint_persona_script(script: str, *, channel_id: str = "tapin") -> list[str]:
    """Return banned-filler hits. Empty list on a clean script (no WARNING)."""
    text = script or ""
    if not text.strip():
        return []
    tells = _channel_tells(channel_id)
    # Pattern-catch: a MoneyWise range is not a style defect.
    hits = _has_filler(text, tells)
    if channel_id == "moneywise" and _RANGE_RE.search(text) and not hits:
        return []
    if hits:
        logger.debug("persona lint %s: %s", channel_id, hits)
    return hits


def _has_filler(text: str, tells: tuple[str, ...] | None = None) -> list[str]:
    lowered = text.lower()
    phrases = tells if tells is not None else _FILLER_PHRASES
    return [p for p in phrases if p in lowered]
