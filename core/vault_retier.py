"""Move scraped page lines that were saved as operator facts to link tier (#857).

Until run 98 the key-facts prompt saved every line it collected, pasted-link lines
included, to `_operator_facts/` as `tier: operator` - a `Source: <page title>` line
followed by the page's paragraphs and, sometimes, its newsletter/cookie boilerplate.
Wave 33 (#845) sends new link lines to `_link_facts/` and stopped vault lines pinning;
the old notes still read as operator facts and still surface as suggestions.

This lists `_operator_facts/` notes holding lines that are recognisably scraped - the
reader's own `Source:` / `Source video:` lines, or page boilerplate the link reader
drops - and, only when asked, moves each whole note to `_link_facts/` at link tier.
A note is moved whole rather than split: demoting a typed line to link tier costs
rank, splitting rewrites the operator's note. Nothing is deleted, and a note already
at the target path is never overwritten.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger("core.vault_retier")

_OPERATOR = "_operator_facts"
_LINK = "_link_facts"
# What `link_facts` wrote for a pasted page before run 98, and for a YouTube link today.
_SCRAPED_PREFIXES = ("source:", "source video:")


def scraped_line(line: str) -> bool:
    """True for a line the link reader produced, not one the operator typed."""
    low = (line or "").strip().lower()
    if low.startswith(_SCRAPED_PREFIXES):
        return True
    from core.link_facts import is_page_boilerplate

    return is_page_boilerplate(line)


@dataclass(frozen=True)
class RetierPlan:
    rel_path: str
    scraped: int
    total: int
    samples: tuple[str, ...]


def plan_retier(channel_id: str | None = None) -> list[RetierPlan]:
    """`_operator_facts/` notes holding at least one scraped line. Read-only."""
    from core.obsidian_facts import _note_matches_channel, _vault_path
    from core.vault_index import iter_notes

    vault = _vault_path()
    if not vault:
        return []
    plans: list[RetierPlan] = []
    for note in iter_notes(vault):
        rel = Path(note.rel_path)
        if _OPERATOR not in {p.lower() for p in rel.parts}:
            continue
        if channel_id and not _note_matches_channel(note.meta, rel, channel_id):
            continue
        if (note.meta.get("tier") or "").strip().lower() == "link":
            continue
        scraped = [b for b in note.bullets if scraped_line(b)]
        if scraped:
            plans.append(
                RetierPlan(
                    rel_path=str(rel).replace("\\", "/"),
                    scraped=len(scraped),
                    total=len(note.bullets),
                    samples=tuple(scraped[:2]),
                )
            )
    return sorted(plans, key=lambda p: p.rel_path)


def _link_path(rel_path: str) -> Path:
    parts = [(_LINK if p.lower() == _OPERATOR else p) for p in Path(rel_path).parts]
    return Path(*parts)


def _retier_text(text: str, day: str) -> str:
    """The note with link tier in its frontmatter; the body is untouched."""
    stamp = f"retiered: {day} from {_OPERATOR}"
    if not text.startswith("---"):
        return f"---\ntier: link\n{stamp}\n---\n\n{text}"
    end = text.find("\n---", 3)
    if end == -1:
        return f"---\ntier: link\n{stamp}\n---\n\n{text}"
    block, rest = text[3:end], text[end:]
    lines = block.strip("\n").splitlines()
    out: list[str] = []
    tiered = False
    for line in lines:
        key = line.partition(":")[0].strip().lower()
        if key == "tier":
            out.append("tier: link")
            tiered = True
        elif key == "tags":
            out.append(re.sub(r"\boperator\b", "link", line))
        elif key == "retiered":
            continue
        else:
            out.append(line)
    if not tiered:
        out.append("tier: link")
    out.append(stamp)
    return "---\n" + "\n".join(out) + rest


def apply_retier(plans: list[RetierPlan], *, today: date | None = None) -> list[dict[str, Any]]:
    """Move each planned note to `_link_facts/`. Never overwrites; never raises."""
    from core.obsidian_facts import _vault_path

    vault = _vault_path()
    if not vault:
        return []
    day = (today or date.today()).isoformat()
    results: list[dict[str, Any]] = []
    for plan in plans:
        src = vault / plan.rel_path
        dst = vault / _link_path(plan.rel_path)
        row: dict[str, Any] = {"from": plan.rel_path, "to": str(_link_path(plan.rel_path))}
        try:
            if dst.exists():
                row["status"] = "exists"
            else:
                text = src.read_text(encoding="utf-8")
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(_retier_text(text, day), encoding="utf-8", newline="\n")
                src.unlink()
                row["status"] = "moved"
        except OSError as exc:
            logger.warning("vault re-tier failed for %s: %s", plan.rel_path, exc)
            row["status"] = f"failed: {exc}"
        results.append(row)
    return results


def report_lines(channel_id: str, *, apply: bool = False) -> list[str]:
    """What `ops vault-retier` prints."""
    from core.obsidian_facts import _vault_path

    if not _vault_path():
        return ["Vault re-tier: OBSIDIAN_VAULT_PATH is not set - nothing to scan."]
    plans = plan_retier(channel_id)
    if not plans:
        return [f"Vault re-tier - {channel_id}: no {_OPERATOR} note holds scraped page lines."]
    head = "moving" if apply else "dry run, nothing moved"
    out = [
        f"Vault re-tier - {channel_id} ({head})",
        f"  {len(plans)} {_OPERATOR} note(s) hold lines scraped from pasted pages:",
    ]
    for plan in plans:
        out.append(f"    {plan.rel_path}  {plan.scraped} of {plan.total} lines scraped")
        for sample in plan.samples:
            out.append(f"      e.g. {sample[:100]}")
    if not apply:
        out.append(
            f"  Move them to {_LINK}/ (link tier, never pinned): "
            "py -m scripts.ops vault-retier --apply"
        )
        return out
    for row in apply_retier(plans):
        out.append(f"  {row['status']:<7} {row['from']} -> {row['to']}")
    out.append(
        f"  To undo one: move it back into {_OPERATOR}/ and set `tier: operator` "
        "in its frontmatter."
    )
    return out
