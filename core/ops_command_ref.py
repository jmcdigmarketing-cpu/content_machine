"""#458: ops command reference generated from the live COMMANDS registry."""

from __future__ import annotations

import os

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
