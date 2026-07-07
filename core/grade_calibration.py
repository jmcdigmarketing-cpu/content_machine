"""Grade calibration loop (Pillar 2, data-gated).

Closes the audit gap "no pre-publish score is calibrated against outcomes":

- **Actual grade** — a published run's realized engaged-rate expressed as a
  percentile of the channel's measured distribution (0–100, comparable to the
  pre-publish report card).
- **Grade↔engagement correlation** — Pearson r between pre-publish grades and
  realized engaged-rates: the "is the report card meaningful yet?" number.
- **Thumbnail join** — the `thumbnail_scores` table finally gets its reader:
  correlation of pre-publish thumbnail `overall` vs realized engaged-rate
  (engagement stands in for CTR until YouTube exposes impressions).

Everything is read-only, fail-open, and confidence-gated (≥5 measured runs for
any correlation; below that the render says "collecting"). Surfaced via
`py -m scripts.ops calibration` and one line in the weekly report.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from core.logging import get_logger

logger = get_logger("core.grade_calibration")

MIN_MEASURED = 5


@dataclass
class CalibrationRow:
    run_id: int
    title: str
    grade: float  # pre-publish report card 0-100
    actual_percentile: float  # realized engaged-rate percentile 0-100
    engaged_rate: float
    predicted_rate: float | None = None


@dataclass
class CalibrationReport:
    channel_id: str
    rows: list[CalibrationRow] = field(default_factory=list)
    grade_correlation: float | None = None
    thumbnail_correlation: float | None = None
    thumbnail_n: int = 0

    @property
    def measured(self) -> int:
        return len(self.rows)


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sx = (sum((x - mx) ** 2 for x in xs)) ** 0.5
    sy = (sum((y - my) ** 2 for y in ys)) ** 0.5
    if sx <= 1e-9 or sy <= 1e-9:
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False))
    return cov / (sx * sy)


def _percentile(value: float, population: list[float]) -> float:
    if not population:
        return 50.0
    below = sum(1 for p in population if p < value)
    equal = sum(1 for p in population if p == value)
    return round(100.0 * (below + 0.5 * equal) / len(population), 1)


def _thumbnail_scores(channel_id: str) -> dict[int, float]:
    """content_run_id -> pre-publish thumbnail overall (best per run)."""
    out: dict[int, float] = {}
    try:
        from sqlalchemy import select

        from storage.db import get_session
        from storage.models import ThumbnailScore

        session = get_session()
        try:
            rows = session.scalars(
                select(ThumbnailScore).where(ThumbnailScore.channel_id == channel_id)
            ).all()
            for row in rows:
                if row.content_run_id and row.overall:
                    existing = out.get(row.content_run_id, 0.0)
                    out[row.content_run_id] = max(existing, float(row.overall))
        finally:
            session.close()
    except Exception as exc:
        logger.debug("thumbnail score load skipped: %s", exc)
    return out


def build_calibration(channel_id: str | None = None) -> CalibrationReport:
    from config.channels import resolve_channel_id
    from core.engagement_predictor import run_engagement_map
    from core.video_grade import grade_from_parts

    channel = resolve_channel_id(channel_id)
    report = CalibrationReport(channel_id=channel)

    engagement = run_engagement_map(channel)
    if not engagement:
        return report
    population = list(engagement.values())

    try:
        from storage.repositories.content_runs import get_content_run_repository

        runs = get_content_run_repository().list_for_channel(channel)
    except Exception:
        runs = []

    for run in runs:
        rate = engagement.get(run.id)
        if rate is None:
            continue
        try:
            quality = json.loads(run.quality_json or "{}")
        except Exception:
            quality = {}
        if not isinstance(quality, dict) or not quality:
            continue
        # Grade WITHOUT the predictor (channel_id=None) — calibration must not
        # recurse into prediction, and the grade should reflect content only.
        grade = grade_from_parts(quality=quality, composite_score=float(run.composite_score or 0))
        predicted = quality.get("predicted_engaged_rate")
        report.rows.append(
            CalibrationRow(
                run_id=run.id,
                title=(run.title or run.selected_topic or "")[:50],
                grade=grade.score,
                actual_percentile=_percentile(rate, population),
                engaged_rate=rate,
                predicted_rate=float(predicted) if predicted is not None else None,
            )
        )

    if report.measured >= MIN_MEASURED:
        report.grade_correlation = _pearson(
            [r.grade for r in report.rows], [r.engaged_rate for r in report.rows]
        )

    thumbs = _thumbnail_scores(channel)
    joined = [(thumbs[rid], engagement[rid]) for rid in thumbs.keys() & engagement.keys()]
    report.thumbnail_n = len(joined)
    if len(joined) >= MIN_MEASURED:
        report.thumbnail_correlation = _pearson([t for t, _ in joined], [e for _, e in joined])
    return report


def summary_line(report: CalibrationReport) -> str | None:
    """One weekly-report line, or None when still collecting."""
    if report.grade_correlation is None:
        if report.measured:
            return (
                f"Grade calibration: collecting ({report.measured}/{MIN_MEASURED} "
                "measured runs with quality)"
            )
        return None
    return (
        f"Grade calibration: report-card vs engaged-rate r={report.grade_correlation:+.2f} "
        f"over {report.measured} videos"
    )


def render(channel_id: str | None = None) -> str:
    report = build_calibration(channel_id)
    lines = [f"Grade calibration - {report.channel_id}", "=" * 64]
    if not report.rows:
        lines.append(
            "No measured runs with persisted quality yet - publish + sync-metrics, "
            "then re-run. (Runs recorded before the ledger have no quality_json.)"
        )
        return "\n".join(lines)
    for r in sorted(report.rows, key=lambda r: r.run_id, reverse=True)[:15]:
        pred = f"  pred {r.predicted_rate * 100:.1f}%" if r.predicted_rate is not None else ""
        lines.append(
            f"  #{r.run_id:<5} {r.title:<50} grade {r.grade:5.1f} -> "
            f"actual p{r.actual_percentile:.0f} ({r.engaged_rate * 100:.1f}%){pred}"
        )
    lines.append("-" * 64)
    grade_line = summary_line(report)
    if grade_line:
        lines.append(f"  {grade_line}")
    if report.thumbnail_correlation is not None:
        lines.append(
            f"  Thumbnail score vs engaged-rate r={report.thumbnail_correlation:+.2f} "
            f"over {report.thumbnail_n} videos"
        )
    elif report.thumbnail_n:
        lines.append(
            f"  Thumbnail join: collecting ({report.thumbnail_n}/{MIN_MEASURED} scored+measured)"
        )
    return "\n".join(lines)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Pre-publish grade vs realized engagement")
    parser.add_argument("--channel", default=None)
    args = parser.parse_args()
    print(render(args.channel))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
