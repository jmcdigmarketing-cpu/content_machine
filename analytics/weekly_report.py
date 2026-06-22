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
from typing import Any

from config.channels import resolve_channel_id

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

    return {
        "channel_id": channel_id,
        "n": len(rows),
        "ready": True,
        "baseline": baseline,
        "dimensions": dimensions,
        "avg_cost": _avg(costs) if costs else None,
        "total_cost": round(sum(costs), 2) if costs else None,
    }


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
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rules-based weekly intelligence report")
    parser.add_argument("--channel", default="tapin")
    args = parser.parse_args(argv)
    print(format_report(build_report(args.channel)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
