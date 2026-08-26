"""#89 Public-safe redaction for SKU / export paths.

Strips operator key-fact dumps, unpublished scripts, and key material.
A rewrite that drops lines reports both pre and post counts (decisions.md §25).
"""

from __future__ import annotations

import re

_SK = re.compile(r"sk-[A-Za-z0-9_\-]+")
_KEY_ASSIGN = re.compile(r"(?i)\b(?:[A-Z0-9_]+)?(?:API[_-]?KEY|SECRET|TOKEN|PASSWORD)\s*[:=]\s*\S+")


def redact_for_public(text: str) -> tuple[str, dict]:
    """Return (redacted_text, {pre_lines, post_lines, stripped})."""
    raw = text or ""
    pre = raw.splitlines()
    out: list[str] = []
    i = 0
    while i < len(pre):
        line = pre[i]
        lower = line.lower()
        if "operator key facts" in lower:
            i += 1
            while i < len(pre) and (
                not pre[i].strip() or pre[i].lstrip().startswith(("-", "*", "•"))
            ):
                i += 1
            continue
        if "unpublished script" in lower:
            i += 1
            if i < len(pre) and pre[i].strip():
                i += 1
            continue
        if _SK.search(line) or _KEY_ASSIGN.search(line):
            i += 1
            continue
        out.append(line)
        i += 1
    redacted = "\n".join(out)
    if raw.endswith("\n") and redacted:
        redacted += "\n"
    stats = {
        "pre_lines": len(pre),
        "post_lines": len(out),
        "stripped": len(out) < len(pre),
    }
    return redacted, stats
