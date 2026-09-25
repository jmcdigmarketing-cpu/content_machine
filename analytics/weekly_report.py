"""Analytics report v1 — rules-based weekly intelligence.

Joins content-run features (the feature store) to real engagement outcomes and
reports which feature values out/under-perform the channel baseline, with sample-size
gating so small-n noise isn't presented as signal. This is intentionally statistics,
not ML — it starts the habit and exposes feature-schema gaps early (roadmap 120-day).

    py -m analytics.weekly_report --channel tapin
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from config.channels import resolve_channel_id
from core.logging import get_logger

logger = get_logger("analytics.weekly_report")

# A feature value needs at least this many videos before we trust its average.
_MIN_SAMPLES = 3

# Which feature dimensions to break performance down by.
_DIMENSIONS = ("domain", "angle", "title_structure", "format", "fact_source")


def _load_rows(channel_id: str) -> list[dict[str, Any]]:
    """Runs joined to engagement + parsed features. Only rows with engagement data."""
    from core.best_bet import _engaged_rate
    from storage.repositories.content_runs import get_content_run_repository
    from storage.repositories.publish_log import get_publish_log_repository

    runs = get_content_run_repository().list_for_channel(channel_id)
    logs = {
        log.content_run_id: log
        for log in get_publish_log_repository().list_timed_outcomes(channel_id)
    }

    rows: list[dict[str, Any]] = []
    for run in runs:
        log = logs.get(run.id)
        rate = _engaged_rate(log.metrics_json) if log else None
        if rate is None:
            continue
        try:
            features = json.loads(run.features_json or "{}")
        except (json.JSONDecodeError, TypeError):
            features = {}
        rows.append({"run_id": run.id, "engaged_rate": rate, "features": features})
    return rows


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def build_report(channel_id: str) -> dict[str, Any]:
    """Return a structured report: baseline, per-dimension winners/losers, cost."""
    channel_id = resolve_channel_id(channel_id)
    rows = _load_rows(channel_id)
    if len(rows) < _MIN_SAMPLES:
        return {"channel_id": channel_id, "n": len(rows), "ready": False}

    baseline = _avg([r["engaged_rate"] for r in rows])

    dimensions: dict[str, list[dict[str, Any]]] = {}
    for dim in _DIMENSIONS:
        groups: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            val = r["features"].get(dim)
            if val:
                groups[str(val)].append(r["engaged_rate"])
        scored = [
            {
                "value": value,
                "avg": _avg(rates),
                "n": len(rates),
                "delta": _avg(rates) - baseline,
            }
            for value, rates in groups.items()
            if len(rates) >= _MIN_SAMPLES
        ]
        scored.sort(key=lambda g: g["avg"], reverse=True)
        if scored:
            dimensions[dim] = scored

    # Cost summary from whatever runs recorded it.
    costs = [
        float((r["features"].get("cost") or {}).get("total") or 0)
        for r in rows
        if r["features"].get("cost")
    ]

    report = {
        "channel_id": channel_id,
        "n": len(rows),
        "ready": True,
        "baseline": baseline,
        "dimensions": dimensions,
        "avg_cost": _avg(costs) if costs else None,
        "total_cost": round(sum(costs), 2) if costs else None,
    }
    report["next_actions"] = build_next_actions(report)
    return report


# Delta (vs baseline) below which a feature value is treated as neutral noise.
_ACTION_DELTA = 0.03

# How each dimension's winner/loser translates into an operator instruction.
_ACTION_PHRASES: dict[str, tuple[str, str]] = {
    "domain": ("Make more {value} videos", "Pause {value} topics"),
    "angle": ("Lead with the '{value}' angle again", "Retire the '{value}' angle"),
    "title_structure": ("Keep using {value} titles", "Drop {value} titles"),
    "format": ("Stick with the {value} format", "Rework the {value} format"),
    "fact_source": ("Keep sourcing facts via {value}", "Improve {value} fact sourcing"),
}


def build_next_actions(report: dict[str, Any], *, max_actions: int = 5) -> list[str]:
    """Concrete operator instructions from the per-dimension winners/losers.

    One "do more" from the strongest over-performer and one "do less" from the
    weakest under-performer per dimension (only past the noise threshold), then
    a cadence/coach pointer. Purely derived — no new data reads.
    """
    if not report.get("ready"):
        return []
    actions: list[str] = []
    for dim, groups in (report.get("dimensions") or {}).items():
        more_tpl, less_tpl = _ACTION_PHRASES.get(
            dim, (f"Do more {dim}={{value}}", f"Do less {dim}={{value}}")
        )
        best, worst = groups[0], groups[-1]
        if best["delta"] >= _ACTION_DELTA:
            actions.append(
                f"{more_tpl.format(value=best['value'])} "
                f"({best['avg']:.0%} vs {report['baseline']:.0%} baseline, n={best['n']})"
            )
        if worst is not best and worst["delta"] <= -_ACTION_DELTA:
            actions.append(
                f"{less_tpl.format(value=worst['value'])} "
                f"({worst['avg']:.0%} vs {report['baseline']:.0%} baseline, n={worst['n']})"
            )
    return actions[:max_actions]


def operator_digest(report: dict[str, Any], *, limit: int = 3) -> str:
    """#452: at most three decisions this week. Empty when the report is not ready."""
    if not report.get("ready"):
        return ""
    actions = [str(a) for a in (report.get("next_actions") or []) if str(a).strip()][:limit]
    if not actions:
        return ""
    channel = str(report.get("channel_id") or "this channel")
    lines = [f"This week's three decisions ({channel}):", ""]
    lines.extend(f"{i}. {action}" for i, action in enumerate(actions, 1))
    return "\n".join(lines)


def write_operator_digest(channel_id: str, report: dict[str, Any]) -> Path | None:
    """Land the digest in the vault. Does not call YouTube."""
    draft = operator_digest(report)
    if not draft:
        return None
    from core.vault_dossiers import write_report_note

    return write_report_note(channel_id, "digest", "Operator digest", draft, fenced=False)


def community_post_draft(report: dict[str, Any]) -> str:
    """YouTube Community post text from this week's next actions. Never posted."""
    if not report.get("ready"):
        return ""
    actions = [str(a) for a in (report.get("next_actions") or []) if str(a).strip()]
    if not actions:
        return ""
    channel = str(report.get("channel_id") or "this channel")
    lines = [
        f"This week's plan for {channel} (draft — not posted to YouTube):",
        "",
    ]
    lines.extend(f"- {action}" for action in actions)
    return "\n".join(lines)


def write_community_post_draft(channel_id: str, report: dict[str, Any]) -> Path | None:
    """Land the community-post draft in the vault. Does not call YouTube."""
    draft = community_post_draft(report)
    if not draft:
        return None
    from core.vault_dossiers import write_report_note

    return write_report_note(
        channel_id,
        "community-draft",
        "Community post draft",
        draft,
        fenced=False,
    )


def format_report(report: dict[str, Any]) -> str:
    if not report.get("ready"):
        return (
            f"Weekly report — {report['channel_id']}\n"
            f"  Not enough analytics yet ({report.get('n', 0)} videos with engagement; "
            f"need {_MIN_SAMPLES}+). Publish + sync metrics, then re-run."
        )

    lines = [
        f"Weekly intelligence — {report['channel_id']}",
        f"  {report['n']} videos analyzed · baseline engagement {report['baseline']:.1%}",
        "",
    ]
    for dim, groups in report["dimensions"].items():
        lines.append(f"  By {dim}:")
        for g in groups:
            marker = "+" if g["delta"] >= 0 else "-"
            lines.append(
                f"    [{marker}] {g['value']}: {g['avg']:.1%} "
                f"({g['delta']:+.1%} vs baseline, n={g['n']})"
            )
        lines.append("")

    if report.get("avg_cost") is not None:
        lines.append(
            f"  Cost: ~${report['avg_cost']:.3f}/video · "
            f"~${report['total_cost']:.2f} across {report['n']} tracked"
        )

    # Pillar 1 unit economics: contribution margin once revenue data exists.
    try:
        from core.unit_economics import channel_economics, summary_lines

        for line in summary_lines(channel_economics(report["channel_id"])):
            lines.append(f"  {line}")
    except Exception as exc:
        logger.debug("channel_economics skipped: %s", exc)

    # Pillar 2 calibration: is the pre-publish report card predictive yet?
    try:
        from core.grade_calibration import build_calibration, coverage_line, summary_line

        built = build_calibration(report["channel_id"])
        calibration = summary_line(built)
        if calibration:
            lines.append(f"  {calibration}")
        # #818: "collecting" reads like a volume problem; it is a history one.
        coverage = coverage_line(built, runs_total=len(report.get("rows") or []) or None)
        if coverage:
            lines.append(f"  {coverage}")
    except Exception as exc:
        logger.debug("build_calibration skipped: %s", exc)

    actions = report.get("next_actions") or []
    if actions:
        lines.append("")
        lines.append("  Next actions:")
        for i, action in enumerate(actions, 1):
            lines.append(f"    {i}. {action}")
        lines.append("    (daily ideas: py -m scripts.ops coach)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rules-based weekly intelligence report")
    parser.add_argument("--channel", default="tapin")
    args = parser.parse_args(argv)
    channel_id = resolve_channel_id(args.channel)
    report = build_report(channel_id)
    rendered = format_report(report)
    print(rendered)
    # Pillar 4: land a copy in the vault (no-op without OBSIDIAN_VAULT_PATH).
    try:
        from core.vault_dossiers import write_weekly_report_note

        path = write_weekly_report_note(channel_id, rendered)
        if path:
            print(f"\n  (saved to vault: {path})")
        draft_path = write_community_post_draft(channel_id, report)
        if draft_path:
            print(f"  (community post draft: {draft_path})")
        digest_path = write_operator_digest(channel_id, report)
        if digest_path:
            print(f"  (operator digest: {digest_path})")
    except Exception as exc:
        logger.debug("write_weekly_report_note skipped: %s", exc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
