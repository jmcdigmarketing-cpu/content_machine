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
# #1510: an idea filed for one of the hands-off plan's shortfalls carries "*(S21.3, filed ...".
SHORTFALL_RE = re.compile(r"\*\(S(\d{2})\.\d+, filed")
PLAN_HEADING_RE = re.compile(r"^### (S\d{2}) (.+?)\s*$")

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
        "by_shortfall": shortfall_counts(_lines("backlog.md")),
        "per_file": per_file,
        "by_size": by_size,
        "untagged": untagged,
        "open_total": sum(v["open"] for v in per_file.values()),
        "done_total": sum(v["done"] for v in per_file.values()),
        "numbered_open": len(numbers),
        "highest_number": max(numbers) if numbers else 0,
    }


def shortfall_counts(lines: list[str]) -> dict[str, int]:
    """#1510: open backlog items per shortfall of the hands-off plan, "S01" to "S22" - an item
    that names none is not counted."""
    out: dict[str, int] = {}
    for line in lines:
        if not OPEN_RE.match(line):
            continue
        tag = SHORTFALL_RE.search(line)
        if tag:
            key = f"S{tag.group(1)}"
            out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items()))


def shortfall_names(lines: list[str]) -> dict[str, str]:
    """{"S21": "The hook score is backwards (Oct 18)"} from the plan's section headings."""
    out: dict[str, str] = {}
    for line in lines:
        match = PLAN_HEADING_RE.match(line)
        if match:
            out[match.group(1)] = match.group(2)
    return out


def open_numbered(lines: list[str]) -> list[tuple[int, str]]:
    """Open numbered backlog lines, in file order. A ticked line is not open."""
    out: list[tuple[int, str]] = []
    for line in lines:
        match = NUM_RE.match(line)
        if not match:
            continue
        title = line.split(".", 1)[1].strip().replace("**", "")
        out.append((int(match.group(1)), title))
    return out


def render(
    data: dict[str, object] | None = None, *, list_open: bool = False, by_shortfall: bool = False
) -> str:
    """Operator-facing report. ASCII only (candidate 250).

    The open numbered lines are behind `list_open` (#1257). The default is the
    counts; `ops roadmap-index` had grown to 232 lines.
    """
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
        f"  {'TOTAL':22} {'':5}         open {data['open_total']:4}   done {data['done_total']:4}"
    )
    out.append("")
    sizes = "  ".join(f"{s} {by_size[s]}" for s in SIZES)
    out.append(f"  open by size : {sizes}")
    if data["untagged"]:
        out.append(f"  untagged     : {data['untagged']} open item(s) carry no size")
    out.append(f"  numbered     : {data['numbered_open']} open, highest #{data['highest_number']}")
    shortfalls: dict[str, int] = data.get("by_shortfall") or {}  # type: ignore[assignment]
    if shortfalls:
        # #1510: the plan says "falling after this wave" per shortfall; the five with the most
        # open on one line, all of them behind --by-shortfall.
        top = sorted(shortfalls.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        out.append(
            f"  by shortfall : {sum(shortfalls.values())} open across {len(shortfalls)} - most "
            + ", ".join(f"{k} {v}" for k, v in top)
            + " (--by-shortfall for each)"
        )
    if by_shortfall:
        names = shortfall_names(_lines("hands_off_plan.md"))
        out.append("Open by shortfall (hands_off_plan.md)")
        for key in sorted(set(names) | set(shortfalls)):
            out.append(
                f"  {key} {names.get(key, '(no section)')[:66]:66} {shortfalls.get(key, 0):3}"
            )
    if list_open:
        out.append("Open numbered")
        for number, title in open_numbered(_lines("backlog.md")):
            shown = title.replace("\u2192", "->").replace("\u2014", "-").replace("\u2013", "-")
            shown = shown.encode("cp1252", "replace").decode("cp1252")
            out.append(f"  #{number} {shown}")
    return "\n".join(out)
