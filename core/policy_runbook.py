"""#132 policy-incident runbook path — operator-facing, not a silent markdown file."""

from __future__ import annotations

from pathlib import Path

from config.paths import ROOT_DIR

_REL = Path("docs") / "policy_incident_runbook.md"


def runbook_path() -> Path:
    return Path(ROOT_DIR) / _REL


def runbook_text() -> str:
    path = runbook_path()
    return path.read_text(encoding="utf-8")
