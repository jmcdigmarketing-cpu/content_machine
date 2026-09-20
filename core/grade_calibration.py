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
UNVERSIONED = "unversioned"


@dataclass
class CalibrationRow:
    run_id: int
    title: str
    grade: float  # pre-publish report card 0-100
    actual_percentile: float  # realized engaged-rate percentile 0-100
    engaged_rate: float
    predicted_rate: float | None = None
    grade_version: str = UNVERSIONED
    # #808. `grade` is the number the row's own rubric produced when one was
    # recorded; `regraded` is what today's code makes of the same inputs. The
    # gap between them is the measured effect of a component change - the thing
    # `GRADE_VERSION` could only assert. None when the row carries no snapshot,
    # in which case `grade` *is* today's re-grade.
    regraded: float | None = None
    recorded: bool = False
    # Component name -> score, as recorded and as today's code makes it. The
    # per-component pair is the whole point of #808: "the grade moved" is a
    # fact `GRADE_VERSION` could already assert, "authenticity moved 65 points"
    # is the one it could not.
    components: dict[str, float] = field(default_factory=dict)
    regraded_components: dict[str, float] = field(default_factory=dict)
    # #823: this grade was recomputed by today's code, not recorded by the
    # rubric that graded the run. It cannot be evidence that the rubric held.
    backfilled: bool = False


@dataclass
class CalibrationReport:
    channel_id: str
    rows: list[CalibrationRow] = field(default_factory=list)
    grade_correlation: float | None = None
    thumbnail_correlation: float | None = None
    thumbnail_n: int = 0
    mixed_versions: bool = False
    # #805. The grade correlation needs a persisted `quality_json` and so is
    # stuck at n=3 on the only channel with data; `composite_score` sits on
    # every run row, which is why the same channel has n=12 here. Different
    # population, different number - never averaged together.
    composite_correlation: float | None = None
    composite_n: int = 0

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


def _recorded_components(quality: dict) -> dict[str, float]:
    """The per-component scores `run_quality.snapshot_grade` stored (#808)."""
    raw = quality.get("grade_components")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for name, entry in raw.items():
        value = entry.get("score") if isinstance(entry, dict) else entry
        if isinstance(value, int | float) and not isinstance(value, bool):
            out[str(name)] = float(value)
    return out


def worst_component_drift(row: CalibrationRow) -> tuple[str, float] | None:
    """Which component moved most between the recorded grade and today's."""
    shared = row.components.keys() & row.regraded_components.keys()
    deltas = [(name, row.regraded_components[name] - row.components[name]) for name in shared]
    deltas = [(n, d) for n, d in deltas if abs(d) >= 0.05]
    if not deltas:
        return None
    return max(deltas, key=lambda pair: abs(pair[1]))


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

    # #805, before the quality filter below: a run needs no quality dict to
    # have been scored and measured, and 12 of them are in exactly that state.
    composite_pairs = [
        (float(run.composite_score), engagement[run.id])
        for run in runs
        if run.composite_score and engagement.get(run.id) is not None
    ]
    report.composite_n = len(composite_pairs)
    if report.composite_n >= MIN_MEASURED:
        report.composite_correlation = _pearson(
            [c for c, _ in composite_pairs], [e for _, e in composite_pairs]
        )

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
        # #808: prefer the grade the row's own rubric recorded. Re-grading a v2
        # row with v4 code was never the row's grade, and until the snapshot
        # existed nothing could tell the two apart.
        snapshot = quality.get("grade_score")
        recorded = isinstance(snapshot, int | float) and not isinstance(snapshot, bool)
        score = float(snapshot) if isinstance(snapshot, int | float) else grade.score
        predicted = quality.get("predicted_engaged_rate")
        version = str(quality.get("grade_version") or UNVERSIONED)
        report.rows.append(
            CalibrationRow(
                run_id=run.id,
                title=(run.title or run.selected_topic or "")[:50],
                grade=score,
                regraded=grade.score if recorded else None,
                recorded=recorded,
                backfilled=bool(quality.get("grade_backfilled")),
                components=_recorded_components(quality) if recorded else {},
                regraded_components={c.name: float(c.score) for c in grade.components},
                actual_percentile=_percentile(rate, population),
                engaged_rate=rate,
                predicted_rate=float(predicted) if predicted is not None else None,
                grade_version=version,
            )
        )

    versions = {r.grade_version for r in report.rows}
    # "unversioned" is not a version. Every run graded before the stamp existed
    # carries no `grade_version`, and those are precisely the rows this guard was
    # filed about: four components moved across v1/v2/v3 while nothing recorded
    # which rubric produced which letter. Treating that population as one shared
    # rubric is the mistake, not the fix -- measured, it produced a 0.99998
    # correlation over eight unlabelled rows.
    report.mixed_versions = len(versions) > 1 or UNVERSIONED in versions
    if report.measured >= MIN_MEASURED and not report.mixed_versions:
        report.grade_correlation = _pearson(
            [r.grade for r in report.rows], [r.engaged_rate for r in report.rows]
        )

    thumbs = _thumbnail_scores(channel)
    joined = [(thumbs[rid], engagement[rid]) for rid in thumbs.keys() & engagement.keys()]
    report.thumbnail_n = len(joined)
    if len(joined) >= MIN_MEASURED:
        report.thumbnail_correlation = _pearson([t for t, _ in joined], [e for _, e in joined])
    return report


_ACCURACY_CACHE: dict[str, str | None] = {}


def composite_line(report: CalibrationReport) -> str:
    """One line on whether the topic score has ever tracked engagement (#805)."""
    if report.composite_correlation is not None:
        return (
            f"Composite vs engaged-rate r={report.composite_correlation:+.2f} "
            f"(n={report.composite_n})"
        )
    return f"Composite vs engaged-rate: collecting ({report.composite_n}/{MIN_MEASURED})"


def accuracy_line(channel_id: str | None = None, *, use_cache: bool = True) -> str | None:
    """The card's own track record, as one line. Fail-open, never raises.

    Cached per process: the card is printed once per run but `ops grade` can be
    called in a loop, and this walks every run row plus the analytics join.
    """
    key = str(channel_id or "")
    if use_cache and key in _ACCURACY_CACHE:
        return _ACCURACY_CACHE[key]
    line: str | None = None
    try:
        report = build_calibration(channel_id)
        grade_part = (
            f"grade r={report.grade_correlation:+.2f} (n={report.measured})"
            if report.grade_correlation is not None
            else f"grade collecting ({report.measured}/{MIN_MEASURED})"
        )
        composite_part = (
            f"composite r={report.composite_correlation:+.2f} (n={report.composite_n})"
            if report.composite_correlation is not None
            else f"composite collecting ({report.composite_n}/{MIN_MEASURED})"
        )
        line = f"card accuracy: {grade_part}, {composite_part}"
    except Exception as exc:
        logger.debug("card accuracy line skipped: %s", exc)
        line = None
    if use_cache:
        _ACCURACY_CACHE[key] = line
    return line


def snapshot_line(report: CalibrationReport) -> str:
    """How much of the archive can answer "what did this actually score?" (#808)."""
    recorded = [r for r in report.rows if r.recorded]
    backfilled = [r for r in recorded if r.backfilled]
    if not recorded:
        return (
            f"Recorded grades: 0/{report.measured} - every row above is re-graded with "
            "today's rubric. Rows generated from now on carry their own."
        )
    drifts: list[tuple[float, CalibrationRow]] = [
        (r.regraded - r.grade, r)
        for r in recorded
        if r.regraded is not None and abs(r.regraded - r.grade) >= 0.05
    ]
    line = f"Recorded grades: {len(recorded)}/{report.measured}"
    if drifts:
        delta, worst = max(drifts, key=lambda pair: abs(pair[0]))
        line += (
            f" - {len(drifts)} would grade differently today "
            f"(worst {delta:+.1f} on #{worst.run_id}"
        )
        component = worst_component_drift(worst)
        line += f", {component[0]} {component[1]:+.0f})" if component else ")"
    elif len(backfilled) == len(recorded):
        # Tautological otherwise: the backfill computed these with today's code.
        line += (
            " - all backfilled (#823), so this says nothing about rubric "
            "stability; new runs from here carry their own"
        )
    elif backfilled:
        line += (
            f" - today's rubric reproduces every one, but {len(backfilled)} were "
            "backfilled and cannot show drift"
        )
    else:
        line += " - today's rubric reproduces every one"
    return line


def coverage_line(report: CalibrationReport, *, runs_total: int | None = None) -> str:
    """#818: why the correlation is collecting, when the reason is history.

    `summary_line` says "collecting (3/5)", which reads like "publish more".
    The actual shape on `tapin` is 87 runs, 37 with a grade, 12 with an
    outcome, 3 with both: quality persistence landed after most of the
    publishing did, so the overlap grows one row per *new* publish and no
    amount of past volume helps. Empty when every measured run already carries
    a grade - there is nothing to explain then.
    """
    try:
        measured = report.composite_n  # runs with an outcome
        both = report.measured  # runs with an outcome AND a quality dict
        if not measured or both >= measured:
            return ""
        graded = _graded_row_count(report.channel_id)
        total = f"{runs_total} runs, " if runs_total else ""
        return (
            f"Calibration coverage: {total}{graded} with a grade, {measured} with an outcome, "
            f"{both} with both - the overlap is historical (quality persistence postdates most "
            f"of the publishing) and grows one per publish, not one per past run"
        )
    except Exception as exc:
        logger.debug("coverage line skipped: %s", exc)
        return ""


def _graded_row_count(channel_id: str) -> int:
    """Runs carrying a non-empty `quality_json`, outcome or not."""
    try:
        from storage.repositories.content_runs import get_content_run_repository

        runs = get_content_run_repository().list_for_channel(channel_id)
    except Exception:
        return 0
    return sum(1 for r in runs if (r.quality_json or "").strip() not in ("", "{}"))


def summary_line(report: CalibrationReport) -> str | None:
    """One weekly-report line, or None when still collecting."""
    if report.grade_correlation is None:
        # "still collecting" wins below the threshold: with too few runs the
        # version question has not bitten yet, and reporting a refusal implies
        # the data would otherwise be usable.
        if report.measured and report.measured < MIN_MEASURED:
            return (
                f"Grade calibration: collecting ({report.measured}/{MIN_MEASURED} "
                "measured runs with quality)"
            )
        if report.mixed_versions:
            versions = sorted({r.grade_version for r in report.rows})
            if versions == [UNVERSIONED]:
                return (
                    "Grade calibration: refusing to correlate unversioned grades "
                    f"({report.measured} runs predate the rubric stamp and span "
                    "more than one rubric)"
                )
            return (
                f"Grade calibration: refusing to mix rubric versions "
                f"({', '.join(versions)}; {report.measured} runs)"
            )
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
        drift = ""
        if r.regraded is not None and abs(r.regraded - r.grade) >= 0.05:
            drift = f"  [{r.grade_version} {r.regraded - r.grade:+.1f} under today's rubric]"
        lines.append(
            f"  #{r.run_id:<5} {r.title:<50} grade {r.grade:5.1f} -> "
            f"actual p{r.actual_percentile:.0f} ({r.engaged_rate * 100:.1f}%){pred}{drift}"
        )
    lines.append("-" * 64)
    lines.append(f"  {snapshot_line(report)}")
    grade_line = summary_line(report)
    if grade_line:
        lines.append(f"  {grade_line}")
    lines.append(f"  {composite_line(report)}")
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
