"""Measure auto-research on the stored runs (#863).

Wave 34 turned auto-research on by default (decisions §35) on the promise that it
would be measured over the next ten runs, then retuned or switched off. This reads
each run's persisted `features_json.auto_research` report and counts pages read, lines
kept, lines dropped as off-topic, and - the number that decides it - how many kept
lines a *supported* claim actually cited (`claim_verification.claims[].citation_line`).

Runs from before wave 35 have counts but no `kept_lines`, so they cannot count cites.

    py -m scripts.ops auto-research --channel tapin
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from typing import Any

from config.channels import resolve_channel_id
from core.logging import get_logger

logger = get_logger("analytics.auto_research_report")

_PREFIX = re.compile(r"^[\s\-\*•\d\.\)\]\[]+")


def _load(raw: Any) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _norm(text: str) -> str:
    return _PREFIX.sub("", str(text or "")).strip().lower()[:80]


def _cited(kept: list[str], claims: list[dict[str, Any]]) -> int:
    """How many kept lines back at least one supported claim."""
    cites = [_norm(c.get("citation_line", "")) for c in claims if c.get("supported")]
    cites = [c for c in cites if len(c) >= 20]
    hits = 0
    for line in kept:
        key = _norm(line)
        if len(key) >= 20 and any(key in c or c in key for c in cites):
            hits += 1
    return hits


def summarize(runs: list[Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "runs": len(runs),
        "with_report": 0,
        "pages": 0,
        "lines": 0,
        "off_topic": 0,
        "cited": 0,
        "cite_measurable": 0,
        "reasons": Counter(),
        "rows": [],
    }
    for run in runs:
        features = _load(getattr(run, "features_json", None))
        report = features.get("auto_research")
        if not isinstance(report, dict):
            continue
        summary["with_report"] += 1
        for key in ("pages", "lines", "off_topic"):
            summary[key] += int(report.get(key) or 0)
        summary["reasons"][str(report.get("reason") or "unknown")] += 1
        kept = report.get("kept_lines")
        cited = None
        if isinstance(kept, list):
            claims = (features.get("claim_verification") or {}).get("claims") or []
            cited = _cited([str(k) for k in kept], [c for c in claims if isinstance(c, dict)])
            summary["cited"] += cited
            summary["cite_measurable"] += 1
        summary["rows"].append(
            {
                "run_id": getattr(run, "id", None),
                "topic": str(getattr(run, "input_topic", "") or "")[:50],
                "pages": int(report.get("pages") or 0),
                "lines": int(report.get("lines") or 0),
                "cited": cited,
                "reason": str(report.get("reason") or ""),
            }
        )
    return summary


def render(summary: dict[str, Any], channel_id: str = "") -> str:
    head = f"Auto-research across stored runs{f' ({channel_id})' if channel_id else ''}"
    n = summary["with_report"]
    if not n:
        return f"{head}\n  No run has an auto-research report yet (it started in wave 34)."
    lines = [
        head,
        f"  runs with a report : {n} of {summary['runs']}",
        f"  pages read         : {summary['pages']}",
        f"  lines kept         : {summary['lines']}  (off-topic dropped: {summary['off_topic']})",
    ]
    if summary["cite_measurable"]:
        lines.append(
            f"  lines a supported claim cited: {summary['cited']} "
            f"(over {summary['cite_measurable']} run(s) that stored their lines)"
        )
    else:
        lines.append("  cited lines: not measurable yet - reports before wave 35 kept no lines")
    reasons = ", ".join(f"{k} {v}" for k, v in summary["reasons"].most_common())
    lines.append(f"  outcomes           : {reasons}")
    lines.append("  last runs:")
    for row in summary["rows"][-10:]:
        cited = "-" if row["cited"] is None else row["cited"]
        lines.append(
            f"    #{row['run_id']}: {row['pages']} page(s), {row['lines']} line(s), "
            f"cited {cited} [{row['reason']}] {row['topic']}"
        )
    if n < 10:
        lines.append(
            f"  {10 - n} more run(s) before the #863 verdict (keep, retune or switch off)."
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure auto-research on stored runs (#863)")
    parser.add_argument("--channel", default="tapin")
    args = parser.parse_args(argv)
    channel_id = resolve_channel_id(args.channel)
    try:
        from storage.repositories.content_runs import get_content_run_repository

        runs = get_content_run_repository().list_for_channel(channel_id)
    except Exception as exc:
        logger.warning("auto-research report: runs unreadable: %s", exc)
        runs = []
    runs = sorted(runs, key=lambda r: int(getattr(r, "id", 0) or 0))
    print(render(summarize(runs), channel_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
