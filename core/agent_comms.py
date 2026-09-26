"""Agent hand-off status — who wrote what, and whether the mailbox still tells the truth.

Two agents work in this tree and both commit as the same git author, so the
`Co-authored-by:` trailer is the only per-commit record of who did the work. The
mailbox (`docs/handoff.md`) is prose and can go stale; `git log` cannot. This module
reads both and reports where they disagree.

Read-only: it shells out to `git` and reads one markdown file. Never writes.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from core.logging import get_logger

logger = get_logger("core.agent_comms")

ROOT = Path(__file__).resolve().parent.parent
MAILBOX = ROOT / "docs" / "handoff.md"

# Agents that sign commits here. Matched case-insensitively against the trailer.
AGENTS = ("Claude", "Cursor")

_SLOT_RE = re.compile(r"^##\s+Slot\s+[—-]\s+(?P<name>.+?)\s*$", re.MULTILINE)
_HEAD_RE = re.compile(r"HEAD at write:\*{0,2}\s*`(?P<sha>[0-9a-f]{7,40})`", re.IGNORECASE)
_WRITTEN_RE = re.compile(r"\*\*Written:\*\*\s*(?P<when>[0-9]{4}-[0-9]{2}-[0-9]{2}|_[^_]*_)")


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("git %s skipped: %s", args[0] if args else "", exc)
        return ""


def signed_commit_counts() -> dict[str, int]:
    """Commits carrying each agent's Co-authored-by trailer."""
    counts: dict[str, int] = {}
    for agent in AGENTS:
        raw = _git("log", "-i", "--grep", f"Co-authored-by: {agent}", "--format=%h")
        counts[agent] = len([ln for ln in raw.splitlines() if ln.strip()])
    return counts


def tree_state() -> dict[str, int | str]:
    """HEAD plus how much work is sitting uncommitted right now."""
    porcelain = _git("status", "--porcelain")
    lines = [ln for ln in porcelain.splitlines() if ln.strip()]
    return {
        "head": _git("log", "-1", "--format=%h %s"),
        "modified": len([ln for ln in lines if not ln.startswith("??")]),
        "untracked": len([ln for ln in lines if ln.startswith("??")]),
    }


def slots() -> list[dict[str, str]]:
    """Each mailbox slot with the HEAD it claims to have been written at."""
    if not MAILBOX.is_file():
        return []
    body = MAILBOX.read_text(encoding="utf-8")
    found: list[dict[str, str]] = []
    marks = list(_SLOT_RE.finditer(body))
    for i, mark in enumerate(marks):
        chunk = body[mark.end() : marks[i + 1].start() if i + 1 < len(marks) else len(body)]
        sha = _HEAD_RE.search(chunk)
        when = _WRITTEN_RE.search(chunk)
        found.append(
            {
                "agent": mark.group("name").strip(),
                "sha": sha.group("sha") if sha else "",
                "written": (when.group("when").strip("_ ") if when else "") or "never",
            }
        )
    return found


def commits_since(sha: str) -> int:
    """How many commits landed after a slot was written. -1 when unknowable."""
    if not sha:
        return -1
    raw = _git("log", f"{sha}..HEAD", "--format=%h")
    if not raw and not _git("cat-file", "-t", sha):
        return -1
    return len([ln for ln in raw.splitlines() if ln.strip()])


def behind_note(behind: int) -> str:
    """How a slot's age reads in the report. The second agent helps intermittently, so
    being behind HEAD is the normal state, not a defect - unfindable work is."""
    if behind < 0:
        return "unknown sha"
    if behind == 0:
        return "current"
    return f"{behind} commit(s) behind HEAD - normal for an intermittent partner"


_GLYPHS = str.maketrans(
    {"\u2192": "->", "\u2190": "<-", "\u2014": "-", "\u2013": "-", "\u2026": "...", "\u00b7": "-"}
)


def _console_safe(text: str) -> str:
    """cp1252-safe by construction. Git output (commit subjects) is not this module's
    to keep ASCII - wave 32 found main's HEAD subject carried a U+2192 arrow, which
    reached the report verbatim and broke it on a Windows console (candidate 250)."""
    return text.translate(_GLYPHS).encode("cp1252", errors="replace").decode("cp1252")


def render() -> str:
    """Operator-facing report. ASCII only (cp1252-safe, candidate 250)."""
    return _console_safe(_render())


def _render() -> str:
    out: list[str] = ["Agent hand-off"]
    state = tree_state()
    out.append(f"  HEAD        : {state['head'] or 'unknown'}")

    dirty = int(state["modified"]) + int(state["untracked"])
    detail = f"{state['modified']} modified, {state['untracked']} untracked"
    if dirty:
        out.append(f"  Uncommitted : {detail}  <- a fresh clone and CI see none of this")
    else:
        out.append(f"  Uncommitted : {detail}")

    counts = signed_commit_counts()
    signed = ", ".join(f"{a} {n}" for a, n in counts.items())
    out.append(f"  Signed      : {signed}")
    unsigned = [a for a, n in counts.items() if n == 0]
    if unsigned:
        out.append(f"                {' and '.join(unsigned)} has never signed a commit")

    out.append("  Mailbox     : docs/handoff.md")
    for slot in slots():
        if slot["written"] == "never" or not slot["sha"]:
            out.append(f"    {slot['agent']:<12} never written")
            continue
        age = behind_note(commits_since(slot["sha"]))
        out.append(f"    {slot['agent']:<12} {slot['written']} @ {slot['sha']} ({age})")
    return "\n".join(out)
