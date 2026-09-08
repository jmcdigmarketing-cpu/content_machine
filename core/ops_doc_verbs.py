"""#633: every ops verb named in docs must exist in COMMANDS."""

from __future__ import annotations

import re
from pathlib import Path

from config.paths import ROOT_DIR

_OPS = re.compile(r"`(?:ops\s+|py -m scripts\.ops\s+)([a-z][a-z0-9-]*)`", re.I)
_SKIP = {"list", "help"}


def verbs_named_in_docs(docs_dir: str | None = None) -> set[str]:
    root = Path(docs_dir or ROOT_DIR) / "docs"
    found: set[str] = set()
    if not root.is_dir():
        return found
    for path in root.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for match in _OPS.findall(text):
            verb = match.strip().lower()
            if verb and verb not in _SKIP:
                found.add(verb)
    return found
