"""Roadmap counts, read from the files rather than maintained by hand.

The roadmap header carried hand-written totals for months and was measurably
wrong: "318 open" against a real 317 before the 2026-08-28 split. A number a human
retypes is a number that drifts, so this counts the files and `ops roadmap-index`
prints it.

Read-only. Never writes a doc.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

OPEN_RE = re.compile(r"^\s*- \[ \]")
DONE_RE = re.compile(r"^\s*- \[x\]")
# Decision 82 (2026-10-27): an item that moves no bridge number is parked - neither open nor done.
PARKED_RE = re.compile(r"^\s*- \[-\]")
LANES = ("views", "subscribers", "hours", "money", "cost", "defect")
LANE_RE = re.compile(r"· lane: (" + "|".join(LANES) + r")\b")
SIZE_RE = re.compile(r"`\[(XL|L|M|S)\]`")
NUM_RE = re.compile(r"^\s*- \[ \] \*{0,2}(\d+)\.")
# #1510: an idea filed for one of the hands-off plan's shortfalls carries "*(S21.3, filed ...".
SHORTFALL_RE = re.compile(r"\*\(S(\d{2})\.\d+, filed")
# Decision 82: the bridge's ideas ("*(B01.3, filed ...") expire on the same 90 days.
FILED_RE = re.compile(r"\*\([SB]\d{2}\.\d+, filed (\d{4}-\d{2}-\d{2})\)")
IDEA_DAYS = 90  # decision 68: an idea with no measurement after 90 days is retired (#1509)
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
            "parked": sum(1 for ln in rows if PARKED_RE.match(ln)),
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
        "parked_total": sum(v["parked"] for v in per_file.values()),
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


def lane_counts(lines: list[str]) -> tuple[dict[str, int], list[int]]:
    """Decision 82: ({lane: open items}, the open numbered items that name no lane). A lane is
    written at the end of the item's line, " · lane: views"."""
    lanes: dict[str, int] = {}
    unlaned: list[int] = []
    for line in lines:
        if not OPEN_RE.match(line):
            continue
        lane = LANE_RE.search(line)
        if lane:
            lanes[lane.group(1)] = lanes.get(lane.group(1), 0) + 1
            continue
        number = NUM_RE.match(line)
        if number:
            unlaned.append(int(number.group(1)))
    return dict(sorted(lanes.items())), unlaned


def idea_expiry(lines: list[str], *, today: date | None = None) -> dict[str, Any]:
    """#1509: the open shortfall ideas filed `IDEA_DAYS` or more days ago - each to be measured or
    retired with the reason - and the day the next one reaches it."""
    moment = today or date.today()
    overdue: list[int] = []
    due_days: list[date] = []
    for line in lines:
        if not OPEN_RE.match(line):
            continue
        filed = FILED_RE.search(line)
        number = NUM_RE.match(line)
        if not filed or not number:
            continue
        due = date.fromisoformat(filed.group(1)) + timedelta(days=IDEA_DAYS)
        if due <= moment:
            overdue.append(int(number.group(1)))
        else:
            due_days.append(due)
    return {"overdue": overdue, "next_due": min(due_days) if due_days else None}


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
    data: dict[str, object] | None = None,
    *,
    list_open: bool = False,
    by_shortfall: bool = False,
    public_videos: int | None = None,
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
        f"   parked {data.get('parked_total', 0)}"
    )
    out.append("")
    lanes, unlaned = lane_counts(_lines("backlog.md"))
    if lanes or unlaned:  # decision 82: the race to monetization or big views for little money
        line = "  by lane      : " + "  ".join(f"{k} {v}" for k, v in lanes.items())
        if unlaned:
            line += f"  - no lane: {', '.join(f'#{n}' for n in unlaned[:8])}"
        out.append(line)
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
    expiry = idea_expiry(_lines("backlog.md"))
    if expiry["overdue"]:
        out.append(
            f"  ideas expire : {len(expiry['overdue'])} past {IDEA_DAYS} days - measure or retire "
            f"them with the reason (decision 68): "
            + ", ".join(f"#{n}" for n in expiry["overdue"][:8])
        )
    elif expiry["next_due"]:
        out.append(f"  ideas expire : the first reaches {IDEA_DAYS} days on {expiry['next_due']}")
    if public_videos:  # #1515: whether the backlog grows faster than what reaches viewers
        out.append(
            f"  per public video: {data['open_total']} open over {public_videos} public videos - "
            f"{int(data['open_total']) / public_videos:.1f} each"  # type: ignore[call-overload]
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


# ---- #1517 (S22): each shortfall with the check that says it is done ---------------------------
#
# `docs/hands_off_plan.md` gives every shortfall a **Done when** - a command and what it must show.
# Nothing said them together, so whether a shortfall was closing was read by hand. `ops shortfalls`
# prints each with its open backlog items (#1510), and the weekly review runs it.

PLAN = DOCS / "hands_off_plan.md"
_HEADING_RE = re.compile(r"^### (S\d{2}) (.+?)\s*$")
_DONE_RE = re.compile(r"\*\*Done when:\*\*\s*(.*)$")
_OPS_RE = re.compile(r"py -m scripts\.ops ([a-z][a-z0-9-]*)")


def sections(text: str | None = None) -> list[dict[str, Any]]:
    """[{key, name, done_when, commands}] in plan order. `done_when` is the sentence, its wrapped
    lines joined; `commands` the `ops` commands it names."""
    lines = (PLAN.read_text(encoding="utf-8") if text is None else text).splitlines()
    out: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    reading = False
    for line in lines:
        heading = _HEADING_RE.match(line)
        if heading:
            current = {"key": heading.group(1), "name": heading.group(2), "done_when": "",
                       "commands": []}  # fmt: skip
            out.append(current)
            reading = False
            continue
        if line.startswith("## "):
            current, reading = None, False
            continue
        if current is None:
            continue
        done = _DONE_RE.search(line)
        if done:
            current["done_when"] = done.group(1).strip()
            reading = True
        elif reading and line.strip() and not line.startswith("**"):
            current["done_when"] += " " + line.strip()
        else:
            reading = False
    for section in out:
        section["commands"] = list(dict.fromkeys(_OPS_RE.findall(section["done_when"])))
    return out


def shortfall_lines() -> list[str]:
    """`ops shortfalls`: one line a shortfall - its open items and its done-when."""
    try:
        open_by = counts().get("by_shortfall") or {}
    except Exception:
        open_by = {}
    found = sections()
    out = [
        f"Shortfalls - {len(found)} in docs/hands_off_plan.md, each with the check that closes it"
    ]
    for s in found:
        n = open_by.get(s["key"], 0) if isinstance(open_by, dict) else 0
        out.append(f"  {s['key']} {s['name'][:52]} - {n} open")
        out.append(f"      done when {s['done_when'] or '(none written)'}")
    return out
