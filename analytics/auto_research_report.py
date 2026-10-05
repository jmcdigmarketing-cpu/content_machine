"""Measure auto-research on the stored runs (#863).

Wave 34 turned auto-research on by default (decisions §35) on the promise that it
would be measured over the next ten runs, then retuned or switched off. This reads
each run's persisted `features_json.auto_research` report and counts pages read, lines
kept, lines dropped as off-topic, and - the number that decides it - how many kept
lines a *supported* claim actually cited (`claim_verification.claims[].citation_line`).

Runs from before wave 35 have counts but no `kept_lines`, so they cannot count cites.

It also measures research by need (#967): each run's settled/fresh verdict (#964), its
who's-who lines (#963) and how many a supported claim cited, and whether facts were
pasted - so "a known topic needs no paste" is a count, not a promise.

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


def _research(runs: list[Any]) -> dict[str, Any]:
    """#967: settled/fresh verdicts, who's-who lines, and pastes - before and after."""
    out: dict[str, Any] = {
        "with_verdict": 0, "settled": 0, "settled_pasted": 0, "fresh": 0, "fresh_pasted": 0,
        "who_lines": 0, "who_cited": 0, "before": 0, "before_pasted": 0, "rows": [],
    }  # fmt: skip
    for run in runs:
        features = _load(getattr(run, "features_json", None))
        pasted = int(features.get("key_facts_count") or 0) > 0
        verdict = features.get("research")
        need = str(verdict.get("need") or "") if isinstance(verdict, dict) else ""
        if need not in ("settled", "fresh"):
            out["before"] += 1
            out["before_pasted"] += int(pasted)
            continue
        out["with_verdict"] += 1
        out[need] += 1
        out[f"{need}_pasted"] += int(pasted)
        who = features.get("entity_research")
        who = who if isinstance(who, dict) else {}
        claims = (features.get("claim_verification") or {}).get("claims") or []
        cited = _cited([str(x) for x in who.get("kept_lines") or []],
                       [c for c in claims if isinstance(c, dict)])  # fmt: skip
        out["who_lines"] += int(who.get("lines") or 0)
        out["who_cited"] += cited
        out["rows"].append({
            "run_id": getattr(run, "id", None), "need": need, "pasted": pasted,
            "who": int(who.get("lines") or 0), "cited": cited,
            "topic": str(getattr(run, "input_topic", "") or "")[:50],
        })  # fmt: skip
    return out


def render_research(research: dict[str, Any]) -> list[str]:
    lines = ["  Research by need (#963-#967):"]
    if not research["with_verdict"]:
        lines.append("    no run has a settled/fresh verdict yet (it started in wave 58).")
    else:
        lines.append(
            f"    {research['with_verdict']} run(s): settled {research['settled']} "
            f"(pasted {research['settled_pasted']}), fresh {research['fresh']} "
            f"(pasted {research['fresh_pasted']}); who's-who lines {research['who_lines']}, "
            f"cited {research['who_cited']}"
        )
        for row in research["rows"][-5:]:
            lines.append(
                f"    #{row['run_id']}: {row['need']}, {row['who']} who's-who line(s), cited "
                f"{row['cited']}, {'pasted' if row['pasted'] else 'no paste'} - {row['topic']}"
            )
    if research["before"]:
        lines.append(
            f"    before the verdict: {research['before_pasted']} of {research['before']} "
            "run(s) had pasted facts"
        )
    return lines


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
        "research": _research(runs),
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


VERDICT_RUNS = 10


def verdict(summary: dict[str, Any]) -> dict[str, str] | None:
    """#863: keep, retune, give longer or switch off - once `VERDICT_RUNS` runs stored their
    kept lines (the ones whose cites can be counted); None before then."""
    runs = int(summary.get("cite_measurable") or 0)
    if runs < VERDICT_RUNS:
        return None
    rows = [r for r in summary.get("rows") or [] if r.get("cited") is not None]
    lines = sum(int(r.get("lines") or 0) for r in rows)
    cited = sum(int(r.get("cited") or 0) for r in rows)
    deadline = sum(1 for r in rows if "deadline" in str(r.get("reason") or ""))
    basis = f"{cited} of {lines} kept line(s) cited over {runs} run(s)"
    if cited == 0:
        call, act = "switch off", "nothing it kept backed a claim - set AUTO_RESEARCH_ENABLED=false"
    elif lines and cited / lines < 0.10:
        call, act = "retune", "few kept lines are used - read fewer pages: AUTO_RESEARCH_URLS=2"
    elif deadline * 2 >= len(rows):
        call, act = (
            "longer",
            (f"the deadline cut {deadline} of {len(rows)} run(s) - raise AUTO_RESEARCH_DEADLINE_S"),
        )
    else:
        call, act = "keep", "it earns its time - leave it on"
    return {"call": call, "line": f"#863 verdict: {call} ({basis}) - {act}"}


def _runs(channel_id: str) -> list[Any]:
    from storage.repositories.content_runs import get_content_run_repository

    return list(get_content_run_repository().list_for_channel(channel_id) or [])


def verdict_line(channel_id: str) -> str:
    """`ops status`: the verdict once it is due, else ""."""
    try:
        runs = _runs(channel_id)
    except Exception as exc:
        logger.debug("auto-research verdict skipped: %s", exc)
        return ""
    found = verdict(summarize(runs))
    return f"Auto-research {found['line']} (ops auto-research)" if found else ""


def render(summary: dict[str, Any], channel_id: str = "") -> str:
    head = f"Auto-research across stored runs{f' ({channel_id})' if channel_id else ''}"
    n = summary["with_report"]
    research = render_research(summary.get("research") or _research([]))
    if not n:
        return "\n".join(
            [head, "  No run has an auto-research report yet (it started in wave 34).", *research]
        )
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
    found = verdict(summary)
    if found:
        lines.append(f"  {found['line']}")
    else:
        left = VERDICT_RUNS - int(summary["cite_measurable"])
        lines.append(
            f"  {left} more run(s) with kept lines before the #863 verdict "
            "(keep, retune or switch off)."
        )
    return "\n".join(lines + research)


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
