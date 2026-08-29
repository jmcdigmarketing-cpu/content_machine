"""Roadmap counts, read from the files rather than maintained by hand.

The roadmap header carried hand-written totals for months and was measurably
wrong: "318 open" against a real 317 before the 2026-08-28 split. A number a human
retypes is a number that drifts, so this counts the files and `ops roadmap-index`
prints it.

Read-only. Never writes a doc.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

OPEN_RE = re.compile(r"^\s*- \[ \]")
DONE_RE = re.compile(r"^\s*- \[x\]")
SIZE_RE = re.compile(r"`\[(XL|L|M|S)\]`")
NUM_RE = re.compile(r"^\s*- \[ \] \*{0,2}(\d+)\.")

FILES = ("roadmap.md", "desktop_app.md", "backlog.md", "roadmap_archive.md")
SIZES = ("XL", "L", "M", "S")


def _lines(name: str) -> list[str]:
    path = DOCS / name
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def counts() -> dict[str, object]:
    """Open/shipped per file, open by size, and the numbered range in use."""
    per_file: dict[str, dict[str, int]] = {}
    by_size: dict[str, int] = dict.fromkeys(SIZES, 0)
    untagged = 0
    numbers: list[int] = []

    for name in FILES:
        rows = _lines(name)
        opens = [ln for ln in rows if OPEN_RE.match(ln)]
        per_file[name] = {
            "lines": len(rows),
            "open": len(opens),
            "done": sum(1 for ln in rows if DONE_RE.match(ln)),
        }
        for ln in opens:
            size = SIZE_RE.search(ln)
            if size:
                by_size[size.group(1)] += 1
            else:
                untagged += 1
            num = NUM_RE.match(ln)
            if num:
                numbers.append(int(num.group(1)))

    return {
        "per_file": per_file,
        "by_size": by_size,
        "untagged": untagged,
        "open_total": sum(v["open"] for v in per_file.values()),
        "done_total": sum(v["done"] for v in per_file.values()),
        "numbered_open": len(numbers),
        "highest_number": max(numbers) if numbers else 0,
    }


def render(data: dict[str, object] | None = None) -> str:
    """Operator-facing report. ASCII only (candidate 250)."""
    data = data or counts()
    per_file: dict[str, dict[str, int]] = data["per_file"]  # type: ignore[assignment]
    by_size: dict[str, int] = data["by_size"]  # type: ignore[assignment]

    out = ["Roadmap index"]
    for name in FILES:
        row = per_file.get(name)
        if not row:
            out.append(f"  {name:22} MISSING")
            continue
        out.append(
            f"  {name:22} {row['lines']:5} lines   open {row['open']:4}   done {row['done']:4}"
        )
    out.append(
        f"  {'TOTAL':22} {'':5}         open {data['open_total']:4}   "
        f"done {data['done_total']:4}"
    )
    out.append("")
    sizes = "  ".join(f"{s} {by_size[s]}" for s in SIZES)
    out.append(f"  open by size : {sizes}")
    if data["untagged"]:
        out.append(f"  untagged     : {data['untagged']} open item(s) carry no size")
    out.append(f"  numbered     : {data['numbered_open']} open, highest #{data['highest_number']}")
    return "\n".join(out)
