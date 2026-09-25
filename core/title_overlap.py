"""#596: advisory when a title copies a competitor word-for-word."""

from __future__ import annotations

from typing import Any


def verbatim_competitor_advisory(title: str, rows: list[dict[str, Any]] | None) -> str:
    needle = " ".join((title or "").split()).strip().lower()
    if not needle:
        return ""
    for row in rows or []:
        other = " ".join(str(row.get("title") or "").split()).strip().lower()
        if other and other == needle:
            channel = str(row.get("channel") or "competitor")
            return f"Title matches {channel} word-for-word"
    return ""
