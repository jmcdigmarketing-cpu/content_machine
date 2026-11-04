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


# Wave 145: `ops <verb>` at the start of a code span, closed or followed by its arguments.
_OPS_START = re.compile(r"`(?:ops\s+|py -m scripts\.ops\s+)([a-z][a-z0-9-]*)", re.I)


def unregistered_verbs(
    commands: set[str] | dict[str, object], docs_dir: str | None = None
) -> dict[str, list[str]]:
    """{verb: [doc names]} for each `ops <verb>` a living doc (line-3 card) names that is not
    in `commands`. A snapshot or a log may name a retired command; a living doc may not."""
    root = Path(docs_dir or ROOT_DIR) / "docs"
    found: dict[str, list[str]] = {}
    if not root.is_dir():
        return found
    for path in sorted(root.glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) < 3 or "living" not in lines[2]:
            continue
        for match in _OPS_START.findall("\n".join(lines)):
            verb = match.strip().lower()
            if verb and verb not in _SKIP and verb not in commands:
                found.setdefault(verb, [])
                if path.name not in found[verb]:
                    found[verb].append(path.name)
    return found
