"""#595: what YouTube actually shows above the description fold."""

from __future__ import annotations

_FOLD_CHARS = 100


def fold_preview(description: str, *, limit: int = _FOLD_CHARS) -> tuple[str, str]:
    """Split a description into (above the fold, below it).

    YouTube mobile hides everything past ~100 characters / the first two lines.
    Prefer a newline inside the budget so we do not cut a word when the author
    already broke the line.
    """
    text = description or ""
    if len(text) <= limit:
        return text, ""
    window = text[: limit + 1]
    break_at = window.rfind("\n")
    if break_at < limit // 2:
        break_at = window.rfind(" ")
    if break_at < limit // 2:
        break_at = limit
    above = text[:break_at].rstrip()
    below = text[break_at:].lstrip()
    return above, below


def format_fold_preview(description: str) -> str:
    above, below = fold_preview(description)
    lines = ["Above the fold (what viewers see):", above or "(empty)", ""]
    if below:
        lines.extend(["Below the fold (after Show more):", below])
    else:
        lines.append("Below the fold: (nothing — the whole description is visible)")
    return "\n".join(lines)
