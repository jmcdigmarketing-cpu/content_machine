"""#448: ranked answer for which phase ate the last run."""

from __future__ import annotations

from typing import Any


def why_slow_lines(timings: dict[str, Any] | None) -> list[str]:
    rows: list[tuple[str, float]] = []
    for name, raw in (timings or {}).items():
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue
        rows.append((str(name), value))
    rows.sort(key=lambda item: item[1], reverse=True)
    if not rows:
        return ["no phase timings on the last trace"]
    lines = ["slowest phases:"]
    for name, value in rows[:8]:
        lines.append(f"  {name}: {value:.1f}s")
    return lines
