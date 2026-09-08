"""#458: ops command reference generated from the live COMMANDS registry."""

from __future__ import annotations

import os
from pathlib import Path

from config.paths import ROOT_DIR

DOCS_PATH = os.path.join(ROOT_DIR, "docs", "ops_commands.md")


def _registry_commands() -> list[tuple[str, str]]:
    from scripts.ops import COMMANDS

    return [(name, help_text) for name, (help_text, _fn) in sorted(COMMANDS.items())]


def command_ref_markdown(commands: list[tuple[str, str]] | None = None) -> str:
    cmds = commands if commands is not None else _registry_commands()
    lines = [
        "# Ops command reference",
        "",
        "Generated from `scripts/ops.py` `COMMANDS` by `py -m scripts.ops command-ref`.",
        "`ops list` is the live catalog; this file must match it.",
        "",
        "| Command | What it does |",
        "| --- | --- |",
    ]
    for name, help_text in cmds:
        safe = help_text.replace("|", "\\|")
        lines.append(f"| `{name}` | {safe} |")
    lines.append("")
    return "\n".join(lines)


def write_command_ref(path: str | None = None) -> str:
    target = path or DOCS_PATH
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(command_ref_markdown())
    return target


def check_command_ref(path: str | None = None) -> int:
    """0 when docs/ops_commands.md matches the live registry. Used by pre-commit."""
    target = path or DOCS_PATH
    try:
        on_disk = Path(target).read_text(encoding="utf-8")
    except OSError:
        print(f"{target} is missing; run: py -m scripts.ops command-ref")
        return 1
    if on_disk != command_ref_markdown():
        print("docs/ops_commands.md is stale; run: py -m scripts.ops command-ref")
        return 1
    return 0
