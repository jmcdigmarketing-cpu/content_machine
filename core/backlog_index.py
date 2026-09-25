"""#632: open items must carry a size tag the roadmap index can see."""

from __future__ import annotations

from core.roadmap_index import FILES, OPEN_RE, SIZE_RE, _lines


def untagged_open_items(path: str | None = None) -> list[str]:
    """Open checklist rows missing a backtick size tag (`` `[S]` `` / M / L / XL)."""
    del path
    leftover: list[str] = []
    for name in FILES:
        for i, line in enumerate(_lines(name), 1):
            if OPEN_RE.match(line) and not SIZE_RE.search(line):
                leftover.append(f"{name}:{i}")
    return leftover
