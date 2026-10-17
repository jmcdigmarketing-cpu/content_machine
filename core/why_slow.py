"""#448: ranked answer for which phase ate the last run."""

from __future__ import annotations

from typing import Any

_NOT_PHASES = frozenset(
    {
        "word_count",
        "min_words",
        "max_words",
        "length_preset",
        "hook_score",
        "authenticity_score",
        # Wave 104 (run 157): a 0-1 spread of the angles, not seconds.
        "angle_spread",
    }
)


def phase_seconds(timings: dict[str, Any] | None) -> list[tuple[str, float]]:
    """The timed phases, in stored order: numbers only, never a count, a score or a list
    (run 157's `angle_frames` and `intent_read` sit in the same dict)."""
    rows: list[tuple[str, float]] = []
    for name, raw in (timings or {}).items():
        if str(name) in _NOT_PHASES or isinstance(raw, bool):
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            rows.append((str(name), value))
    return rows


def why_slow_lines(timings: dict[str, Any] | None) -> list[str]:
    rows = phase_seconds(timings)
    rows.sort(key=lambda item: item[1], reverse=True)
    if not rows:
        return ["no phase timings on the last trace"]
    lines = ["slowest phases:"]
    for name, value in rows[:8]:
        lines.append(f"  {name}: {value:.1f}s")
    return lines
