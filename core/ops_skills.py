"""Agent Skills (Pillar 7 C1) — expose the operator CLI as a SKILL.md.

The Agent Skills open standard (`SKILL.md` folders that Claude Code / Copilot agents
auto-load) lets an agent operate the Content OS pipeline through its ~40 `scripts/ops.py`
`@_register` commands as a first-class skill. This module regenerates
`skills/content-ops/SKILL.md` from the **live** `COMMANDS` registry so the skill never
drifts from the CLI — edit the registry, then run `py -m scripts.ops gen-skills`.

ASCII-only output (skills are read by `scripts/ops.py`, which is cp1252 on Windows).
"""

from __future__ import annotations

import os

SKILL_NAME = "content-ops"
SKILL_DIR = os.path.join("skills", SKILL_NAME)
SKILL_PATH = os.path.join(SKILL_DIR, "SKILL.md")

_DESCRIPTION = (
    "Operate the Content OS short-form video pipeline via its operator CLI "
    "(py -m scripts.ops <command>): discovery, batch drafts, status and reliability "
    "dashboards, analytics sync, publish queue, voice catalog, and unattended overnight "
    "runs. Use when asked to run, check, or automate Content OS operations."
)


def _registry_commands() -> list[tuple[str, str]]:
    """(name, help) for every ops command, sorted. Imports at call time to avoid a cycle."""
    from scripts.ops import COMMANDS

    return [(name, help_text) for name, (help_text, _fn) in sorted(COMMANDS.items())]


def render_skill(commands: list[tuple[str, str]] | None = None) -> str:
    """The full SKILL.md text (Agent Skills frontmatter + a command reference table)."""
    cmds = commands if commands is not None else _registry_commands()
    lines = [
        "---",
        f"name: {SKILL_NAME}",
        f"description: {_DESCRIPTION}",
        "---",
        "",
        "# Content OS operator skill",
        "",
        "Run any operator command with:",
        "",
        "```bash",
        "py -m scripts.ops <command> [--channel tapin] [--count N] [...]",
        "```",
        "",
        "`py -m scripts.ops list` prints this catalog live. Most-used: `all-checks`, "
        "`status`, `reliability` (credit/quota/cache), `weekly-report`, `batch-drafts`, "
        "`overnight`.",
        "",
        "## Commands",
        "",
        "| Command | What it does |",
        "| --- | --- |",
    ]
    for name, help_text in cmds:
        lines.append(f"| `{name}` | {help_text.replace('|', chr(92) + '|')} |")
    lines += [
        "",
        "## Notes",
        "",
        "- Windows/PowerShell dev box; command output is ASCII-safe (cp1252).",
        "- Paid signals (Apify) and LLM calls cost credits: check budget first with "
        "`reliability` / `free-doctor`; `RUN_COST_MODE=free` pins $0 backends.",
        "- Generated from the ops registry by `py -m scripts.ops gen-skills` "
        "(core/ops_skills.py) — edit the registry, not this file.",
        "- Claude Code users can also symlink this folder into `.claude/skills/`.",
        "",
    ]
    return "\n".join(lines)


def write_skill(path: str | None = None) -> str:
    """Write the SKILL.md (default skills/content-ops/SKILL.md). Returns the path."""
    target = path or SKILL_PATH
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(render_skill())
    return target
