"""#639: env keys read in code vs keys documented in `.env.example`.

Measured when filed: 392 read against 273 documented. Every wave since added a flag
that was documented by hand or not at all, and nothing measured the gap, so it could
only grow. This measures it, and `config/env_lint_baseline.json` freezes today's
undocumented set: a *new* undocumented key fails a test, the old ones stay visible and
can only shrink.

"Read" means a literal key name passed to `os.getenv`, `os.environ.get`,
`os.environ[...]`, `flag_enabled`, or the module-local `_flag` / `_f` / `_env_*`
wrappers. A read through a variable cannot be resolved statically, so it is counted as
a blind spot rather than guessed at. "Documented" includes commented example lines
(`# FLAG=true`), which is how optional flags are documented here.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from config.paths import ROOT_DIR

BASELINE_FILE = Path(ROOT_DIR) / "config" / "env_lint_baseline.json"

_EXCLUDED_DIRS = {
    "tests",
    ".venv",
    "venv",
    "env",
    "ComfyUI",
    "node_modules",
    "build",
    "dist",
    "__pycache__",
    "ai-marketing-skills",
    "qiaomu-anything-to-notebooklm",
    "system_prompts_leaks",
    "piper-voice-models-main",
}
_KEY = r"([A-Z][A-Z0-9_]{2,})"
_LITERAL_RE = re.compile(
    r"(?<![\w.])(?:os\.getenv|os\.environ\.get|flag_enabled|_flag|_f|_env_[a-z_]+)\(\s*\""
    + _KEY
    + r"\""
    r"|os\.environ\[\s*\"" + _KEY + r"\"\s*\]"
)
_DYNAMIC_RE = re.compile(r"os\.(?:getenv|environ\.get)\(\s*[a-z_]")


@dataclass
class EnvReads:
    keys: set[str]
    dynamic: int


@dataclass
class EnvLint:
    undocumented: list[str]
    unread: list[str]
    dynamic: int
    new_undocumented: list[str]


def _python_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        for current, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d not in _EXCLUDED_DIRS and not d.startswith(".")]
            files.extend(Path(current) / name for name in names if name.endswith(".py"))
    return files


def scan_reads(roots: list[Path] | None = None) -> EnvReads:
    keys: set[str] = set()
    dynamic = 0
    for path in _python_files(roots or [Path(ROOT_DIR)]):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in _LITERAL_RE.finditer(text):
            keys.add(match.group(1) or match.group(2))
        dynamic += len(_DYNAMIC_RE.findall(text))
    return EnvReads(keys=keys, dynamic=dynamic)


def documented_keys(path: str | Path | None = None) -> set[str]:
    from core.config_diff import env_example_keys

    return set(env_example_keys(path, include_commented=True))


def load_baseline(path: str | Path | None = None) -> set[str]:
    try:
        data = json.loads(Path(path or BASELINE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {str(key) for key in (data.get("undocumented") or [])}


def lint() -> EnvLint:
    reads = scan_reads()
    documented = documented_keys()
    undocumented = sorted(reads.keys - documented)
    return EnvLint(
        undocumented=undocumented,
        unread=sorted(documented - reads.keys),
        dynamic=reads.dynamic,
        new_undocumented=sorted(set(undocumented) - load_baseline()),
    )


def render_lint(report: EnvLint) -> str:
    lines = [
        "Env lint (.env.example vs code)",
        f"  undocumented : {len(report.undocumented)} key(s) read in code, absent from .env.example",
        f"  unread       : {len(report.unread)} key(s) documented but never read by literal name",
        f"  dynamic reads: {report.dynamic} (a variable key cannot be checked; blind spot)",
    ]
    if report.new_undocumented:
        lines.append(f"  NEW since the baseline ({len(report.new_undocumented)}):")
        lines.extend(f"    {key}" for key in report.new_undocumented)
        lines.append(
            "  Document them in .env.example, or deliberately add to config/env_lint_baseline.json."
        )
    else:
        lines.append("  no new undocumented key since config/env_lint_baseline.json")
    if report.unread:
        lines.append("  documented but unread:")
        lines.extend(f"    {key}" for key in report.unread)
    return "\n".join(lines)
